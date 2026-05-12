"""Phase 11 GO/NO-GO decision gate and markdown renderer.

This module is intentionally lightweight and stdlib-only. It consumes the
Phase 11 metrics JSON plus the Phase 10 GGUF handoff report and fails closed
for missing, null, or non-finite decision-critical evidence.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

from tsc_cycle.eval.phase11_matrix import FROZEN_V1_ROOT, PHASE11_OUT_ROOT, V1_Q4, V4_HF, V4_Q4, V4_RUN_ROOT, reject_frozen_v1_output_path
from tsc_cycle.eval.phase11_metrics import build_phase11_metrics_json, render_phase11_report
from tsc_cycle.eval.phase11_stats import paired_delta_ci, tail_metrics

PROJECT_ROOT = Path("/home/samuel/TSC_CYCLE")
PHASE10_REPORT = V4_RUN_ROOT / "phase10_gguf_report.json"
METRICS_PATH = PHASE11_OUT_ROOT / "metrics.json"
DECISION_MD_PATH = PHASE11_OUT_ROOT / "decision.md"
V4_Q4_ARTIFACT = V4_RUN_ROOT / "gguf" / "model.q4_K_M.gguf"
V1_Q4_ARTIFACT = FROZEN_V1_ROOT / "gguf" / "model.q4_K_M.gguf"
V1_PER_SAMPLE = FROZEN_V1_ROOT / "eval" / "per_sample.jsonl"

THRESHOLDS = {
    "v4_q4_hard_constraint_pass_min": 0.98,
    "q4_vs_hf_hard_pass_ratio_min": 0.95,
    "hard_pass_delta_ci_lower_min": -0.01,
    "teacher_mae_delta_ci_upper_max_sec": 0.5,
}

REQUIREMENTS_COVERED = ["EVAL4B-03", "EVAL4B-04"]


def _load_json(path_or_payload: str | Path | dict[str, Any]) -> dict[str, Any]:
    if isinstance(path_or_payload, dict):
        return path_or_payload
    path = Path(path_or_payload)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON payload is not an object: {path}")
    return payload


def _write_json(path: Path | None, payload: dict[str, Any]) -> None:
    if path is None:
        return
    reject_frozen_v1_output_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def _write_text(path: Path | None, content: str) -> None:
    if path is None:
        return
    reject_frozen_v1_output_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _finite_float(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(out):
        return None
    return out


def _verdict_label(verdict: str) -> str:
    if verdict == "NO_GO":
        return "NO-GO"
    if verdict == "USER_DECISION_REQUIRED":
        return "USER_DECISION"
    return verdict


def _gate(ok: bool, reason: str | None = None, data: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"ok": bool(ok), "reason": reason, "data": data or {}}


def _decision_input(metrics: dict[str, Any], primary: str, fallbacks: list[tuple[str, ...]]) -> Any:
    decision_inputs = metrics.get("decision_inputs") or {}
    if primary in decision_inputs:
        return decision_inputs.get(primary)
    for path in fallbacks:
        cur: Any = metrics
        for key in path:
            if not isinstance(cur, dict) or key not in cur:
                cur = None
                break
            cur = cur[key]
        if cur is not None:
            return cur
    return None


def _phase10_report_green(phase10: dict[str, Any], metrics_phase10: dict[str, Any]) -> tuple[bool, str | None]:
    if phase10:
        if phase10.get("ok") is not True:
            return False, "Phase 10 handoff report ok is not true"
        if phase10.get("next_phase_allowed") is not True:
            return False, "Phase 10 handoff report next_phase_allowed is not true"
        handoff = phase10.get("phase11_handoff") or {}
        if handoff.get("allowed") is not True:
            return False, "Phase 10 phase11_handoff.allowed is not true"
        return True, None
    if metrics_phase10.get("ok") is True:
        return True, None
    return False, "Phase 10 handoff evidence is missing or not ok"


def _pending_cache_warnings(metrics: dict[str, Any]) -> list[dict[str, str]]:
    warnings: list[dict[str, str]] = []
    backends = metrics.get("backends") or {}
    for backend in (V4_HF, V4_Q4, V1_Q4):
        agg = backends.get(backend) or {}
        denom = agg.get("hard_pass_n")
        pass_value = agg.get("ood_hard_constraint_pass", agg.get("hard_pass"))
        if denom == 0 or (denom is None and _finite_float(pass_value) is None):
            warnings.append({"gate": f"cache_{backend}", "reason": f"No decision rows available for {backend}; cache or per-sample evidence is pending"})
    baseline = (metrics.get("comparisons") or {}).get("v4_q4_vs_v1_q4_comparable_ood") or {}
    if baseline:
        if baseline.get("paired_sample_count") in (None, 0):
            reason = baseline.get("error") or "No paired comparable OOD rows are available"
            warnings.append({"gate": "paired_comparable_ood", "reason": str(reason)})
    elif "decision_inputs" in metrics:
        hard_low = (metrics.get("decision_inputs") or {}).get("v4_vs_v1_hard_pass_delta_ci95_lower")
        mae_high = (metrics.get("decision_inputs") or {}).get("v4_vs_v1_teacher_mae_delta_ci95_upper")
        if _finite_float(hard_low) is None or _finite_float(mae_high) is None:
            warnings.append({"gate": "paired_comparable_ood", "reason": "No paired comparable OOD rows are available"})
    return warnings


def bootstrap_ci(
    paired_rows: list[dict[str, Any]],
    *,
    seed: int = 42,
    n_resamples: int = 2000,
    confidence: float = 0.95,
) -> dict[str, Any]:
    """Return deterministic paired bootstrap CIs for hard-pass and MAE deltas."""
    if not paired_rows:
        raise ValueError("bootstrap_ci requires non-empty paired comparable sample rows")
    rows = sorted(paired_rows, key=lambda r: str(r.get("sample_id", "")))
    left_hard = [{"sample_id": r["sample_id"], "value": 1.0 if r.get("v4_q4_hard_pass") else 0.0} for r in rows]
    right_hard = [{"sample_id": r["sample_id"], "value": 1.0 if r.get("v1_q4_hard_pass") else 0.0} for r in rows]
    left_mae = [{"sample_id": r["sample_id"], "value": r.get("v4_q4_teacher_mae")} for r in rows]
    right_mae = [{"sample_id": r["sample_id"], "value": r.get("v1_q4_teacher_mae")} for r in rows]
    alpha = 1.0 - float(confidence)
    hard = paired_delta_ci(left_hard, right_hard, value_key="value", seed=seed, n=n_resamples, alpha=alpha)
    mae = paired_delta_ci(left_mae, right_mae, value_key="value", seed=seed, n=n_resamples, alpha=alpha)
    return {
        "seed": seed,
        "n_resamples": n_resamples,
        "confidence": confidence,
        "slice": "v1_comparable_ood",
        "sample_ids": sorted(str(r["sample_id"]) for r in rows),
        "metrics": {"hard_pass_delta": hard, "teacher_mae_delta": mae},
    }


def compute_tail_stats(rows: list[dict[str, Any]], *, backend: str, split: str = "ood") -> dict[str, Any]:
    sub = [
        r for r in rows
        if r.get("backend") == backend and (r.get("split_hint") == split or r.get("slice_hint") == split)
    ]
    if not sub:
        raise ValueError(f"empty denominator for tail stats backend={backend} split={split}")
    return tail_metrics(sub)


def evaluate_phase11_decision(
    metrics: dict[str, Any],
    *,
    phase10_report: dict[str, Any] | None = None,
    advisory_warnings: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Evaluate the locked U-01 Phase 11 GO/NO-GO/USER_DECISION gate."""
    failures: list[dict[str, Any]] = []
    warnings: list[dict[str, str]] = list(advisory_warnings or [])
    warnings.extend(_pending_cache_warnings(metrics))

    phase10_metrics = metrics.get("phase10_handoff") or {}
    phase10_ok, phase10_reason = _phase10_report_green(phase10_report or {}, phase10_metrics)
    if not phase10_ok:
        failures.append({"gate": "phase10_handoff", "reason": phase10_reason or "Phase 10 handoff is not green"})

    frozen = metrics.get("frozen_v1_baseline") or {}
    if frozen and frozen.get("ok") is not True:
        failures.append({"gate": "frozen_v1_baseline", "reason": "Frozen v1 baseline evidence is marked not ok"})
    if not frozen and metrics.get("backends", {}).get(V1_Q4, {}).get("hard_pass_n") in (None, 0):
        failures.append({"gate": "frozen_v1_baseline", "reason": "Frozen v1 comparable baseline evidence is missing from metrics"})

    checks = [
        {
            "gate": "v4_q4_hard_constraint_pass",
            "metric": "v4_q4_hard_pass_ood",
            "value": _decision_input(metrics, "v4_q4_hard_pass_ood", [("backends", V4_Q4, "ood_hard_constraint_pass")]),
            "threshold": THRESHOLDS["v4_q4_hard_constraint_pass_min"],
            "operator": ">=",
            "description": "v4 q4_K_M OOD hard-constraint pass rate",
        },
        {
            "gate": "q4_vs_hf_hard_pass_ratio",
            "metric": "v4_q4_vs_v4_hf_hard_pass_ratio",
            "value": _decision_input(metrics, "v4_q4_vs_v4_hf_hard_pass_ratio", [("q4_vs_hf", "hard_pass_ratio"), ("comparisons", "v4_q4_vs_v4_hf", "hard_pass_ratio")]),
            "threshold": THRESHOLDS["q4_vs_hf_hard_pass_ratio_min"],
            "operator": ">=",
            "description": "q4 hard-pass ratio versus v4 HF",
        },
        {
            "gate": "hard_pass_delta_ci_lower",
            "metric": "v4_vs_v1_hard_pass_delta_ci95_lower",
            "value": _decision_input(metrics, "v4_vs_v1_hard_pass_delta_ci95_lower", [("baseline_comparison", "hard_pass_delta_ci", "lower"), ("baseline_comparison", "hard_pass_delta_ci95", "lower")]),
            "threshold": THRESHOLDS["hard_pass_delta_ci_lower_min"],
            "operator": ">=",
            "description": "v4 q4 minus frozen v1 q4 hard-pass CI95 lower bound",
        },
        {
            "gate": "teacher_mae_delta_ci_upper",
            "metric": "v4_vs_v1_teacher_mae_delta_ci95_upper",
            "value": _decision_input(metrics, "v4_vs_v1_teacher_mae_delta_ci95_upper", [("baseline_comparison", "teacher_mae_delta_ci", "upper"), ("baseline_comparison", "teacher_mae_delta_ci95", "upper")]),
            "threshold": THRESHOLDS["teacher_mae_delta_ci_upper_max_sec"],
            "operator": "<=",
            "description": "v4 q4 minus frozen v1 q4 teacher-MAE CI95 upper bound in seconds",
        },
    ]

    check_results: list[dict[str, Any]] = []
    for check in checks:
        value_f = _finite_float(check["value"])
        if value_f is None:
            ok = False
            reason = f"non-finite decision input: {check['value']!r}"
        elif check["operator"] == ">=":
            ok = value_f >= float(check["threshold"])
            reason = None if ok else f"{value_f} < {check['threshold']}"
        else:
            ok = value_f <= float(check["threshold"])
            reason = None if ok else f"{value_f} > {check['threshold']}"
        result = dict(check)
        result["value"] = value_f
        result["ok"] = ok
        result["reason"] = reason
        check_results.append(result)
        if not ok:
            failures.append({"gate": str(check["gate"]), "reason": reason or "threshold failed", "value": value_f, "threshold": check["threshold"], "operator": check["operator"]})

    artifact_paths = {
        "recommended_artifact": str((metrics.get("artifacts") or {}).get("v4_q4") or V4_Q4_ARTIFACT),
        "fallback_artifact": str((metrics.get("artifacts") or {}).get("v1_q4") or V1_Q4_ARTIFACT),
    }
    if not Path(artifact_paths["recommended_artifact"]).exists():
        failures.append({"gate": "recommended_artifact", "reason": f"Recommended v4 q4_K_M artifact is missing: {artifact_paths['recommended_artifact']}"})
    if not Path(artifact_paths["fallback_artifact"]).exists():
        failures.append({"gate": "fallback_artifact", "reason": f"Frozen v1 q4_K_M fallback artifact is missing: {artifact_paths['fallback_artifact']}"})

    hard_ok = not failures
    if hard_ok and warnings:
        verdict = "USER_DECISION_REQUIRED"
        ok = False
        next_phase_allowed = False
    elif hard_ok:
        verdict = "GO"
        ok = True
        next_phase_allowed = True
    else:
        verdict = "NO_GO"
        ok = False
        next_phase_allowed = False

    return {
        "ok": ok,
        "verdict": verdict,
        "next_phase_allowed": next_phase_allowed,
        "thresholds": THRESHOLDS.copy(),
        "checks": check_results,
        "fatal_failures": failures,
        "warnings": warnings,
        "requirements_covered": list(REQUIREMENTS_COVERED),
        "recommended_artifact": artifact_paths["recommended_artifact"] if verdict == "GO" else None,
        "fallback_artifact": artifact_paths["fallback_artifact"],
        "comparison_artifact": artifact_paths["fallback_artifact"],
        "decision_policy": "GO only when all locked U-01 hard gates, Phase 10 handoff, artifacts, and finite inputs pass; hard failures remain NO_GO.",
    }


def _fmt_num(value: Any, digits: int = 4) -> str:
    value_f = _finite_float(value)
    if value_f is None:
        return "pending/non-finite"
    return f"{value_f:.{digits}f}"


def _fmt_bool(value: Any) -> str:
    return "PASS" if value else "FAIL"


def render_decision_markdown(metrics: dict[str, Any], decision: dict[str, Any]) -> str:
    """Render auditable Phase 11 decision markdown from structured data."""
    verdict = str(decision.get("verdict", "UNKNOWN"))
    phase10 = metrics.get("phase10_handoff") or {}
    advisory = metrics.get("phase10_advisory") or {}
    contribution = metrics.get("contribution") or {}
    recommended = decision.get("recommended_artifact") or str((metrics.get("artifacts") or {}).get("v4_q4") or V4_Q4_ARTIFACT)
    fallback = decision.get("fallback_artifact") or str((metrics.get("artifacts") or {}).get("v1_q4") or V1_Q4_ARTIFACT)

    lines = [
        "# Phase 11 Decision Gate",
        "",
        f"**Verdict:** {_verdict_label(verdict)}",
        f"**Machine verdict code:** `{verdict}`",
        f"**Next phase allowed:** `{bool(decision.get('next_phase_allowed'))}`",
        "",
        "## Deployment / Fallback Artifacts",
        "",
        f"- Deployable v4 q4_K_M artifact on GO: `{recommended}`",
        f"- Frozen v1 q4_K_M fallback/comparison baseline: `{fallback}`",
        f"- Frozen v1 evidence root: `{FROZEN_V1_ROOT}`",
        "",
        "## Locked U-01 Thresholds",
        "",
        "| Gate | Computed value | Threshold | Result |",
        "|---|---:|---:|---|",
    ]
    for check in decision.get("checks", []):
        lines.append(
            f"| `{check.get('metric')}` | {_fmt_num(check.get('value'))} | {check.get('operator')} {check.get('threshold')} | {_fmt_bool(check.get('ok'))} |"
        )

    lines.extend([
        "",
        "## Fatal Failures",
        "",
    ])
    failures = decision.get("fatal_failures") or []
    if failures:
        for failure in failures:
            lines.append(f"- `{failure.get('gate')}`: {failure.get('reason')}")
    else:
        lines.append("None.")

    lines.extend([
        "",
        "## Warnings / Pending Evidence",
        "",
    ])
    warnings = decision.get("warnings") or []
    if warnings:
        for warning in warnings:
            lines.append(f"- `{warning.get('gate')}`: {warning.get('reason')}")
    else:
        lines.append("None.")

    lines.extend([
        "",
        "## Contribution Narrative",
        "",
        "- Expanded data: " + str(contribution.get("expanded_data") or "Phase 11 separates v4-expanded OOD from v1-comparable OOD so new coverage explains robustness without contaminating the no-regression denominator."),
        "- Tag fix: " + str(contribution.get("tag_fix") or "Format pass and reasoning checks track custom tag repair, including malformed `</end_working_out>` and native `<think>` regressions."),
        "",
        "## Phase 10 q4-vs-HF Smoke MAE Advisory",
        "",
        f"Phase 10 report path: `{phase10.get('report_path') or PHASE10_REPORT}`",
        f"Phase 10 q4-vs-HF smoke MAE sensitivity: `{_fmt_num(advisory.get('q4_vs_hf_smoke_mae_sensitivity_sec', phase10.get('q4_vs_hf_smoke_mae_sensitivity_sec')), 3)}` seconds.",
        "This is advisory only; the Phase 11 metrics matrix is the authoritative decision input.",
        "",
        "## Source Evidence",
        "",
        f"- Metrics JSON: `{METRICS_PATH}`",
        f"- Decision markdown: `{DECISION_MD_PATH}`",
        f"- Comparable frozen v1 per-sample evidence: `{V1_PER_SAMPLE}`",
        "",
    ])
    return "\n".join(lines)


# Compatibility alias expected by older task text.
def render_phase11_decision_md(metrics: dict[str, Any], decision: dict[str, Any]) -> str:
    return render_decision_markdown(metrics=metrics, decision=decision)


def evaluate_phase11_report(
    *,
    metrics: dict[str, Any],
    phase10_handoff_report: str | Path,
    frozen_v1_per_sample: str | Path,
    out_path: str | Path | None = None,
) -> dict[str, Any]:
    """Compatibility fail-closed aggregate report used by Phase 11 contracts."""
    phase10_path = Path(phase10_handoff_report)
    frozen_path = Path(frozen_v1_per_sample)
    failures: list[dict[str, Any]] = []
    phase10_payload: dict[str, Any] = {}
    if not phase10_path.exists():
        failures.append({"gate": "phase10_handoff", "reason": f"Phase 10 handoff report missing: {phase10_path}"})
    else:
        try:
            phase10_payload = _load_json(phase10_path)
            if phase10_payload.get("ok") is not True or phase10_payload.get("next_phase_allowed") is not True:
                failures.append({"gate": "phase10_handoff", "reason": "Phase 10 handoff report is not green"})
        except Exception as exc:  # pragma: no cover - defensive parsing
            failures.append({"gate": "phase10_handoff", "reason": f"Phase 10 handoff unreadable: {exc}"})
    if not frozen_path.exists():
        failures.append({"gate": "frozen_v1_baseline", "reason": f"Frozen v1 baseline per_sample missing: {frozen_path}"})

    decision = evaluate_phase11_decision(metrics, phase10_report=phase10_payload)
    failures.extend(decision.get("fatal_failures") or [])
    ok = not failures and decision.get("ok") is True
    report = {
        "ok": ok,
        "next_phase_allowed": ok,
        "requirements_covered": ["EVAL4B-01", "EVAL4B-02", "EVAL4B-03", "EVAL4B-04"],
        "gates": {
            "phase10_handoff": _gate(phase10_path.exists() and phase10_payload.get("ok") is True, None if phase10_path.exists() and phase10_payload.get("ok") is True else "Phase 10 handoff failed", {"path": str(phase10_path)}),
            "frozen_v1_baseline": _gate(frozen_path.exists(), None if frozen_path.exists() else "Frozen v1 per-sample evidence missing", {"path": str(frozen_path)}),
            "decision": _gate(decision.get("ok") is True, None if decision.get("ok") is True else "Phase 11 decision is not GO"),
        },
        "fatal_failures": failures,
        "warnings": decision.get("warnings") or [],
        "decision": decision,
        "recommended_artifact": decision.get("recommended_artifact"),
        "fallback_artifact": decision.get("fallback_artifact"),
        "reports": {"phase10_handoff": str(phase10_path)},
    }
    _write_json(Path(out_path) if out_path is not None else None, report)
    return report


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate Phase 11 decision gate and render decision.md")
    parser.add_argument("--metrics", type=Path, default=METRICS_PATH)
    parser.add_argument("--phase10-report", type=Path, default=PHASE10_REPORT)
    parser.add_argument("--out-decision", type=Path, default=DECISION_MD_PATH)
    parser.add_argument("--out-json", type=Path, default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    reject_frozen_v1_output_path(args.out_decision)
    metrics = _load_json(args.metrics)
    phase10_report = _load_json(args.phase10_report) if args.phase10_report.exists() else {}
    phase10_handoff = metrics.setdefault("phase10_handoff", {})
    phase10_handoff.setdefault("report_path", str(args.phase10_report))
    if phase10_report:
        phase10_handoff.setdefault("ok", bool(phase10_report.get("ok") is True and phase10_report.get("next_phase_allowed") is True))
    metrics.setdefault("frozen_v1_baseline", {"ok": V1_PER_SAMPLE.exists(), "root": str(FROZEN_V1_ROOT), "per_sample": str(V1_PER_SAMPLE)})
    metrics.setdefault("artifacts", {"v4_q4": str(V4_Q4_ARTIFACT), "v1_q4": str(V1_Q4_ARTIFACT), "decision_md": str(args.out_decision)})
    metrics.setdefault("contribution", {
        "expanded_data": "Phase 11 reports v4-expanded OOD separately from frozen-v1 comparable OOD to show added-data contribution without hiding no-regression evidence.",
        "tag_fix": "Format pass captures custom reasoning tag repair, including malformed </end_working_out> and native <think> regressions.",
    })
    decision = evaluate_phase11_decision(metrics, phase10_report=phase10_report)
    _write_text(args.out_decision, render_decision_markdown(metrics=metrics, decision=decision))
    _write_json(args.out_json, decision)
    print(json.dumps(decision, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False))
    return 0 if decision.get("ok") is True else 1


if __name__ == "__main__":
    sys.exit(main())
