"""OOD gap aggregator: same-distribution metric minus OOD metric for one backend.

Positive gap => OOD degradation. Used by `compute_metrics.py` after per-sample
rows are computed; never operates on raw cache files.
"""

from __future__ import annotations

import math
from typing import Any


def _agg(rows: list[dict], metric_key: str) -> float:
    if not rows:
        return float("nan")
    if metric_key in ("lint_ok", "exact_match"):
        return sum(1 for r in rows if r.get(metric_key)) / len(rows)
    if metric_key == "mae":
        vals = [r["mae"] for r in rows if r.get("mae") is not None]
        return sum(vals) / len(vals) if vals else float("nan")
    raise ValueError(f"unsupported metric_key: {metric_key}")


def compute_ood_gap(per_sample: list[dict], backend: str, metric_key: str) -> dict[str, Any]:
    """Aggregate per-sample rows into id/ood splits for one backend.

    Returns
    -------
    {"backend": str, "metric": str, "id": float, "ood": float, "gap": float}
        gap = id - ood. NaN propagates if either split is empty / all-None.
    """
    rows = [r for r in per_sample if r.get("backend") == backend]
    id_rows = [r for r in rows if r.get("split_hint") == "id"]
    ood_rows = [r for r in rows if r.get("split_hint") == "ood"]
    id_v = _agg(id_rows, metric_key)
    ood_v = _agg(ood_rows, metric_key)
    if math.isnan(id_v) or math.isnan(ood_v):
        gap = float("nan")
    else:
        gap = id_v - ood_v
    return {"backend": backend, "metric": metric_key,
            "id": id_v, "ood": ood_v, "gap": gap}
