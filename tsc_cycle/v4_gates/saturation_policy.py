"""Canonical Phase 17 saturation policy helpers.

The saturation policy is an offline audit/data/evaluation gate. It is not part
of the deployment prompt. Forced per-phase ranges (``min_green == max_green``)
are classified separately because max-green is unavoidable for those rows and
must not be counted as low-saturation policy failures.
"""

from __future__ import annotations

import math
from typing import Any

BAND_NEAR_MIN = "sat_lt_0.2_near_min"
BAND_INTERPOLATED = "sat_0.2_0.6_interpolated"
BAND_HIGH_NOT_MAX = "sat_0.6_1.0_high_not_max"
BAND_ALLOWED_MAX = "sat_ge_1.0_allowed_max"
SATURATION_BANDS = [BAND_NEAR_MIN, BAND_INTERPOLATED, BAND_HIGH_NOT_MAX, BAND_ALLOWED_MAX]

VIOLATION_NONE = "none"
VIOLATION_UNSATURATED_MAX_GREEN = "final_equals_max_when_unsaturated"
VIOLATION_ALLOWED_SATURATED_MAX_GREEN = "allowed_saturated_max_green"
VIOLATION_FORCED_TRIVIAL_RANGE = "forced_trivial_range"

REQUIREMENTS_COVERED = ["POLICY-01"]


def _finite_float(value: Any, *, field: str = "value") -> float:
    try:
        out = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be finite numeric, got {value!r}") from exc
    if not math.isfinite(out):
        raise ValueError(f"{field} must be finite numeric, got {value!r}")
    return out


def _finite_int(value: Any, *, field: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field} must be an integer, got bool")
    if isinstance(value, int):
        return value
    if isinstance(value, float) and math.isfinite(value) and value.is_integer():
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
