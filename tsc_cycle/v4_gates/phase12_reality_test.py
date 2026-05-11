"""Phase 12 reality.log replay CLI and audited final-log writer."""

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
from tsc_cycle.v4_gates.phase12_log_render import (
    DEFAULT_BACKEND_LABEL,
    ensure_phase12_output_passes,
    lint_phase12_payload,
    render_reality_test_log,
)
from tsc_cycle.v4_gates.phase12_report import evaluate_phase12_report

PROJECT_ROOT = Path("/home/samuel/TSC_CYCLE")
REALITY_LOG = PROJECT_ROOT / "reality.log"
FINAL_LOG = PROJECT_ROOT / "reality_test.log"
ARTIFACT_ROOT = PROJECT_ROOT / "artifacts" / "v4" / "phase12"
CACHE_DIR = ARTIFACT_ROOT / "gen_cache"
MANIFEST_PATH = ARTIFACT_ROOT / "manifest.json"
PER_SAMPLE_PATH = ARTIFACT_ROOT / "per_sample.jsonl"
REPORT_PATH = ARTIFACT_ROOT / "phase12_report.json"
SERVER_LOG = ARTIFACT_ROOT / "llama_server.log"
PHASE11_GATE_REPORT = PROJECT_ROOT / "artifacts" / "v4" / "phase11" / "phase11_gate_report.json"
APPROVED_MODEL_ARTIFACT = PROJECT_ROOT / "runs" / "v4.0-4B-20260509T184844Z" / "gguf" / "model.q4_K_M.gguf"
FROZEN_V1_ROOT = PROJECT_ROOT / "runs" / "20260507T032419Z"
DEFAULT_LLAMA_SERVER = Path("/home/samuel/llama.cpp/build/bin/llama-server")
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


def _is_under(path: Path, root: Path) -> bool:
    candidate = path.expanduser().resolve(strict=False)
    root = root.expanduser().resolve(strict=False)
    return candidate == root or root in candidate.parents


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


def default_model_artifact() -> Path:
    return APPROVED_MODEL_ARTIFACT


def reject_unsafe_phase12_output_path(path: str | Path) -> Path:
    candidate = Path(path).expanduser().resolve(strict=False)
    if _is_under(candidate, FROZEN_V1_ROOT):
        raise ValueError(f"refusing Phase 12 write under frozen v1 root: {candidate}")
    allowed_final = FINAL_LOG.resolve(strict=False)
    allowed_tmp = Path(str(FINAL_LOG) + ".tmp").resolve(strict=False)
    artifact_root = ARTIFACT_ROOT.resolve(strict=False)
    if candidate in {allowed_final, allowed_tmp} or _is_under(candidate, artifact_root):
        return candidate
    raise ValueError(f"Phase 12 output path is not allowed: {candidate}")


def _iter_log_blocks(text: str) -> Iterable[tuple[re.Match[str], str]]:
    matches = list(HEADER_RE.finditer(text))
    for index, match in enumerate(matches):
        block_start = match.end()
        block_end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        yield match, text[block_start:block_end]


def _prompt_header(match: re.Match[str]) -> dict[str, str | None]:
    rest = match.group("rest") or ""
    crossing_match = re.search(r"crossing_id=([^|\s]+)", rest)
    return {
        "timestamp": match.group("ts"),
        "crossing_id": crossing_match.group(1) if crossing_match else None,
    }


def extract_reality_inputs(log_path: str | Path = REALITY_LOG) -> list[dict[str, Any]]:
    text = Path(log_path).read_text(encoding="utf-8")
    records: list[dict[str, Any]] = []
    for header_match, block in _iter_log_blocks(text):
        if header_match.group("type") != "prompt":
            continue
        header = _prompt_header(header_match)
        for match in INPUT_FRAME_RE.finditer(block):
            payload_text = match.group("payload").strip()
            payload = json.loads(payload_text)
            if not isinstance(payload, dict):
                raise ValueError("framed reality input JSON must be an object")
            sample_id = f"reality-{len(records) + 1:04d}"
            prediction = payload.get("prediction") if isinstance(payload.get("prediction"), dict) else {}
            record = RealityInputRecord(
                sample_id=sample_id,
                crossing_id=header.get("crossing_id"),
                timestamp=header.get("timestamp"),
                as_of=prediction.get("as_of") if isinstance(prediction.get("as_of"), str) else None,
                input=payload,
                input_sha256=sha256_text(_stable_json(payload)),
            )
            records.append(asdict(record))
    return records


def _lint_payload(prediction_input: dict[str, Any], solution: dict[str, int] | None) -> dict[str, Any]:
    return lint_phase12_payload(prediction_input, solution)


def _ensure_output_passes(record: dict[str, Any], output: dict[str, Any]) -> None:
    ensure_phase12_output_passes(record, output)


def write_final_log_atomically(
    *,
    text: str,
    out_log: str | Path = FINAL_LOG,
    records: Iterable[dict[str, Any]],
    outputs: Iterable[dict[str, Any]],
    allow_test_path: bool = False,
) -> Path:
    out_path = Path(out_log).expanduser().resolve(strict=False) if allow_test_path else reject_unsafe_phase12_output_path(out_log)
    recs = list(records)
    outs = list(outputs)
    if len(recs) != len(outs):
        raise ValueError("Phase 12 final gate failed: count mismatch")
    for record, output in zip(recs, outs, strict=True):
        _ensure_output_passes(record, output)
    tmp_path = Path(str(out_path) + ".tmp")
    tmp_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path.write_text(text, encoding="utf-8")
    tmp_path.replace(out_path)
    return out_path


def _synthetic_solution(record: dict[str, Any]) -> dict[str, int]:
    waits = record.get("input", {}).get("prediction", {}).get("phase_waits", [])
    return {str(wait["phase_id"]): int(wait["min_green"]) for wait in waits}


def _format_synthetic_output(record: dict[str, Any]) -> str:
    solution = _synthetic_solution(record)
    waits = record.get("input", {}).get("prediction", {}).get("phase_waits", [])
    parts = [f"相位{w.get('phase_id')}检查min_green={w.get('min_green')}和max_green={w.get('max_green')}，参考pred_saturation={w.get('pred_saturation')}。" for w in waits[:3]]
    reasoning = "".join(parts) or "检查相位顺序、上下界和整数秒。"
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
    lint_payload = _lint_payload(record["input"], solution)
    constraint_score = score_constraint(record["input"], solution)
    reasoning_score = score_reasoning(raw_text, record["input"])
    return {
        "sample_id": record["sample_id"],
        "crossing_id": record.get("crossing_id"),
        "backend": backend_label,
        "dry_run": bool(dry_run),
        "raw_text": raw_text,
        "reasoning": reasoning,
        "solution": solution,
        "parse_error": parse_error,
        "lint_ok": bool(lint_payload.get("ok")),
        "lint": lint_payload,
        "constraint_score": constraint_score,
        "reasoning_score": reasoning_score,
        "elapsed_sec": elapsed_sec,
        "timeout": timeout,
        "http_status": http_status,
        "n_predict": n_predict,
        "retry": retry or {},
        "input_sha256": record["input_sha256"],
        "raw_sha256": sha256_text(raw_text),
        "model_sha256": "",
    }


def _write_per_sample(outputs: list[dict[str, Any]], path: Path) -> None:
    reject_unsafe_phase12_output_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for output in outputs:
            fh.write(json.dumps(output, ensure_ascii=False, sort_keys=True, allow_nan=False))
            fh.write("\n")


def _write_manifest(manifest: dict[str, Any], path: Path) -> None:
    reject_unsafe_phase12_output_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def _load_cache(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"cache file is not an object: {path}")
    return payload


def _write_cache(path: Path, output: dict[str, Any]) -> None:
    reject_unsafe_phase12_output_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def _generation_metadata(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "n_predict": int(args.n_predict),
        "retry_n_predict": int(args.retry_n_predict),
        "timeout_sec": int(args.timeout_sec),
        "ngl": int(args.ngl),
        "threads": int(args.threads),
        "ctx_size": int(args.ctx_size),
    }


def _cache_matches_current_run(cached: dict[str, Any], record: dict[str, Any], args: argparse.Namespace, model_sha: str) -> bool:
    if cached.get("sample_id") != record.get("sample_id"):
        return False
    if cached.get("input_sha256") != record.get("input_sha256"):
        return False
    if cached.get("backend") != args.backend_label:
        return False
    if cached.get("model_sha256") != model_sha:
        return False
    if cached.get("generation") != _generation_metadata(args):
        return False
    try:
        _ensure_output_passes(record, cached)
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
                if cached is not None and _cache_matches_current_run(cached, record, args, model_sha):
                    outputs.append(cached)
                    continue
            prompt = build_user_prompt(record["input"]) + "\n" + build_assistant_prefill()
            text, meta = _post_completion(port, prompt, args.n_predict, args.timeout_sec)
            retry_meta: dict[str, Any] = {}
            reasoning, solution = parse_assistant_output(text)
            if solution is None and text and "</SOLUTION>" not in text and args.retry_n_predict > args.n_predict:
                retry_text, retry_http = _post_completion(port, prompt, args.retry_n_predict, args.timeout_sec)
                retry_meta = {"attempted": True, "n_predict": args.retry_n_predict, "meta": retry_http}
                text = retry_text
                meta = retry_http
            output = _build_output_record(
                record,
                raw_text=text,
                backend_label=args.backend_label,
                dry_run=False,
                elapsed_sec=float(meta.get("elapsed_sec") or 0.0),
                n_predict=args.retry_n_predict if retry_meta else args.n_predict,
                timeout=bool(meta.get("timeout")),
                http_status=meta.get("http_status"),
                retry=retry_meta,
            )
            output["model_sha256"] = model_sha
            output["generation"] = _generation_metadata(args)
            _write_cache(cache_path, output)
            outputs.append(output)
        return outputs
    finally:
        _kill_server(proc)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate audited Phase 12 reality_test.log via GGUF llama-server")
    parser.add_argument("--reality-log", type=Path, default=REALITY_LOG)
    parser.add_argument("--out-log", type=Path, default=FINAL_LOG)
    parser.add_argument("--artifact-root", type=Path, default=ARTIFACT_ROOT)
    parser.add_argument("--gguf-path", type=Path, default=APPROVED_MODEL_ARTIFACT)
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
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    artifact_root = Path(args.artifact_root)
    cache_dir = artifact_root / "gen_cache"
    manifest_path = artifact_root / "manifest.json"
    per_sample_path = artifact_root / "per_sample.jsonl"
    report_path = artifact_root / "phase12_report.json"

    reject_unsafe_phase12_output_path(manifest_path)
    reject_unsafe_phase12_output_path(per_sample_path)
    reject_unsafe_phase12_output_path(report_path)
    reject_unsafe_phase12_output_path(args.out_log)
    if _is_under(Path(args.gguf_path), FROZEN_V1_ROOT):
        raise SystemExit("refusing to use frozen v1 GGUF for Phase 12 generation")

    if not args.dry_run:
        if not Path(args.llama_server).exists():
            raise SystemExit(f"missing llama-server: {args.llama_server}")
        if not Path(args.gguf_path).exists():
            raise SystemExit(f"missing GGUF artifact: {args.gguf_path}")

    records = extract_reality_inputs(args.reality_log)
    if args.limit is not None:
        records = records[: args.limit]
    if not records:
        raise SystemExit("no Phase 12 input records selected")

    started = time.time()
    input_log_sha = sha256_file(args.reality_log)
    model_sha = "dry-run-no-model" if args.dry_run else sha256_file(args.gguf_path)

    if args.dry_run:
        outputs = [
            {
                **_build_output_record(
                    record,
                    raw_text=_format_synthetic_output(record),
                    backend_label=args.backend_label,
                    dry_run=True,
                    n_predict=0,
                ),
                "model_sha256": model_sha,
                "generation": _generation_metadata(args),
            }
            for record in records
        ]
    else:
        outputs = _run_live(records, args, cache_dir, model_sha)

    _write_per_sample(outputs, per_sample_path)
    rendered = render_reality_test_log(records, outputs, backend_label=args.backend_label)
    output_sha = sha256_text(rendered)

    manifest = {
        "ok": True,
        "dry_run": bool(args.dry_run),
        "started_at_epoch": started,
        "elapsed_sec": time.time() - started,
        "reality_log": str(args.reality_log),
        "out_log": str(args.out_log),
        "artifact_root": str(artifact_root),
        "model_artifact": str(args.gguf_path),
        "model_sha256": model_sha,
        "input_sha256": input_log_sha,
        "output_sha256": output_sha,
        "input_count": len(records),
        "output_count": len(outputs),
        "limit": args.limit,
        "backend_label": args.backend_label,
        "phase11_gate_report": str(PHASE11_GATE_REPORT),
        "records": records,
    }
    _write_manifest(manifest, manifest_path)

    if args.dry_run:
        report = evaluate_phase12_report(
            records=records,
            outputs=outputs,
            model_artifact=args.gguf_path,
            model_sha256=model_sha,
            input_sha256=input_log_sha,
            output_sha256=output_sha,
            out_path=report_path,
            dry_run=True,
            manifest_path=manifest_path,
            per_sample_path=per_sample_path,
            final_log_path=args.out_log,
        )
        print(f"[PHASE12] dry-run OK records={len(records)} manifest={manifest_path} report={report_path}")
        return 0 if report.get("dry_run") is True else 1

    write_final_log_atomically(text=rendered, out_log=args.out_log, records=records, outputs=outputs)
    report = evaluate_phase12_report(
        records=records,
        outputs=outputs,
        model_artifact=args.gguf_path,
        model_sha256=model_sha,
        input_sha256=input_log_sha,
        output_sha256=output_sha,
        out_path=report_path,
        dry_run=False,
        manifest_path=manifest_path,
        per_sample_path=per_sample_path,
        final_log_path=args.out_log,
    )

    if report.get("ok") is not True:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False), file=sys.stderr)
        return 1
    print(f"[PHASE12] OK wrote {args.out_log} records={len(records)} report={report_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
