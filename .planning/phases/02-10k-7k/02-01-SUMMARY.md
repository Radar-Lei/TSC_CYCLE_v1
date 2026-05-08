---
phase: 02-10k-7k
plan: "01"
subsystem: testing
tags: [pytest, datagen, teacher-labeler, merge-gate, red-tests]
requires:
  - phase: 01-tokenizer-llama-cpp
    provides: Phase 1 hard gates and v3 baseline context
provides:
  - Wave 0 RED pytest coverage for DATAGEN-01 through DATAGEN-07
  - Mini fixtures for Phase 2 prior, old labels, and eval failure seeds
  - Executable contracts for reservoir generation, labeler hardening, and merge reporting
affects: [02-10k-7k, DATAGEN-01, DATAGEN-02, DATAGEN-03, DATAGEN-04, DATAGEN-05, DATAGEN-06, DATAGEN-07]
tech-stack:
  added: []
  patterns:
    - pytest RED tests with lazy imports for not-yet-implemented public APIs
    - tmp_path JSONL fixtures to avoid production data mutation
key-files:
  created:
    - tests/conftest.py
    - tests/test_v3_datagen_inputs.py
    - tests/test_v3_labeler.py
    - tests/test_v3_datagen_merge.py
  modified: []
key-decisions:
  - "Wave 0 intentionally leaves tests RED only on missing Phase 2 implementation entry points."
  - "Tests use tmp_path fixtures and byte checks to protect data/labeled.jsonl from mutation."
patterns-established:
  - "Phase 2 RED tests lazy-import planned APIs so pytest collection succeeds before implementation."
  - "Labeler tests use fake clients/results and sentinel secret checks to avoid OpenAI/API-key dependency."
requirements-completed: [DATAGEN-01, DATAGEN-02, DATAGEN-03, DATAGEN-04, DATAGEN-05, DATAGEN-06, DATAGEN-07]
duration: 4 min
completed: 2026-05-08
---

# Phase 02 Plan 01: Wave 0 RED Tests for DATAGEN-01..07 Summary

**Executable RED pytest contracts for Phase 2 10K/7K datagen reservoir, GPT-5.5 high labeler hardening, and frozen-baseline merge gates**

## Performance

- **Duration:** 4 min
- **Started:** 2026-05-08T15:01:44Z
- **Completed:** 2026-05-08T15:06:21Z
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments

- Added shared mini Phase 2 fixtures for priors, old labeled JSONL, and per-sample eval rows.
- Added RED tests for same_dist/OOD/targeted reservoir counts, sample IDs, old-label exclusion, and targeted provenance from `lint_ok=false` or `mae > 10.0` rows.
- Added RED tests for labeler worker cap, `gpt-5.5`/`high` defaults, isolated input/output/cache args, resume skip behavior, lint-failure rejection, and API-key non-serialization.
- Added RED tests for Phase 2 merge report fields, ≥9000 merged valid gate, frozen old SHA mismatch failure, and new-label lint violation failure.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add reservoir and targeted-sampler RED tests** - `88b2bf5` (test)
2. **Task 2: Add labeler hardening RED tests** - `4a91e17` (test)
3. **Task 3: Add merge and frozen-baseline RED tests** - `039503a` (test)

**Plan metadata:** committed after this summary.

## Files Created/Modified

- `tests/conftest.py` - Shared mini prior, old labeled JSONL, eval seed JSONL, and JSONL writer fixtures.
- `tests/test_v3_datagen_inputs.py` - DATAGEN-01/02 RED tests for three-source reservoir generation, dedupe, and targeted provenance.
- `tests/test_v3_labeler.py` - DATAGEN-03/04/05 RED tests for labeler CLI/config, resume safety, lint rejection, fake-client operation, and secret safety.
- `tests/test_v3_datagen_merge.py` - DATAGEN-06/07 RED tests for merge/report gates, frozen SHA invariants, and lint-pass requirements.

## Decisions Made

- Used lazy imports for planned public APIs so the tests collect and fail on missing implementation behavior instead of import-time syntax/collection errors.
- Kept all fixtures under `tmp_path` and added explicit production `data/labeled.jsonl` byte-stability assertions.
- Mocked the teacher client entirely; no test imports OpenAI, requires `OPENAI_API_KEY`, or performs network calls.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Converted top-level reservoir import to lazy import**
- **Found during:** Task 1 (reservoir tests)
- **Issue:** Directly importing `build_v3_phase2_reservoir` caused pytest collection to error before RED assertions could run.
- **Fix:** Moved the import behind a helper that imports `tsc_cycle.sample_inputs` at test execution time and fails on the planned missing symbol.
- **Files modified:** `tests/test_v3_datagen_inputs.py`
- **Verification:** Focused pytest collects and runs tests, failing on the missing planned API.
- **Committed in:** `88b2bf5`

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** The fix preserves Wave 0 RED intent and avoids unrelated collection errors. No implementation scope was added.

## Issues Encountered

- RED verification fails as intended because implementation entry points are not yet present:
  - `tsc_cycle.sample_inputs.build_v3_phase2_reservoir`
  - `tsc_cycle.teacher.labeler.build_parser`
  - `tsc_cycle.teacher.labeler.run_labeling`
  - `tsc_cycle.v3_gates.phase2_datagen_report.build_phase2_report`

## Verification

- `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest -q tests/test_v3_datagen_inputs.py` collected and ran 4 tests; all failed on missing `build_v3_phase2_reservoir` behavior as expected for RED.
- `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest -q tests/test_v3_labeler.py` collected and ran 4 tests; all failed on missing `build_parser`/`run_labeling` behavior as expected for RED.
- `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest -q tests/test_v3_datagen_merge.py` collected and ran 4 tests; all failed on missing `phase2_datagen_report` behavior as expected for RED.
- Combined Wave 0 command collected and ran 12 tests; all failures are planned missing implementation symbols or APIs.

## Known Stubs

None. The new files are tests/fixtures only; planned missing production APIs are RED targets, not committed stubs.

## User Setup Required

None - no external service configuration required for Wave 0 tests.

## Next Phase Readiness

Ready for `02-02-PLAN.md` to implement the three-source isolated Phase 2 input reservoir generator against the RED tests.

## Self-Check: PASSED

- Found `tests/conftest.py`, `tests/test_v3_datagen_inputs.py`, `tests/test_v3_labeler.py`, and `tests/test_v3_datagen_merge.py`.
- Found task commits `88b2bf5`, `4a91e17`, and `039503a`.
- Verified focused pytest commands collect and fail only on planned missing Phase 2 implementation APIs.

---
*Phase: 02-10k-7k*
*Completed: 2026-05-08*
