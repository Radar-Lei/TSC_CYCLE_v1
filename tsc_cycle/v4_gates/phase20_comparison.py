from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable

from tsc_cycle.v4_gates.phase17_audit import DEFAULT_THRESHOLDS
from tsc_cycle.v4_gates.saturation_policy import VIOLATION_UNSATURATED_MAX_GREEN
from tsc_cycle.v4_gates.phase20_eval import validate_phase20_eval_report
from tsc_cycle.v4_gates.phase20_reality_test import validate_phase20_replay_report

PROJECT_ROOT = Path("/home/samuel/TSC_CYCLE")
ARTIFACT_ROOT = PROJECT_ROOT / "artifacts" / "v4_2" / "phase20"
DEFAULT_RUN_ROOT = PROJECT_ROOT / "runs" / "v4.2-4B-20260518T111519Z"
BASELINE_PHASE12_PER_SAMPLE = PROJECT_ROOT / "artifacts" / "v4" / "phase12" / "per_sample.jsonl"
BASELINE_PHASE17_GATE = PROJECT_ROOT / "artifacts" / "v4" / "phase17" / "saturation_policy_gate.json"
EVAL_REPORT_PATH = ARTIFACT_ROOT / "eval_report.json"
REPLAY_REPORT_PATH = ARTIFACT_ROOT / "reality_replay_report.json"
COMPARISON_REPORT_PATH = ARTIFACT_ROOT / "comparison_report.json"
REQUIREMENTS_COVERED = ["EVAL-03"]


def _read_json(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON payload must be an object: {path}")
    return payload


def _read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    path = Path(path)
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


def _write_json(path: str | Path, payload: dict[str, Any]) -> dict[str, Any]:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    return payload


def _hard_ok(row: dict[str, Any]) -> bool:
    if "hard_constraint_ok" in row:
        return bool(row.get("hard_constraint_ok"))
    if "lint_ok" in row:
        return bool(row.get("lint_ok"))
    return not bool(row.get("violations"))


def _is_low_saturation_violation(row: dict[str, Any]) -> bool:
    if row.get("violation_category") == VIOLATION_UNSATURATED_MAX_GREEN:
        return True
    try:
        sat = float(row.get("pred_saturation"))
        final_green = int(row.get("final_green"))
        max_green = int(row.get("max_green"))
    except (TypeError, ValueError):
        return False
    return sat < 1.0 and final_green == max_green and row.get("trivial_range") is not True


def _stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
    denominator = len(rows)
    hard_pass = sum(1 for row in rows if _hard_ok(row))
    low_sat_failures = sum(1 for row in rows if _is_low_saturation_violation(row))
    return {
        "rows": denominator,
        "hard_pass_count": hard_pass,
        "hard_pass_rate": hard_pass / denominator if denominator else 0.0,
        "low_saturation_max_green_count": low_sat_failures,
        "low_saturation_max_green_rate": low_sat_failures / denominator if denominator else 0.0,
    }


def _comparable_rows(baseline_rows: list[dict[str, Any]], v42_rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    base_by_key = {(str(row.get("sample_id")), str(row.get("phase_id"))): row for row in baseline_rows}
    v42_by_key = {(str(row.get("sample_id")), str(row.get("phase_id"))): row for row in v42_rows}
    keys = sorted(set(base_by_key).intersection(v42_by_key))
    if keys:
        return [base_by_key[key] for key in keys], [v42_by_key[key] for key in keys], {"mode": "paired_sample_phase", "paired_rows": len(keys)}
    return baseline_rows, v42_rows, {"mode": "aggregate", "paired_rows": 0}


def _baseline_rows_from_reports(path: Path) -> list[dict[str, Any]]:
    rows = _read_jsonl(path)
    out: list[dict[str, Any]] = []
    for row in rows:
        solution = row.get("solution") if isinstance(row.get("solution"), dict) else None
        prediction_input = row.get("input") if isinstance(row.get("input"), dict) else None
        waits = prediction_input.get("prediction", {}).get("phase_waits", []) if isinstance(prediction_input, dict) else []
        for wait in waits if isinstance(waits, list) else []:
            phase_id = str(wait.get("phase_id"))
            out.append({
                "sample_id": str(row.get("sample_id")),
                "phase_id": phase_id,
                "pred_saturation": wait.get("pred_saturation"),
                "min_green": wait.get("min_green"),
                "max_green": wait.get("max_green"),
                "final_green": solution.get(phase_id) if solution else None,
                "hard_constraint_ok": bool(row.get("lint_ok")),
                "violation_category": row.get("violation_category"),
            })
    return out


def _v42_rows_from_replay_report(report_path: Path) -> list[dict[str, Any]]:
    report = _read_json(report_path)
    rows = report.get("phase_rows") or report.get("rows") or []
    return list(rows) if isinstance(rows, list) else []


def _upstream_failures(run_root: Path, eval_report_path: Path, replay_report_path: Path) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    eval_report = validate_phase20_eval_report(report_path=eval_report_path, run_root=run_root)
    if eval_report.get("ok") is not True or eval_report.get("next_phase_allowed") is not True:
        failures.append({"gate": "phase20_eval", "reason": "Phase 20 eval report is not accepted", "details": eval_report.get("fatal_failures", [])})
    replay_report = validate_phase20_replay_report(replay_report_path, run_root=run_root, eval_report_path=eval_report_path)
    if replay_report.get("ok") is not True or replay_report.get("next_phase_allowed") is not True:
        failures.append({"gate": "phase20_replay", "reason": "Phase 20 replay report is not accepted", "details": replay_report.get("fatal_failures", [])})
    return failures


def compare_v4_v42_outputs(
    *,
    baseline_rows: Iterable[dict[str, Any]] | None = None,
    v42_rows: Iterable[dict[str, Any]] | None = None,
    run_root: str | Path = DEFAULT_RUN_ROOT,
    eval_report_path: str | Path = EVAL_REPORT_PATH,
    replay_report_path: str | Path = REPLAY_REPORT_PATH,
    baseline_per_sample_path: str | Path = BASELINE_PHASE12_PER_SAMPLE,
    report_path: str | Path | None = None,
) -> dict[str, Any]:
    run_root = Path(run_root)
    eval_report_path = Path(eval_report_path)
    replay_report_path = Path(replay_report_path)
    failures = _upstream_failures(run_root, eval_report_path, replay_report_path)
    baseline = list(baseline_rows) if baseline_rows is not None else _baseline_rows_from_reports(Path(baseline_per_sample_path))
    v42 = list(v42_rows) if v42_rows is not None else _v42_rows_from_replay_report(replay_report_path)
    comparable_baseline, comparable_v42, comparability = _comparable_rows(baseline, v42)
    baseline_stats = _stats(comparable_baseline)
    v42_stats = _stats(comparable_v42)

    if not comparable_baseline or not comparable_v42:
        failures.append({"gate": "comparison_denominator", "reason": "comparison requires non-empty baseline and v4.2 rows"})
    if v42_stats["hard_pass_rate"] < baseline_stats["hard_pass_rate"]:
        failures.append({"gate": "hard_constraint_regression", "reason": f"{v42_stats['hard_pass_rate']} < {baseline_stats['hard_pass_rate']}"})
    threshold = float(DEFAULT_THRESHOLDS["sat_lt_0.2_max_green_rate"])
    if v42_stats["low_saturation_max_green_count"] >= baseline_stats["low_saturation_max_green_count"] and baseline_stats["low_saturation_max_green_count"] > 0:
        failures.append({"gate": "saturation_not_reduced", "reason": "v4.2 low-saturation max-green failures were not reduced"})
    if v42_stats["low_saturation_max_green_rate"] > threshold:
        failures.append({"gate": "saturation_threshold", "reason": f"{v42_stats['low_saturation_max_green_rate']} > {threshold}"})

    ok = not failures
    report = {
        "ok": ok,
        "next_phase_allowed": ok,
        "requirements_covered": list(REQUIREMENTS_COVERED) if ok else [],
        "gates": {
            "upstream": {"ok": not any(f["gate"].startswith("phase20_") for f in failures)},
            "hard_constraint_non_regression": {"ok": v42_stats["hard_pass_rate"] >= baseline_stats["hard_pass_rate"], "baseline": baseline_stats["hard_pass_rate"], "v42": v42_stats["hard_pass_rate"]},
            "saturation_reduction": {"ok": v42_stats["low_saturation_max_green_count"] < baseline_stats["low_saturation_max_green_count"] or baseline_stats["low_saturation_max_green_count"] == 0, "baseline": baseline_stats["low_saturation_max_green_count"], "v42": v42_stats["low_saturation_max_green_count"]},
            "saturation_threshold": {"ok": v42_stats["low_saturation_max_green_rate"] <= threshold, "threshold": threshold, "v42": v42_stats["low_saturation_max_green_rate"]},
        },
        "fatal_failures": failures,
        "warnings": [],
        "decision_inputs": {
            "baseline_hard_pass_rate": baseline_stats["hard_pass_rate"],
            "v42_hard_pass_rate": v42_stats["hard_pass_rate"],
            "baseline_low_saturation_max_green_count": baseline_stats["low_saturation_max_green_count"],
            "v42_low_saturation_max_green_count": v42_stats["low_saturation_max_green_count"],
            "v42_low_saturation_max_green_rate": v42_stats["low_saturation_max_green_rate"],
            "low_saturation_threshold": threshold,
        },
        "comparability": comparability,
        "baseline": baseline_stats,
        "v42": v42_stats,
        "advisory": {},
        "reports": {"eval_report": str(eval_report_path), "replay_report": str(replay_report_path), "comparison_report": str(report_path or COMPARISON_REPORT_PATH)},
    }
    if report_path is not None:
        write_phase20_comparison_report(report, report_path)
    return report


def write_phase20_comparison_report(report: dict[str, Any], report_path: str | Path = COMPARISON_REPORT_PATH) -> dict[str, Any]:
    return _write_json(report_path, report)


def validate_phase20_comparison_report(report_path: str | Path = COMPARISON_REPORT_PATH, *, run_root: str | Path = DEFAULT_RUN_ROOT, eval_report_path: str | Path = EVAL_REPORT_PATH, replay_report_path: str | Path = REPLAY_REPORT_PATH) -> dict[str, Any]:
    try:
        report = _read_json(report_path)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        return {"ok": False, "next_phase_allowed": False, "requirements_covered": [], "fatal_failures": [{"gate": "report_json", "reason": str(exc)}], "report_path": str(report_path)}
    failures = list(report.get("fatal_failures", [])) if isinstance(report.get("fatal_failures"), list) else [{"gate": "fatal_failures", "reason": "fatal_failures must be a list"}]
    failures.extend(_upstream_failures(Path(run_root), Path(eval_report_path), Path(replay_report_path)))
    if report.get("ok") is not True or report.get("next_phase_allowed") is not True:
        failures.append({"gate": "report_green", "reason": "comparison report is not green"})
    covered = report.get("requirements_covered", [])
    if not isinstance(covered, list) or "EVAL-03" not in {str(item) for item in covered}:
        failures.append({"gate": "requirements_covered", "reason": "EVAL-03 coverage missing"})
    out = dict(report)
    out.update({"ok": not failures, "next_phase_allowed": not failures, "requirements_covered": list(REQUIREMENTS_COVERED) if not failures else [], "fatal_failures": failures, "report_path": str(report_path)})
    return out


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compare v4.0 and v4.2 Phase 20 replay/eval outcomes")
    parser.add_argument("--run-root", type=Path, default=DEFAULT_RUN_ROOT)
    parser.add_argument("--eval-report", type=Path, default=EVAL_REPORT_PATH)
    parser.add_argument("--replay-report", type=Path, default=REPLAY_REPORT_PATH)
    parser.add_argument("--baseline-per-sample", type=Path, default=BASELINE_PHASE12_PER_SAMPLE)
    parser.add_argument("--report", type=Path, default=COMPARISON_REPORT_PATH)
    parser.add_argument("--validate", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.validate:
        result = validate_phase20_comparison_report(args.report, run_root=args.run_root, eval_report_path=args.eval_report, replay_report_path=args.replay_report)
    else:
        result = compare_v4_v42_outputs(run_root=args.run_root, eval_report_path=args.eval_report, replay_report_path=args.replay_report, baseline_per_sample_path=args.baseline_per_sample, report_path=args.report)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False))
    return 0 if result.get("ok") is True else 1


if __name__ == "__main__":
    sys.exit(main())
