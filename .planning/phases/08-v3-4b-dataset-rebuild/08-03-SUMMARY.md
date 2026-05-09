---
phase: 08-v3-4b-dataset-rebuild
plan: 03
subsystem: data
tags: [dataset-rebuild, qwen3-4b, aggregate-gate, shell-wrapper, v4]

requires:
  - phase: 08-v3-4b-dataset-rebuild
    provides: v4 source, cleaning, split, and rebuild artifacts from Plan 08-02
  - phase: 07-4b-baseline-label-protocol-gate
    provides: Phase 7 next-phase handoff and native think tokenizer audit
provides:
  - fail-closed aggregate Phase 8 gate report for DATA4B handoff into Phase 9
  - fixed-argv one-command wrapper for v4 dataset rebuild plus aggregate report generation
affects: [phase9-4b-qlora-retrain, DATA4B, phase8-dataset-card]

tech-stack:
  added: []
  patterns:
    - Aggregate JSON artifact gates include loaded data, requirement coverage, fatal failures, artifact paths, and hashes
    - Fixed absolute shell argv with quoted variables and no environment mutation

key-files:
  created:
    - tsc_cycle/v4_gates/phase8_report.py
    - scripts/run_v4_phase8_dataset_rebuild.sh
    - artifacts/v4/phase8/phase8_gate_report.json
  modified: []

key-decisions:
  - "Phase 8 aggregate reporting intentionally keeps next_phase_allowed=false until the dataset card Phase 8 section is added in Plan 08-04."
  - "The self-referential phase8_gate_report hash is recorded as a sentinel rather than a changing content hash so repeated CLI runs are deterministic."

patterns-established:
  - "Phase 8 handoff gates fail closed on missing/malformed JSON, red sub-artifacts, incomplete DATA4B coverage, bad truncation/native-think evidence, and missing dataset card evidence."
  - "Phase 8 wrappers use fixed /home/samuel/TSC_CYCLE paths and explicit v1/v3 source arguments instead of a merged-source shortcut."

requirements-completed: [DATA4B-01, DATA4B-02, DATA4B-03, DATA4B-04]

duration: 6min
completed: 2026-05-09
---

# Phase 08 Plan 03: Phase 8 Aggregate Gate and Wrapper Summary

**Fail-closed Phase 8 DATA4B aggregate handoff gate plus fixed-argv v4 rebuild wrapper for Qwen3-4B dataset artifacts**

## Performance

- **Duration:** 6 min
- **Started:** 2026-05-09T17:51:45Z
- **Completed:** 2026-05-09T17:57:23Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Added `tsc_cycle/v4_gates/phase8_report.py` with `evaluate_phase8_report`, `build_parser`, and `main` for aggregate DATA4B gate evaluation.
- Created `artifacts/v4/phase8/phase8_gate_report.json`; it currently fails closed only on the missing dataset card Phase 8 section expected before Plan 08-04.
- Added executable `scripts/run_v4_phase8_dataset_rebuild.sh` with fixed absolute v4/Qwen3-4B source paths and chained aggregate report generation.

## Task Commits

1. **Task 1: Implement fail-closed Phase 8 aggregate report** - `c5da615` (feat)
2. **Task 2: Add fixed-argv Phase 8 rebuild wrapper** - `7af366a` (chore)
3. **Task 1 fix: Stabilize Phase 8 report manifest** - `127cbf7` (fix)

**Plan metadata:** pending final docs commit

## Files Created/Modified

- `tsc_cycle/v4_gates/phase8_report.py` - fail-closed Phase 8 aggregate evaluator and CLI.
- `scripts/run_v4_phase8_dataset_rebuild.sh` - executable one-command rebuild/report wrapper with fixed absolute paths.
- `artifacts/v4/phase8/phase8_gate_report.json` - aggregate handoff report showing Phase 9 remains blocked until dataset card coverage is added.
- `.planning/phases/08-v3-4b-dataset-rebuild/08-03-SUMMARY.md` - this execution summary.

## Verification

- `PYTHONPATH=/home/samuel/TSC_CYCLE /home/samuel/TSC_CYCLE/.venv/bin/python -m pytest -q /home/samuel/TSC_CYCLE/tests/test_v4_phase8_dataset_rebuild.py`
  - Result: 10 passed.
- `bash -n /home/samuel/TSC_CYCLE/scripts/run_v4_phase8_dataset_rebuild.sh`
  - Result: passed.
- Aggregate report CLI:
  - `PYTHONPATH=/home/samuel/TSC_CYCLE /home/samuel/TSC_CYCLE/.venv/bin/python -m tsc_cycle.v4_gates.phase8_report --out /home/samuel/TSC_CYCLE/artifacts/v4/phase8/phase8_gate_report.json`
  - Result: exit code 1 as expected before Plan 08-04 because `dataset_card_v4_section` is red.
- Acceptance greps passed for DATA4B-04/DATA4B-05 mentions and wrapper fixed source/model paths; forbidden merged-source, install/sudo/eval/vllm/flash-attn, and frozen-run path patterns were absent.

## Decisions Made

- Kept the aggregate handoff strict: `next_phase_allowed` mirrors overall `ok`, so Phase 9 remains blocked until dataset card evidence exists.
- Accepted the existing RED-contract dataset card heading variant in tests while keeping the stricter planned heading as the default missing-section diagnostic.
- Used `self-referential-report` for the report's own hash entry to avoid non-deterministic hash drift across repeated CLI writes.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Stabilized phase8 report self-hash drift**
- **Found during:** Overall verification after Task 2
- **Issue:** Re-running the aggregate CLI changed the hash recorded for `phase8_gate_report.json` because the report was hashing a payload that then embedded that hash.
- **Fix:** Recorded the report path in `artifact_manifest.paths` and used a deterministic `self-referential-report` sentinel for its own hash entry.
- **Files modified:** `tsc_cycle/v4_gates/phase8_report.py`, `artifacts/v4/phase8/phase8_gate_report.json`
- **Verification:** Re-ran tests and the aggregate CLI twice; report output no longer drifted after generation.
- **Committed in:** `127cbf7`

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** The fix preserves the planned artifact manifest while making the CLI reproducible.

## Issues Encountered

- The aggregate report intentionally exits non-zero before Plan 08-04 because `data/dataset_card.md` does not yet contain the v4 Phase 8 dataset card section.

## User Setup Required

None - no external service configuration required.

## Known Stubs

None detected in files created/modified by this plan. The string `PENDING` appears only as a forbidden-marker check in `phase8_report.py`, not as placeholder output.

## Threat Flags

None - the plan adds local filesystem/JSON artifact gates and a fixed-argv wrapper only; no network endpoints, auth paths, or new external trust boundaries were introduced beyond the planned artifact and wrapper boundaries.

## Next Phase Readiness

- Plan 08-04 can update `data/dataset_card.md` with real source hashes, split hashes, normalization count, and artifact boundaries.
- After the dataset card section is added, the same wrapper and aggregate CLI should turn `phase8_gate_report.json` green and allow Phase 9 planning/execution.

## Self-Check: PASSED

- Found `tsc_cycle/v4_gates/phase8_report.py`.
- Found `scripts/run_v4_phase8_dataset_rebuild.sh`.
- Found `artifacts/v4/phase8/phase8_gate_report.json`.
- Found `.planning/phases/08-v3-4b-dataset-rebuild/08-03-SUMMARY.md`.
- Found task commit `c5da615` in git history.
- Found task commit `7af366a` in git history.
- Found task fix commit `127cbf7` in git history.
  

---
*Phase: 08-v3-4b-dataset-rebuild*
*Completed: 2026-05-09*
