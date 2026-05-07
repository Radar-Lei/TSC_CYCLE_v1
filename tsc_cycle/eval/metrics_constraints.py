"""Constraint-satisfaction metric.

Wraps `tsc_cycle.constraint_lint.validate` + `is_trivial` for use by the
evaluation orchestrator (plan 06-05). Returns a flat dict per sample so the
orchestrator can aggregate without re-importing the validator.
"""

from __future__ import annotations

from typing import Any

from tsc_cycle.constraint_lint import is_trivial, validate


def score_constraint(prediction_input: dict, solution: dict | None) -> dict[str, Any]:
    """Score a single (input, student_solution) pair against hard constraints.

    Parameters
    ----------
    prediction_input : dict
        Eval prompt's `input` field — the same dict accepted by `validate`.
    solution : dict | None
        Student's parsed `<SOLUTION>` JSON, or None if unparseable.

    Returns
    -------
    {"lint_ok": bool, "violations": list[str], "trivial": bool}
        - `lint_ok=False` and `violations=["unparseable"]` if `solution` is None.
        - `violations` are stringified `Violation.kind` values for JSONL.
    """
    trivial = is_trivial(prediction_input)
    if solution is None:
        return {"lint_ok": False, "violations": ["unparseable"], "trivial": trivial}
    res = validate(prediction_input, solution)
    # Violations are dicts like {"kind": "below_min", "phase": "1", ...}; surface kinds.
    kinds: list[str] = []
    for v in res.violations or []:
        if isinstance(v, dict):
            kinds.append(str(v.get("kind", "unknown")))
        elif hasattr(v, "value"):
            kinds.append(v.value)
        else:
            kinds.append(str(v))
    return {"lint_ok": bool(res.ok), "violations": kinds, "trivial": trivial}
