from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from tsc_cycle.constraint_lint import validate
from tsc_cycle.prompt_builder import parse_assistant_output
from tsc_cycle.v4_gates.phase17_audit import evaluate_saturation_policy_gate
from tsc_cycle.v4_gates.saturation_policy import classify_saturation_band, classify_violation, is_trivial_phase_range
from tsc_cycle.v4_gates.phase19_export import validate_phase19_export_report

PROJECT_ROOT = Path("/home/samuel/TSC_CYCLE")
DEFAULT_RUN_ROOT = PROJECT_ROOT / "runs" / "v4.2-4B-20260518T111519Z"
DEFAULT_LABELED_PATH = PROJECT_ROOT / "data" / "v4_2" / "phase18" / "labeled_calibrated.jsonl"
DEFAULT_SPLIT_INDEXES = (
    PROJECT_ROOT / "data" / "v4_2" / "phase18" / "splits" / "val.index.jsonl",
    PROJECT_ROOT / "data" / "v4_2" / "phase18" / "splits" / "ood_val.index.jsonl",
)
ARTIFACT_ROOT = PROJECT_ROOT / "artifacts" / "v4_2" / "phase20"
EVAL_PROMPTS_PATH = ARTIFACT_ROOT / "eval_prompts.jsonl"
EVAL_PROMPT_MANIFEST_PATH = ARTIFACT_ROOT / "eval_prompt_manifest.json"
EVAL_CACHE_DIR = ARTIFACT_ROOT / "gen_cache" / "v4_2_hf"
EVAL_OUTPUTS_PATH = ARTIFACT_ROOT / "eval_outputs.jsonl"
EVAL_REPORT_PATH = ARTIFACT_ROOT / "eval_report.json"
REQUIREMENTS_COVERED = ("EVAL-01",)


def _read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with Path(path).open("r", encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, start=1):
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


def _write_jsonl(path: str | Path, rows: list[dict[str, Any]]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n")


def _split_name(path: Path) -> str:
    name = path.name
    suffix = ".index.jsonl"
    return name[: -len(suffix)] if name.endswith(suffix) else path.stem


def _solution_from_labeled_row(row: dict[str, Any]) -> dict[str, int] | None:
    result = row.get("result")
    solution = result.get("solution") if isinstance(result, dict) else row.get("solution")
    if not isinstance(solution, dict):
        return None
    out: dict[str, int] = {}
    for key, value in solution.items():
        if isinstance(value, bool) or not isinstance(value, int):
            return None
        out[str(key)] = value
    return out


def _phase_count(prediction_input: dict[str, Any]) -> int:
    waits = prediction_input.get("prediction", {}).get("phase_waits", [])
    return len(waits) if isinstance(waits, list) else 0


def build_phase20_eval_prompts(
    *,
    labeled_path: str | Path = DEFAULT_LABELED_PATH,
    split_indexes: tuple[str | Path, ...] = DEFAULT_SPLIT_INDEXES,
    out_path: str | Path = EVAL_PROMPTS_PATH,
    manifest_path: str | Path = EVAL_PROMPT_MANIFEST_PATH,
) -> list[dict[str, Any]]:
    labeled_path = Path(labeled_path)
    by_id: dict[str, dict[str, Any]] = {}
    for row in _read_jsonl(labeled_path):
        sample_id = row.get("sample_id")
        if isinstance(sample_id, str) and sample_id:
            by_id[sample_id] = row

    rows: list[dict[str, Any]] = []
    slice_counts: Counter[str] = Counter()
    for split_index in split_indexes:
        index_path = Path(split_index)
        slice_hint = _split_name(index_path)
        for index_row in _read_jsonl(index_path):
            sample_id = str(index_row.get("sample_id") or "")
            if not sample_id:
                raise ValueError(f"missing sample_id in split index: {index_path}")
            source = by_id.get(sample_id)
            if source is None:
                raise ValueError(f"split sample_id not found in calibrated labels: {sample_id}")
            prediction_input = source.get("input")
            teacher_solution = _solution_from_labeled_row(source)
            if not isinstance(prediction_input, dict) or teacher_solution is None:
                raise ValueError(f"calibrated row lacks input or solution: {sample_id}")
            row = {
                "sample_id": sample_id,
                "split_hint": slice_hint,
                "slice_hint": slice_hint,
                "input": prediction_input,
                "teacher_solution": teacher_solution,
                "phase_count": _phase_count(prediction_input),
                "trivial": bool(source.get("trivial", False)),
            }
            rows.append(row)
            slice_counts[slice_hint] += 1

    _write_jsonl(out_path, rows)
    _write_json(
        manifest_path,
        {
            "ok": True,
            "requirements_covered": list(REQUIREMENTS_COVERED),
            "source_labeled_path": str(labeled_path),
            "split_indexes": [str(Path(path)) for path in split_indexes],
            "out_path": str(out_path),
            "slice_counts": dict(sorted(slice_counts.items())),
            "total_rows": len(rows),
        },
    )
    return rows


def load_phase20_generated_outputs(
    *,
    prompts_path: str | Path = EVAL_PROMPTS_PATH,
    cache_dir: str | Path = EVAL_CACHE_DIR,
    out_path: str | Path = EVAL_OUTPUTS_PATH,
) -> list[dict[str, Any]]:
    prompts = _read_jsonl(prompts_path)
    cache_dir = Path(cache_dir)
    rows: list[dict[str, Any]] = []
    missing: list[str] = []
    for prompt in prompts:
        sample_id = str(prompt.get("sample_id") or "")
        cache_path = cache_dir / f"{sample_id}.json"
        if not cache_path.is_file():
            missing.append(str(cache_path))
            continue
        cache = json.loads(cache_path.read_text(encoding="utf-8"))
        if not isinstance(cache, dict):
            raise ValueError(f"cache JSON is not an object: {cache_path}")
        rows.append(
            {
                "sample_id": sample_id,
                "split_hint": prompt.get("split_hint"),
                "slice_hint": prompt.get("slice_hint") or prompt.get("split_hint"),
                "input": prompt.get("input"),
                "teacher_solution": prompt.get("teacher_solution"),
                "raw_text": cache.get("raw_text", ""),
                "solution": cache.get("solution"),
                "parse_error": cache.get("parse_error"),
                "backend": "v4_2_hf",
                "phase_count": prompt.get("phase_count"),
                "trivial": bool(prompt.get("trivial", False)),
                "source_prompt": prompt,
                "source_cache_path": str(cache_path),
            }
        )
    if missing:
        raise FileNotFoundError(f"missing Phase 20 generated cache files: {len(missing)}; first={missing[0]}")
    _write_jsonl(out_path, rows)
    return rows


def _teacher_mae(rows: list[dict[str, Any]]) -> dict[str, Any]:
    values: list[float] = []
    for row in rows:
        solution = row.get("solution")
        teacher = row.get("teacher_solution")
        if not isinstance(solution, dict) or not isinstance(teacher, dict):
            continue
        for key, teacher_value in teacher.items():
            pred_value = solution.get(str(key))
            if isinstance(pred_value, int) and not isinstance(pred_value, bool) and isinstance(teacher_value, int) and not isinstance(teacher_value, bool):
                values.append(abs(float(pred_value - teacher_value)))
    return {"value": sum(values) / len(values) if values else None, "n": len(values)}


def _phase_rows_for_output(row: dict[str, Any], solution: dict[str, int]) -> list[dict[str, Any]]:
    prediction_input = row.get("input")
    waits = prediction_input.get("prediction", {}).get("phase_waits", []) if isinstance(prediction_input, dict) else []
    phase_rows: list[dict[str, Any]] = []
    for wait in waits:
        if not isinstance(wait, dict):
            raise ValueError(f"malformed phase_waits entry for sample_id={row.get('sample_id')}")
        phase_id = str(wait.get("phase_id"))
        phase_row = {
            "origin_artifact": "phase20_eval_outputs",
            "sample_id": str(row.get("sample_id")),
            "phase_id": phase_id,
            "pred_saturation": wait.get("pred_saturation"),
            "min_green": wait.get("min_green"),
            "max_green": wait.get("max_green"),
            "final_green": solution.get(phase_id),
            "split": str(row.get("slice_hint") or row.get("split_hint") or "unknown"),
            "source": str(row.get("backend") or "v4_2_hf"),
            "source_origin": "phase20_eval",
        }
        phase_row["saturation_band"] = classify_saturation_band(phase_row["pred_saturation"])
        phase_row["trivial_range"] = is_trivial_phase_range(phase_row)
        phase_row["violation_category"] = classify_violation(phase_row)
        phase_rows.append(phase_row)
    return phase_rows


def _phase19_gate(run_root: Path) -> dict[str, Any]:
    try:
        return validate_phase19_export_report(run_root, run_root / "phase19_export_report.json")
    except Exception as exc:  # pragma: no cover - fail-closed boundary
        return {
            "ok": False,
            "next_phase_allowed": False,
            "requirements_covered": [],
            "fatal_failures": [{"gate": "phase19_export", "reason": f"{type(exc).__name__}: {exc}"}],
        }


def evaluate_phase20_outputs(
    *,
    outputs_path: str | Path = EVAL_OUTPUTS_PATH,
    run_root: str | Path = DEFAULT_RUN_ROOT,
    report_path: str | Path | None = None,
) -> dict[str, Any]:
    run_root = Path(run_root)
    outputs_path = Path(outputs_path)
    write_path = Path(report_path) if report_path is not None else None
    display_report_path = write_path or EVAL_REPORT_PATH
    phase19 = _phase19_gate(run_root)
    if phase19.get("ok") is not True or phase19.get("next_phase_allowed") is not True:
        failures = [{"gate": "phase19_export", "reason": "Phase 19 export report is not accepted", "details": phase19.get("fatal_failures", [])}]
        report = {
            "ok": False,
            "next_phase_allowed": False,
            "requirements_covered": [],
            "gates": {"phase19_export": {"ok": False, "data": phase19}},
            "fatal_failures": failures,
            "warnings": [],
            "reports": {"eval_report": str(display_report_path)},
            "artifacts": {"eval_outputs": str(outputs_path)},
        }
        if write_path is not None:
            write_phase20_eval_report(report, write_path)
        return report

    rows = _read_jsonl(outputs_path)
    fatal_failures: list[dict[str, Any]] = []
    evaluated_rows: list[dict[str, Any]] = []
    phase_rows: list[dict[str, Any]] = []
    parse_ok = 0
    lint_ok = 0
    for row in rows:
        sample_id = str(row.get("sample_id") or "")
        raw_text = row.get("raw_text") if isinstance(row.get("raw_text"), str) else ""
        _, parsed_solution = parse_assistant_output(raw_text)
        row_solution = row.get("solution") if isinstance(row.get("solution"), dict) else None
        if row.get("parse_error") is not None or parsed_solution is None or row_solution is None:
            fatal_failures.append({"gate": "parse_protocol", "sample_id": sample_id, "reason": row.get("parse_error") or "solution_unparseable"})
            evaluated_rows.append({**row, "format_ok": False, "lint_ok": False, "violations": []})
            continue
        parse_ok += 1
        prediction_input = row.get("input")
        lint = validate(prediction_input if isinstance(prediction_input, dict) else {}, parsed_solution)
        if not lint.ok:
            fatal_failures.append({"gate": "hard_constraint_lint", "sample_id": sample_id, "violations": lint.violations})
            evaluated_rows.append({**row, "solution": parsed_solution, "format_ok": True, "lint_ok": False, "violations": lint.violations})
            continue
        lint_ok += 1
        try:
            projected = _phase_rows_for_output(row, parsed_solution)
        except (TypeError, ValueError) as exc:
            fatal_failures.append({"gate": "saturation_projection", "sample_id": sample_id, "reason": str(exc)})
            evaluated_rows.append({**row, "solution": parsed_solution, "format_ok": True, "lint_ok": True, "violations": []})
            continue
        phase_rows.extend(projected)
        evaluated_rows.append({**row, "solution": parsed_solution, "format_ok": True, "lint_ok": True, "violations": []})

    saturation_gate = evaluate_saturation_policy_gate(
        {"ok": True, "input_count": len(rows), "rows": phase_rows, "excluded_counts": {}},
        source_type="eval",
    )
    for failure in saturation_gate.get("fatal_failures") or []:
        fatal_failures.append(failure)

    ok = not fatal_failures
    report = {
        "ok": ok,
        "next_phase_allowed": ok,
        "requirements_covered": list(REQUIREMENTS_COVERED) if ok else [],
        "gates": {
            "phase19_export": {"ok": True, "data": phase19},
            "parse_protocol": {"ok": parse_ok == len(rows), "passed": parse_ok, "total": len(rows)},
            "hard_constraint_lint": {"ok": lint_ok == len(rows), "passed": lint_ok, "total": len(rows)},
            "saturation_policy": {"ok": saturation_gate.get("ok") is True, "report": saturation_gate},
        },
        "fatal_failures": fatal_failures,
        "warnings": [],
        "reports": {
            "eval_prompts": str(EVAL_PROMPTS_PATH),
            "eval_outputs": str(outputs_path),
            "eval_report": str(display_report_path),
        },
        "artifacts": {
            "run_root": str(run_root),
            "merged_hf": str(run_root / "merged_hf"),
            "gen_cache": str(EVAL_CACHE_DIR),
            "eval_outputs": str(outputs_path),
        },
        "counts": {"samples": len(rows), "phase_rows": len(phase_rows)},
        "advisory": {"teacher_mae": _teacher_mae(evaluated_rows)},
        "per_sample": evaluated_rows,
    }
    if write_path is not None:
        write_phase20_eval_report(report, write_path)
    return report


def write_phase20_eval_report(report: dict[str, Any], report_path: str | Path = EVAL_REPORT_PATH) -> dict[str, Any]:
    return _write_json(report_path, report)


def validate_phase20_eval_report(
    *,
    report_path: str | Path = EVAL_REPORT_PATH,
    run_root: str | Path = DEFAULT_RUN_ROOT,
) -> dict[str, Any]:
    report_path = Path(report_path)
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return {"ok": False, "next_phase_allowed": False, "requirements_covered": [], "fatal_failures": [{"gate": "report_json", "reason": str(exc)}], "report_path": str(report_path)}
    if not isinstance(report, dict):
        return {"ok": False, "next_phase_allowed": False, "requirements_covered": [], "fatal_failures": [{"gate": "report_json", "reason": "report must be an object"}], "report_path": str(report_path)}

    failures = list(report.get("fatal_failures", [])) if isinstance(report.get("fatal_failures"), list) else [{"gate": "fatal_failures", "reason": "fatal_failures must be a list"}]
    phase19 = _phase19_gate(Path(run_root))
    if phase19.get("ok") is not True or phase19.get("next_phase_allowed") is not True:
        failures.append({"gate": "phase19_export", "reason": "Phase 19 export report is not accepted"})
    if report.get("ok") is not True or report.get("next_phase_allowed") is not True:
        failures.append({"gate": "report_green", "reason": "Phase 20 eval report is not green"})
    covered = report.get("requirements_covered", [])
    if not isinstance(covered, list) or "EVAL-01" not in {str(item) for item in covered}:
        failures.append({"gate": "requirements_covered", "reason": "EVAL-01 coverage missing"})
    gates = report.get("gates") if isinstance(report.get("gates"), dict) else {}
    for gate_name in ("phase19_export", "parse_protocol", "hard_constraint_lint", "saturation_policy"):
        if (gates.get(gate_name) or {}).get("ok") is not True:
            failures.append({"gate": gate_name, "reason": f"{gate_name} gate is not green"})
    out = dict(report)
    out.update({
        "ok": not failures,
        "next_phase_allowed": not failures,
        "requirements_covered": list(REQUIREMENTS_COVERED) if not failures else [],
        "fatal_failures": failures,
        "report_path": str(report_path),
    })
    return out


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build and validate Phase 20 v4.2 EVAL-01 evidence")
    sub = parser.add_subparsers(dest="command", required=True)

    build = sub.add_parser("build-prompts")
    build.add_argument("--run-root", type=Path, default=DEFAULT_RUN_ROOT)
    build.add_argument("--labeled", type=Path, default=DEFAULT_LABELED_PATH)
    build.add_argument("--split-index", type=Path, action="append", default=[])
    build.add_argument("--out", type=Path, default=EVAL_PROMPTS_PATH)
    build.add_argument("--manifest", type=Path, default=EVAL_PROMPT_MANIFEST_PATH)

    normalize = sub.add_parser("normalize-outputs")
    normalize.add_argument("--prompts", type=Path, default=EVAL_PROMPTS_PATH)
    normalize.add_argument("--cache-dir", type=Path, default=EVAL_CACHE_DIR)
    normalize.add_argument("--out", type=Path, default=EVAL_OUTPUTS_PATH)

    evaluate = sub.add_parser("evaluate")
    evaluate.add_argument("--run-root", type=Path, default=DEFAULT_RUN_ROOT)
    evaluate.add_argument("--outputs", type=Path, default=EVAL_OUTPUTS_PATH)
    evaluate.add_argument("--report", type=Path, default=EVAL_REPORT_PATH)

    validate_report = sub.add_parser("validate-report")
    validate_report.add_argument("--run-root", type=Path, default=DEFAULT_RUN_ROOT)
    validate_report.add_argument("--report", type=Path, default=EVAL_REPORT_PATH)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "build-prompts":
        split_indexes = tuple(args.split_index) if args.split_index else DEFAULT_SPLIT_INDEXES
        rows = build_phase20_eval_prompts(labeled_path=args.labeled, split_indexes=split_indexes, out_path=args.out, manifest_path=args.manifest)
        result = {"ok": True, "rows": len(rows), "out": str(args.out), "manifest": str(args.manifest)}
    elif args.command == "normalize-outputs":
        rows = load_phase20_generated_outputs(prompts_path=args.prompts, cache_dir=args.cache_dir, out_path=args.out)
        result = {"ok": True, "rows": len(rows), "out": str(args.out)}
    elif args.command == "evaluate":
        result = evaluate_phase20_outputs(outputs_path=args.outputs, run_root=args.run_root, report_path=args.report)
    elif args.command == "validate-report":
        result = validate_phase20_eval_report(report_path=args.report, run_root=args.run_root)
    else:  # pragma: no cover
        raise AssertionError(args.command)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False))
    return 0 if result.get("ok") is True else 1


if __name__ == "__main__":
    sys.exit(main())
