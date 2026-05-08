---
phase: 02-10k-7k
plan: "04"
subsystem: datagen
tags: [merge-gate, jsonl, constraint-lint, frozen-baseline, wrapper]
requires:
  - phase: 02-10k-7k
    provides: Phase 2 isolated input reservoir and Phase 2-safe GPT-5.5 high labeler outputs
provides:
  - Fail-closed Phase 2 old/new label merge report builder
  - CLI and wrapper for producing Phase 3 raw merged JSONL only after gates pass
  - DATAGEN-01..07 merge evidence fields including labeler and resume/no-duplicate evidence
affects: [02-10k-7k, DATAGEN-01, DATAGEN-02, DATAGEN-03, DATAGEN-04, DATAGEN-05, DATAGEN-06, DATAGEN-07, 02-05, 03-dataset-rebuild]
tech-stack:
  added: []
  patterns:
    - fail-closed JSONL merge gates with frozen baseline SHA evidence
    - constraint_lint revalidation of every accepted new label before merge
    - operational shell wrapper with git diff guards around protected data/labeled.jsonl
key-files:
  created:
    - tsc_cycle/v3_gates/phase2_datagen_report.py
    - scripts/run_v3_phase2_merge.sh
  modified: []
key-decisions:
  - "Phase 2 merge writes labeled_merged.jsonl only when all fatal data-governance gates pass; failed reports do not overwrite an existing merged output."
  - "Merge evidence treats DATAGEN-03 and DATAGEN-05 as first-class report objects via labeler_evidence and resume_evidence."
patterns-established:
  - "Use build_phase2_report(...) for offline merge evidence and fail-closed raw dataset assembly."
  - "Use scripts/run_v3_phase2_merge.sh as the canonical wrapper after full labeling has produced labeled_new.jsonl and rejected_new.jsonl."
requirements-completed: [DATAGEN-01, DATAGEN-02, DATAGEN-03, DATAGEN-04, DATAGEN-05, DATAGEN-06, DATAGEN-07]
duration: 4 min
completed: 2026-05-08
---

# Phase 02 Plan 04: Phase 2 Merge/Report Gate Summary

**Fail-closed Phase 2 JSONL merge gate with frozen v1 SHA protection, new-label lint revalidation, labeler evidence, and resume/no-duplicate reporting**

## Performance

- **Duration:** 4 min
- **Started:** 2026-05-08T15:43:13Z
- **Completed:** 2026-05-08T15:46:53Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Added `build_phase2_report(...)` and CLI entry point in `tsc_cycle/v3_gates/phase2_datagen_report.py`.
- Implemented fail-closed gates for old SHA stability, expected old SHA, old/new overlap, accepted-new lint, minimum new valid count, minimum merged valid count, worker cap, labeler model/effort, append-output presence, and duplicate done IDs.
- Added report evidence for DATAGEN-03 (`labeler_evidence`) and DATAGEN-05 (`resume_evidence`) alongside DATAGEN-01..07 `requirements_covered`.
- Added `scripts/run_v3_phase2_merge.sh` using the project venv, fixed Phase 2 thresholds, and `git diff --quiet -- data/labeled.jsonl` before and after the merge command.

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement fail-closed Phase 2 report builder** - `1b166f1` (feat)
2. **Task 2: Add merge CLI and operational wrapper** - `7dbef6c` (feat)

**Plan metadata:** committed after this summary.

## Files Created/Modified

- `tsc_cycle/v3_gates/phase2_datagen_report.py` - Phase 2 merge/report builder, CLI parser, fail-closed gate logic, lint revalidation, labeler/resume evidence, and conditional merged JSONL writer.
- `scripts/run_v3_phase2_merge.sh` - Canonical Phase 2 merge wrapper with absolute venv Python, fixed thresholds, default v3 paths, and frozen-baseline diff guards.

## Decisions Made

- Kept the merge/report gate separate from tokenization and split work; Phase 3 remains responsible for dataset rebuild.
- Used `constraint_lint.validate()` as the only accepted-new lint authority instead of introducing a parallel schema validator.
- Reported worker/model/effort evidence as explicit fatal gates so the merge fails closed if Phase 2 labeler evidence does not match GPT-5.5 high with workers ≤10.

## Deviations from Plan

None - plan executed exactly as written.

**Total deviations:** 0 auto-fixed.
**Impact on plan:** No scope change.

## Issues Encountered

- Existing unrelated Phase 1 modifications and operational smoke artifacts were present in the working tree and intentionally left unstaged/uncommitted.
- No implementation blockers were encountered.

## Verification

- `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest -q /home/samuel/TSC_CYCLE/tests/test_v3_datagen_merge.py` passed: 4 tests.
- `/home/samuel/TSC_CYCLE/.venv/bin/python -m py_compile /home/samuel/TSC_CYCLE/tsc_cycle/v3_gates/phase2_datagen_report.py` passed.
- `bash -n /home/samuel/TSC_CYCLE/scripts/run_v3_phase2_merge.sh` passed.
- Acceptance checks confirmed wrapper contains `--min-new-valid 6000`, `--min-merged-valid 9000`, `labeled_merged.jsonl`, and `merge_report.json`.
- Acceptance checks confirmed wrapper runs `git diff --quiet -- data/labeled.jsonl` before and after the merge command.

## Known Stubs

None. Stub-pattern scan of files created by this plan found no TODO/FIXME/placeholders or hardcoded empty UI values.

## Threat Flags

None. The trust-boundary surfaces introduced by this plan are the planned offline JSONL merge boundary and frozen-baseline SHA boundary, both covered by the plan threat model and mitigated by fail-closed gates.

## User Setup Required

None - no external service configuration required for the merge/report gate. The wrapper should be run only after full Phase 2 labeling has produced `data/v3/phase2/labeled_new.jsonl` and `data/v3/phase2/rejected_new.jsonl`.

## Next Phase Readiness

Ready for `02-05-PLAN.md` to consume the Phase 2 merge/report gate and execute or verify final Phase 2 data-governance artifacts once full new-label outputs are available.

## Self-Check: PASSED

- Found `/home/samuel/TSC_CYCLE/tsc_cycle/v3_gates/phase2_datagen_report.py`.
- Found `/home/samuel/TSC_CYCLE/scripts/run_v3_phase2_merge.sh`.
- Found task commits `1b166f1` and `7dbef6c` in git log.
- Verified focused pytest, py_compile, wrapper syntax, and acceptance criteria all pass.

---
*Phase: 02-10k-7k*
*Completed: 2026-05-08*
