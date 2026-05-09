---
phase: 04-qlora-sft-9b-batch-1
plan: "05"
subsystem: training
tags: [qlora, sft, aggregate-report, artifact-manifest, fail-closed]

requires:
  - phase: 04-04
    provides: Full-run wrapper and early-stopping manifest contract; long full training intentionally not launched
  - phase: 03-dataset-rebuild-qwen3-5-retokenize-split
    provides: Phase 3 split manifest and Arrow input artifacts
provides:
  - Aggregate Phase 4 SFT evaluator for SFT-01 through SFT-08
  - Fail-closed pending report path when no green full-run sft_manifest.json/adapter exists
  - Artifact manifest contract with paths and SHA-256 handoff evidence for Phase 5 once full training is complete
affects: [phase-05-merge-gguf-export, phase-06-eval]

tech-stack:
  added: []
  patterns:
    - Fail-closed aggregate gates with next_phase_allowed only when all SFT gates are green
    - Artifact path and SHA-256 manifest for training input/output evidence
    - Pending full-run status instead of false-green completion

key-files:
  created:
    - .planning/phases/04-qlora-sft-9b-batch-1/04-05-SUMMARY.md
  modified:
    - tests/test_v3_sft_artifacts.py
    - tsc_cycle/v3_gates/sft_report_v3.py

key-decisions:
  - "Do not mark Phase 4 complete or allow Phase 5 unless a green full-run sft_manifest.json and adapter exist."
  - "Expose --allow-pending so automation can write an explicit ok=false pending report without pretending long training ran."
  - "Preserve evaluate_sft_manifest compatibility while making evaluate_gates the aggregate SFT-01..08 contract."

patterns-established:
  - "Aggregate Phase 4 reports carry ok, next_phase_allowed, requirements_covered, gates, fatal_failures, and artifact_manifest.paths/sha256."
  - "Missing full-run artifacts are represented as status=pending_full_run, human_needed=true, and fatal_failures[full_run_pending]."

requirements-completed:
  - SFT-01
  - SFT-02
  - SFT-03
  - SFT-04
  - SFT-05
  - SFT-06
  - SFT-07
  - SFT-08

duration: 9 min
completed: 2026-05-09
---

# Phase 04 Plan 05: Aggregate SFT Report Gate Summary

**SFT-01..SFT-08 aggregate gate now hashes Phase 4 evidence and blocks Phase 5 unless a real early-stopped full-run adapter exists.**

## Performance

- **Duration:** 9 min
- **Started:** 2026-05-09T15:08:29Z
- **Completed:** 2026-05-09T15:17:29Z
- **Tasks:** 3 completed; Task 3 completed as fail-closed pending because no green full-run artifact exists
- **Files modified:** 3

## Accomplishments

- Extended `tests/test_v3_sft_artifacts.py` with aggregate `evaluate_gates`/CLI contract tests covering `next_phase_allowed`, complete SFT-01..SFT-08 coverage, dry/full gate failures, LoRA 24/8 layer coverage, artifact paths, and SHA-256 evidence.
- Replaced the minimal 04-02 manifest evaluator with `tsc_cycle/v3_gates/sft_report_v3.py` aggregate reporting: SFT-01..08 gates, `artifact_manifest.paths`, `artifact_manifest.sha256`, adapter/best-checkpoint handoff, v1.0 FROZEN evidence, and CLI writing.
- Honored the 04-04 “只实现不启动” decision: no long full training was launched; no actual green `phase4_sft_report.json` was fabricated. Missing full-run state is represented as `status="pending_full_run"`, `human_needed=true`, `ok=false`, and `next_phase_allowed=false`.

## Task Commits

Each task was committed atomically:

1. **Task 1: Extend artifact tests for aggregate Phase 4 report** - `e6489b4` (test)
2. **Task 2: Implement aggregate SFT report evaluator and CLI** - `22d1b1c` (feat)
3. **Task 3: Generate final Phase 4 report for completed run** - `d2fd3cb` (fix; fail-closed pending because full-run artifacts are absent)

**Plan metadata:** pending final docs commit

## Files Created/Modified

- `tests/test_v3_sft_artifacts.py` - Aggregate report tests for complete SFT coverage, fail-closed dry/full run checks, artifact manifest hashes, LoRA coverage, and CLI output.
- `tsc_cycle/v3_gates/sft_report_v3.py` - Aggregate Phase 4 evaluator/CLI with SFT-01..08 gates, artifact SHA-256 manifest, compatibility `evaluate_sft_manifest`, and `--allow-pending` fail-closed path.
- `.planning/phases/04-qlora-sft-9b-batch-1/04-05-SUMMARY.md` - This execution summary.

## Decisions Made

- Phase 4 aggregate reporting is implemented, but Phase 4 runtime completion remains pending until a human-approved full SFT run produces a green `sft_manifest.json` and adapter.
- `--allow-pending` exists for automation/reporting only; it writes/prints an explicit failed pending report and exits non-zero, so it cannot accidentally unblock Phase 5.
- Artifact hashes include all evidence that exists; missing Phase 4 full-run outputs remain fatal failures rather than placeholders.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added explicit pending report mode for absent full-run artifacts**
- **Found during:** Task 3 (Generate final Phase 4 report for completed run)
- **Issue:** The plan expected a completed full run, but 04-04 was implementation-only and no green `runs/v3.0-9B-*/sft_manifest.json` exists. Without an explicit pending path, automation could only fail with an assertion and would not expose machine-readable fail-closed status.
- **Fix:** Added `--allow-pending` producing `ok=false`, `next_phase_allowed=false`, `status="pending_full_run"`, `human_needed=true`, and `fatal_failures=[full_run_pending]`.
- **Files modified:** `tsc_cycle/v3_gates/sft_report_v3.py`
- **Verification:** Pytest suite passed; pending CLI output was validated to be ok=false and exit non-zero.
- **Committed in:** `d2fd3cb`

---

**Total deviations:** 1 auto-fixed (1 missing critical).
**Impact on plan:** This prevents false-green Phase 4 completion and matches the user requirement to fail closed when full training was not launched.

## Verification

- Task 1 RED verification failed as expected before implementation: `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest /home/samuel/TSC_CYCLE/tests/test_v3_sft_artifacts.py -q` reported missing `evaluate_gates`/`main` imports.
- Task 1 acceptance grep checks passed for `next_phase_allowed`, `SFT-08`, and `artifact_manifest`.
- Task 2 verification passed: `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest /home/samuel/TSC_CYCLE/tests/test_v3_sft_artifacts.py -q`.
- Task 2 acceptance grep checks passed for `SFT-01`, `next_phase_allowed`, `sha256`, `20260507T032419Z`, `expected_gated_deltanet_layers.*24`, `expected_full_attention_layers.*8`, `early_stopping_triggered`, and `stop_reason.*early_stopping`.
- Task 3 actual full-run discovery failed closed with `AssertionError: no valid Phase 4 full run root found`, as expected because the full training was not launched.
- Pending report verification passed: `--allow-pending` wrote an ok=false report with `status="pending_full_run"`, `human_needed=true`, and `next_phase_allowed=false`.
- Plan-level fast check passed: `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest /home/samuel/TSC_CYCLE/tests/test_v3_sft_artifacts.py -q`.

## Known Stubs

None found in files modified by this plan. The pending report is intentional fail-closed runtime state, not a stub: it blocks Phase 5 until the deferred full SFT run exists.

## Threat Flags

None. This plan implements the threat mitigations listed in the plan: artifact hashing, run-root isolation, v1.0 FROZEN evidence, and false-green prevention.

## Issues Encountered

- No valid `runs/v3.0-9B-*/sft_manifest.json` with `ok=true`, `early_stopping_triggered=true`, `stop_reason="early_stopping"`, and an existing adapter was found. This is expected from the 04-04 implementation-only decision.
- Existing unrelated modified/untracked files were present before execution and were left untouched.

## User Setup Required

To unblock Phase 5, a human must explicitly authorize and run the long full SFT via the existing 04-04 wrapper after a green dry-run root exists. After it produces a green `sft_manifest.json` and adapter, run:

`/home/samuel/TSC_CYCLE/.venv/bin/python -m tsc_cycle.v3_gates.sft_report_v3 --run-dir /home/samuel/TSC_CYCLE/runs/v3.0-9B-{utc} --out /home/samuel/TSC_CYCLE/runs/v3.0-9B-{utc}/phase4_sft_report.json`

## Next Phase Readiness

Phase 5 is **not** unblocked yet. The aggregate gate is ready, but it will keep `next_phase_allowed=false` until the deferred full-run manifest and adapter exist and all SFT-01..SFT-08 gates pass.

## Self-Check: PASSED

- Found modified files on disk: `tests/test_v3_sft_artifacts.py`, `tsc_cycle/v3_gates/sft_report_v3.py`, and this `04-05-SUMMARY.md`.
- Found task commits in git history: `e6489b4`, `22d1b1c`, `d2fd3cb`.
- Verified fast pytest suite passes.
- Verified actual full-run report generation remains fail-closed/pending because no green full-run artifact exists.

---
*Phase: 04-qlora-sft-9b-batch-1*
*Completed: 2026-05-09*
