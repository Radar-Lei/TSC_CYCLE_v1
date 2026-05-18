"""Canonical Phase 17 saturation policy helpers.

The saturation policy is an offline audit/data/evaluation gate. It is not part
of the deployment prompt. Forced per-phase ranges (``min_green == max_green``)
are classified separately because max-green is unavoidable for those rows and
must not be counted as low-saturation policy failures.
"""

from __future__ import annotations

import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

from tsc_cycle.constraint_lint import validate

BAND_NEAR_MIN = "sat_lt_0.2_near_min"
BAND_INTERPOLATED = "sat_0.2_0.6_interpolated"
BAND_HIGH_NOT_MAX = "sat_0.6_1.0_high_not_max"
BAND_ALLOWED_MAX = "sat_ge_1.0_allowed_max"
SATURATION_BANDS = [BAND_NEAR_MIN, BAND_INTERPOLATED, BAND_HIGH_NOT_MAX, BAND_ALLOWED_MAX]

VIOLATION_NONE = "none"
VIOLATION_UNSATURATED_MAX_GREEN = "final_equals_max_when_unsaturated"
VIOLATION_ALLOWED_SATURATED_MAX_GREEN = "allowed_saturated_max_green"
VIOLATION_FORCED_TRIVIAL_RANGE = "forced_trivial_range"

REQUIREMENTS_COVERED = ["AUDIT-01", "AUDIT-02", "POLICY-01"]

PROJECT_ROOT = Path("/home/samuel/TSC_CYCLE")
DATASET_PATH = PROJECT_ROOT / "data" / "v4" / "phase8" / "labeled_merged.jsonl"
SPLIT_DIR = PROJECT_ROOT / "data" / "v4" / "phase8" / "splits"
PHASE12_MANIFEST_PATH = PROJECT_ROOT / "artifacts" / "v4" / "phase12" / "manifest.json"
PHASE12_PER_SAMPLE_PATH = PROJECT_ROOT / "artifacts" / "v4" / "phase12" / "per_sample.jsonl"



def _finite_float(value: Any, *, field: str = "value") -> float:
    try:
        out = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be finite numeric, got {value!r}") from exc
    if not math.isfinite(out):
        raise ValueError(f"{field} must be finite numeric, got {value!r}")
    return out


def _finite_int(value: Any, *, field: str, strict_json_int: bool = True) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field} must be an integer, got bool")
    if isinstance(value, int):
        return value
    if not strict_json_int and isinstance(value, float) and math.isfinite(value) and value.is_integer():
        return int(value)
    raise ValueError(f"{field} must be an integer, got {value!r}")


def classify_saturation_band(sat: Any) -> str:
    """Classify a finite saturation value into the POLICY-01 half-open band."""
    sat_f = _finite_float(sat, field="pred_saturation")
    if sat_f < 0.2:
        return BAND_NEAR_MIN
    if sat_f < 0.6:
        return BAND_INTERPOLATED
    if sat_f < 1.0:
        return BAND_HIGH_NOT_MAX
    return BAND_ALLOWED_MAX


def is_trivial_phase_range(row: dict[str, Any]) -> bool:
    """Return true when a phase has no choice because min_green equals max_green."""
    min_green = _finite_int(row.get("min_green"), field="min_green")
    max_green = _finite_int(row.get("max_green"), field="max_green")
    return min_green == max_green


def classify_violation(row: dict[str, Any]) -> str:
    """Classify one projected per-phase decision into a stable audit category."""
    band = classify_saturation_band(row.get("pred_saturation"))
    min_green = _finite_int(row.get("min_green"), field="min_green")
    max_green = _finite_int(row.get("max_green"), field="max_green")
    final_green = _finite_int(row.get("final_green"), field="final_green")
    if min_green == max_green:
        return VIOLATION_FORCED_TRIVIAL_RANGE
    if final_green == max_green and band == BAND_ALLOWED_MAX:
        return VIOLATION_ALLOWED_SATURATED_MAX_GREEN
    if final_green == max_green and band != BAND_ALLOWED_MAX:
        return VIOLATION_UNSATURATED_MAX_GREEN
    return VIOLATION_NONE


def _read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    path = Path(path)
    with path.open("r", encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, start=1):
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"malformed JSONL at {path}:{line_no}: {exc.msg}") from exc
            if not isinstance(obj, dict):
                raise ValueError(f"JSONL row is not an object at {path}:{line_no}")
            rows.append(obj)
    return rows


def _load_split_index(split_dir: str | Path | None) -> dict[str, dict[str, Any]]:
    if split_dir is None:
        return {}
    root = Path(split_dir)
    if not root.exists():
        return {}
    by_sample: dict[str, dict[str, Any]] = {}
    for path in sorted(root.glob("*.index.jsonl")):
        for row in _read_jsonl(path):
            sample_id = str(row.get("sample_id") or "")
            if sample_id:
                by_sample[sample_id] = row
    return by_sample


def _solution_from_dataset_record(record: dict[str, Any]) -> dict[str, Any] | None:
    result = record.get("result")
    if isinstance(result, dict) and isinstance(result.get("solution"), dict):
        return result["solution"]
    if isinstance(record.get("solution"), dict):
        return record["solution"]
    parsed = record.get("parsed")
    if isinstance(parsed, dict):
        return parsed
    return None


def _project_record_phases(
    *,
    sample_id: str,
    prediction_input: dict[str, Any],
    solution: dict[str, Any],
    split: str,
    source: str,
    source_origin: str,
    origin_artifact: str,
) -> list[dict[str, Any]]:
    waits = prediction_input.get("prediction", {}).get("phase_waits", [])
    if not isinstance(waits, list):
        raise ValueError(f"phase_waits is not a list for sample_id={sample_id}")
    rows: list[dict[str, Any]] = []
    for wait in waits:
        if not isinstance(wait, dict):
            raise ValueError(f"phase_waits entry is not an object for sample_id={sample_id}")
        phase_id = str(wait.get("phase_id"))
        row = {
            "origin_artifact": origin_artifact,
            "sample_id": sample_id,
            "phase_id": phase_id,
            "pred_saturation": _finite_float(wait.get("pred_saturation"), field="pred_saturation"),
            "min_green": _finite_int(wait.get("min_green"), field="min_green"),
            "max_green": _finite_int(wait.get("max_green"), field="max_green"),
            "final_green": _finite_int(solution.get(phase_id), field="final_green"),
            "split": split,
            "source": source,
            "source_origin": source_origin,
        }
        row["saturation_band"] = classify_saturation_band(row["pred_saturation"])
        row["trivial_range"] = is_trivial_phase_range(row)
        row["violation_category"] = classify_violation(row)
        rows.append(row)
    return rows


def project_dataset_phase_decisions(
    dataset_path: str | Path = DATASET_PATH,
    *,
    split_dir: str | Path | None = SPLIT_DIR,
) -> dict[str, Any]:
    """Project v4 labeled dataset rows into one audit row per phase decision."""
    dataset_path = Path(dataset_path)
    split_index = _load_split_index(split_dir)
    rows: list[dict[str, Any]] = []
    excluded_samples: list[dict[str, Any]] = []
    excluded_counts: Counter[str] = Counter()
    input_rows = _read_jsonl(dataset_path)
    for record_index, record in enumerate(input_rows, start=1):
        sample_id = str(record.get("sample_id") or record.get("input", {}).get("sample_id") or f"row-{record_index}")
        prediction_input = record.get("input")
        solution = _solution_from_dataset_record(record)
        if not isinstance(prediction_input, dict) or not isinstance(solution, dict):
            excluded_counts["missing_solution_or_input"] += 1
            excluded_samples.append({"sample_id": sample_id, "reason": "missing_solution_or_input"})
            continue
        lint = validate(prediction_input, solution)
        if not lint.ok:
            excluded_counts["hard_constraint_invalid"] += 1
            excluded_samples.append({"sample_id": sample_id, "reason": "hard_constraint_invalid", "violations": lint.violations})
            continue
        split_row = split_index.get(sample_id, {})
        split = str(split_row.get("split") or record.get("split") or record.get("split_hint") or "unknown")
        source = str(split_row.get("source") or record.get("source") or record.get("split_hint") or "unknown")
        source_origin = str(split_row.get("source_origin") or record.get("source_origin") or "unknown")
        rows.extend(
            _project_record_phases(
                sample_id=sample_id,
                prediction_input=prediction_input,
                solution=solution,
                split=split,
                source=source,
                source_origin=source_origin,
                origin_artifact=f"dataset:{dataset_path.name}",
            )
        )
    return {
        "ok": True,
        "origin_artifact": f"dataset:{dataset_path.name}",
        "input_count": len(input_rows),
        "phase_row_count": len(rows),
        "rows": rows,
        "excluded_counts": dict(excluded_counts),
        "excluded_samples": excluded_samples,
        "requirements_covered": ["AUDIT-01", "POLICY-01"],
    }


def project_replay_phase_decisions(
    manifest_path: str | Path = PHASE12_MANIFEST_PATH,
    per_sample_path: str | Path = PHASE12_PER_SAMPLE_PATH,
) -> dict[str, Any]:
    """Project Phase 12 manifest/per-sample structured evidence into phase rows."""
    manifest_path = Path(manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError(f"manifest JSON is not an object: {manifest_path}")
    records = manifest.get("records") or []
    if not isinstance(records, list):
        raise ValueError("manifest records is not a list")
    outputs = _read_jsonl(per_sample_path)
    record_ids = [str(record.get("sample_id") or "") for record in records if isinstance(record, dict)]
    output_ids = [str(output.get("sample_id") or "") for output in outputs]
    if len(records) != len(outputs):
        raise ValueError(f"replay input/output count mismatch: {len(records)} != {len(outputs)}")
    if record_ids != output_ids:
        raise ValueError("replay output sample_id order does not match manifest records")

    rows: list[dict[str, Any]] = []
    excluded_samples: list[dict[str, Any]] = []
    excluded_counts: Counter[str] = Counter()
    for record, output in zip(records, outputs, strict=True):
        if not isinstance(record, dict):
            raise ValueError("manifest record is not an object")
        sample_id = str(record.get("sample_id") or "")
        prediction_input = record.get("input")
        solution = output.get("solution")
        if not isinstance(prediction_input, dict) or not isinstance(solution, dict):
            excluded_counts["missing_solution_or_input"] += 1
            excluded_samples.append({"sample_id": sample_id, "reason": "missing_solution_or_input"})
            continue
        lint = validate(prediction_input, solution)
        if not lint.ok:
            excluded_counts["hard_constraint_invalid"] += 1
            excluded_samples.append({"sample_id": sample_id, "reason": "hard_constraint_invalid", "violations": lint.violations})
            continue
        rows.extend(
            _project_record_phases(
                sample_id=sample_id,
                prediction_input=prediction_input,
                solution=solution,
                split=str(record.get("split") or record.get("split_hint") or "replay"),
                source=str(record.get("source") or output.get("backend") or "phase12_replay"),
                source_origin=str(record.get("source_origin") or output.get("backend") or "phase12_replay"),
                origin_artifact="replay:phase12",
            )
        )
    return {
        "ok": True,
        "origin_artifact": "replay:phase12",
        "input_count": len(records),
        "phase_row_count": len(rows),
        "rows": rows,
        "excluded_counts": dict(excluded_counts),
        "excluded_samples": excluded_samples,
        "requirements_covered": ["AUDIT-01", "AUDIT-02", "POLICY-01"],
    }


def _empty_slice() -> dict[str, Any]:
    return {
        "total_rows": 0,
        "included_rows": 0,
        "trivial_rows": 0,
        "low_saturation_rows": 0,
        "final_equals_max_when_unsaturated": {"count": 0, "rate": 0.0, "denominator": 0},
    }


def _add_to_slice(stats: dict[str, Any], row: dict[str, Any]) -> None:
    stats["total_rows"] += 1
    if row.get("trivial_range"):
        stats["trivial_rows"] += 1
        return
    stats["included_rows"] += 1
    if row.get("saturation_band") != BAND_ALLOWED_MAX:
        stats["low_saturation_rows"] += 1
        metric = stats["final_equals_max_when_unsaturated"]
        metric["denominator"] += 1
        if row.get("violation_category") == VIOLATION_UNSATURATED_MAX_GREEN:
            metric["count"] += 1
        metric["rate"] = metric["count"] / metric["denominator"] if metric["denominator"] else 0.0


def _normalise_audit_row(row: dict[str, Any]) -> dict[str, Any]:
    required = {
        "origin_artifact",
        "sample_id",
        "phase_id",
        "pred_saturation",
        "min_green",
        "max_green",
        "final_green",
        "split",
        "source",
    }
    missing = sorted(field for field in required if field not in row)
    if missing:
        raise ValueError(f"missing required audit row field(s): {', '.join(missing)}")
    out = dict(row)
    out["pred_saturation"] = _finite_float(out["pred_saturation"], field="pred_saturation")
    out["min_green"] = _finite_int(out["min_green"], field="min_green")
    out["max_green"] = _finite_int(out["max_green"], field="max_green")
    out["final_green"] = _finite_int(out["final_green"], field="final_green")

    computed_band = classify_saturation_band(out["pred_saturation"])
    computed_trivial = is_trivial_phase_range(out)
    computed_violation = classify_violation({**out, "saturation_band": computed_band})
    for field, computed in {
        "saturation_band": computed_band,
        "trivial_range": computed_trivial,
        "violation_category": computed_violation,
    }.items():
        if field in row and row[field] != computed:
            raise ValueError(f"inconsistent derived audit row field {field}")
        out[field] = computed
    return out


def compute_saturation_audit(rows: list[dict[str, Any]], *, example_limit: int = 10, excluded_counts: dict[str, int] | None = None) -> dict[str, Any]:
    """Compute band/split/source/origin audit statistics from projected rows."""
    normalised_rows = [_normalise_audit_row(row) for row in rows]
    bands = {band: _empty_slice() for band in SATURATION_BANDS}
    by_split: dict[str, dict[str, Any]] = {}
    by_source: dict[str, dict[str, Any]] = {}
    by_origin: dict[str, dict[str, Any]] = {}
    required_example_fields = [
        "origin_artifact",
        "sample_id",
        "phase_id",
        "pred_saturation",
        "saturation_band",
        "min_green",
        "max_green",
        "final_green",
        "split",
        "source",
        "violation_category",
    ]
    sorted_rows = sorted(normalised_rows, key=lambda r: (str(r.get("origin_artifact")), str(r.get("sample_id")), str(r.get("phase_id"))))
    violation_rows: list[dict[str, Any]] = []
    for row in sorted_rows:
        band = str(row["saturation_band"])
        _add_to_slice(bands.setdefault(band, _empty_slice()), row)
        _add_to_slice(by_split.setdefault(str(row.get("split") or "unknown"), _empty_slice()), row)
        _add_to_slice(by_source.setdefault(str(row.get("source") or "unknown"), _empty_slice()), row)
        _add_to_slice(by_origin.setdefault(str(row.get("origin_artifact") or "unknown"), _empty_slice()), row)
        if row.get("violation_category") == VIOLATION_UNSATURATED_MAX_GREEN:
            violation_rows.append(row)

    examples: list[dict[str, Any]] = []
    selected_keys: set[tuple[str, str, str]] = set()

    def add_example(row: dict[str, Any]) -> None:
        key = (str(row.get("origin_artifact")), str(row.get("sample_id")), str(row.get("phase_id")))
        if key in selected_keys or len(examples) >= example_limit:
            return
        selected_keys.add(key)
        examples.append({field: row.get(field) for field in required_example_fields})

    if example_limit > 0:
        seen_origins: set[str] = set()
        for row in violation_rows:
            origin = str(row.get("origin_artifact") or "unknown")
            if origin in seen_origins:
                continue
            add_example(row)
            seen_origins.add(origin)
        for row in violation_rows:
            add_example(row)
    return {
        "ok": True,
        "requirements_covered": list(REQUIREMENTS_COVERED),
        "total_rows": len(normalised_rows),
        "included_rows": sum(1 for row in normalised_rows if not row.get("trivial_range")),
        "trivial_rows": sum(1 for row in normalised_rows if row.get("trivial_range")),
        "excluded_counts": dict(excluded_counts or {}),
        "bands": bands,
        "by_split": by_split,
        "by_source": by_source,
        "by_origin": by_origin,
        "representative_examples": examples,
    }
