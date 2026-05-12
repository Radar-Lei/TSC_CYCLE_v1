"""Fail-closed aggregate handoff report for Phase 11 evaluation matrix."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from tsc_cycle.eval.phase11_decision import DECISION_MD_PATH, METRICS_PATH, PHASE10_REPORT, V1_PER_SAMPLE, evaluate_phase11_decision
from tsc_cycle.eval.phase11_matrix import FROZEN_V1_ROOT, PHASE11_OUT_ROOT, V1_Q4, V4_HF, V4_Q4, V4_RUN_ROOT, reject_frozen_v1_output_path

PROJECT_ROOT = Path("/home/samuel/TSC_CYCLE")
ARTIFACT_ROOT = PROJECT_ROOT / "artifacts" / "v4" / "phase11"
GATE_REPORT_PATH = ARTIFACT_ROOT / "phase11_gate_report.json"
MATRIX_MANIFEST_PATH = PHASE11_OUT_ROOT / "matrix_manifest.json"
PER_SAMPLE_PATH = PHASE11_OUT_ROOT / "per_sample.jsonl"
REPORT_MD_PATH = PHASE11_OUT_ROOT / "report.md"
EVAL_PROMPTS_PATH = PHASE11_OUT_ROOT / "eval_prompts.jsonl"
V4_Q4_ARTIFACT = V4_RUN_ROOT / "gguf" / "model.q4_K_M.gguf"
V1_Q4_ARTIFACT = FROZEN_V1_ROOT / "gguf" / "model.q4_K_M.gguf"
REQUIREMENTS_COVERED = ["EVAL4B-01", "EVAL4B-02", "EVAL4B-03", "EVAL4B-04"]


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
    reject_frozen_v1_output_path(path)
    _assert_allowed_output(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def _is_under(path: Path, root: Path) -> bool:
    path = path.expanduser().resolve(strict=False)
    root = root.expanduser().resolve(strict=False)
    return path == root or root in path.parents


def _assert_allowed_output(path: str | Path) -> None:
    candidate = Path(path)
    if _is_under(candidate, FROZEN_V1_ROOT):
        raise ValueError(f"refusing Phase 11 report output under frozen v1 root: {candidate}")
    if not (_is_under(candidate, PHASE11_OUT_ROOT) or _is_under(candidate, ARTIFACT_ROOT)):
        raise ValueError(f"Phase 11 report output must be under eval_phase11 or artifacts/v4/phase11: {candidate}")


def _gate(ok: bool, reason: str | None = None, data: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"ok": bool(ok), "reason": reason, "data": data or {}}


def _check_file(path: Path, label: str, failures: list[dict[str, str]], *, nonempty: bool = True) -> bool:
    if not path.exists():
        failures.append({"gate": label, "reason": f"missing {label}: {path}"})
        return False
    if nonempty and path.is_file() and path.stat().st_size <= 0:
        failures.append({"gate": label, "reason": f"empty {label}: {path}"})
        return False
    return True


def _check_dir(path: Path, label: str, failures: list[dict[str, str]]) -> bool:
    if not path.is_dir():
        failures.append({"gate": label, "reason": f"missing directory {label}: {path}"})
        return False
    return True


def _phase10_green(path: Path, failures: list[dict[str, str]]) -> dict[str, Any]:
    if not _check_file(path, "phase10_handoff", failures):
        return {}
    try:
        report = _load_json(path)
    except Exception as exc:
        failures.append({"gate": "phase10_handoff", "reason": f"unreadable Phase 10 handoff: {exc}"})
        return {}
    if report.get("ok") is not True:
        failures.append({"gate": "phase10_handoff", "reason": "Phase 10 handoff ok is not true"})
    if report.get("next_phase_allowed") is not True:
        failures.append({"gate": "phase10_handoff", "reason": "Phase 10 next_phase_allowed is not true"})
    if (report.get("phase11_handoff") or {}).get("allowed") is not True:
        failures.append({"gate": "phase10_handoff", "reason": "Phase 10 phase11_handoff.allowed is not true"})
    paths = (report.get("artifact_manifest") or {}).get("paths") or {}
    q4 = paths.get("gguf_q4_K_M")
    if str(q4) != str(V4_Q4_ARTIFACT):
        failures.append({"gate": "phase10_handoff", "reason": f"Phase 10 q4 artifact mismatch: {q4}"})
    return report


def _matrix_ok(manifest_path: Path, failures: list[dict[str, str]]) -> dict[str, Any]:
    if not _check_file(manifest_path, "matrix_manifest", failures):
        return {}
    try:
        manifest = _load_json(manifest_path)
    except Exception as exc:
        failures.append({"gate": "matrix_manifest", "reason": f"unreadable matrix manifest: {exc}"})
        return {}
    backends = set((manifest.get("backends") or {}).keys())
    required = {V4_HF, V4_Q4, V1_Q4}
    if backends != required:
        failures.append({"gate": "matrix_manifest", "reason": f"backend set mismatch: {sorted(backends)}"})
    v1 = (manifest.get("backends") or {}).get(V1_Q4) or {}
    if v1.get("read_only") is not True or v1.get("generate") is not False:
        failures.append({"gate": "frozen_v1_read_only", "reason": "frozen v1 backend is not marked read_only=true and generate=false"})
    if str(FROZEN_V1_ROOT) not in json.dumps(manifest, ensure_ascii=False):
        failures.append({"gate": "frozen_v1_read_only", "reason": "frozen v1 root missing from matrix manifest evidence"})
    return manifest


def _metrics_ok(metrics_path: Path, failures: list[dict[str, str]]) -> dict[str, Any]:
    if not _check_file(metrics_path, "metrics_json", failures):
        return {}
    try:
        metrics = _load_json(metrics_path)
    except Exception as exc:
        failures.append({"gate": "metrics_json", "reason": f"unreadable metrics JSON: {exc}"})
        return {}
    required_sections = ["backends", "q4_vs_hf", "baseline_comparison", "tail_stats", "decision_inputs"]
    for section in required_sections:
        if section not in metrics:
            failures.append({"gate": "metrics_json", "reason": f"missing metrics section: {section}"})
    return metrics


def evaluate_phase11_report(
    *,
    metrics: str | Path | dict[str, Any] = METRICS_PATH,
    phase10_handoff_report: str | Path = PHASE10_REPORT,
    matrix_manifest: str | Path = MATRIX_MANIFEST_PATH,
    decision_md: str | Path = DECISION_MD_PATH,
    report_md: str | Path = REPORT_MD_PATH,
    per_sample: str | Path = PER_SAMPLE_PATH,
    frozen_v1_per_sample: str | Path = V1_PER_SAMPLE,
    out_path: str | Path | None = None,
) -> dict[str, Any]:
    failures: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []

    phase10_path = Path(phase10_handoff_report)
    manifest_path = Path(matrix_manifest)
    decision_path = Path(decision_md)
    report_path = Path(report_md)
    per_sample_path = Path(per_sample)
    frozen_path = Path(frozen_v1_per_sample)

    phase10_report = _phase10_green(phase10_path, failures)
    matrix = _matrix_ok(manifest_path, failures)
    if isinstance(metrics, dict):
        metrics_payload = metrics
    else:
        metrics_payload = _metrics_ok(Path(metrics), failures)

    _check_file(EVAL_PROMPTS_PATH, "eval_prompts", failures)
    _check_dir(PHASE11_OUT_ROOT / "gen_cache" / V4_HF, "v4_hf_cache_dir", failures)
    _check_dir(PHASE11_OUT_ROOT / "gen_cache" / V4_Q4, "v4_q4_cache_dir", failures)
    _check_file(per_sample_path, "per_sample", failures)
    _check_file(report_path, "metrics_report_md", failures)
    _check_file(decision_path, "decision_md", failures)
    _check_file(frozen_path, "frozen_v1_per_sample", failures)
    _check_file(V4_Q4_ARTIFACT, "recommended_v4_q4_artifact", failures)
    _check_file(V1_Q4_ARTIFACT, "fallback_v1_q4_artifact", failures)

    if metrics_payload:
        enriched_metrics = dict(metrics_payload)
        enriched_metrics.setdefault("phase10_handoff", {"ok": bool(phase10_report.get("ok") is True), "report_path": str(phase10_path)})
        enriched_metrics.setdefault("frozen_v1_baseline", {"ok": frozen_path.exists(), "root": str(FROZEN_V1_ROOT), "per_sample": str(frozen_path)})
        enriched_metrics.setdefault("artifacts", {"v4_q4": str(V4_Q4_ARTIFACT), "v1_q4": str(V1_Q4_ARTIFACT), "decision_md": str(decision_path)})
    else:
        enriched_metrics = {}
    decision = evaluate_phase11_decision(enriched_metrics, phase10_report=phase10_report) if enriched_metrics else {"ok": False, "verdict": "NO_GO", "fatal_failures": [{"gate": "metrics_json", "reason": "metrics missing"}], "warnings": []}
    failures.extend(decision.get("fatal_failures") or [])
    warnings.extend(decision.get("warnings") or [])

    ok = not failures and decision.get("ok") is True
    gates = {
        "phase10_handoff": _gate(bool(phase10_report.get("ok") is True and phase10_report.get("next_phase_allowed") is True), None if phase10_report.get("ok") is True else "Phase 10 handoff not green", {"path": str(phase10_path)}),
        "matrix_manifest": _gate(bool(matrix and set((matrix.get("backends") or {}).keys()) == {V4_HF, V4_Q4, V1_Q4}), None if matrix else "matrix manifest failed", {"path": str(manifest_path)}),
        "metrics_json": _gate(bool(metrics_payload and metrics_payload.get("decision_inputs") is not None), None if metrics_payload else "metrics JSON failed", {"path": str(metrics if not isinstance(metrics, dict) else METRICS_PATH)}),
        "decision": _gate(decision.get("ok") is True, None if decision.get("ok") is True else "Phase 11 decision is not GO", {"verdict": decision.get("verdict")}),
        "frozen_v1_read_only": _gate(bool(frozen_path.exists() and not _is_under(GATE_REPORT_PATH, FROZEN_V1_ROOT)), None if frozen_path.exists() else "frozen v1 evidence missing", {"root": str(FROZEN_V1_ROOT)}),
    }

    payload = {
        "ok": ok,
        "next_phase_allowed": ok,
        "requirements_covered": list(REQUIREMENTS_COVERED),
        "gates": gates,
        "fatal_failures": failures,
        "warnings": warnings,
        "decision": decision,
        "recommended_artifact": decision.get("recommended_artifact"),
        "fallback_artifact": decision.get("fallback_artifact") or str(V1_Q4_ARTIFACT),
        "reports": {
            "phase10_handoff": str(phase10_path),
            "matrix_manifest": str(manifest_path),
            "metrics_json": str(metrics if not isinstance(metrics, dict) else METRICS_PATH),
            "metrics_report_md": str(report_path),
            "decision_md": str(decision_path),
            "per_sample": str(per_sample_path),
            "gate_report": str(out_path) if out_path is not None else str(GATE_REPORT_PATH),
        },
        "phase11_handoff": {
            "allowed": ok,
            "report_path": str(out_path) if out_path is not None else str(GATE_REPORT_PATH),
            "status": decision.get("verdict", "NO_GO"),
        },
    }
    _write_json(Path(out_path) if out_path is not None else None, payload)
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Aggregate Phase 11 eval matrix/decision gate")
    parser.add_argument("--metrics", type=Path, default=METRICS_PATH)
    parser.add_argument("--phase10-report", type=Path, default=PHASE10_REPORT)
    parser.add_argument("--matrix-manifest", type=Path, default=MATRIX_MANIFEST_PATH)
    parser.add_argument("--decision-md", type=Path, default=DECISION_MD_PATH)
    parser.add_argument("--report-md", type=Path, default=REPORT_MD_PATH)
    parser.add_argument("--per-sample", type=Path, default=PER_SAMPLE_PATH)
    parser.add_argument("--frozen-v1-per-sample", type=Path, default=V1_PER_SAMPLE)
    parser.add_argument("--out", type=Path, default=GATE_REPORT_PATH)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = evaluate_phase11_report(
        metrics=args.metrics,
        phase10_handoff_report=args.phase10_report,
        matrix_manifest=args.matrix_manifest,
        decision_md=args.decision_md,
        report_md=args.report_md,
        per_sample=args.per_sample,
        frozen_v1_per_sample=args.frozen_v1_per_sample,
        out_path=args.out,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False))
    return 0 if report.get("ok") is True else 1


if __name__ == "__main__":
    sys.exit(main())
