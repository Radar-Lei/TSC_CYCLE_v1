"""Fail-closed aggregate report evaluator for Phase 12 reality replay."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Iterable

from tsc_cycle.constraint_lint import validate
from tsc_cycle.prompt_builder import parse_assistant_output

PROJECT_ROOT = Path("/home/samuel/TSC_CYCLE")
REALITY_TEST_LOG = PROJECT_ROOT / "reality_test.log"
ARTIFACT_ROOT = PROJECT_ROOT / "artifacts" / "v4" / "phase12"
REPORT_PATH = ARTIFACT_ROOT / "phase12_report.json"
MANIFEST_PATH = ARTIFACT_ROOT / "manifest.json"
PER_SAMPLE_PATH = ARTIFACT_ROOT / "per_sample.jsonl"
APPROVED_MODEL_ARTIFACT = PROJECT_ROOT / "runs" / "v4.0-4B-20260509T184844Z" / "gguf" / "model.q4_K_M.gguf"
FROZEN_V1_ROOT = PROJECT_ROOT / "runs" / "20260507T032419Z"
REQUIREMENTS_COVERED = ["PHASE12-GOAL"]


def _is_under(path: Path, root: Path) -> bool:
    candidate = path.expanduser().resolve(strict=False)
    root = root.expanduser().resolve(strict=False)
    return candidate == root or root in candidate.parents


def sha256_file(path: str | Path) -> str:
    hasher = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _reject_unsafe_report_path(path: str | Path) -> Path:
    candidate = Path(path).expanduser().resolve(strict=False)
    artifact_root = ARTIFACT_ROOT.resolve(strict=False)
    if candidate == REPORT_PATH.resolve(strict=False) or _is_under(candidate, artifact_root):
        return candidate
    raise ValueError(f"Phase 12 report output path is not allowed: {candidate}")


def _write_json(path: Path | None, payload: dict[str, Any]) -> None:
    if path is None:
        return
    safe_path = _reject_unsafe_report_path(path)
    safe_path.parent.mkdir(parents=True, exist_ok=True)
    safe_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def _normalise_records(records: Iterable[Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for record in records:
        if isinstance(record, dict):
            result.append(record)
        elif hasattr(record, "__dict__"):
            result.append(dict(record.__dict__))
        else:
            raise TypeError(f"unsupported Phase 12 record type: {type(record).__name__}")
    return result


def _sample_id(output: dict[str, Any]) -> str:
    return str(output.get("sample_id") or "")


def evaluate_phase12_report(
    *,
    records: Iterable[Any],
    outputs: Iterable[dict[str, Any]],
    model_artifact: str | Path,
    model_sha256: str,
    input_sha256: str,
    output_sha256: str,
    out_path: str | Path | None = None,
    dry_run: bool = False,
    manifest_path: str | Path = MANIFEST_PATH,
    per_sample_path: str | Path = PER_SAMPLE_PATH,
    final_log_path: str | Path = REALITY_TEST_LOG,
) -> dict[str, Any]:
    """Evaluate Phase 12 evidence and fail closed on any missing gate."""
    recs = _normalise_records(records)
    outs = list(outputs)
    fatal_failures: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []

    record_ids = [str(record.get("sample_id") or "") for record in recs]
    output_ids = [_sample_id(output) for output in outs]
    if len(recs) == 0:
        fatal_failures.append({"gate": "input_count", "reason": "no Phase 12 input records selected"})
    if len(recs) != len(outs):
        fatal_failures.append({"gate": "output_count", "reason": f"input/output count mismatch: {len(recs)} != {len(outs)}"})
    if record_ids != output_ids:
        fatal_failures.append({"gate": "sample_ids", "reason": "output sample_id order does not match input records"})

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
            lint = validate(record["input"], solution)
            if lint.ok:
                lint_ok_count += 1
            serialized_solution = output.get("solution")
            if serialized_solution is not None and serialized_solution != solution:
                fatal_failures.append({"gate": "solution_consistency", "reason": f"serialized solution mismatch for {record.get('sample_id')}"})

    if parse_ok_count != len(recs):
        fatal_failures.append({"gate": "parse", "reason": f"parse_ok_count={parse_ok_count}, expected={len(recs)}"})
    if lint_ok_count != len(recs):
        fatal_failures.append({"gate": "lint", "reason": f"lint_ok_count={lint_ok_count}, expected={len(recs)}"})
    if protocol_ok_count != len(recs):
        fatal_failures.append({"gate": "protocol", "reason": f"protocol_ok_count={protocol_ok_count}, expected={len(recs)}"})
    if timeout_count:
        fatal_failures.append({"gate": "timeout", "reason": f"timeout_count={timeout_count}"})

    model_path = Path(model_artifact).expanduser().resolve(strict=False)
    if _is_under(model_path, FROZEN_V1_ROOT):
        fatal_failures.append({"gate": "model_artifact", "reason": f"frozen v1 artifact is not allowed: {model_path}"})
    if not str(model_path):
        fatal_failures.append({"gate": "model_artifact", "reason": "model_artifact is empty"})
    if not model_sha256:
        fatal_failures.append({"gate": "model_sha256", "reason": "missing model_sha256"})
    elif dry_run and model_sha256 == "dry-run-no-model":
        pass
    elif not model_path.is_file():
        fatal_failures.append({"gate": "model_artifact", "reason": f"model artifact is missing: {model_path}"})
    elif sha256_file(model_path) != model_sha256:
        fatal_failures.append({"gate": "model_sha256", "reason": "model artifact hash mismatch"})

    if not input_sha256:
        fatal_failures.append({"gate": "input_sha256", "reason": "missing input_sha256"})

    final_log = Path(final_log_path).expanduser().resolve(strict=False)
    if not output_sha256:
        fatal_failures.append({"gate": "output_sha256", "reason": "missing output_sha256"})
    elif dry_run:
        pass
    elif not final_log.is_file():
        fatal_failures.append({"gate": "final_log", "reason": f"missing final reality_test.log: {final_log}"})
    elif sha256_file(final_log) != output_sha256:
        fatal_failures.append({"gate": "output_sha256", "reason": "final log hash mismatch"})

    if dry_run:
        warnings.append({"gate": "dry_run", "reason": "dry-run evidence is parser/report proof only and cannot authorize final reality_test.log"})

    full_generation_ok = not fatal_failures and not dry_run
    payload = {
        "ok": full_generation_ok,
        "next_phase_allowed": full_generation_ok,
        "dry_run": bool(dry_run),
        "input_count": len(recs),
        "output_count": len(outs),
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
            "reality_test_log": str(final_log_path),
            "gate_report": str(out_path) if out_path is not None else str(REPORT_PATH),
        },
        "requirements_covered": list(REQUIREMENTS_COVERED),
    }
    _write_json(Path(out_path) if out_path is not None else None, payload)
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate Phase 12 reality replay gate evidence")
    parser.add_argument("--manifest", type=Path, default=MANIFEST_PATH)
    parser.add_argument("--per-sample", type=Path, default=PER_SAMPLE_PATH)
    parser.add_argument("--reality-test-log", type=Path, default=REALITY_TEST_LOG)
    parser.add_argument("--artifact-root", type=Path, default=ARTIFACT_ROOT)
    parser.add_argument("--out", type=Path, default=REPORT_PATH)
    return parser


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


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    manifest = json.loads(args.manifest.read_text(encoding="utf-8")) if args.manifest.exists() else {}
    outputs = _load_jsonl(args.per_sample)
    records = manifest.get("records") or []
    report = evaluate_phase12_report(
        records=records,
        outputs=outputs,
        model_artifact=manifest.get("model_artifact") or APPROVED_MODEL_ARTIFACT,
        model_sha256=str(manifest.get("model_sha256") or ""),
        input_sha256=str(manifest.get("input_sha256") or ""),
        output_sha256=str(manifest.get("output_sha256") or ""),
        out_path=args.out,
        dry_run=bool(manifest.get("dry_run")),
        manifest_path=args.manifest,
        per_sample_path=args.per_sample,
        final_log_path=args.reality_test_log,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False))
    return 0 if report.get("ok") is True else 1


if __name__ == "__main__":
    sys.exit(main())
