"""Hard-constraint validator for teacher / student outputs.

Returns a structured result with a list of typed violations. Used both by the
teacher labeling pipeline (drop on violation) and by the eval suite (compute
constraint-satisfaction rate).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Violation(str, Enum):
    NOT_DICT = "not_dict"
    BAD_KEY_TYPE = "bad_key_type"          # key not a string-form integer phase id
    PHASE_MISMATCH = "phase_mismatch"      # keys != input phase_ids
    NOT_INTEGER = "not_integer"            # value not an integer
    BELOW_MIN = "below_min"                # final < min_green
    ABOVE_MAX = "above_max"                # final > max_green
    PHASE_ORDER = "phase_order"            # output order != input order


@dataclass
class LintResult:
    ok: bool
    violations: list[dict] = field(default_factory=list)

    def add(self, kind: Violation, **details: Any) -> None:
        self.violations.append({"kind": kind.value, **details})
        self.ok = False


def validate(prediction_input: dict[str, Any], output: Any) -> LintResult:
    """Validate output against the input's hard constraints.

    Parameters
    ----------
    prediction_input : dict
        {"prediction": {"phase_waits": [{"phase_id": int, "min_green": int, "max_green": int, ...}, ...]}}
    output : Any
        Should be {"<phase_id>": <int_seconds>, ...}.
    """
    result = LintResult(ok=True)

    if not isinstance(output, dict):
        result.add(Violation.NOT_DICT, got=type(output).__name__)
        return result

    waits = prediction_input.get("prediction", {}).get("phase_waits", [])
    expected_ids = [str(w["phase_id"]) for w in waits]

    # Key set match
    output_keys = list(output.keys())
    if set(output_keys) != set(expected_ids):
        result.add(
            Violation.PHASE_MISMATCH,
            expected=expected_ids,
            got=output_keys,
        )
        return result  # downstream checks meaningless if phases don't match

    # Phase ORDER must match input order (we treat dict insertion order as semantic)
    if output_keys != expected_ids:
        result.add(Violation.PHASE_ORDER, expected=expected_ids, got=output_keys)

    # Per-phase validation
    for w in waits:
        pid = str(w["phase_id"])
        v = output.get(pid)
        # key type — JSON dict keys are always strings, but defensively check
        if not isinstance(pid, str) or not pid.lstrip("-").isdigit():
            result.add(Violation.BAD_KEY_TYPE, key=pid)

        # int check (reject bool, since bool is subclass of int)
        if isinstance(v, bool) or not isinstance(v, int):
            # Accept floats only if integral
            if isinstance(v, float) and v.is_integer():
                v = int(v)
            else:
                result.add(Violation.NOT_INTEGER, phase=pid, got=v)
                continue

        if v < w["min_green"]:
            result.add(Violation.BELOW_MIN, phase=pid, value=v, min=w["min_green"])
        if v > w["max_green"]:
            result.add(Violation.ABOVE_MAX, phase=pid, value=v, max=w["max_green"])

    return result


def is_trivial(prediction_input: dict[str, Any]) -> bool:
    """Trivial sample: all phases have min_green == max_green (forced single value)."""
    waits = prediction_input.get("prediction", {}).get("phase_waits", [])
    return bool(waits) and all(w["min_green"] == w["max_green"] for w in waits)
