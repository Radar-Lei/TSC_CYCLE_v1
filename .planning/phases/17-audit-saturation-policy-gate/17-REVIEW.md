---
phase: 17-audit-saturation-policy-gate
reviewed: 2026-05-18T07:44:39Z
depth: standard
files_reviewed: 5
files_reviewed_list:
  - tsc_cycle/v4_gates/saturation_policy.py
  - tsc_cycle/v4_gates/phase17_audit.py
  - tsc_cycle/v4_gates/fixtures/v4_prompt_protocol_golden.json
  - tests/test_v4_phase17_saturation_policy.py
  - artifacts/v4/phase17/saturation_audit_report.json
findings:
  critical: 2
  warning: 0
  info: 0
  total: 2
status: issues_found
---

# Phase 17: Code Review Report

**Reviewed:** 2026-05-18T07:44:39Z
**Depth:** standard
**Files Reviewed:** 5
**Status:** issues_found

## Summary

Reviewed the Phase 17 saturation policy helpers, audit CLI/gate, prompt golden fixture, tests, and generated audit report after gap closure. The artifact-root output boundary is materially improved, and the representative examples now preserve at least one replay-origin example before filling the remainder. However, two fail-closed gate defects remain: the prompt leakage guard misses a common saturation-threshold wording, and malformed phase input can still crash the audit instead of producing a controlled fatal report.

Tests run during review: `python -m pytest /home/samuel/TSC_CYCLE/tests/test_v4_phase17_saturation_policy.py` passed (`38 passed`). Passing tests do not cover the defects below.

## Narrative Findings (AI reviewer)

## Critical Issues

### CR-01 (BLOCKER): Prompt leakage guard misses `sat >= 1` / `saturation >= 1` policy text

**File:** `/home/samuel/TSC_CYCLE/tsc_cycle/v4_gates/phase17_audit.py:54`

**Issue:** The saturated-band leakage regex only matches `1.0`, so policy text such as `sat >= 1 may use max green`, `saturation >= 1 may use max green`, or `pred_saturation >= 1 may use max green` is not reported. With the locked prompt unchanged, `evaluate_prompt_protocol_guard(prompt_text=EXPECTED_V4_PROMPT, prompt_surfaces={"synthetic.py": "sat >= 1 may use max green"})` returns `ok=True` with no forbidden snippets. That violates POLICY-03 because explicit saturation band guidance can enter scanned prompt surfaces without failing the gate.

**Fix:** Accept both `1` and `1.0` in the saturated-band pattern and add regression coverage where the rendered prompt remains byte-for-byte expected but a scanned surface contains the leakage.

```python
re.compile(
    r"\b(?:pred_)?sat(?:uration)?\s*"
    r"(?:>=|≥|>|大于等于|不小于|不低于|達到|达到)\s*1(?:\.0)?\b",
    re.IGNORECASE,
)
```

### CR-02 (BLOCKER): Malformed phase rows can raise uncaught `KeyError` instead of failing closed

**File:** `/home/samuel/TSC_CYCLE/tsc_cycle/v4_gates/saturation_policy.py:194-195` and `/home/samuel/TSC_CYCLE/tsc_cycle/v4_gates/saturation_policy.py:259-260`

**Issue:** `project_dataset_phase_decisions()` and `project_replay_phase_decisions()` call `validate(prediction_input, solution)` before validating the input schema. `validate()` indexes fields like `phase_id` directly, so a malformed `prediction.phase_waits` entry missing `phase_id` raises `KeyError`. `evaluate_phase17_audit()` does not catch `KeyError`, so the Phase 17 CLI can crash without writing the fail-closed JSON reports that downstream gates expect.

**Fix:** Treat schema exceptions from validation/projection as malformed evidence and continue accounting for them in `excluded_counts`, or pre-validate every `phase_waits` entry before calling `validate()`.

```python
try:
    lint = validate(prediction_input, solution)
except (KeyError, TypeError, ValueError) as exc:
    excluded_counts["malformed_prediction_input"] += 1
    excluded_samples.append({
        "sample_id": sample_id,
        "reason": "malformed_prediction_input",
        "error": str(exc),
    })
    continue
```

Apply the same fail-closed handling to replay projection and add tests for missing `phase_id`, `min_green`, `max_green`, and non-object `phase_waits` entries.

---

_Reviewed: 2026-05-18T07:44:39Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
