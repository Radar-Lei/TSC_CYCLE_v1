"""Rule-based reasoning quality metric (no LLM-as-judge).

Tier mapping by `hit_count` inside the `<start_working_out>...<end_working_out>`
segment:
  0 hits        -> miss
  1-2 hits      -> partial
  >=3 hits      -> full

`hit_count` = (# KEYWORDS appearing literally) + (# distinct min/max integers
from the input that appear as standalone tokens in the reasoning).
"""

from __future__ import annotations

import re
from typing import Any

from tsc_cycle.prompt_builder import parse_assistant_output

KEYWORDS = ["pred_saturation", "min_green", "max_green", "pred_wait"]


def score_reasoning(raw_text: str, prediction_input: dict) -> dict[str, Any]:
    """Score the reasoning segment of a model response."""
    reasoning, _ = parse_assistant_output(raw_text or "")
    if not reasoning:
        return {"reasoning_tier": "miss", "hit_count": 0,
                "keywords_found": [], "numbers_found": []}

    kws = [k for k in KEYWORDS if k in reasoning]

    # Collect candidate numbers from input (min_green / max_green).
    numbers: set[int] = set()
    waits = (prediction_input or {}).get("prediction", {}).get("phase_waits", [])
    for w in waits:
        for fld in ("min_green", "max_green"):
            v = w.get(fld) if isinstance(w, dict) else None
            if isinstance(v, int):
                numbers.add(v)

    # Standalone integer hit (avoid matching substrings of larger numbers).
    nums_in_reasoning: list[int] = []
    for n in numbers:
        if re.search(rf"(?<!\d){n}(?!\d)", reasoning):
            nums_in_reasoning.append(n)

    hits = len(kws) + len(nums_in_reasoning)
    if hits >= 3:
        tier = "full"
    elif hits >= 1:
        tier = "partial"
    else:
        tier = "miss"
    return {"reasoning_tier": tier, "hit_count": hits,
            "keywords_found": kws, "numbers_found": sorted(nums_in_reasoning)}
