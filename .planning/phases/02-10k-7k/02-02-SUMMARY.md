---
phase: 02-10k-7k
plan: "02"
subsystem: datagen
tags: [pytest, jsonl, reservoir, targeted-sampling, manifest]
requires:
  - phase: 02-10k-7k
    provides: Wave 0 RED tests for Phase 2 DATAGEN-01 and DATAGEN-02
provides:
  - Three-source Phase 2 candidate reservoir builder
  - Reproducible CLI and shell wrapper for isolated v3 Phase 2 inputs
  - Generated 7,500-record candidate reservoir under data/v3/phase2
  - Manifest proving zero old overlap, zero self duplicates, and unchanged v1 labeled SHA
affects: [02-10k-7k, DATAGEN-01, DATAGEN-02, 02-03, 02-04, 02-05]
tech-stack:
  added: []
  patterns:
    - deterministic JSONL reservoir generation with content-addressed sample_id
    - frozen-baseline SHA gate before and after isolated artifact writes
    - targeted neighbor sampling from v1 eval high-MAE/lint-fail rows
key-files:
  created:
    - scripts/generate_v3_phase2_inputs.sh
    - data/v3/phase2/inputs_same_dist.jsonl
    - data/v3/phase2/inputs_ood.jsonl
    - data/v3/phase2/inputs_targeted.jsonl
    - data/v3/phase2/inputs_all.jsonl
    - data/v3/phase2/datagen_manifest.json
  modified:
    - tsc_cycle/sample_inputs.py
key-decisions:
  - "Phase 2 input generation writes only to data/v3/phase2 and treats data/labeled.jsonl as read-only exclude input."
  - "Targeted samples use v1 eval rows where lint_ok is false or mae > 10.0, then perturb numeric fields before recomputing sample_id."
patterns-established:
  - "Use build_v3_phase2_reservoir(prior, counts, seed, exclude_ids, per_sample_path) for deterministic same_dist/OOD/targeted reservoirs."
  - "Use scripts/generate_v3_phase2_inputs.sh for the canonical 5250/1500/750 reservoir gate."
requirements-completed: [DATAGEN-01, DATAGEN-02]
duration: 4 min
completed: 2026-05-08
---

# Phase 02 Plan 02: Three-source Isolated Phase 2 Input Reservoir Generator Summary

**Deterministic 7,500-record Phase 2 input reservoir with same-dist/OOD/targeted sources and frozen v1 baseline SHA gates**

## Performance

- **Duration:** 4 min
- **Started:** 2026-05-08T15:10:35Z
- **Completed:** 2026-05-08T15:14:50Z
- **Tasks:** 3
- **Files modified:** 7

## Accomplishments

- Added `build_v3_phase2_reservoir` in `tsc_cycle/sample_inputs.py` with exact `same_dist`, `ood`, and `targeted` source counts, deterministic IDs, and old-ID exclusion.
- Added targeted sampling from v1 eval failure neighborhoods (`lint_ok is False` or `mae > 10.0`) with numeric perturbation and provenance fields.
- Added a reproducible wrapper that generates the canonical 5,250 same-dist / 1,500 OOD / 750 targeted reservoir under `data/v3/phase2/`.
- Generated and committed `inputs_all.jsonl` with 7,500 records and `datagen_manifest.json` proving zero old overlap, zero self duplicates, and unchanged `data/labeled.jsonl` SHA.

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement three-source Phase 2 reservoir builder** - `b128f03` (feat)
2. **Task 2: Add reproducible Phase 2 reservoir CLI and wrapper** - `7eb29ab` (feat)
3. **Task 3 blocker fix: Run wrapper from project root** - `c285a16` (fix)
4. **Task 3: Execute and gate the Phase 2 reservoir before labeling** - `76f5b1c` (feat)

**Plan metadata:** committed after this summary.

## Files Created/Modified

- `tsc_cycle/sample_inputs.py` - Adds Phase 2 reservoir builder, targeted sampler, v3 CLI mode, manifest writing, and SHA gates.
- `scripts/generate_v3_phase2_inputs.sh` - Canonical executable wrapper using `/home/samuel/TSC_CYCLE/.venv/bin/python` and fixed 5250/1500/750 counts.
- `data/v3/phase2/inputs_same_dist.jsonl` - 5,250 same-distribution candidate inputs.
- `data/v3/phase2/inputs_ood.jsonl` - 1,500 OOD/boundary candidate inputs.
- `data/v3/phase2/inputs_targeted.jsonl` - 750 targeted candidate inputs derived from v1 high-MAE/lint-fail seeds.
- `data/v3/phase2/inputs_all.jsonl` - Combined 7,500-record reservoir for later labeling.
- `data/v3/phase2/datagen_manifest.json` - Source counts, dedupe/overlap gates, and baseline SHA evidence.

## Decisions Made

- Kept Phase 2 generation inside `tsc_cycle/sample_inputs.py` instead of creating a parallel generator, preserving existing same-dist/OOD primitives.
- Wrote all new artifacts under `data/v3/phase2/`; `data/labeled.jsonl` is only read as an exclusion set and SHA-checked before/after generation.
- Used existing v1 input files as lookup sources for per-sample eval seed IDs because the production per-sample eval rows contain seed IDs and metrics but not full input objects.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Made wrapper executable and root-relative**
- **Found during:** Task 3 (Execute and gate the Phase 2 reservoir before labeling)
- **Issue:** Direct execution initially failed because the new shell wrapper was not executable, and `python -m tsc_cycle.sample_inputs` resolved from the caller's working directory instead of the project root.
- **Fix:** Changed the wrapper to `cd /home/samuel/TSC_CYCLE` before invoking the module and committed the executable mode bit.
- **Files modified:** `scripts/generate_v3_phase2_inputs.sh`
- **Verification:** `/home/samuel/TSC_CYCLE/scripts/generate_v3_phase2_inputs.sh` executed successfully and produced the gated 7,500-record reservoir.
- **Committed in:** `c285a16`

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** The fix was required to run the planned wrapper reliably. No scope beyond Phase 2 reservoir generation was added.

## Issues Encountered

- Wrapper execution failed before the chmod/root fix; resolved in `c285a16` and re-run successfully.
- Existing unrelated Phase 1 working-tree modifications and untracked files were left untouched and were not staged.

## Verification

- `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest -q /home/samuel/TSC_CYCLE/tests/test_v3_datagen_inputs.py` passed: 4 tests.
- `bash -n /home/samuel/TSC_CYCLE/scripts/generate_v3_phase2_inputs.sh` passed.
- Phase 2 artifact gate passed with `inputs_all.jsonl` line count 7,500 and source counts `same_dist=5250`, `ood=1500`, `targeted=750`.
- `datagen_manifest.json` records `overlap_with_old_labeled: 0`, `self_duplicate_count: 0`, and matching SHA fields: `2214301555f22640e542234abcd9c5f0e3f6982df08c894124af45367ad30809`.

## Known Stubs

None. No placeholders/TODO/FIXME markers were found in the files created or modified by this plan.

## Threat Flags

None. This plan introduced no network endpoints, auth paths, schema trust-boundary changes, or secret handling.

## User Setup Required

None - no external service configuration required for input reservoir generation.

## Next Phase Readiness

Ready for `02-03-PLAN.md` to harden the Phase 2-safe GPT-5.5 high labeler and run smoke/full labeling wrappers against `data/v3/phase2/inputs_all.jsonl`.

## Self-Check: PASSED

- Found `tsc_cycle/sample_inputs.py`, `scripts/generate_v3_phase2_inputs.sh`, `data/v3/phase2/inputs_all.jsonl`, and `data/v3/phase2/datagen_manifest.json`.
- Found task commits `b128f03`, `7eb29ab`, `c285a16`, and `76f5b1c`.
- Verified focused pytest, wrapper syntax, generated record counts, zero old overlap, zero self duplicates, and unchanged old SHA.

---
*Phase: 02-10k-7k*
*Completed: 2026-05-08*
