---
phase: 18-calibrated-dataset-rebuild
reviewed: 2026-05-18T10:35:55Z
depth: standard
files_reviewed: 3
files_reviewed_list:
  - /home/samuel/TSC_CYCLE/tsc_cycle/v4_gates/calibrated_dataset_rebuild.py
  - /home/samuel/TSC_CYCLE/tests/test_v4_phase18_calibrated_dataset_rebuild.py
  - /home/samuel/TSC_CYCLE/artifacts/v4_2/phase18/reconstruction_report.json
findings:
  critical: 2
  warning: 1
  info: 0
  total: 3
status: issues_found
---

# Phase 18: Code Review Report

**Reviewed:** 2026-05-18T10:35:55Z
**Depth:** standard
**Files Reviewed:** 3
**Status:** issues_found

## Summary

Reviewed the calibrated v4.2 dataset rebuild implementation, its Phase 18 tests, and the generated reconstruction report against DATA-01/DATA-02, policy-gate semantics, hard-constraint preservation, split determinism, path safety, report honesty, and denominator handling. The implementation has correctness defects that can let invalid retained rows ship and can make the reconstruction report/policy gate claim clean evidence with wrong denominators. Split artifacts also lose Phase 8 lineage metadata for retained samples.

## Narrative Findings (AI reviewer)

## Critical Issues

### CR-01: Hard-constraint validation is run on coerced solutions, so invalid float labels can be retained

**File:** `/home/samuel/TSC_CYCLE/tsc_cycle/v4_gates/calibrated_dataset_rebuild.py:309-311`

**Issue:** `_record_solution()` converts every solution value with `int(val)` before `validate()` runs. This truncates non-integral floats (for example `30.9 -> 30`) and makes `constraint_lint.validate()` pass a coerced solution while the original row is written unchanged to the calibrated JSONL. The report can then state `retained_pass_rate: 1.0` even though retained output still contains a non-integer `final_green`, violating DATA-01 hard-constraint preservation.

**Fix:** Validate the raw solution object before any integer coercion, and only coerce after a raw hard-constraint pass if needed for policy projection.

```python
def _record_raw_solution(record: dict[str, Any]) -> Any:
    return _record_result(record).get("solution", {})

# in build_calibrated_dataset
input_obj = _record_input(record)
raw_solution = _record_raw_solution(record)
lint = validate(input_obj, raw_solution)
if not lint.ok:
    rejected_counts["hard_constraint_rejected_rows"] += 1
    ...
    continue
solution = _record_solution(record)  # safe only after lint.ok
phase_rows = _phase_rows_for_record(record, split_index)
```

Add a regression test where `result.solution` contains `30.9`; it must be rejected as `hard_constraint_rejected_rows`, not retained.

### CR-02: Post-policy gate uses phase-count denominator for malformed/missing row rates, hiding bad-row rates

**File:** `/home/samuel/TSC_CYCLE/tsc_cycle/v4_gates/calibrated_dataset_rebuild.py:338-339`; `/home/samuel/TSC_CYCLE/artifacts/v4_2/phase18/reconstruction_report.json:4842-4851`

**Issue:** `evaluate_saturation_policy_gate(retained_policy_rows, ...)` receives a list of phase rows, so Phase 17’s `_metric_denominator()` falls back to `audit.total_rows` (phase decisions), not dataset sample rows. The generated report shows `source_rows: 9501` and `retained_rows: 4532`, but `data_malformed_row_rate` / `data_missing_output_rate` denominators are `18026` in `post_gate`. If any malformed or missing-output rows reach the gate path, their rates are diluted by number of phases and can incorrectly pass strict DATA-02 policy gates. This is a hidden denominator issue and makes the report dishonest about row-level pass rates.

**Fix:** Pass structured evidence with an explicit row-level `input_count` and `excluded_counts` into `evaluate_saturation_policy_gate`, not a bare phase-row list.

```python
post_gate = evaluate_saturation_policy_gate(
    {
        "input_count": retained_count,
        "rows": retained_policy_rows,
        "excluded_counts": {},
    },
    thresholds=DEFAULT_THRESHOLDS,
    source_type="data",
)
```

For pre-gate/report evidence, use `input_count: source_count` and the same rejected-count taxonomy expected by Phase 17, so malformed/missing-output denominators are sample counts rather than phase counts.

## Warnings

### WR-01: Reconstructed split indexes discard Phase 8 lineage metadata

**File:** `/home/samuel/TSC_CYCLE/tsc_cycle/v4_gates/calibrated_dataset_rebuild.py:122-134`; `/home/samuel/TSC_CYCLE/data/v4_2/phase18/splits/train.index.jsonl:1`

**Issue:** `_record_lineage()` does not map `source_origin == "v1_valid"` / `"v3_new_lint_pass"` back to `v1.0` / `v3.0`, unlike the Phase 8 rebuild helper. The real Phase 18 split index therefore emits many retained rows with `"lineage": "unknown"`; the first row in `train.index.jsonl` is a v1-valid row with `source_origin: "v1_valid"` but `lineage: "unknown"`. This degrades provenance preservation and can break downstream analyses that depend on deterministic v1/v3 lineage accounting.

**Fix:** Preserve lineage from the original Phase 8 split row when present, or mirror Phase 8’s source-origin mapping.

```python
def _record_lineage(record: dict[str, Any]) -> str:
    origin = _record_source_origin(record)
    if origin == "v1_valid":
        return "v1.0"
    if origin == "v3_new_lint_pass":
        return "v3.0"
    ...
```

Also add a test against a fixture row with `source_origin="v1_valid"` and no explicit `lineage`, asserting the Phase 18 index keeps `lineage == "v1.0"`.

---

_Reviewed: 2026-05-18T10:35:55Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
