---
phase: 04-qlora-sft-9b-batch-1
plan: 04
subsystem: training
tags: [qwen3.5, qlora, sft, dgx-spark, early-stopping, run-safe]

requires:
  - phase: 04-03
    provides: dry-run gate evaluator and safe dry-run wrapper
provides:
  - Full-run manifest writer with early-stopping convergence evidence
  - Full-run wrapper gated by green dry-run report and run_safe 100G
  - Human authorization boundary for long no-cap training
affects: [phase-05-gguf-export, phase-06-eval]

tech-stack:
  added: []
  patterns:
    - fail-closed SFT manifest gates
    - dry-run-gated full-run launch wrapper

key-files:
  created:
    - scripts/run_v3_phase4_full.sh
  modified:
    - tsc_cycle/student/train.py
    - tsc_cycle/v3_gates/sft_report_v3.py
    - tests/test_v3_sft_artifacts.py

key-decisions:
  - "Full-run wrapper requires an existing dry-run RUN_ROOT and refuses to create a fresh root in full mode."
  - "Full-run launch was not executed because the user selected implementation-only authorization for 04-04."
  - "Full manifests are green only when early stopping actually triggers; max-epoch completion is fail-closed."

patterns-established:
  - "Full training must pass through scripts/dgx_spark/run_safe.sh 100G -- with WANDB_PROJECT=tsc-cycle-v3-9b."
  - "Phase 4 full-run artifacts stay under the same runs/v3.0-9B-* root as the green dry-run report."

requirements-completed: [SFT-05, SFT-06, SFT-07, SFT-08]

duration: 18min
completed: 2026-05-09
---

# Phase 04 Plan 04 Summary

**Dry-run-gated full-run wrapper and fail-closed SFT convergence manifest for Qwen3.5-9B training**

## Performance

- **Duration:** 18 min
- **Tasks:** 3 planned; 2 implementation tasks completed, long training checkpoint deferred by user authorization
- **Files modified:** 4

## Accomplishments

- Added full-run manifest evidence in `tsc_cycle/student/train.py`, including early-stopping config, stop reason, best checkpoint, grad gate, FROZEN evidence, LoRA coverage, Arrow hashes, and adapter path.
- Added `scripts/run_v3_phase4_full.sh`, requiring a positional `RUN_ROOT`, green `dry_run_report.json`, `run_safe.sh 100G --`, and isolated `WANDB_PROJECT=tsc-cycle-v3-9b` before launching full training.
- Extended manifest evaluation/tests so full runs fail closed if early stopping does not trigger or required evidence is missing.

## Task Commits

1. **Task 1 tests: Full-run manifest evidence tests** — `44eb71a` (`test(04-04): add full-run manifest evidence tests`)
2. **Task 1 implementation: Full-run convergence manifest** — `4100cfd` (`feat(04-04): write full-run convergence manifest`)
3. **Task 3 implementation: Gated full-run wrapper** — `b54311a` (`feat(04-04): add gated full-run wrapper`)

## Files Created/Modified

- `scripts/run_v3_phase4_full.sh` — full-run launcher gated on existing green dry-run RUN_ROOT and DGX safe-run wrapper.
- `tsc_cycle/student/train.py` — writes `sft_manifest.json` and full-run evidence after training.
- `tsc_cycle/v3_gates/sft_report_v3.py` — evaluates full-run early-stopping evidence fail-closed.
- `tests/test_v3_sft_artifacts.py` — covers green and failed full-run manifest cases.

## Verification

- `bash -n scripts/run_v3_phase4_full.sh`
- `./.venv/bin/python -m pytest tests/test_v3_sft_config.py tests/test_v3_sft_artifacts.py tests/test_v3_sft_frozen.py -q` — 16 passed
- Wrapper contract grep checks passed: `full_run_allowed`, `run_safe.sh 100G --`, `tsc-cycle-v3-9b`, no timeout/6h/21600 pattern, positional RUN_ROOT requirement.

## Deviations from Plan

Task 2 and the long full-run launch portion of Task 3 were intentionally not executed. The user selected “只实现不启动”, so this plan stops before running `scripts/run_v3_phase4_full.sh "$RUN_ROOT"`.

## Issues Encountered

The first executor connection closed after committing manifest changes but before wrapper/SUMMARY completion. Work was resumed in the main workspace; no destructive recovery commands were used.

## User Setup Required

Before launching full training, produce or identify a green dry-run report under `runs/v3.0-9B-*/dry_run_report.json` or `runs/v3.0-9B-*/reports/dry-run/dry_run_report.json`, then explicitly approve the long no-6h-cap run.

## Next Phase Readiness

Plan 04-05 can aggregate the Phase 4 implementation evidence, but final full-run success remains contingent on the deferred human-approved training launch and resulting green `sft_manifest.json`.

## Self-Check: PASSED

- Full-run wrapper is implemented, executable, syntax-valid, dry-run gated, and safe-run protected.
- Long full training was not launched.
- Remaining launch authorization boundary is documented.
