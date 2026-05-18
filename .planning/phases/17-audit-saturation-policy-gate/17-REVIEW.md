---
phase: 17-audit-saturation-policy-gate
reviewed: 2026-05-18T06:58:10Z
depth: standard
files_reviewed: 6
files_reviewed_list:
  - artifacts/v4/phase17/prompt_protocol_report.json
  - artifacts/v4/phase17/saturation_audit_report.json
  - artifacts/v4/phase17/saturation_policy_gate.json
  - tests/test_v4_phase17_saturation_policy.py
  - tsc_cycle/v4_gates/phase17_audit.py
  - tsc_cycle/v4_gates/saturation_policy.py
findings:
  critical: 3
  warning: 2
  info: 0
  total: 5
status: issues_found
---

# Phase 17: Code Review Report

**Reviewed:** 2026-05-18T06:58:10Z
**Depth:** standard
**Files Reviewed:** 6
**Status:** issues_found

## Summary

Reviewed the Phase 17 saturation audit/policy gate implementation, reports, and tests. The implementation contains policy-gate bypasses around derived audit fields and missing-output thresholds, plus brittle prompt-leakage scanning and CLI artifact-root behavior that can produce reports in the wrong location.

## Narrative Findings (AI reviewer)

## Critical Issues

### CR-01: Caller-supplied derived audit fields can bypass saturation thresholds

**File:** `tsc_cycle/v4_gates/saturation_policy.py:332-334`

**Issue:** `_normalise_audit_row()` trusts `saturation_band`, `trivial_range`, and `violation_category` when they are already present on an input row. Eval JSONL rows and externally supplied row lists therefore can forge `saturation_band: sat_ge_1.0_allowed_max`, `trivial_range: true`, or `violation_category: none` while keeping `pred_saturation < 1.0` and `final_green == max_green`. `compute_saturation_audit()` will then exclude or mis-bucket the row, allowing low-saturation max-green violations to disappear before `evaluate_saturation_policy_gate()` checks thresholds.

**Fix:** Recompute all derived fields from canonical numeric inputs and reject inconsistent supplied values instead of trusting them.

```python
computed_band = classify_saturation_band(out["pred_saturation"])
computed_trivial = is_trivial_phase_range(out)
computed_violation = classify_violation({**out, "saturation_band": computed_band})

for field, computed in {
    "saturation_band": computed_band,
    "trivial_range": computed_trivial,
    "violation_category": computed_violation,
}.items():
    if field in row and row[field] != computed:
        raise ValueError(f"inconsistent derived audit row field {field}")
    out[field] = computed
```

### CR-02: `missing_output_rate` threshold is defined but never enforced

**File:** `tsc_cycle/v4_gates/phase17_audit.py:207-222`

**Issue:** `DEFAULT_THRESHOLDS` includes `missing_output_rate: 0.0`, and dataset/replay projection records `missing_solution_or_input` exclusions, but `evaluate_saturation_policy_gate()` only evaluates saturation-band rates. A projection can contain missing outputs and still pass the policy gate as long as the remaining rows stay under saturation thresholds. This violates fail-closed threshold semantics and can allow incomplete evidence to advance.

**Fix:** Evaluate exclusion-rate gates using `input_count` and `excluded_counts`, at minimum for `missing_solution_or_input`, and fail when the rate exceeds `missing_output_rate`.

```python
input_count = int(rows_or_audit.get("input_count", audit.get("total_rows", 0)))
missing_count = int((rows_or_audit.get("excluded_counts") or {}).get("missing_solution_or_input", 0))
missing_rate = missing_count / input_count if input_count else 0.0
threshold = active_thresholds["missing_output_rate"]
gate_name = f"{source}_missing_output_rate"
gates[gate_name] = {"ok": missing_rate <= threshold, "count": missing_count, "denominator": input_count, "rate": missing_rate, "threshold": threshold}
if missing_rate > threshold:
    fatal_failures.append({"gate": f"{source}_threshold_excess_missing_output_rate", "reason": f"{missing_rate} > {threshold}"})
```

### CR-03: Prompt leakage guard only matches a few exact ASCII substrings

**File:** `tsc_cycle/v4_gates/phase17_audit.py:47-56`

**Issue:** The prompt protocol guard scans only exact snippets such as `sat < 0.2`. It does not detect semantically identical leaks using the project’s actual field name (`pred_saturation < 0.2`), spacing variants (`sat<0.2`), Unicode comparison symbols, or Chinese prompt wording. Because the deployment prompt is Chinese, a leaked rule like `pred_saturation 小于 0.2 时接近最小绿灯` would pass `evaluate_prompt_protocol_guard()`.

**Fix:** Normalize text and use regex/semantic patterns that cover `sat`, `saturation`, `pred_saturation`, spacing variants, comparison symbols, and Chinese policy wording for the protected saturation bands.

```python
FORBIDDEN_POLICY_PATTERNS = [
    re.compile(r"\b(?:pred_)?saturation\s*(?:<|小于|低于)\s*0\.2", re.I),
    re.compile(r"0\.2\s*(?:<=|≤)\s*(?:pred_)?saturation\s*(?:<|<|小于)\s*0\.6", re.I),
    re.compile(r"饱和度.*(?:最小绿灯|最大绿灯|接近最小|插值|达到最大)"),
]
```

## Warnings

### WR-01: `--artifact-root` does not change default output paths

**File:** `tsc_cycle/v4_gates/phase17_audit.py:424-427`

**Issue:** `--artifact-root` updates the global `ARTIFACT_ROOT` in `main()`, but `--out`, `--audit-out`, and `--prompt-protocol-out` defaults are bound to the original module-level paths when the parser is built. Running the CLI with only `--artifact-root /tmp/...` still writes reports under the repository’s default `artifacts/v4/phase17` unless all three output flags are also supplied.

**Fix:** Make output defaults `None` in the parser and derive them after applying `args.artifact_root`.

```python
parser.add_argument("--out", type=Path, default=None)
parser.add_argument("--audit-out", type=Path, default=None)
parser.add_argument("--prompt-protocol-out", type=Path, default=None)
# after ARTIFACT_ROOT = Path(args.artifact_root):
out_path = args.out or ARTIFACT_ROOT / "saturation_policy_gate.json"
audit_out = args.audit_out or ARTIFACT_ROOT / "saturation_audit_report.json"
prompt_out = args.prompt_protocol_out or ARTIFACT_ROOT / "prompt_protocol_report.json"
```

### WR-02: Integer coercion accepts JSON floats for fields that must be integers

**File:** `tsc_cycle/v4_gates/saturation_policy.py:54-55`

**Issue:** `_finite_int()` accepts finite floats whose numeric value is integral. For raw eval/audit evidence this means JSON values such as `50.0` are accepted as valid `final_green`, `min_green`, or `max_green`, even though the hard constraint requires integer seconds and JSON integer values. This weakens malformed-input handling for externally supplied Phase 17 evidence.

**Fix:** Reject floats in strict audit/eval paths, or add a strict mode and use it for parsed JSON evidence.

```python
def _finite_int(value: Any, *, field: str, strict_json_int: bool = True) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field} must be an integer, got bool")
    if isinstance(value, int):
        return value
    if not strict_json_int and isinstance(value, float) and math.isfinite(value) and value.is_integer():
        return int(value)
    raise ValueError(f"{field} must be an integer, got {value!r}")
```

---

_Reviewed: 2026-05-18T06:58:10Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
