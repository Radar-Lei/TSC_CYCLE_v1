# Phase 18: Calibrated Dataset Rebuild - Pattern Map

**Mapped:** 2026-05-18
**Files analyzed:** Phase 8 rebuild, Phase 17 policy gate, hard-constraint validator, Phase 8 tests
**Analogs found:** 3 / 3

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `tsc_cycle/v4_gates/calibrated_dataset_rebuild.py` | CLI/report + dataset transform | JSONL input -> calibrated JSONL/splits/report | `tsc_cycle/v4_gates/dataset_rebuild.py` + `tsc_cycle/v4_gates/phase17_audit.py` | role-match |
| `tests/test_v4_phase18_calibrated_dataset_rebuild.py` | contract tests | tiny fixtures -> files/reports | `tests/test_v4_phase8_dataset_rebuild.py` + `tests/test_v4_phase17_saturation_policy.py` | exact |
| `artifacts/v4_2/phase18/reconstruction_report.json` | maintainer report | counts/hashes/gates | `artifacts/v4/phase8/rebuild_report.json` + `artifacts/v4/phase17/saturation_policy_gate.json` | role-match |

## Primary Patterns

### Dataset row helpers

Use Phase 8 helpers as the main style reference:

- `_record_input(record)`
- `_record_result(record)`
- `_record_sample_id(record)`
- `_record_source_origin(record)`
- `_record_lineage(record)`
- `_record_source(record)`
- `_record_reasoning(record)`
- `_record_solution(record)`
- `_manifest_hash(record)`
- `_index_row(record, split, raw_index, seed)`

Phase 18 should preserve row shape and provenance instead of inventing a new schema.

### Saturation policy reuse

Use Phase 17 functions directly:

- `classify_violation(row)` for per-phase rejection reason.
- `project_dataset_phase_decisions(...)` for source evidence projection.
- `compute_saturation_audit(...)` for pre/post audit summaries.
- `evaluate_saturation_policy_gate(...)` for final policy gate semantics.

Do not copy band thresholds or reimplement classifier logic in Phase 18.

### Hard constraint first

Use `constraint_lint.validate(prediction_input, solution)` before keeping a row. Invalid or malformed rows are not retained as policy successes. The report must expose counts for malformed/missing/hard-constraint-invalid rows.

### Split preservation

Read Phase 8 split index JSONL files and create `sample_id -> split row` lookup. Retained samples keep their existing split. Phase 18 split indexes should write the same hash fields as Phase 8 using canonical prompt/assistant construction.

### Path safety

Follow Phase 17's stricter artifact-root boundary and Phase 8's frozen-root guard:

- reject frozen v1 root writes.
- reject writing calibrated outputs under `data/v4/phase8` or `artifacts/v4/phase8`.
- accept defaults only under `data/v4_2/phase18` and `artifacts/v4_2/phase18`.

### CLI/report shape

Follow Phase 12/17 gate payload style:

- `ok`
- `next_phase_allowed`
- `requirements_covered`
- `gates`
- `fatal_failures`
- `warnings`
- `reports` / `paths`
- `counts`

The CLI should print JSON and exit nonzero on red reports.

## Testing Patterns

Use existing JSON/JSONL fixture helpers from Phase 8 tests. Keep imports lazy and avoid GPU/model/training dependencies in collection and test execution.

Add tests for:

- filter mode removes unsaturated max-green violations.
- saturated max-green and forced trivial rows are retained.
- hard-constraint-invalid rows are rejected and counted.
- post-calibration policy gate passes on retained rows.
- split indexes preserve source split membership.
- report includes hashes, counts, rejection examples, and requirement coverage.
- path guard rejects Phase 8/frozen/broad output paths.
