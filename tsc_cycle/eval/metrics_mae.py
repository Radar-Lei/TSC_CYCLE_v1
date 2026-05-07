"""Teacher MAE metric — integer absolute error against teacher solution.

Strict integer math (`abs(int(student) - int(teacher))`); never floats.
Returns mae=None if any phase is missing — orchestrator excludes those rows
from the MAE denominator.
"""

from __future__ import annotations

from typing import Any


def score_mae(student_solution: dict | None, teacher_solution: dict) -> dict[str, Any]:
    """Compute integer MAE + exact_match.

    Returns
    -------
    {"mae": float | None, "exact_match": bool,
     "n_phases": int, "per_phase_abs_err": list[int]}
        - mae=None when student_solution is None or any phase key missing.
        - per_phase_abs_err follows teacher_solution.keys() order.
    """
    n_phases = len(teacher_solution)
    if student_solution is None:
        return {"mae": None, "exact_match": False,
                "n_phases": n_phases, "per_phase_abs_err": []}
    keys = list(teacher_solution.keys())
    if not all(k in student_solution for k in keys):
        return {"mae": None, "exact_match": False,
                "n_phases": n_phases, "per_phase_abs_err": []}
    try:
        errs = [abs(int(student_solution[k]) - int(teacher_solution[k])) for k in keys]
    except (TypeError, ValueError):
        return {"mae": None, "exact_match": False,
                "n_phases": n_phases, "per_phase_abs_err": []}
    return {"mae": float(sum(errs)) / len(errs),
            "exact_match": all(e == 0 for e in errs),
            "n_phases": n_phases, "per_phase_abs_err": errs}
