"""Deterministic Phase 11 statistics helpers.

The helpers in this module are intentionally stdlib-only and fail closed for
empty, missing, or non-finite decision-critical inputs.
"""

from __future__ import annotations

import math
import random
from collections.abc import Iterable, Sequence
from typing import Any


def _as_finite_float(value: Any, *, label: str) -> float:
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    try:
        out = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be numeric and finite; got {value!r}") from exc
    if not math.isfinite(out):
        raise ValueError(f"{label} must be numeric and finite; got {value!r}")
    return out


def _validate_resample_count(n: int) -> int:
    try:
        out = int(n)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"bootstrap resample count must be an integer; got {n!r}") from exc
    if out <= 0:
        raise ValueError(f"bootstrap resample count must be positive; got {out}")
    return out


def _percentile(sorted_values: Sequence[float], q: float) -> float:
    if not sorted_values:
        raise ValueError("percentile requires non-empty values")
    if not 0.0 <= q <= 1.0:
        raise ValueError(f"percentile q must be in [0, 1]; got {q!r}")
    # Nearest-rank percentile. This keeps tiny fixture behavior intuitive and is
    # deterministic for the audit trail.
    idx = max(0, min(len(sorted_values) - 1, math.ceil(q * len(sorted_values)) - 1))
    return float(sorted_values[idx])


def bootstrap_mean_ci(
    values: Iterable[Any],
    *,
    seed: int = 42,
    n: int = 2000,
    alpha: float = 0.05,
) -> dict[str, Any]:
    """Return a deterministic percentile bootstrap CI for the mean.

    Raises ``ValueError`` for empty values, non-finite values, invalid ``alpha``,
    or invalid resample counts so downstream gates fail closed.
    """
    vals = [_as_finite_float(v, label="bootstrap value") for v in values]
    if not vals:
        raise ValueError("bootstrap_mean_ci requires non-empty numeric values")
    n_resamples = _validate_resample_count(n)
    alpha_f = _as_finite_float(alpha, label="alpha")
    if not 0.0 < alpha_f < 1.0:
        raise ValueError(f"alpha must be in (0, 1); got {alpha!r}")

    rng = random.Random(seed)
    reps: list[float] = []
    size = len(vals)
    for _ in range(n_resamples):
        total = 0.0
        for _idx in range(size):
            total += vals[rng.randrange(size)]
        reps.append(total / size)
    reps.sort()

    return {
        "mean": sum(vals) / size,
        "lower": _percentile(reps, alpha_f / 2.0),
        "upper": _percentile(reps, 1.0 - alpha_f / 2.0),
        "confidence": 1.0 - alpha_f,
        "seed": int(seed),
        "n_resamples": n_resamples,
        "n": size,
    }


def _row_value(row: Any, *, value_key: str | None, label: str) -> float:
    if value_key is None:
        return _as_finite_float(row, label=label)
    if not isinstance(row, dict):
        raise ValueError(f"{label} row must be a dict when value_key is used")
    if value_key not in row:
        raise ValueError(f"{label} row missing value key {value_key!r}")
    return _as_finite_float(row[value_key], label=f"{label}.{value_key}")


def _sample_id(row: Any, *, sample_id_key: str, label: str) -> str:
    if not isinstance(row, dict):
        raise ValueError(f"{label} row must be a dict with sample IDs")
    sid = row.get(sample_id_key)
    if sid is None or str(sid) == "":
        raise ValueError(f"{label} row missing sample id key {sample_id_key!r}")
    return str(sid)


def paired_delta_ci(
    left: Sequence[Any],
    right: Sequence[Any],
    *,
    value_key: str | None = None,
    sample_id_key: str = "sample_id",
    seed: int = 42,
    n: int = 2000,
    alpha: float = 0.05,
) -> dict[str, Any]:
    """Bootstrap a paired ``left - right`` mean-delta confidence interval.

    ``left`` and ``right`` must contain the same sample IDs. Ordering is ignored
    by sorting on ``sample_id_key`` before deltas are computed.
    """
    if not left or not right:
        raise ValueError("paired_delta_ci requires non-empty paired samples")
    if len(left) != len(right):
        raise ValueError(f"paired_delta_ci sample counts differ: {len(left)} != {len(right)}")

    left_by_id = {_sample_id(row, sample_id_key=sample_id_key, label="left"): row for row in left}
    right_by_id = {_sample_id(row, sample_id_key=sample_id_key, label="right"): row for row in right}
    if len(left_by_id) != len(left) or len(right_by_id) != len(right):
        raise ValueError("paired_delta_ci requires unique sample IDs")
    if set(left_by_id) != set(right_by_id):
        missing_left = sorted(set(right_by_id).difference(left_by_id))[:5]
        missing_right = sorted(set(left_by_id).difference(right_by_id))[:5]
        raise ValueError(
            "paired_delta_ci sample IDs do not align; "
            f"missing_left={missing_left} missing_right={missing_right}"
        )

    deltas = []
    for sid in sorted(left_by_id):
        l_val = _row_value(left_by_id[sid], value_key=value_key, label=f"left[{sid}]")
        r_val = _row_value(right_by_id[sid], value_key=value_key, label=f"right[{sid}]")
        deltas.append(l_val - r_val)
    ci = bootstrap_mean_ci(deltas, seed=seed, n=n, alpha=alpha)
    ci["sample_ids"] = sorted(left_by_id)
    return ci


def tail_metrics(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Return p99/max tail metrics for sample MAE and per-phase abs errors."""
    sample_mae: list[float] = []
    per_phase: list[float] = []
    for idx, row in enumerate(rows):
        mae = row.get("mae")
        if mae is not None:
            sample_mae.append(_as_finite_float(mae, label=f"rows[{idx}].mae"))
        errs = row.get("per_phase_abs_err") or []
        if not isinstance(errs, list):
            raise ValueError(f"rows[{idx}].per_phase_abs_err must be a list")
        for j, err in enumerate(errs):
            per_phase.append(_as_finite_float(err, label=f"rows[{idx}].per_phase_abs_err[{j}]"))

    if not sample_mae:
        raise ValueError("tail_metrics requires at least one finite mae value")
    if not per_phase:
        raise ValueError("tail_metrics requires at least one finite per-phase absolute error")

    sample_sorted = sorted(sample_mae)
    phase_sorted = sorted(per_phase)
    return {
        "sample_mae_p99": _percentile(sample_sorted, 0.99),
        "sample_mae_max": float(sample_sorted[-1]),
        "per_phase_abs_err_p99": _percentile(phase_sorted, 0.99),
        "per_phase_abs_err_max": float(phase_sorted[-1]),
        "n_mae": len(sample_mae),
        "n_per_phase_abs_err": len(per_phase),
    }
