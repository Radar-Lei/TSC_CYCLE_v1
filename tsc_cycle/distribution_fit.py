"""Extract empirical distribution from reality.log → data/dist_prior.json.

The log format is line-oriented:

  <ts>|INFO|type=prompt|crossing_id=<n>
  <multi-line prompt body containing 【cycle_predict_input_json】 ... 【/cycle_predict_input_json】>
  --------------------------------------------------------------------------------

We extract every embedded `prediction.phase_waits` and fit:
  - phase_count distribution
  - per-position min_green / max_green / capacity / pred_wait / pred_saturation marginals
  - phase_count → joint min/max range modes
"""

from __future__ import annotations

import json
import re
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

PROMPT_HEADER = re.compile(r"\|type=prompt\|")
JSON_OPEN = "【cycle_predict_input_json】"
JSON_CLOSE = "【/cycle_predict_input_json】"


def iter_prompts(log_path: Path):
    """Yield each (crossing_id, prediction_dict) embedded in reality.log."""
    text = log_path.read_text(encoding="utf-8", errors="replace")
    blocks = text.split("\n--------------------------------------------------------------------------------\n")
    for blk in blocks:
        if "type=prompt" not in blk:
            continue
        m = re.search(r"crossing_id=(\d+)", blk)
        crossing_id = int(m.group(1)) if m else -1
        i = blk.find(JSON_OPEN)
        if i < 0:
            continue
        i += len(JSON_OPEN)
        j = blk.find(JSON_CLOSE, i)
        if j < 0:
            continue
        try:
            data = json.loads(blk[i:j])
        except json.JSONDecodeError:
            continue
        yield crossing_id, data


def fit(log_path: Path) -> dict[str, Any]:
    """Return distribution prior dict suitable for sampling P2 inputs."""
    phase_counts: Counter[int] = Counter()
    per_position: dict[int, dict[str, list[float]]] = defaultdict(
        lambda: {"min_green": [], "max_green": [], "capacity": [],
                 "pred_wait": [], "pred_saturation": []}
    )
    range_modes: Counter[tuple[int, int]] = Counter()  # (min, max) tuples
    crossings: Counter[int] = Counter()
    n = 0

    for crossing_id, pred in iter_prompts(log_path):
        crossings[crossing_id] += 1
        waits = pred.get("prediction", {}).get("phase_waits", [])
        if not waits:
            continue
        n += 1
        phase_counts[len(waits)] += 1
        for idx, w in enumerate(waits):
            slot = per_position[idx]
            for k in ("min_green", "max_green", "capacity", "pred_wait", "pred_saturation"):
                v = w.get(k)
                if isinstance(v, (int, float)):
                    slot[k].append(float(v))
            range_modes[(int(w["min_green"]), int(w["max_green"]))] += 1

    def summarize(values: list[float]) -> dict[str, Any]:
        if not values:
            return {"n": 0}
        return {
            "n": len(values),
            "min": min(values),
            "max": max(values),
            "mean": statistics.fmean(values),
            "median": statistics.median(values),
            "stdev": statistics.pstdev(values) if len(values) > 1 else 0.0,
            "p05": _quantile(values, 0.05),
            "p25": _quantile(values, 0.25),
            "p50": _quantile(values, 0.50),
            "p75": _quantile(values, 0.75),
            "p95": _quantile(values, 0.95),
            "values_sample": sorted(set(values))[:50],  # bounded sample for sampling
        }

    out: dict[str, Any] = {
        "n_prompts": n,
        "n_crossings": len(crossings),
        "crossings": dict(sorted(crossings.items())),
        "phase_count_distribution": dict(sorted(phase_counts.items())),
        "per_position": {},
        "range_modes_top": [
            {"min_green": mn, "max_green": mx, "count": c}
            for (mn, mx), c in range_modes.most_common(50)
        ],
    }
    for pos, slots in sorted(per_position.items()):
        out["per_position"][str(pos)] = {k: summarize(v) for k, v in slots.items()}
    return out


def _quantile(sorted_values: list[float], q: float) -> float:
    s = sorted(sorted_values)
    if not s:
        return float("nan")
    if len(s) == 1:
        return s[0]
    pos = q * (len(s) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(s) - 1)
    frac = pos - lo
    return s[lo] * (1 - frac) + s[hi] * frac


def main() -> int:
    log = Path("reality.log")
    if not log.exists():
        raise SystemExit("reality.log not found")
    prior = fit(log)
    out_dir = Path("data")
    out_dir.mkdir(exist_ok=True)
    out = out_dir / "dist_prior.json"
    out.write_text(json.dumps(prior, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {out}: n_prompts={prior['n_prompts']}, n_crossings={prior['n_crossings']}")
    print(f"phase_count_distribution: {prior['phase_count_distribution']}")
    print(f"top 5 (min,max) modes:")
    for r in prior["range_modes_top"][:5]:
        print(f"  ({r['min_green']}, {r['max_green']}) -> {r['count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
