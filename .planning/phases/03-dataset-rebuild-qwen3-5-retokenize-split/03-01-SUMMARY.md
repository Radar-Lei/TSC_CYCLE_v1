---
phase: 03-dataset-rebuild-qwen3-5-retokenize-split
plan: 01
subsystem: testing
tags: [pytest, dataset-rebuild, split-contract, arrow-ipc, qwen3.5]

requires:
  - phase: 01-tokenizer-llama-cpp
    provides: Qwen3.5 tokenizer safety and max_seq_length=2048 gate evidence
  - phase: 02-10k-7k
    provides: merged 9501-row Phase 2 dataset contract
provides:
  - Wave 0 RED pytest contract for DATA-01 deterministic exact split and v1 OOD alignment
  - Wave 0 RED pytest contract for DATA-02 Arrow IPC tokenized outputs
  - Wave 0 RED pytest contract for DATA-03 fail-closed truncation gating
  - Wave 0 RED pytest contract for DATA-04 split reproducibility artifacts
  - Lazy-import test interface for tsc_cycle.v3_gates.dataset_rebuild_v3
affects: [03-dataset-rebuild-qwen3-5-retokenize-split, phase-4-sft]

tech-stack:
  added: []
  patterns: [pytest tmp_path fixtures, lazy implementation imports, fail-closed artifact assertions, fake tokenizer]

key-files:
  created:
    - tests/test_v3_dataset_rebuild.py
  modified: []

key-decisions:
  - "Keep Phase 3 Wave 0 as RED-only contract tests; implementation remains in later plans 03-02 and 03-03."
  - "Use compact synthetic tmp_path JSONL fixtures instead of reading or embedding real Phase 2 dataset contents."

patterns-established:
  - "Lazy import planned dataset_rebuild_v3 symbols inside tests so pytest collection succeeds before implementation exists."
  - "Assert fail-closed behavior by checking tmp_path output artifacts are absent when split or truncation gates fail."

requirements-completed: [DATA-01, DATA-02, DATA-03, DATA-04]

duration: 2 min
completed: 2026-05-09
---

# Phase 03 Plan 01: Wave 0 RED Tests for DATA-01..04 Summary

**Executable RED pytest contract for deterministic Phase 3 split indices, Arrow IPC tokenization outputs, truncation gating, and reproducibility metadata**

## Performance

- **Duration:** 2 min
- **Started:** 2026-05-09T10:07:53Z
- **Completed:** 2026-05-09T10:09:56Z
- **Tasks:** 2
- **Files modified:** 1

## Accomplishments

- Added `tests/test_v3_dataset_rebuild.py` with five collectable RED tests covering DATA-01 through DATA-04.
- Defined exact split expectations: train=7601, val=950, ood_val=950, seed=42 determinism, pairwise disjoint IDs, all 300 v1 OOD rows pinned, and exactly 650 new OOD rows sampled.
- Defined tokenization artifact expectations: `data/tokenized/v3/{train,val,ood_val}.arrow` as Arrow IPC files with raw-text token columns and no chat-template metadata.
- Defined fail-closed behavior for duplicate sample IDs and truncation rate >5%, including no partial split or Arrow artifacts.

## Task Commits

Each task was committed atomically:

1. **Task 1: DATA-01/DATA-04 split and reproducibility RED tests** - `aa9969e` (test)
2. **Task 2: DATA-02/DATA-03 tokenization and Arrow RED tests** - `3d50134` (test)

**Plan metadata:** committed after this summary write.

## Files Created/Modified

- `tests/test_v3_dataset_rebuild.py` - Wave 0 RED contract tests for deterministic split planning, reproducibility artifacts, Arrow IPC tokenization outputs, truncation gating, and native `<think>` leak checks.

## Verification

- Task 1 command passed as RED verification by observing non-zero pytest status:
  - `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest tests/test_v3_dataset_rebuild.py::test_split_exact_sizes_and_v1_ood_alignment tests/test_v3_dataset_rebuild.py::test_split_indices_persist_hashes_and_manifest -q; status=$?; test "$status" -ne 0`
  - Result: both tests collected and failed because `tsc_cycle.v3_gates.dataset_rebuild_v3` is not implemented yet.
- Task 2 command passed as RED verification by observing non-zero pytest status:
  - `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest tests/test_v3_dataset_rebuild.py::test_writes_arrow_ipc_files tests/test_v3_dataset_rebuild.py::test_truncation_rate_gate_fails_closed -q; status=$?; test "$status" -ne 0`
  - Result: both tests collected and failed because `tsc_cycle.v3_gates.dataset_rebuild_v3` is not implemented yet.
- Plan-level RED command passed by observing non-zero pytest status:
  - `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest tests/test_v3_dataset_rebuild.py -q; status=$?; test "$status" -ne 0`
  - Result: five tests collected and failed for the expected missing implementation module.

## Decisions Made

- Kept all implementation imports lazy inside helper functions so pytest can collect the file before `dataset_rebuild_v3.py` exists.
- Used compact synthetic records under `tmp_path` to model 9501 rows without reading or embedding real Phase 2 JSONL contents.
- Added one explicit native `<think>` pre-truncation test in addition to the two required Task 2 named tests to capture DATA-03 tokenizer safety from the plan behavior.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None. The failing test output is the intended RED state for Wave 0.

## TDD Gate Compliance

- RED commits present: `aa9969e`, `3d50134`.
- GREEN commit intentionally absent: plan 03-01 is a Wave 0 RED contract-only plan; implementation is scheduled for later Phase 3 plans.

## Known Stubs

None. The new file contains tests only; no UI-facing hardcoded empty values, placeholder production behavior, TODO, or FIXME patterns were introduced.

## User Setup Required

None - no external service configuration required.

## Threat Flags

No new network endpoints, auth paths, schema migrations, production data writes, or trust-boundary implementation surfaces were introduced. Tests write only under pytest `tmp_path` fixtures.

## Next Phase Readiness

Ready for Plan 03-02 to implement `tsc_cycle.v3_gates.dataset_rebuild_v3` split planning, index persistence, manifest writing, and v1 OOD alignment evidence against these RED contracts.

## Self-Check: PASSED

- `tests/test_v3_dataset_rebuild.py` exists.
- Commit `aa9969e` exists and contains Task 1 RED tests.
- Commit `3d50134` exists and contains Task 2 RED tests.
- Plan-level RED verification collected the file and returned non-zero for the expected missing implementation module.

---
*Phase: 03-dataset-rebuild-qwen3-5-retokenize-split*
*Completed: 2026-05-09*
