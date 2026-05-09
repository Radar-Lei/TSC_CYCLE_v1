---
phase: 08-v3-4b-dataset-rebuild
plan: 01
subsystem: testing
tags: [pytest, dataset-rebuild, qwen3-4b, tdd, phase8]

requires:
  - phase: 07-4b-baseline-label-protocol-gate
    provides: Phase 7 tokenizer/native-think gate and corrected label protocol handoff
provides:
  - CPU-fast RED contract tests for Phase 8 source merge, cleaning, dedupe, split/tokenize, and aggregate report gates
affects: [08-v3-4b-dataset-rebuild, phase9-4b-qlora-retrain, DATA4B]

tech-stack:
  added: []
  patterns:
    - Lazy imports for planned Phase 8 public APIs so pytest collection succeeds before implementation exists
    - Fake injected Qwen3-4B tokenizer for CPU-only tokenization contracts without HF downloads

key-files:
  created:
    - tests/test_v4_phase8_dataset_rebuild.py
  modified: []

key-decisions:
  - "Phase 8 implementation must expose build_v4_source_dataset, build_v4_splits_and_tokenized, build_parser, and evaluate_phase8_report against these RED contracts."
  - "Tests enforce v4-isolated data/artifact paths and reject v3 merged-only source input for DATA4B-01."

patterns-established:
  - "RED contracts use compact tmp_path JSONL fixtures and lazy imports to fail only on missing planned implementation symbols."
  - "Tokenizer safety is asserted through an injected fake tokenizer that maps native <think> tags to [151667, 151668]."

requirements-completed: [DATA4B-01, DATA4B-02, DATA4B-03, DATA4B-04, DATA4B-05]

duration: 3min
completed: 2026-05-09
---

# Phase 08 Plan 01: RED Phase 8 Dataset Rebuild Contracts Summary

**CPU-fast RED pytest contracts for v4 4B dataset rebuild source hygiene, deterministic split/tokenize safety, and Phase 8 handoff gating**

## Performance

- **Duration:** 3 min
- **Started:** 2026-05-09T17:36:58Z
- **Completed:** 2026-05-09T17:39:33Z
- **Tasks:** 2
- **Files modified:** 1

## Accomplishments

- Created `tests/test_v4_phase8_dataset_rebuild.py` with lazy imports for planned Phase 8 implementation symbols.
- Added RED contracts for explicit v1 valid + v3 new lint-pass source merge, malformed close-tag normalization, native `<think>` rejection, canonical hash dedupe, and source manifest evidence.
- Added RED contracts for Qwen3-4B default CLI paths, deterministic v4 80/10/10-style split behavior, fake raw-text tokenization, native think ID checks before truncation, truncation-rate gating, dataset card gating, and Phase 7 handoff enforcement.

## Task Commits

1. **Task 1: Write RED contracts for source merge, dedupe, and cleaning** - `cd983f6` (test)
2. **Task 2: Write RED contracts for split/tokenize, aggregate gate, and dataset card** - `a2074eb` (test)

**Plan metadata:** pending final docs commit

## Files Created/Modified

- `tests/test_v4_phase8_dataset_rebuild.py` - Phase 8 RED pytest contracts covering DATA4B-01 through DATA4B-05.

## Verification

- `PYTHONPATH=/home/samuel/TSC_CYCLE /home/samuel/TSC_CYCLE/.venv/bin/python -m pytest -q /home/samuel/TSC_CYCLE/tests/test_v4_phase8_dataset_rebuild.py --maxfail=1`
  - Result: controlled RED failure on missing planned implementation module `tsc_cycle.v4_gates.dataset_rebuild`.
- Grep gates:
  - `data/v4/phase8` occurrences in non-comment lines: 4
  - `Qwen/Qwen3-4B-Thinking-2507` occurrences in non-comment lines: 2
  - Requirement IDs present: DATA4B-01, DATA4B-02, DATA4B-03, DATA4B-04, DATA4B-05
- Line count: 531 lines.

## Decisions Made

- Kept all Phase 8 implementation imports lazy inside helper functions so pytest collection remains valid before implementation exists.
- Used an injected `FakeQwen4BTokenizer` instead of loading any live HF tokenizer, preserving CPU-fast/no-network execution.
- Required aggregate Phase 8 reporting to block Phase 9 unless the dataset card contains a v4 Phase 8 section and Phase 7 `next_phase_allowed` is true.

## Deviations from Plan

None - plan executed exactly as written.

## Known Stubs

None detected in files created/modified by this plan.

## Issues Encountered

- The verification command fails as expected because the planned implementation module does not yet exist. This is the intended RED state for Plan 08-01.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 08-02 can implement `tsc_cycle.v4_gates.dataset_rebuild` against the source merge/clean/dedupe contracts.
- Plan 08-03/08-04 can implement split/tokenized artifact generation and aggregate Phase 8 handoff reporting against the remaining RED contracts.

## Self-Check: PASSED

- Found `tests/test_v4_phase8_dataset_rebuild.py`.
- Found `.planning/phases/08-v3-4b-dataset-rebuild/08-01-SUMMARY.md`.
- Found task commits `cd983f6` and `a2074eb` in git history.

---
*Phase: 08-v3-4b-dataset-rebuild*
*Completed: 2026-05-09*
