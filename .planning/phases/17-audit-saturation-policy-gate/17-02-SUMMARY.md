---
phase: 17-audit-saturation-policy-gate
plan: "02"
subsystem: offline-audit-gate
tags: [python, pytest, jsonl, saturation-policy, prompt-protocol]

requires:
  - phase: 17-audit-saturation-policy-gate
    provides: canonical saturation policy core from Plan 01
provides:
  - Safe Phase 17 maintainer CLI/report writer constrained to artifacts/v4/phase17
  - Configurable fail-closed saturation threshold gate for data, replay, and eval-style phase-decision rows
  - Prompt protocol guard proving v4 deployment prompt bytes stay unchanged and explicit band rules stay offline-only
affects: [phase-18-calibrated-dataset-rebuild, phase-20-evaluation-replay]

tech-stack:
  added: []
  patterns: [stdlib argparse CLI, allow_nan_false JSON reports, reusable fail-closed threshold gate, byte-for-byte prompt guard]

key-files:
  created:
    - tsc_cycle/v4_gates/phase17_audit.py
    - artifacts/v4/phase17/saturation_audit_report.json
    - artifacts/v4/phase17/saturation_policy_gate.json
    - artifacts/v4/phase17/prompt_protocol_report.json
  modified:
    - tests/test_v4_phase17_saturation_policy.py
    - .planning/STATE.md
    - .planning/ROADMAP.md
    - .planning/REQUIREMENTS.md

key-decisions:
  - "Use deterministic default thresholds for POLICY-02 and expose every value through CLI/API overrides."
  - "Keep sat_ge_1.0_allowed_max outside low-saturation max-green failure thresholds because max-green is allowed for saturated rows."
  - "Guard prompt protocol by hashing a deterministic build_user_prompt fixture and scanning in-repo prompt helper surfaces without editing prompt_builder.py."

patterns-established:
  - "Phase 17 reports use ok/next_phase_allowed/fatal_failures plus artifacts/v4/phase17-only path guards."
  - "Data, replay, and eval phase-decision outputs share evaluate_saturation_policy_gate rather than duplicating threshold logic."
  - "Prompt policy leakage is checked as an offline report gate, not by changing deployment prompts."

requirements-completed: [AUDIT-01, AUDIT-02, POLICY-01, POLICY-02, POLICY-03]

duration: 9 min
completed: 2026-05-18
---

# Phase 17 Plan 02: Offline CLI Gate and Prompt Protocol Summary

**Safe Phase 17 JSON report CLI with reusable saturation threshold failures and byte-for-byte v4 prompt protocol guard**

## Performance

- **Duration:** 9 min
- **Started:** 2026-05-18T06:43:26Z
- **Completed:** 2026-05-18T06:52:36Z
- **Tasks:** 3
- **Files modified:** 8

## Accomplishments

- Added `tsc_cycle/v4_gates/phase17_audit.py` with safe JSON writers, parser defaults, artifact-root guards, CLI exit semantics, and integrated report orchestration.
- Implemented `DEFAULT_THRESHOLDS` and `evaluate_saturation_policy_gate(...)` so data, replay, and eval-style rows fail closed on configured low-saturation max-green threshold excess.
- Added `evaluate_prompt_protocol_guard(...)` to lock the v4 prompt fixture hash and scan prompt helper surfaces for explicit saturation band snippets without modifying `prompt_builder.py`.
- Generated committed Phase 17 JSON artifacts under `artifacts/v4/phase17/` showing current v4 data/replay fail the new policy thresholds while prompt protocol guard passes.

## Task Commits

Each task was committed atomically:

1. **Task 1: Safe Phase 17 CLI/report artifact writer** - `56cc7b5` (feat)
2. **Task 2 RED: Reusable threshold gate contracts** - `8e466d2` (test)
3. **Task 2 GREEN: Reusable threshold gate implementation** - `b67c6c8` (feat)
4. **Task 3 RED: Prompt protocol guard contracts** - `45eae1f` (test)
5. **Task 3 GREEN: Prompt protocol guard implementation** - `eadba92` (feat)
6. **Plan artifact capture: Generated Phase 17 reports** - `2714377` (chore)

**Plan metadata:** pending final metadata commit

## Files Created/Modified

- `tsc_cycle/v4_gates/phase17_audit.py` - Phase 17 CLI, safe writers, threshold gate, integrated audit reports, and prompt protocol guard.
- `tests/test_v4_phase17_saturation_policy.py` - Parser/path/CLI, threshold gate, eval-output, and prompt protocol contract tests.
- `artifacts/v4/phase17/saturation_audit_report.json` - Banded dataset and replay audit statistics with representative failures.
- `artifacts/v4/phase17/saturation_policy_gate.json` - Fail-closed policy gate report for current v4 evidence.
- `artifacts/v4/phase17/prompt_protocol_report.json` - Prompt hash and forbidden-snippet scan evidence.
- `.planning/STATE.md` - Phase 17 position, decisions, and next action updated.
- `.planning/ROADMAP.md` - Phase 17 marked complete.
- `.planning/REQUIREMENTS.md` - POLICY-02 and POLICY-03 marked complete.

## Decisions Made

- Used strict default thresholds from the resolved research contract and exposed CLI overrides for every threshold key.
- Left saturated rows (`sat_ge_1.0_allowed_max`) without a max-green failure threshold; this is reported as allowed behavior.
- Stored generated JSON gate artifacts because they are the maintainer-facing Phase 17 report outputs.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- The integration CLI returns exit code 1 on current v4 artifacts because the newly enforced POLICY-02 thresholds intentionally detect low-saturation max-green excess. This is expected success behavior for the gate and is documented in the generated `saturation_policy_gate.json` fatal failures.

## User Setup Required

None - no external service configuration required.

## Known Stubs

None.

## Threat Flags

None - new security-relevant surfaces were the planned offline CLI filesystem writes and prompt-surface scans, both covered by the plan threat model.

## Verification

- `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest tests/test_v4_phase17_saturation_policy.py -q` — PASS
- `/home/samuel/TSC_CYCLE/.venv/bin/python -m tsc_cycle.v4_gates.phase17_audit --out /home/samuel/TSC_CYCLE/artifacts/v4/phase17/saturation_policy_gate.json` — EXPECTED RED / exit 1 with fatal threshold failures
- `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest tests/test_v4_phase17_saturation_policy.py tests/test_phase12_reality_log_generation.py tests/test_v4_phase8_dataset_rebuild.py -q` — PASS

## TDD Gate Compliance

- RED commits present: `8e466d2`, `45eae1f`
- GREEN commits present: `56cc7b5`, `b67c6c8`, `eadba92`
- REFACTOR commits: none needed
- Note: Task 1 used a combined feature commit after adding its CLI tests; Tasks 2 and 3 followed explicit RED/GREEN commits.

## Self-Check: PASSED

- FOUND: `/home/samuel/TSC_CYCLE/tsc_cycle/v4_gates/phase17_audit.py`
- FOUND: `/home/samuel/TSC_CYCLE/tests/test_v4_phase17_saturation_policy.py`
- FOUND: `/home/samuel/TSC_CYCLE/artifacts/v4/phase17/saturation_audit_report.json`
- FOUND: `/home/samuel/TSC_CYCLE/artifacts/v4/phase17/saturation_policy_gate.json`
- FOUND: `/home/samuel/TSC_CYCLE/artifacts/v4/phase17/prompt_protocol_report.json`
- FOUND commits: `56cc7b5`, `8e466d2`, `b67c6c8`, `45eae1f`, `eadba92`, `2714377`

## Next Phase Readiness

Phase 18 can consume the Phase 17 policy gate and representative failures to rebuild calibrated training data. Current v4 artifacts fail the low-saturation threshold gate by design, so Phase 18 should filter or relabel those violations rather than loosening defaults for production validation.

---
*Phase: 17-audit-saturation-policy-gate*
*Completed: 2026-05-18*
