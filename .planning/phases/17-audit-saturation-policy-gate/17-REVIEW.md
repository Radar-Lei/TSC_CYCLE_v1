---
phase: 17-audit-saturation-policy-gate
reviewed: 2026-05-18T07:08:09Z
depth: standard
files_reviewed: 3
files_reviewed_list:
  - tsc_cycle/v4_gates/saturation_policy.py
  - tsc_cycle/v4_gates/phase17_audit.py
  - tests/test_v4_phase17_saturation_policy.py
findings:
  critical: 1
  warning: 0
  info: 0
  total: 1
status: issues_found
---

# Phase 17: Code Review Report

**Reviewed:** 2026-05-18T07:08:09Z
**Depth:** standard
**Files Reviewed:** 3
**Status:** issues_found

## Summary

Re-reviewed the Phase 17 saturation audit/policy gate implementation and tests after fixes. The prior findings CR-01, CR-02, CR-03, WR-01, and WR-02 are resolved: derived audit fields are recomputed/rejected on inconsistency, missing-output rate is now enforced, prompt leakage scanning is broader, artifact-root defaults are derived after parsing, and JSON float integer fields are rejected.

However, the configured `malformed_row_rate` threshold remains unenforced. The test suite passes (`python -m pytest /home/samuel/TSC_CYCLE/tests/test_v4_phase17_saturation_policy.py`: 29 passed), but it does not cover this remaining fail-closed gate path.

## Narrative Findings (AI reviewer)

## Critical Issues

### CR-01: `malformed_row_rate` threshold is still never enforced

**Classification:** BLOCKER

**File:** `tsc_cycle/v4_gates/phase17_audit.py:37-43,244-256`

**Issue:** `DEFAULT_THRESHOLDS` still exposes `malformed_row_rate: 0.0`, and the Phase 17 plan requires malformed rows to fail closed, but `evaluate_saturation_policy_gate()` only evaluates saturation-band thresholds and `missing_output_rate`. Excluded malformed/invalid evidence such as `hard_constraint_invalid` is accepted as long as the remaining projected rows satisfy saturation and missing-output gates. For example, a projection with `input_count: 2`, one valid row, and `excluded_counts: {"hard_constraint_invalid": 1}` currently returns `ok: True`, bypassing the configured zero-tolerance malformed-row threshold.

**Fix:** Add a malformed-row rate gate using `input_count` and non-missing excluded counts, and fail when it exceeds `malformed_row_rate`. Keep `missing_solution_or_input` under the existing `missing_output_rate` gate so the two thresholds remain distinct.

```python
def _malformed_row_rate_metric(rows_or_audit: Any, audit: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    evidence = rows_or_audit if isinstance(rows_or_audit, dict) else {}
    excluded_counts = evidence.get("excluded_counts") if isinstance(evidence.get("excluded_counts"), dict) else audit.get("excluded_counts", {})
    try:
        denominator = int(evidence.get("input_count", audit.get("total_rows", 0)))
        count = sum(
            int(value)
            for key, value in excluded_counts.items()
            if key != "missing_solution_or_input"
        )
    except (AttributeError, TypeError, ValueError) as exc:
        return None, f"non-numeric malformed_row_rate metric: {exc}"
    if denominator < 0 or count < 0 or count > denominator:
        return None, "invalid malformed_row_rate denominator/count"
    return {"count": count, "denominator": denominator, "rate": count / denominator if denominator else 0.0}, None
```

Then evaluate it alongside `data_missing_output_rate`/`replay_missing_output_rate`/`eval_missing_output_rate`, using the active `malformed_row_rate` threshold and appending a fatal failure such as `{source}_threshold_excess_malformed_row_rate` when exceeded. Add a regression test that `excluded_counts={"hard_constraint_invalid": 1}` fails under the default threshold and passes only when `malformed_row_rate` is explicitly loosened.

---

_Reviewed: 2026-05-18T07:08:09Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
