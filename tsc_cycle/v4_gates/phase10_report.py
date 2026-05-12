from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tsc_cycle.constraint_lint import validate
from tsc_cycle.v4_gates.phase10_export import sha256_file
from tsc_cycle.prompt_builder import (
    NATIVE_THINK_TAGS,
    TAG_SOLUTION_CLOSE,
    TAG_SOLUTION_OPEN,
    TAG_THINK_CLOSE,
    TAG_THINK_OPEN,
    parse_assistant_output,
)

REQUIRED_BACKENDS = ("hf", "gguf_fp16", "gguf_q4_K_M")
REQUIREMENTS_COVERED = ["GGUF4B-02", "GGUF4B-04"]
AGGREGATE_REQUIREMENTS = ["GGUF4B-01", "GGUF4B-02", "GGUF4B-03", "GGUF4B-04"]


def _load_json(path_or_payload: str | Path | dict[str, Any]) -> dict[str, Any]:
    if isinstance(path_or_payload, dict):
        return path_or_payload
    path = Path(path_or_payload)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON report is not an object: {path}")
    return payload


def _write_json(path: Path | None, payload: dict[str, Any]) -> None:
    if path is None:
        return
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _gate(ok: bool, reason: str | None = None, data: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"ok": bool(ok), "reason": reason, "data": data or {}}


def _sample_input(sample: dict[str, Any]) -> dict[str, Any]:
    value = sample.get("input") if isinstance(sample.get("input"), dict) else sample
    if not isinstance(value, dict):
        raise ValueError("sample input must be a dict")
    return value


def _sample_id(sample: dict[str, Any], fallback: str) -> str:
    value = sample.get("sample_id") or sample.get("id") or fallback
    return str(value)


def _records(report: dict[str, Any]) -> list[dict[str, Any]]:
    rows = report.get("results")
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


def _record_text(record: dict[str, Any]) -> str:
    value = record.get("output_text")
    if not isinstance(value, str):
        value = record.get("text")
    return value if isinstance(value, str) else ""


def _extract_solution_payload(text: str) -> Any:
    start = text.find(TAG_SOLUTION_OPEN)
    end = text.find(TAG_SOLUTION_CLOSE, start + len(TAG_SOLUTION_OPEN))
    if start < 0 or end < 0:
        return None
    raw = text[start + len(TAG_SOLUTION_OPEN) : end].strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def _has_complete_custom_protocol(text: str) -> bool:
    if any(tag in text for tag in NATIVE_THINK_TAGS) or "<end_working_out>" in text:
        return False
    stripped = text.strip()
    return (
        stripped.startswith(TAG_THINK_OPEN)
        and TAG_THINK_CLOSE in stripped
        and TAG_SOLUTION_OPEN in stripped
        and stripped.endswith(TAG_SOLUTION_CLOSE)
    )


def _evaluate_backend(backend: str, samples: list[dict[str, Any]], report: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, str]], bool]:
    failures: list[dict[str, str]] = []
    rows = _records(report)
    by_id = {str(row.get("sample_id")): row for row in rows if row.get("sample_id") is not None}
    protocol_details: list[dict[str, Any]] = []
    constraint_details: list[dict[str, Any]] = []

    for idx, sample in enumerate(samples):
        sid = _sample_id(sample, f"sample-{idx:04d}")
        row = by_id.get(sid) or (rows[idx] if idx < len(rows) else {})
        text = _record_text(row)
        reasoning, solution = parse_assistant_output(text)
        protocol_ok = solution is not None and bool(reasoning)
        if not protocol_ok and _has_complete_custom_protocol(text):
            solution = _extract_solution_payload(text)
            protocol_ok = isinstance(solution, dict)
        if not protocol_ok:
            reason = f"malformed custom protocol for {backend} sample {sid}"
            if "<think>" in text or "</think>" in text:
                reason = f"native <think> tag found for {backend} sample {sid}"
            elif "<end_working_out>" in text:
                reason = f"malformed end_working_out tag for {backend} sample {sid}"
            failures.append({"gate": f"protocol_{backend}", "reason": reason})
            protocol_details.append({"sample_id": sid, "ok": False, "reason": reason})
            constraint_details.append({"sample_id": sid, "ok": False, "reason": "protocol parse failed"})
            continue

        protocol_details.append({"sample_id": sid, "ok": True})
        lint = validate(_sample_input(sample), solution)
        if not lint.ok:
            reason = f"hard constraint failure for {backend} sample {sid}: {lint.violations}"
            failures.append({"gate": f"hard_constraints_{backend}", "reason": reason})
            constraint_details.append({"sample_id": sid, "ok": False, "violations": lint.violations})
        else:
            constraint_details.append({"sample_id": sid, "ok": True, "solution": solution})

    protocol_ok = bool(samples) and not any(not item.get("ok") for item in protocol_details) and len(protocol_details) == len(samples)
    constraints_ok = bool(samples) and not any(not item.get("ok") for item in constraint_details) and len(constraint_details) == len(samples)
    protocol_gate = _gate(protocol_ok, None if protocol_ok else f"protocol failed for {backend}", {"results": protocol_details})
    constraints_gate = _gate(constraints_ok, None if constraints_ok else f"hard constraints failed for {backend}", {"results": constraint_details})
    q4_failed = backend == "gguf_q4_K_M" and (not protocol_ok or not constraints_ok)
    return protocol_gate, constraints_gate, failures, q4_failed


def evaluate_three_backend_smoke(
    *,
    samples: list[dict[str, Any]],
    backend_reports: dict[str, str | Path | dict[str, Any]],
    out_path: str | Path | None = None,
) -> dict[str, Any]:
    samples = list(samples)
    gates: dict[str, Any] = {}
    failures: list[dict[str, str]] = []
    backends: list[str] = []
    q4_failed = False

    for backend in REQUIRED_BACKENDS:
        if backend not in backend_reports:
            failures.append({"gate": f"report_{backend}", "reason": f"missing backend report: {backend}"})
            gates[f"protocol_{backend}"] = _gate(False, "missing backend report")
            gates[f"hard_constraints_{backend}"] = _gate(False, "missing backend report")
            if backend == "gguf_q4_K_M":
                q4_failed = True
            continue
        report = _load_json(backend_reports[backend])
        backends.append(backend)
        protocol_gate, constraint_gate, backend_failures, backend_q4_failed = _evaluate_backend(backend, samples, report)
        gates[f"protocol_{backend}"] = protocol_gate
        gates[f"hard_constraints_{backend}"] = constraint_gate
        failures.extend(backend_failures)
        q4_failed = q4_failed or backend_q4_failed

    q5_reasons: list[str] = []
    if q4_failed:
        q5_reasons.append("q4_K_M backend failed protocol or hard-constraint smoke; q5_K_M fallback decision required")

    payload = {
        "ok": not failures,
        "next_phase_allowed": not failures,
        "backends": backends,
        "n_samples": len(samples),
        "requirements_covered": list(REQUIREMENTS_COVERED),
        "gates": gates,
        "fatal_failures": failures,
        "q5_K_M_decision_required": bool(q5_reasons),
        "q5_K_M_decision_reasons": q5_reasons,
    }
    _write_json(Path(out_path) if out_path is not None else None, payload)
    return payload


def _evaluate_subreport(path: Path, requirement: str, name: str) -> tuple[dict[str, Any], list[dict[str, str]]]:
    failures: list[dict[str, str]] = []
    try:
        report = _load_json(path)
    except Exception as exc:
        return {}, [{"gate": name, "reason": f"missing or unreadable {name}: {exc}"}]
    if name == "smoke_report" and "ok" not in report and "n_parse_failures" in report:
        parse_failures = report.get("parse_failures") if isinstance(report.get("parse_failures"), list) else []
        q4_failures = [item for item in parse_failures if item.get("q4_parse_error")]
        report = dict(report)
        report["ok"] = len(parse_failures) == 0
        report["requirements_covered"] = ["GGUF4B-02", "GGUF4B-04"]
        report["q5_K_M_decision_required"] = bool(q4_failures)
        report["q5_K_M_decision_reasons"] = [f"q4_K_M parse/protocol failure on {len(q4_failures)} prompts"] if q4_failures else []
        report["fatal_failures"] = [{"gate": "three_backend_smoke", "reason": f"parse failures: {parse_failures}"}] if parse_failures else []
    if report.get("ok") is not True:
        failures.append({"gate": name, "reason": f"{name} is red"})
    if requirement not in report.get("requirements_covered", []):
        failures.append({"gate": name, "reason": f"{requirement} missing from {name}"})
    return report, failures


def _artifact_manifest(export: dict[str, Any]) -> dict[str, Any]:
    paths = export.get("paths") if isinstance(export.get("paths"), dict) else {}
    manifest: dict[str, Any] = {"paths": dict(paths), "sha256": {}}
    for key in ("gguf_fp16", "gguf_q4_K_M"):
        value = paths.get(key)
        if isinstance(value, str) and Path(value).is_file():
            manifest["sha256"][key] = sha256_file(Path(value))
    merged = paths.get("merged_hf")
    if isinstance(merged, str) and Path(merged).is_dir():
        safetensors = sorted(Path(merged).glob("*.safetensors"))
        manifest["sha256"]["merged_hf_safetensors"] = {str(path): sha256_file(path) for path in safetensors}
    return manifest


def evaluate_phase10_report(
    *,
    export_report: str | Path,
    tokenizer_report: str | Path,
    smoke_report: str | Path,
    out_path: str | Path | None = None,
) -> dict[str, Any]:
    export, export_failures = _evaluate_subreport(Path(export_report), "GGUF4B-01", "export_report")
    tokenizer, tokenizer_failures = _evaluate_subreport(Path(tokenizer_report), "GGUF4B-03", "tokenizer_report")
    smoke, smoke_failures = _evaluate_subreport(Path(smoke_report), "GGUF4B-02", "smoke_report")

    failures = export_failures + tokenizer_failures + smoke_failures
    if "GGUF4B-04" not in smoke.get("requirements_covered", []):
        failures.append({"gate": "smoke_report", "reason": "GGUF4B-04 missing from smoke_report"})

    q5_required = bool(smoke.get("q5_K_M_decision_required"))
    if q5_required and not any(failure["gate"] == "smoke_report" for failure in failures):
        failures.append({"gate": "smoke_report", "reason": "q5_K_M fallback decision required before Phase 11"})

    payload = {
        "ok": not failures,
        "next_phase_allowed": not failures,
        "requirements_covered": list(AGGREGATE_REQUIREMENTS) if not failures else sorted(set(export.get("requirements_covered", []) + tokenizer.get("requirements_covered", []) + smoke.get("requirements_covered", []))),
        "gates": {
            "export_report": _gate(not export_failures, None if not export_failures else "export report failed", {"path": str(export_report)}),
            "tokenizer_report": _gate(not tokenizer_failures, None if not tokenizer_failures else "tokenizer report failed", {"path": str(tokenizer_report)}),
            "smoke_report": _gate(not smoke_failures and not q5_required, None if not smoke_failures and not q5_required else "smoke report failed", {"path": str(smoke_report)}),
        },
        "fatal_failures": failures,
        "q5_K_M_decision_required": q5_required,
        "q5_K_M_decision_reasons": smoke.get("q5_K_M_decision_reasons", []),
        "reports": {
            "export_report": str(export_report),
            "tokenizer_report": str(tokenizer_report),
            "smoke_report": str(smoke_report),
        },
        "artifact_manifest": _artifact_manifest(export),
        "q4_collapse": q5_required,
        "phase11_handoff": {"allowed": not failures, "report_path": str(out_path) if out_path is not None else None},
    }
    _write_json(Path(out_path) if out_path is not None else None, payload)
    return payload


def write_phase10_report(run_root: str | Path, out: str | Path | None = None) -> dict[str, Any]:
    root = Path(run_root)
    return evaluate_phase10_report(
        export_report=root / "phase10_export_report.json",
        tokenizer_report=root / "gguf" / "tokenizer_parity.json",
        smoke_report=root / "gguf" / "parity_report.json",
        out_path=Path(out) if out is not None else root / "phase10_gguf_report.json",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Aggregate v4 Phase 10 export/tokenizer/smoke gates")
    parser.add_argument("--run-root", default=None)
    parser.add_argument("--export-report", default=None)
    parser.add_argument("--tokenizer-report", default=None)
    parser.add_argument("--smoke-report", default=None)
    parser.add_argument("--out", default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.run_root:
        report = write_phase10_report(Path(args.run_root), Path(args.out) if args.out else None)
    else:
        if not (args.export_report and args.tokenizer_report and args.smoke_report):
            raise SystemExit("either --run-root or all explicit report paths are required")
        report = evaluate_phase10_report(
            export_report=Path(args.export_report),
            tokenizer_report=Path(args.tokenizer_report),
            smoke_report=Path(args.smoke_report),
            out_path=Path(args.out) if args.out else None,
        )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
