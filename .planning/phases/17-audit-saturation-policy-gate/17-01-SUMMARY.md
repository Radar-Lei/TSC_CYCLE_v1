---
phase: 17-audit-saturation-policy-gate
plan: "01"
subsystem: offline-audit-gate
tags: [python, pytest, jsonl, saturation-policy, v4-gates]

requires:
  - phase: 16-verification-and-handoff
    provides: v4.0 reproduction package and Phase 12 replay artifacts
provides:
  - Canonical saturation band classifier for POLICY-01 half-open intervals
  - Dataset and replay per-phase projection rows for AUDIT-01/AUDIT-02
  - Banded audit aggregation with deterministic representative examples
affects: [phase-17-plan-02, phase-18-calibrated-dataset-rebuild, phase-20-evaluation-replay]

tech-stack:
  added: []
  patterns: [stdlib JSONL fail-closed ingestion, per-phase audit rows, TDD red-green commits]

key-files:
  created:
    - tsc_cycle/v4_gates/saturation_policy.py
    - tests/test_v4_phase17_saturation_policy.py
  modified: []

key-decisions:
  - "Keep saturation policy as an offline v4_gates module; do not modify deployment prompts."
  - "Treat per-phase min_green == max_green rows as forced/trivial denominator rows, not policy failures."
  - "Use Phase 8 split indexes and Phase 12 structured replay evidence before ambiguous hints or rendered-log parsing."

patterns-established:
  - "Per-phase audit row contract: origin_artifact, sample_id, phase_id, pred_saturation, band, min/max/final green, split, source, violation category, trivial flag."
  - "Audit denominators expose total, included, trivial, excluded, and unsaturated max-green counts separately."

requirements-completed: [AUDIT-01, AUDIT-02, POLICY-01]

duration: 8 min
completed: 2026-05-18
---

# Phase 17 Plan 01: Canonical Saturation Policy Core Summary

**Offline saturation-policy core with canonical half-open bands, per-phase dataset/replay projectors, and deterministic representative max-green violation examples**

## Performance

- **Duration:** 8 min
- **Started:** 2026-05-18T06:32:20Z
- **Completed:** 2026-05-18T06:40:35Z
- **Tasks:** 3
- **Files modified:** 2

## Accomplishments

- Added `classify_saturation_band` and `classify_violation` as the single POLICY-01 interpretation point.
- Added dataset and Phase 12 replay projectors that validate hard constraints and expose malformed/invalid evidence instead of silently improving denominators.
- Added `compute_saturation_audit` with band/split/source/origin counts, trivial-row separation, excluded counts, and deterministic representative examples.

## Task Commits

Each task was committed atomically:

1. **Task 1 RED: Implement canonical saturation bands and violation categories** - `7c543cd` (test)
2. **Task 1 GREEN: Implement canonical saturation bands and violation categories** - `b9a2666` (feat)
3. **Task 2 RED: Project dataset and replay artifacts into per-phase audit rows** - `f6559b4` (test)
4. **Task 2 GREEN: Project dataset and replay artifacts into per-phase audit rows** - `4591f94` (feat)
5. **Task 3 RED: Compute banded statistics and representative failure examples** - `b3c241c` (test)
6. **Task 3 GREEN: Compute banded statistics and representative failure examples** - `ee1e4c3` (feat)

**Plan metadata:** pending final metadata commit

## Files Created/Modified

- `tsc_cycle/v4_gates/saturation_policy.py` - Canonical Phase 17 saturation classifier, dataset/replay projectors, and audit aggregation.
- `tests/test_v4_phase17_saturation_policy.py` - TDD contract tests for boundaries, fail-closed projection, denominators, and representative examples.

## Decisions Made

- Kept policy logic offline under `tsc_cycle/v4_gates/`; no deployment prompt files were modified.
- Classified forced per-phase ranges separately as `forced_trivial_range` to avoid false low-saturation failures.
- Preferred Phase 8 split index membership and Phase 12 manifest/per-sample structured evidence for provenance and alignment.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Known Stubs

None.

## Verification

- `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest /home/samuel/TSC_CYCLE/tests/test_v4_phase17_saturation_policy.py -q` — PASS
- `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest /home/samuel/TSC_CYCLE/tests/test_v4_phase17_saturation_policy.py /home/samuel/TSC_CYCLE/tests/test_phase12_reality_log_generation.py /home/samuel/TSC_CYCLE/tests/test_v4_phase8_dataset_rebuild.py -q` — PASS

## TDD Gate Compliance

- RED commits present: `7c543cd`, `f6559b4`, `b3c241c`
- GREEN commits present: `b9a2666`, `4591f94`, `ee1e4c3`
- REFACTOR commits: none needed

## Self-Check: PASSED

- FOUND: `/home/samuel/TSC_CYCLE/tsc_cycle/v4_gates/saturation_policy.py`
- FOUND: `/home/samuel/TSC_CYCLE/tests/test_v4_phase17_saturation_policy.py`
- FOUND commits: `7c543cd`, `b9a2666`, `f6559b4`, `4591f94`, `b3c241c`, `ee1e4c3`

## Next Phase Readiness

Plan 02 can add CLI/report gate, threshold enforcement, and prompt protocol guard on top of the shared saturation policy core.

---
*Phase: 17-audit-saturation-policy-gate*
*Completed: 2026-05-18*
