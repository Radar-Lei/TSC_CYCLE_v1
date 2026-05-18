---
phase: 17-audit-saturation-policy-gate
plan: "03"
subsystem: offline-audit-gate
tags: [python, pytest, jsonl, saturation-policy, prompt-protocol, gap-closure]

requires:
  - phase: 17-audit-saturation-policy-gate
    provides: Plans 01-02 saturation audit core, CLI gate, and verification gap report
provides:
  - Independent frozen v4 prompt protocol fixture and sha256 for POLICY-03 drift detection
  - Phase-17-scoped artifact-root trust boundary for report writers
  - Top-level representative audit examples covering both dataset and replay/reality origins
affects: [phase-18-calibrated-dataset-rebuild, phase-20-evaluation-replay]

tech-stack:
  added: []
  patterns: [frozen prompt fixture, Phase-17-scoped safe report roots, per-origin representative example selection]

key-files:
  created:
    - tsc_cycle/v4_gates/fixtures/v4_prompt_protocol_golden.json
    - .planning/phases/17-audit-saturation-policy-gate/17-03-SUMMARY.md
  modified:
    - tsc_cycle/v4_gates/phase17_audit.py
    - tsc_cycle/v4_gates/saturation_policy.py
    - tests/test_v4_phase17_saturation_policy.py
    - artifacts/v4/phase17/saturation_audit_report.json
    - artifacts/v4/phase17/saturation_policy_gate.json
    - artifacts/v4/phase17/prompt_protocol_report.json

key-decisions:
  - "Store POLICY-03 expected prompt bytes in an independent JSON fixture instead of recomputing them from build_user_prompt at import time."
  - "Accept only artifact roots whose resolved path is explicitly an artifacts/v4/phase17 subtree."
  - "Select representative audit examples by deterministic per-origin coverage before filling remaining slots globally."

patterns-established:
  - "Prompt drift guard compares runtime build_user_prompt output to a committed frozen fixture text/hash."
  - "Report writers validate both the artifact root and every output path before creating directories."
  - "Audit examples reserve one deterministic violation per origin before global top-N fill."

requirements-completed: [AUDIT-02, POLICY-03]

duration: 6 min
completed: 2026-05-18
---

# Phase 17 Plan 03: Gap Closure Summary

**Independent prompt drift fixture, safe Phase 17 artifact-root validation, and dataset plus replay representative audit examples**

## Performance

- **Duration:** 6 min
- **Started:** 2026-05-18T07:27:49Z
- **Completed:** 2026-05-18T07:34:48Z
- **Tasks:** 3
- **Files modified:** 7

## Accomplishments

- Replaced the self-referential POLICY-03 prompt golden with `v4_prompt_protocol_golden.json`, including frozen prompt text, fixture input, and sha256.
- Added pre-import prompt drift regression coverage proving a monkeypatched `build_user_prompt` no longer becomes the expected golden.
- Constrained `--artifact-root` to resolved `artifacts/v4/phase17` subtrees and kept per-write output path validation before directory creation.
- Changed representative example selection so top-level audit output includes both `dataset:labeled_merged.jsonl` and `replay:phase12` when both origins have violations.
- Regenerated Phase 17 JSON reports; policy gate remains expected red because current evidence still violates configured saturation thresholds.

## Task Commits

Each task was committed atomically:

1. **Task 1 RED: Replace self-referential prompt golden with frozen fixture and drift regression** - `7b657e7` (test)
2. **Task 1 GREEN: Replace self-referential prompt golden with frozen fixture and drift regression** - `d40daea` (feat)
3. **Task 2 RED: Constrain artifact-root trust boundary to Phase 17 report subtree** - `11d4a87` (test)
4. **Task 2 GREEN: Constrain artifact-root trust boundary to Phase 17 report subtree** - `3046a25` (fix)
5. **Task 3 RED: Guarantee top-level representative examples cover dataset and replay origins** - `7be88a2` (test)
6. **Task 3 GREEN: Guarantee top-level representative examples cover dataset and replay origins** - `cc36e4c` (fix)
7. **Rule 1 fix: Restore prompt module isolation after drift regression** - `b0978ac` (fix)

**Plan metadata:** pending final metadata commit

## Files Created/Modified

- `tsc_cycle/v4_gates/fixtures/v4_prompt_protocol_golden.json` - Independent frozen v4 prompt fixture text/hash used by the prompt protocol guard.
- `tsc_cycle/v4_gates/phase17_audit.py` - Loads frozen prompt fixture and validates Phase-17-scoped artifact roots before report writing.
- `tsc_cycle/v4_gates/saturation_policy.py` - Selects representative violations with per-origin coverage before deterministic global fill.
- `tests/test_v4_phase17_saturation_policy.py` - Adds prompt drift, broad-root rejection, and representative-origin regression coverage.
- `artifacts/v4/phase17/saturation_audit_report.json` - Regenerated top-level audit with dataset and replay representative examples.
- `artifacts/v4/phase17/saturation_policy_gate.json` - Regenerated gate artifact with unchanged expected red threshold failures.
- `artifacts/v4/phase17/prompt_protocol_report.json` - Regenerated prompt protocol report using the independent fixture.

## Decisions Made

- Used a committed JSON fixture for prompt bytes and hash to make the byte-for-byte guard independent of the implementation under test.
- Treated broad roots (`repo`, `data`, `tsc_cycle`, `artifacts`, `artifacts/v4`) as invalid even if individual output paths would later be checked.
- Kept saturation thresholds unchanged; this gap closure only fixes audit/report correctness, not policy strictness.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Restored prompt module isolation after pre-import drift test**
- **Found during:** Overall verification after Task 3
- **Issue:** The drift regression re-imported `phase17_audit` while `build_user_prompt` was still monkeypatched, leaving a contaminated module in `sys.modules` and causing the integrated prompt report test to fail later.
- **Fix:** Removed the re-import inside the monkeypatch scope so pytest restores `build_user_prompt` before subsequent imports rebuild `phase17_audit`.
- **Files modified:** `tests/test_v4_phase17_saturation_policy.py`
- **Verification:** `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest /home/samuel/TSC_CYCLE/tests/test_v4_phase17_saturation_policy.py -q` — PASS
- **Committed in:** `b0978ac`

---

**Total deviations:** 1 auto-fixed (1 Rule 1 bug)
**Impact on plan:** The fix was required to keep the new regression isolated; no scope expansion.

## Issues Encountered

- The Phase 17 CLI still exits 1 because current v4 evidence violates the existing saturation policy thresholds. This is expected and was verified as the intended red gate behavior.

## User Setup Required

None - no external service configuration required.

## Known Stubs

None.

## Threat Flags

None - the security-relevant surfaces were the planned prompt fixture, CLI filesystem trust boundary, and report example selection.

## Verification

- `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest /home/samuel/TSC_CYCLE/tests/test_v4_phase17_saturation_policy.py::test_prompt_protocol_unchanged_and_no_band_rule /home/samuel/TSC_CYCLE/tests/test_v4_phase17_saturation_policy.py::test_prompt_protocol_guard_fails_on_preimport_prompt_drift -q` — PASS
- `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest /home/samuel/TSC_CYCLE/tests/test_v4_phase17_saturation_policy.py::test_phase17_report_paths_are_constrained_to_artifact_root /home/samuel/TSC_CYCLE/tests/test_v4_phase17_saturation_policy.py::test_phase17_cli_rejects_broad_artifact_root -q` — PASS
- `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest /home/samuel/TSC_CYCLE/tests/test_v4_phase17_saturation_policy.py::test_representative_failures_include_dataset_and_replay_fields /home/samuel/TSC_CYCLE/tests/test_v4_phase17_saturation_policy.py::test_representative_examples_keep_replay_when_dataset_exhausts_limit -q` — PASS
- `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest /home/samuel/TSC_CYCLE/tests/test_v4_phase17_saturation_policy.py -q` — PASS
- `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest /home/samuel/TSC_CYCLE/tests/test_v4_phase17_saturation_policy.py /home/samuel/TSC_CYCLE/tests/test_phase12_reality_log_generation.py /home/samuel/TSC_CYCLE/tests/test_v4_phase8_dataset_rebuild.py -q` — PASS
- `/bin/bash -lc 'cd /home/samuel/TSC_CYCLE && /home/samuel/TSC_CYCLE/.venv/bin/python -m tsc_cycle.v4_gates.phase17_audit; test "$?" -eq 1'` — PASS / expected red policy gate

## TDD Gate Compliance

- RED commits present: `7b657e7`, `11d4a87`, `7be88a2`
- GREEN commits present: `d40daea`, `3046a25`, `cc36e4c`
- Rule 1 fix commit present after verification: `b0978ac`
- REFACTOR commits: none needed

## Self-Check: PASSED

- FOUND: `/home/samuel/TSC_CYCLE/tsc_cycle/v4_gates/fixtures/v4_prompt_protocol_golden.json`
- FOUND: `/home/samuel/TSC_CYCLE/tsc_cycle/v4_gates/phase17_audit.py`
- FOUND: `/home/samuel/TSC_CYCLE/tsc_cycle/v4_gates/saturation_policy.py`
- FOUND: `/home/samuel/TSC_CYCLE/tests/test_v4_phase17_saturation_policy.py`
- FOUND: `/home/samuel/TSC_CYCLE/artifacts/v4/phase17/saturation_audit_report.json`
- FOUND commits: `7b657e7`, `d40daea`, `11d4a87`, `3046a25`, `7be88a2`, `cc36e4c`, `b0978ac`

## Next Phase Readiness

Phase 17 verification gaps are closed. Phase 18 can consume a safe, maintainer-facing audit report with both dataset and replay examples plus an independent prompt protocol guard.

---
*Phase: 17-audit-saturation-policy-gate*
*Completed: 2026-05-18*
