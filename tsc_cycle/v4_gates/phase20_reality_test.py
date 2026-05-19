from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

from tsc_cycle.eval.metrics_constraints import score_constraint
from tsc_cycle.eval.metrics_reasoning import score_reasoning
from tsc_cycle.prompt_builder import build_assistant_prefill, build_user_prompt, parse_assistant_output
from tsc_cycle.v4_gates.phase19_export import validate_phase19_export_report
from tsc_cycle.v4_gates.phase20_eval import validate_phase20_eval_report
from tsc_cycle.v4_gates.phase20_log_render import DEFAULT_BACKEND_LABEL, lint_phase20_payload, render_phase20_reality_test_log

PROJECT_ROOT = Path("/home/samuel/TSC_CYCLE")
REALITY_LOG = PROJECT_ROOT / "reality.log"
ARTIFACT_ROOT = PROJECT_ROOT / "artifacts" / "v4_2" / "phase20"
FINAL_LOG = ARTIFACT_ROOT / "reality_test.log"
CACHE_DIR = ARTIFACT_ROOT / "reality_gen_cache"
MANIFEST_PATH = ARTIFACT_ROOT / "reality_manifest.json"
PER_SAMPLE_PATH = ARTIFACT_ROOT / "reality_per_sample.jsonl"
REPORT_PATH = ARTIFACT_ROOT / "reality_replay_report.json"
SERVER_LOG = ARTIFACT_ROOT / "llama_server_phase20.log"
DEFAULT_RUN_ROOT = PROJECT_ROOT / "runs" / "v4.2-4B-20260518T111519Z"
APPROVED_MODEL_ARTIFACT = DEFAULT_RUN_ROOT / "gguf" / "model.q4_K_M.gguf"
DEFAULT_LLAMA_SERVER = Path("/home/samuel/llama.cpp/build/bin/llama-server")
REQUIREMENTS_COVERED = ["EVAL-02"]
INPUT_FRAME_RE = re.compile(r"【cycle_predict_input_json】(?P<payload>.*?)【/cycle_predict_input_json】", re.DOTALL)
HEADER_RE = re.compile(r"^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\|INFO\|type=(?P<type>\w+)(?P<rest>.*)$", re.MULTILINE)


@dataclass(frozen=True)
class RealityInputRecord:
    sample_id: str
    crossing_id: str | None
    timestamp: str | None
    as_of: str | None
    input: dict[str, Any]
    input_sha256: str


def _stable_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: str | Path) -> str:
    hasher = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _write_json(path: str | Path, payload: dict[str, Any]) -> dict[str, Any]:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    return payload


def _write_jsonl(path: str | Path, rows: Iterable[dict[str, Any]]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n")


def _iter_log_blocks(text: str):
    matches = list(HEADER_RE.finditer(text))
    for index, match in enumerate(matches):
        block_start = match.end()
        block_end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        yield match, text[block_start:block_end]


def _prompt_header(match: re.Match[str]) -> dict[str, str | None]:
    rest = match.group("rest") or ""
    crossing_match = re.search(r"crossing_id=([^|\s]+)", rest)
    return {"timestamp": match.group("ts"), "crossing_id": crossing_match.group(1) if crossing_match else None}


def extract_reality_inputs(log_path: str | Path = REALITY_LOG) -> list[dict[str, Any]]:
    text = Path(log_path).read_text(encoding="utf-8")
    records: list[dict[str, Any]] = []
    for header_match, block in _iter_log_blocks(text):
        if header_match.group("type") != "prompt":
            continue
        header = _prompt_header(header_match)
        for match in INPUT_FRAME_RE.finditer(block):
            payload = json.loads(match.group("payload").strip())
            if not isinstance(payload, dict):
                raise ValueError("framed reality input JSON must be an object")
            prediction = payload.get("prediction") if isinstance(payload.get("prediction"), dict) else {}
            record = RealityInputRecord(
                sample_id=f"reality-{len(records) + 1:04d}",
                crossing_id=header.get("crossing_id"),
                timestamp=header.get("timestamp"),
                as_of=prediction.get("as_of") if isinstance(prediction.get("as_of"), str) else None,
                input=payload,
                input_sha256=sha256_text(_stable_json(payload)),
            )
            records.append(asdict(record))
    return records


def _synthetic_solution(record: dict[str, Any]) -> dict[str, int]:
    waits = record.get("input", {}).get("prediction", {}).get("phase_waits", [])
    return {str(wait["phase_id"]): int(wait["min_green"]) for wait in waits}


def _format_synthetic_output(record: dict[str, Any]) -> str:
    solution = _synthetic_solution(record)
    reasoning = "检查相位顺序、上下界和整数秒。"
    return f"<start_working_out>{reasoning}</end_working_out><SOLUTION>{json.dumps(solution, ensure_ascii=False, separators=(',', ':'))}</SOLUTION>"


def _build_output_record(
    record: dict[str, Any],
    *,
    raw_text: str,
    backend_label: str,
    dry_run: bool,
    elapsed_sec: float = 0.0,
    n_predict: int | None = None,
    timeout: bool = False,
    http_status: int | None = None,
    retry: dict[str, Any] | None = None,
) -> dict[str, Any]:
    reasoning, solution = parse_assistant_output(raw_text)
    parse_error = None if solution is not None else "solution_unparseable"
    lint = lint_phase20_payload(record["input"], solution)
    return {
        "sample_id": record["sample_id"],
        "crossing_id": record.get("crossing_id"),
        "backend": backend_label,
        "dry_run": bool(dry_run),
        "raw_text": raw_text,
        "reasoning": reasoning,
        "solution": solution,
        "parse_error": parse_error,
        "lint_ok": bool(lint.get("ok")),
        "lint": lint,
        "constraint_score": score_constraint(record["input"], solution),
        "reasoning_score": score_reasoning(raw_text, record["input"]),
        "elapsed_sec": elapsed_sec,
        "timeout": timeout,
        "http_status": http_status,
        "n_predict": n_predict,
        "retry": retry or {},
        "input_sha256": record["input_sha256"],
        "raw_sha256": sha256_text(raw_text),
        "model_sha256": "",
    }


def _generation_metadata(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "n_predict": int(args.n_predict),
        "retry_n_predict": int(args.retry_n_predict),
        "timeout_sec": int(args.timeout_sec),
        "ngl": int(args.ngl),
        "threads": int(args.threads),
        "ctx_size": int(args.ctx_size),
    }


def _load_cache(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"cache file is not an object: {path}")
    return payload


def _write_cache(path: Path, output: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def _cache_matches(cached: dict[str, Any], record: dict[str, Any], args: argparse.Namespace, model_sha: str) -> bool:
    if cached.get("sample_id") != record.get("sample_id") or cached.get("input_sha256") != record.get("input_sha256"):
        return False
    if cached.get("backend") != args.backend_label or cached.get("model_sha256") != model_sha:
        return False
    if cached.get("generation") != _generation_metadata(args):
        return False
    try:
        render_phase20_reality_test_log([record], [cached], backend_label=args.backend_label)
    except (TypeError, ValueError):
        return False
    return True


def _run_live(records: list[dict[str, Any]], args: argparse.Namespace, cache_dir: Path, model_sha: str) -> list[dict[str, Any]]:
    from tsc_cycle.student.parity_gguf import _find_free_port, _kill_server, _post_completion, _spawn_server, _wait_health

    port = _find_free_port()
    proc = _spawn_server(Path(args.llama_server), Path(args.gguf_path), port, args.ngl, args.threads, args.ctx_size, SERVER_LOG)
    try:
        if not _wait_health(port, args.timeout_sec):
            raise RuntimeError(f"llama-server did not become healthy; see {SERVER_LOG}")
        outputs: list[dict[str, Any]] = []
        for record in records:
            cache_path = cache_dir / f"{record['sample_id']}.json"
            if args.resume:
                cached = _load_cache(cache_path)
                if cached is not None and _cache_matches(cached, record, args, model_sha):
                    outputs.append(cached)
                    continue
            prompt = build_user_prompt(record["input"]) + "\n" + build_assistant_prefill()
            text, meta = _post_completion(port, prompt, args.n_predict, args.timeout_sec)
            retry_meta: dict[str, Any] = {}
            _, solution = parse_assistant_output(text)
            if solution is None and text and "</SOLUTION>" not in text and args.retry_n_predict > args.n_predict:
                text, meta = _post_completion(port, prompt, args.retry_n_predict, args.timeout_sec)
                retry_meta = {"attempted": True, "n_predict": args.retry_n_predict, "meta": meta}
            output = _build_output_record(record, raw_text=text, backend_label=args.backend_label, dry_run=False, elapsed_sec=float(meta.get("elapsed_sec") or 0.0), n_predict=args.retry_n_predict if retry_meta else args.n_predict, timeout=bool(meta.get("timeout")), http_status=meta.get("http_status"), retry=retry_meta)
            output["model_sha256"] = model_sha
            output["generation"] = _generation_metadata(args)
            _write_cache(cache_path, output)
            outputs.append(output)
        return outputs
    finally:
        _kill_server(proc)


def _phase19_export_preflight(run_root: Path) -> dict[str, Any]:
    candidates = [run_root]
    try:
        relative = run_root.resolve(strict=False).relative_to(PROJECT_ROOT.resolve(strict=False))
    except ValueError:
        relative = None
    if relative is not None:
        candidates.append(relative)
    last: dict[str, Any] | None = None
    for candidate in candidates:
        report_path = Path(candidate) / "phase19_export_report.json"
        if not report_path.is_file() and candidate != run_root:
            report_path = run_root / "phase19_export_report.json"
        result = validate_phase19_export_report(candidate, report_path)
        if result.get("ok") is True and result.get("next_phase_allowed") is True:
            return result
        last = result
    return last or {"ok": False, "next_phase_allowed": False, "requirements_covered": [], "fatal_failures": [{"gate": "phase19_export", "reason": "Phase 19 export validation did not run"}]}


def _preflight(run_root: Path, eval_report_path: Path) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    phase19 = _phase19_export_preflight(run_root)
    if phase19.get("ok") is not True or phase19.get("next_phase_allowed") is not True:
        failures.append({"gate": "phase19_export", "reason": "Phase 19 export report is not accepted", "details": phase19.get("fatal_failures", [])})
    phase20_eval = validate_phase20_eval_report(report_path=eval_report_path, run_root=run_root)
    if phase20_eval.get("ok") is not True or phase20_eval.get("next_phase_allowed") is not True:
        failures.append({"gate": "phase20_eval", "reason": "Phase 20 eval report is not accepted", "details": phase20_eval.get("fatal_failures", [])})
    return failures


def evaluate_phase20_replay_report(
    *,
    records: Iterable[dict[str, Any]],
    outputs: Iterable[dict[str, Any]],
    model_artifact: str | Path,
    model_sha256: str,
    input_sha256: str,
    output_sha256: str,
    final_log_path: str | Path = FINAL_LOG,
    report_path: str | Path | None = REPORT_PATH,
    manifest_path: str | Path = MANIFEST_PATH,
    per_sample_path: str | Path = PER_SAMPLE_PATH,
    dry_run: bool = False,
    limit: int | None = None,
    total_input_count: int | None = None,
    run_root: str | Path = DEFAULT_RUN_ROOT,
    eval_report_path: str | Path = ARTIFACT_ROOT / "eval_report.json",
) -> dict[str, Any]:
    recs = list(records)
    outs = list(outputs)
    fatal_failures = _preflight(Path(run_root), Path(eval_report_path))
    warnings: list[dict[str, str]] = []

    record_ids = [str(record.get("sample_id") or "") for record in recs]
    output_ids = [str(output.get("sample_id") or "") for output in outs]
    if not recs:
        fatal_failures.append({"gate": "input_count", "reason": "no Phase 20 replay input records selected"})
    if len(recs) != len(outs):
        fatal_failures.append({"gate": "output_count", "reason": f"input/output count mismatch: {len(recs)} != {len(outs)}"})
    if record_ids != output_ids:
        fatal_failures.append({"gate": "sample_ids", "reason": "output sample_id order does not match input records"})
    if dry_run:
        fatal_failures.append({"gate": "dry_run", "reason": "dry-run evidence cannot satisfy EVAL-02"})
        warnings.append({"gate": "dry_run", "reason": "dry-run evidence is diagnostic only"})
    if limit is not None:
        fatal_failures.append({"gate": "partial_replay", "reason": "limited replay cannot satisfy EVAL-02"})
    if total_input_count is not None and len(recs) != int(total_input_count):
        fatal_failures.append({"gate": "partial_replay", "reason": f"selected {len(recs)} of {total_input_count} reality records"})

    parse_ok_count = 0
    lint_ok_count = 0
    protocol_ok_count = 0
    timeout_count = 0
    for record, output in zip(recs, outs, strict=False):
        if output.get("timeout") is True:
            timeout_count += 1
        raw = str(output.get("raw_text") or "")
        reasoning, solution = parse_assistant_output(raw)
        if reasoning and solution is not None:
            parse_ok_count += 1
            protocol_ok_count += 1
            lint = lint_phase20_payload(record["input"], solution)
            if lint.get("ok") is True:
                lint_ok_count += 1
            if output.get("solution") is not None and output.get("solution") != solution:
                fatal_failures.append({"gate": "solution_consistency", "reason": f"serialized solution mismatch for {record.get('sample_id')}"})
        try:
            render_phase20_reality_test_log([record], [output], backend_label=str(output.get("backend") or DEFAULT_BACKEND_LABEL))
        except (KeyError, TypeError, ValueError) as exc:
            fatal_failures.append({"gate": "canonical_render", "reason": str(exc)})

    if parse_ok_count != len(recs):
        fatal_failures.append({"gate": "parse", "reason": f"parse_ok_count={parse_ok_count}, expected={len(recs)}"})
    if lint_ok_count != len(recs):
        fatal_failures.append({"gate": "lint", "reason": f"lint_ok_count={lint_ok_count}, expected={len(recs)}"})
    if protocol_ok_count != len(recs):
        fatal_failures.append({"gate": "protocol", "reason": f"protocol_ok_count={protocol_ok_count}, expected={len(recs)}"})
    if timeout_count:
        fatal_failures.append({"gate": "timeout", "reason": f"timeout_count={timeout_count}"})

    model_path = Path(model_artifact).expanduser().resolve(strict=False)
    if "v4.0-4B-" in model_path.as_posix():
        fatal_failures.append({"gate": "model_artifact", "reason": f"v4.0 GGUF is not allowed: {model_path}"})
    if not model_path.is_file():
        fatal_failures.append({"gate": "model_artifact", "reason": f"model artifact is missing: {model_path}"})
    elif sha256_file(model_path) != model_sha256:
        fatal_failures.append({"gate": "model_sha256", "reason": "model artifact hash mismatch"})
    if not input_sha256:
        fatal_failures.append({"gate": "input_sha256", "reason": "missing input_sha256"})

    final_log = Path(final_log_path)
    if not output_sha256:
        fatal_failures.append({"gate": "output_sha256", "reason": "missing output_sha256"})
    elif not dry_run:
        if not final_log.is_file():
            fatal_failures.append({"gate": "final_log", "reason": f"missing final reality_test.log: {final_log}"})
        else:
            actual = sha256_file(final_log)
            if actual != output_sha256:
                fatal_failures.append({"gate": "output_sha256", "reason": "final log hash mismatch"})
            try:
                canonical = render_phase20_reality_test_log(recs, outs, backend_label=DEFAULT_BACKEND_LABEL)
            except (KeyError, TypeError, ValueError) as exc:
                fatal_failures.append({"gate": "canonical_final_log", "reason": f"canonical render failed: {exc}"})
            else:
                if final_log.read_text(encoding="utf-8") != canonical:
                    fatal_failures.append({"gate": "canonical_final_log", "reason": "final log content differs from canonical audited render"})
                if sha256_text(canonical) != output_sha256:
                    fatal_failures.append({"gate": "output_sha256", "reason": "output_sha256 does not match canonical audited render"})

    ok = not fatal_failures
    report = {
        "ok": ok,
        "next_phase_allowed": ok,
        "requirements_covered": list(REQUIREMENTS_COVERED) if ok else [],
        "dry_run": bool(dry_run),
        "limit": limit,
        "input_count": len(recs),
        "output_count": len(outs),
        "total_input_count": total_input_count if total_input_count is not None else len(recs),
        "parse_ok_count": parse_ok_count,
        "lint_ok_count": lint_ok_count,
        "protocol_ok_count": protocol_ok_count,
        "timeout_count": timeout_count,
        "model_artifact": str(model_path),
        "model_sha256": str(model_sha256),
        "input_sha256": str(input_sha256),
        "output_sha256": str(output_sha256),
        "fatal_failures": fatal_failures,
        "warnings": warnings,
        "reports": {
            "manifest": str(manifest_path),
            "per_sample": str(per_sample_path),
            "final_log": str(final_log_path),
            "reality_replay_report": str(report_path) if report_path is not None else str(REPORT_PATH),
        },
    }
    if report_path is not None:
        _write_json(report_path, report)
    return report


def run_phase20_reality_replay(args: argparse.Namespace) -> dict[str, Any]:
    records = extract_reality_inputs(args.reality_log)
    total_input_count = len(records)
    if args.limit is not None:
        records = records[: args.limit]
    if not records:
        raise SystemExit("no Phase 20 input records selected")

    started = time.time()
    input_sha = sha256_file(args.reality_log)
    model_sha = "dry-run-no-model" if args.dry_run else sha256_file(args.gguf_path)
    cache_dir = Path(args.artifact_root) / "reality_gen_cache"
    if args.dry_run:
        outputs = [
            {
                **_build_output_record(record, raw_text=_format_synthetic_output(record), backend_label=args.backend_label, dry_run=True, n_predict=0),
                "model_sha256": model_sha,
                "generation": _generation_metadata(args),
            }
            for record in records
        ]
    else:
        outputs = _run_live(records, args, cache_dir, model_sha)

    per_sample_path = Path(args.artifact_root) / "reality_per_sample.jsonl"
    manifest_path = Path(args.artifact_root) / "reality_manifest.json"
    report_path = Path(args.artifact_root) / "reality_replay_report.json"
    final_log_path = Path(args.out_log)
    _write_jsonl(per_sample_path, outputs)
    rendered = render_phase20_reality_test_log(records, outputs, backend_label=args.backend_label)
    output_sha = sha256_text(rendered)
    if not args.dry_run:
        final_log_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = Path(str(final_log_path) + ".tmp")
        tmp.write_text(rendered, encoding="utf-8")
        tmp.replace(final_log_path)

    manifest = {
        "ok": True,
        "dry_run": bool(args.dry_run),
        "started_at_epoch": started,
        "elapsed_sec": time.time() - started,
        "reality_log": str(args.reality_log),
        "out_log": str(final_log_path),
        "artifact_root": str(args.artifact_root),
        "model_artifact": str(args.gguf_path),
        "model_sha256": model_sha,
        "input_sha256": input_sha,
        "output_sha256": output_sha,
        "input_count": len(records),
        "total_input_count": total_input_count,
        "output_count": len(outputs),
        "limit": args.limit,
        "backend_label": args.backend_label,
        "records": records,
    }
    _write_json(manifest_path, manifest)
    return evaluate_phase20_replay_report(
        records=records,
        outputs=outputs,
        model_artifact=args.gguf_path,
        model_sha256=model_sha,
        input_sha256=input_sha,
        output_sha256=output_sha,
        final_log_path=final_log_path,
        report_path=report_path,
        manifest_path=manifest_path,
        per_sample_path=per_sample_path,
        dry_run=bool(args.dry_run),
        limit=args.limit,
        total_input_count=total_input_count,
        run_root=args.run_root,
        eval_report_path=args.eval_report,
    )


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        payload = json.loads(line)
        if not isinstance(payload, dict):
            raise ValueError(f"JSONL row is not an object at {path}:{line_no}")
        rows.append(payload)
    return rows


def validate_phase20_replay_report(report_path: str | Path = REPORT_PATH, *, run_root: str | Path = DEFAULT_RUN_ROOT, eval_report_path: str | Path = ARTIFACT_ROOT / "eval_report.json") -> dict[str, Any]:
    report_path = Path(report_path)
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return {"ok": False, "next_phase_allowed": False, "requirements_covered": [], "fatal_failures": [{"gate": "report_json", "reason": str(exc)}], "report_path": str(report_path)}
    failures = list(report.get("fatal_failures", [])) if isinstance(report.get("fatal_failures"), list) else [{"gate": "fatal_failures", "reason": "fatal_failures must be a list"}]
    failures.extend(_preflight(Path(run_root), Path(eval_report_path)))
    if report.get("ok") is not True or report.get("next_phase_allowed") is not True:
        failures.append({"gate": "report_green", "reason": "Phase 20 replay report is not green"})
    covered = report.get("requirements_covered", [])
    if not isinstance(covered, list) or "EVAL-02" not in {str(item) for item in covered}:
        failures.append({"gate": "requirements_covered", "reason": "EVAL-02 coverage missing"})
    if report.get("dry_run") is True or report.get("limit") is not None:
        failures.append({"gate": "full_replay", "reason": "accepted replay must be full non-dry-run"})
    out = dict(report)
    out.update({"ok": not failures, "next_phase_allowed": not failures, "requirements_covered": list(REQUIREMENTS_COVERED) if not failures else [], "fatal_failures": failures, "report_path": str(report_path)})
    return out


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate and validate Phase 20 v4.2 reality replay evidence")
    parser.add_argument("--reality-log", type=Path, default=REALITY_LOG)
    parser.add_argument("--out-log", type=Path, default=FINAL_LOG)
    parser.add_argument("--artifact-root", type=Path, default=ARTIFACT_ROOT)
    parser.add_argument("--gguf-path", type=Path, default=APPROVED_MODEL_ARTIFACT)
    parser.add_argument("--run-root", type=Path, default=DEFAULT_RUN_ROOT)
    parser.add_argument("--eval-report", type=Path, default=ARTIFACT_ROOT / "eval_report.json")
    parser.add_argument("--llama-server", type=Path, default=DEFAULT_LLAMA_SERVER)
    parser.add_argument("--backend-label", default=DEFAULT_BACKEND_LABEL)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--n-predict", type=int, default=384)
    parser.add_argument("--retry-n-predict", type=int, default=768)
    parser.add_argument("--timeout-sec", type=int, default=600)
    parser.add_argument("--ngl", type=int, default=99)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--ctx-size", type=int, default=4096)
    parser.add_argument("--validate-report", action="store_true")
    parser.add_argument("--report", type=Path, default=REPORT_PATH)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.validate_report:
        result = validate_phase20_replay_report(args.report, run_root=args.run_root, eval_report_path=args.eval_report)
    else:
        if not args.dry_run:
            if not Path(args.llama_server).exists():
                raise SystemExit(f"missing llama-server: {args.llama_server}")
            if not Path(args.gguf_path).exists():
                raise SystemExit(f"missing GGUF artifact: {args.gguf_path}")
        result = run_phase20_reality_replay(args)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False))
    return 0 if result.get("ok") is True else 1


if __name__ == "__main__":
    sys.exit(main())
