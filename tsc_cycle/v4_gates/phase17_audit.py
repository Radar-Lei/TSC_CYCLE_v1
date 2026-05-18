"""Phase 17 offline saturation audit, policy gate, and prompt protocol guard."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any

from tsc_cycle.prompt_builder import build_user_prompt

from tsc_cycle.v4_gates.saturation_policy import (
    BAND_ALLOWED_MAX,
    BAND_HIGH_NOT_MAX,
    BAND_INTERPOLATED,
    BAND_NEAR_MIN,
    PHASE12_MANIFEST_PATH,
    PHASE12_PER_SAMPLE_PATH,
    DATASET_PATH,
    SPLIT_DIR,
    compute_saturation_audit,
    project_dataset_phase_decisions,
    project_replay_phase_decisions,
)

PROJECT_ROOT = Path("/home/samuel/TSC_CYCLE")
ARTIFACT_ROOT = PROJECT_ROOT / "artifacts" / "v4" / "phase17"
AUDIT_REPORT_PATH = ARTIFACT_ROOT / "saturation_audit_report.json"
POLICY_GATE_PATH = ARTIFACT_ROOT / "saturation_policy_gate.json"
PROMPT_PROTOCOL_REPORT_PATH = ARTIFACT_ROOT / "prompt_protocol_report.json"
FROZEN_V1_ROOT = PROJECT_ROOT / "runs" / "20260507T032419Z"
REQUIREMENTS_COVERED = ["AUDIT-01", "AUDIT-02", "POLICY-01", "POLICY-02", "POLICY-03"]
DEFAULT_THRESHOLDS = {
    "sat_lt_0.2_max_green_rate": 0.0,
    "sat_0.2_0.6_max_green_rate": 0.02,
    "sat_0.6_1.0_max_green_rate": 0.10,
    "malformed_row_rate": 0.0,
    "missing_output_rate": 0.0,
}
BAND_THRESHOLD_KEYS = {
    BAND_NEAR_MIN: "sat_lt_0.2_max_green_rate",
    BAND_INTERPOLATED: "sat_0.2_0.6_max_green_rate",
    BAND_HIGH_NOT_MAX: "sat_0.6_1.0_max_green_rate",
}
FORBIDDEN_POLICY_PATTERNS = (
    re.compile(r"\b(?:pred_)?sat(?:uration)?\s*(?:<|＜|≤|<=|小于|低于|低於)\s*0\.2", re.IGNORECASE),
    re.compile(r"0\.2\s*(?:<=|≤|<|＜)\s*(?:pred_)?sat(?:uration)?\s*(?:<|＜|≤|<=|小于|低于|低於)\s*0\.6", re.IGNORECASE),
    re.compile(r"0\.6\s*(?:<=|≤|<|＜)\s*(?:pred_)?sat(?:uration)?\s*(?:<|＜|≤|<=|小于|低于|低於)\s*1\.0", re.IGNORECASE),
    re.compile(r"\b(?:pred_)?sat(?:uration)?\s*(?:>=|≥|>|大于等于|不小于|不低于|達到|达到)\s*1\.0", re.IGNORECASE),
    re.compile(r"\bsat_(?:lt_0\.2|0\.2_0\.6|0\.6_1\.0|ge_1\.0)", re.IGNORECASE),
    re.compile(r"饱和度.*(?:最小绿灯|最大绿灯|接近最小|插值|达到最大)"),
    re.compile(r"飽和度.*(?:最小綠燈|最大綠燈|接近最小|插值|達到最大)"),
    re.compile(r"pred_saturation\s*(?:小于|低于|低於).*?(?:最小绿灯|最大绿灯|最小綠燈|最大綠燈|接近最小|插值|达到最大|達到最大)", re.IGNORECASE),
)
PROMPT_SURFACE_PATHS = [
    PROJECT_ROOT / "tsc_cycle" / "prompt_builder.py",
    PROJECT_ROOT / "tsc_cycle" / "v4_gates" / "phase12_reality_test.py",
    PROJECT_ROOT / "tsc_cycle" / "v4_gates" / "phase12_log_render.py",
    PROJECT_ROOT / "tsc_cycle" / "eval" / "run_eval.py",
    PROJECT_ROOT / "tsc_cycle" / "eval" / "generate_hf.py",
    PROJECT_ROOT / "tsc_cycle" / "eval" / "generate_gguf.py",
    PROJECT_ROOT / "tsc_cycle" / "eval" / "parity.py",
    PROJECT_ROOT / "tsc_cycle" / "teacher" / "labeler.py",
    PROJECT_ROOT / "tsc_cycle" / "student" / "train.py",
    PROJECT_ROOT / "tsc_cycle" / "student" / "dataset.py",
    PROJECT_ROOT / "tsc_cycle" / "student" / "parity_hf.py",
    PROJECT_ROOT / "tsc_cycle" / "student" / "parity_gguf.py",
]
FIXTURE_PREDICTION_INPUT = {
    "prediction": {
        "as_of": "2026-05-18T00:00:00Z",
        "phase_waits": [
            {"phase_id": 1, "pred_wait": 1.0, "pred_saturation": 0.05, "min_green": 20, "max_green": 45, "capacity": 30},
            {"phase_id": 2, "pred_wait": 12.0, "pred_saturation": 0.75, "min_green": 25, "max_green": 60, "capacity": 40},
        ],
    }
}
EXPECTED_V4_PROMPT = build_user_prompt(FIXTURE_PREDICTION_INPUT)
EXPECTED_V4_PROMPT_SHA256 = hashlib.sha256(EXPECTED_V4_PROMPT.encode("utf-8")).hexdigest()


def _is_under(path: Path, root: Path) -> bool:
    candidate = path.expanduser().resolve(strict=False)
    root = root.expanduser().resolve(strict=False)
    return candidate == root or root in candidate.parents


def reject_unsafe_phase17_output_path(path: str | Path) -> Path:
    candidate = Path(path).expanduser().resolve(strict=False)
    artifact_root = ARTIFACT_ROOT.resolve(strict=False)
    if _is_under(candidate, FROZEN_V1_ROOT):
        raise ValueError(f"Phase 17 report output path is not allowed: {candidate}")
    if _is_under(candidate, artifact_root):
        return candidate
    raise ValueError(f"Phase 17 report output path is not allowed: {candidate}")


def _write_json(path: str | Path | None, payload: dict[str, Any]) -> None:
    if path is None:
        return
    safe_path = reject_unsafe_phase17_output_path(path)
    safe_path.parent.mkdir(parents=True, exist_ok=True)
    safe_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def sha256_file(path: str | Path) -> str:
    hasher = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    path = Path(path)
    with path.open("r", encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, start=1):
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"malformed JSONL at {path}:{line_no}: {exc.msg}") from exc
            if not isinstance(payload, dict):
                raise ValueError(f"JSONL row is not an object at {path}:{line_no}")
            rows.append(payload)
    return rows


def _finite_thresholds(thresholds: dict[str, Any] | None) -> tuple[dict[str, float], list[dict[str, str]]]:
    merged: dict[str, Any] = dict(DEFAULT_THRESHOLDS)
    if thresholds:
        merged.update(thresholds)
    failures: list[dict[str, str]] = []
    out: dict[str, float] = {}
    for key in DEFAULT_THRESHOLDS:
        try:
            value = float(merged[key])
        except (KeyError, TypeError, ValueError) as exc:
            failures.append({"gate": "threshold_config", "reason": f"{key} is missing or non-numeric"})
            continue
        if not math.isfinite(value) or value < 0.0 or value > 1.0:
            failures.append({"gate": "threshold_config", "reason": f"{key} must be finite between 0 and 1"})
            continue
        out[key] = value
    return out, failures


def _coerce_rows_or_audit(rows_or_audit: Any) -> tuple[dict[str, Any] | None, list[dict[str, str]]]:
    try:
        if isinstance(rows_or_audit, (str, Path)):
            return compute_saturation_audit(_read_jsonl(rows_or_audit)), []
        if isinstance(rows_or_audit, dict) and "bands" in rows_or_audit:
            return rows_or_audit, []
        if isinstance(rows_or_audit, dict) and "rows" in rows_or_audit:
            return compute_saturation_audit(list(rows_or_audit.get("rows") or []), excluded_counts=rows_or_audit.get("excluded_counts") or {}), []
        if isinstance(rows_or_audit, list):
            return compute_saturation_audit(rows_or_audit), []
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        return None, [{"gate": "malformed_evidence", "reason": str(exc)}]
    return None, [{"gate": "malformed_evidence", "reason": f"unsupported evidence type: {type(rows_or_audit).__name__}"}]


def _finite_rate_metric(audit: dict[str, Any], band: str) -> tuple[dict[str, Any] | None, str | None]:
    bands = audit.get("bands")
    if not isinstance(bands, dict) or band not in bands:
        return None, f"missing band statistics for {band}"
    metric = (bands[band] or {}).get("final_equals_max_when_unsaturated")
    if not isinstance(metric, dict):
        return None, f"missing final_equals_max_when_unsaturated metric for {band}"
    for field in ("count", "denominator", "rate"):
        if field not in metric:
            return None, f"missing {field} for {band}"
    try:
        count = int(metric["count"])
        denominator = int(metric["denominator"])
        rate = float(metric["rate"])
    except (TypeError, ValueError) as exc:
        return None, f"non-numeric metric for {band}: {exc}"
    if denominator < 0 or count < 0 or count > denominator or not math.isfinite(rate):
        return None, f"invalid denominator/count/rate for {band}"
    if denominator > 0 and abs((count / denominator) - rate) > 1e-12:
        return None, f"rate does not match count/denominator for {band}"
    return {"count": count, "denominator": denominator, "rate": rate}, None


def _missing_output_rate_metric(rows_or_audit: Any, audit: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    evidence = rows_or_audit if isinstance(rows_or_audit, dict) else {}
    excluded_counts = evidence.get("excluded_counts") if isinstance(evidence.get("excluded_counts"), dict) else audit.get("excluded_counts")
    if excluded_counts is None:
        excluded_counts = {}
    if not isinstance(excluded_counts, dict):
        return None, "excluded_counts must be an object"
    try:
        denominator = int(evidence.get("input_count", audit.get("total_rows", 0)))
        count = int(excluded_counts.get("missing_solution_or_input", 0))
    except (TypeError, ValueError) as exc:
        return None, f"non-numeric missing_output_rate metric: {exc}"
    if denominator < 0 or count < 0 or count > denominator:
        return None, "invalid missing_output_rate denominator/count"
    rate = count / denominator if denominator else 0.0
    return {"count": count, "denominator": denominator, "rate": rate}, None


def evaluate_saturation_policy_gate(
    rows_or_audit: Any,
    thresholds: dict[str, Any] | None = None,
    source_type: str = "data",
) -> dict[str, Any]:
    """Apply the reusable POLICY-02 low-saturation max-green threshold gate."""
    active_thresholds, fatal_failures = _finite_thresholds(thresholds)
    source = str(source_type or "unknown")
    audit, evidence_failures = _coerce_rows_or_audit(rows_or_audit)
    for failure in evidence_failures:
        fatal_failures.append({"gate": f"{source}_malformed_evidence", "reason": failure["reason"]})

    gates: dict[str, Any] = {}
    if audit is not None:
        for band, threshold_key in BAND_THRESHOLD_KEYS.items():
            metric, reason = _finite_rate_metric(audit, band)
            gate_name = f"{source}_{threshold_key}"
            if metric is None:
                gates[gate_name] = {"ok": False, "reason": reason}
                fatal_failures.append({"gate": f"{gate_name}_denominator", "reason": reason or "invalid denominator"})
                continue
            threshold = active_thresholds.get(threshold_key)
            ok = threshold is not None and metric["rate"] <= threshold
            gates[gate_name] = {"ok": ok, "threshold": threshold, **metric}
            if not ok:
                fatal_failures.append({
                    "gate": f"{source}_threshold_excess_{threshold_key}",
                    "reason": f"{metric['rate']} > {threshold}",
                })
        gates[f"{source}_{BAND_ALLOWED_MAX}"] = {"ok": True, "reason": "no max-green failure threshold; max-green is allowed for saturated rows"}
        metric, reason = _missing_output_rate_metric(rows_or_audit, audit)
        gate_name = f"{source}_missing_output_rate"
        threshold = active_thresholds.get("missing_output_rate")
        if metric is None:
            gates[gate_name] = {"ok": False, "reason": reason}
            fatal_failures.append({"gate": f"{gate_name}_denominator", "reason": reason or "invalid missing_output_rate denominator"})
        else:
            ok_missing = threshold is not None and metric["rate"] <= threshold
            gates[gate_name] = {"ok": ok_missing, "threshold": threshold, **metric}
            if not ok_missing:
                fatal_failures.append({
                    "gate": f"{source}_threshold_excess_missing_output_rate",
                    "reason": f"{metric['rate']} > {threshold}",
                })

    ok = not fatal_failures
    return {
        "ok": ok,
        "next_phase_allowed": ok,
        "source_type": source,
        "thresholds": active_thresholds,
        "gates": gates,
        "fatal_failures": fatal_failures,
        "warnings": [],
        "audit": audit,
        "requirements_covered": ["POLICY-02"],
    }


def _scan_forbidden_snippets(text: str, *, path: str) -> list[dict[str, str]]:
    normalised = unicodedata.normalize("NFKC", text)
    findings: list[dict[str, str]] = []
    for pattern in FORBIDDEN_POLICY_PATTERNS:
        for match in pattern.finditer(normalised):
            findings.append({"path": path, "snippet": match.group(0), "pattern": pattern.pattern})
    return findings


def _default_prompt_surfaces() -> dict[str, str]:
    surfaces: dict[str, str] = {}
    for path in PROMPT_SURFACE_PATHS:
        if path.exists():
            surfaces[str(path)] = path.read_text(encoding="utf-8")
    return surfaces


def evaluate_prompt_protocol_guard(
    *,
    prompt_text: str | None = None,
    prompt_surfaces: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Verify POLICY-03: v4 deployment prompt bytes are locked and policy text stays offline."""
    rendered = prompt_text if prompt_text is not None else build_user_prompt(FIXTURE_PREDICTION_INPUT)
    prompt_sha = hashlib.sha256(rendered.encode("utf-8")).hexdigest()
    fatal_failures: list[dict[str, str]] = []
    forbidden_present = _scan_forbidden_snippets(rendered, path="build_user_prompt")
    surfaces = prompt_surfaces if prompt_surfaces is not None else _default_prompt_surfaces()
    scanned_prompt_surfaces: list[dict[str, Any]] = []
    for path, text in sorted(surfaces.items()):
        found = _scan_forbidden_snippets(text, path=path)
        forbidden_present.extend(found)
        scanned_prompt_surfaces.append({
            "path": path,
            "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "forbidden_snippets_present": found,
        })
    if rendered != EXPECTED_V4_PROMPT or prompt_sha != EXPECTED_V4_PROMPT_SHA256:
        fatal_failures.append({"gate": "prompt_byte_for_byte", "reason": "rendered v4 prompt differs from locked fixture"})
    if forbidden_present:
        fatal_failures.append({"gate": "prompt_policy_leakage", "reason": "explicit saturation band policy text found in prompt surface"})
    ok = not fatal_failures
    return {
        "ok": ok,
        "next_phase_allowed": ok,
        "prompt_sha256": prompt_sha,
        "expected_prompt_sha256": EXPECTED_V4_PROMPT_SHA256,
        "prompt_text": rendered,
        "forbidden_snippets_present": forbidden_present,
        "scanned_prompt_surfaces": scanned_prompt_surfaces,
        "fatal_failures": fatal_failures,
        "warnings": [],
        "requirements_covered": ["POLICY-03"],
    }


def evaluate_phase17_audit(
    *,
    dataset_path: str | Path = DATASET_PATH,
    split_dir: str | Path = SPLIT_DIR,
    phase12_manifest_path: str | Path = PHASE12_MANIFEST_PATH,
    phase12_per_sample_path: str | Path = PHASE12_PER_SAMPLE_PATH,
    phase_decisions_jsonl: str | Path | None = None,
    out_path: str | Path | None = POLICY_GATE_PATH,
    audit_out_path: str | Path | None = AUDIT_REPORT_PATH,
    prompt_protocol_out_path: str | Path | None = PROMPT_PROTOCOL_REPORT_PATH,
    example_limit: int = 10,
    thresholds: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Evaluate Phase 17 evidence and write safe JSON reports.

    This task-1 shell intentionally delegates detailed threshold and prompt checks
    to later Phase 17 tasks while preserving the final fail-closed payload shape.
    """
    fatal_failures: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    input_hashes: dict[str, str] = {}
    projections: dict[str, Any] = {}
    rows: list[dict[str, Any]] = []
    excluded_counts: dict[str, int] = {}

    try:
        dataset_projection = project_dataset_phase_decisions(dataset_path, split_dir=split_dir)
        projections["dataset"] = dataset_projection
        rows.extend(dataset_projection.get("rows") or [])
        for key, value in (dataset_projection.get("excluded_counts") or {}).items():
            excluded_counts[key] = excluded_counts.get(key, 0) + int(value)
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        fatal_failures.append({"gate": "dataset_audit", "reason": str(exc)})

    try:
        replay_projection = project_replay_phase_decisions(phase12_manifest_path, phase12_per_sample_path)
        projections["replay"] = replay_projection
        rows.extend(replay_projection.get("rows") or [])
        for key, value in (replay_projection.get("excluded_counts") or {}).items():
            excluded_counts[key] = excluded_counts.get(key, 0) + int(value)
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        fatal_failures.append({"gate": "replay_audit", "reason": str(exc)})

    if phase_decisions_jsonl is not None:
        try:
            eval_rows = _read_jsonl(phase_decisions_jsonl)
            projections["eval"] = {"ok": True, "rows": eval_rows, "origin_artifact": "eval:phase-decisions"}
            rows.extend(eval_rows)
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            fatal_failures.append({"gate": "eval_malformed_evidence", "reason": str(exc)})

    audit = {
        "ok": False,
        "requirements_covered": ["AUDIT-01", "AUDIT-02", "POLICY-01"],
        "total_rows": 0,
        "included_rows": 0,
        "trivial_rows": 0,
        "excluded_counts": excluded_counts,
        "bands": {},
        "representative_examples": [],
    }
    if rows:
        try:
            audit = compute_saturation_audit(rows, example_limit=example_limit, excluded_counts=excluded_counts)
        except (ValueError, TypeError) as exc:
            fatal_failures.append({"gate": "audit_compute", "reason": str(exc)})

    threshold_reports: dict[str, Any] = {}
    if "dataset" in projections:
        threshold_reports["data"] = evaluate_saturation_policy_gate(projections["dataset"], thresholds=thresholds, source_type="data")
    if "replay" in projections:
        threshold_reports["replay"] = evaluate_saturation_policy_gate(projections["replay"], thresholds=thresholds, source_type="replay")
    if "eval" in projections:
        threshold_reports["eval"] = evaluate_saturation_policy_gate(projections["eval"], thresholds=thresholds, source_type="eval")
    for threshold_report in threshold_reports.values():
        fatal_failures.extend(threshold_report.get("fatal_failures") or [])

    prompt_protocol = evaluate_prompt_protocol_guard()
    fatal_failures.extend(prompt_protocol.get("fatal_failures") or [])

    for label, path in {
        "dataset": dataset_path,
        "phase12_manifest": phase12_manifest_path,
        "phase12_per_sample": phase12_per_sample_path,
    }.items():
        path_obj = Path(path)
        if path_obj.exists():
            input_hashes[label] = sha256_file(path_obj)

    ok = not fatal_failures and bool(audit.get("ok", True))
    policy_gate = {
        "ok": ok,
        "next_phase_allowed": ok,
        "requirements_covered": list(REQUIREMENTS_COVERED),
        "thresholds": _finite_thresholds(thresholds)[0],
        "gates": {
            "dataset_audit": {"ok": "dataset" in projections},
            "replay_audit": {"ok": "replay" in projections},
            "eval_audit": {"ok": phase_decisions_jsonl is None or "eval" in projections},
            "audit_compute": {"ok": bool(audit.get("ok", False))},
            "policy_thresholds": threshold_reports,
            "prompt_protocol": {"ok": prompt_protocol.get("ok") is True},
        },
        "fatal_failures": fatal_failures,
        "warnings": warnings,
        "reports": {
            "audit": str(audit_out_path) if audit_out_path is not None else str(AUDIT_REPORT_PATH),
            "policy_gate": str(out_path) if out_path is not None else str(POLICY_GATE_PATH),
            "prompt_protocol": str(prompt_protocol_out_path) if prompt_protocol_out_path is not None else str(PROMPT_PROTOCOL_REPORT_PATH),
        },
        "counts": {
            "total_rows": audit.get("total_rows", 0),
            "included_rows": audit.get("included_rows", 0),
            "trivial_rows": audit.get("trivial_rows", 0),
            "excluded_counts": audit.get("excluded_counts", {}),
        },
        "audit": audit,
        "policy_gate": threshold_reports,
        "prompt_protocol": prompt_protocol,
        "input_hashes": input_hashes,
    }

    _write_json(audit_out_path, audit)
    _write_json(prompt_protocol_out_path, prompt_protocol)
    _write_json(out_path, policy_gate)
    return policy_gate


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate Phase 17 saturation audit and policy gate evidence")
    parser.add_argument("--dataset", type=Path, default=DATASET_PATH)
    parser.add_argument("--split-dir", type=Path, default=SPLIT_DIR)
    parser.add_argument("--phase12-manifest", type=Path, default=PHASE12_MANIFEST_PATH)
    parser.add_argument("--phase12-per-sample", type=Path, default=PHASE12_PER_SAMPLE_PATH)
    parser.add_argument("--phase-decisions-jsonl", "--eval-outputs", dest="phase_decisions_jsonl", type=Path, default=None)
    parser.add_argument("--artifact-root", type=Path, default=ARTIFACT_ROOT)
    parser.add_argument("--out", type=Path, default=POLICY_GATE_PATH)
    parser.add_argument("--audit-out", type=Path, default=AUDIT_REPORT_PATH)
    parser.add_argument("--prompt-protocol-out", type=Path, default=PROMPT_PROTOCOL_REPORT_PATH)
    parser.add_argument("--example-limit", type=int, default=10)
    parser.add_argument("--sat-lt-0-2-max-green-rate", type=float, default=DEFAULT_THRESHOLDS["sat_lt_0.2_max_green_rate"])
    parser.add_argument("--sat-0-2-0-6-max-green-rate", type=float, default=DEFAULT_THRESHOLDS["sat_0.2_0.6_max_green_rate"])
    parser.add_argument("--sat-0-6-1-0-max-green-rate", type=float, default=DEFAULT_THRESHOLDS["sat_0.6_1.0_max_green_rate"])
    parser.add_argument("--malformed-row-rate", type=float, default=DEFAULT_THRESHOLDS["malformed_row_rate"])
    parser.add_argument("--missing-output-rate", type=float, default=DEFAULT_THRESHOLDS["missing_output_rate"])
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    global ARTIFACT_ROOT
    ARTIFACT_ROOT = Path(args.artifact_root)
    thresholds = {
        "sat_lt_0.2_max_green_rate": args.sat_lt_0_2_max_green_rate,
        "sat_0.2_0.6_max_green_rate": args.sat_0_2_0_6_max_green_rate,
        "sat_0.6_1.0_max_green_rate": args.sat_0_6_1_0_max_green_rate,
        "malformed_row_rate": args.malformed_row_rate,
        "missing_output_rate": args.missing_output_rate,
    }
    report = evaluate_phase17_audit(
        dataset_path=args.dataset,
        split_dir=args.split_dir,
        phase12_manifest_path=args.phase12_manifest,
        phase12_per_sample_path=args.phase12_per_sample,
        phase_decisions_jsonl=args.phase_decisions_jsonl,
        out_path=args.out,
        audit_out_path=args.audit_out,
        prompt_protocol_out_path=args.prompt_protocol_out,
        example_limit=args.example_limit,
        thresholds=thresholds,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False))
    return 0 if report.get("ok") is True else 1


if __name__ == "__main__":
    sys.exit(main())
