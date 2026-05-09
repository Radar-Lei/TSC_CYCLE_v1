---
phase: 04-qlora-sft-9b-batch-1
plan: "03"
subsystem: training
tags: [qlora, sft, dry-run, ood-lint, grad-gate, dgx-spark]

requires:
  - phase: 04-02
    provides: Phase 4 trainer entrypoint, GradNormAbortCallback, grad_gate.json evidence, FROZEN guard, run-root validation, and Arrow IPC loader
  - phase: 03-dataset-rebuild-qwen3-5-retokenize-split
    provides: deterministic OOD index, merged labeled JSONL, and tokenized Arrow artifacts
provides:
  - Fail-closed 500-sample dry-run evaluator requiring OOD hard-constraint pass rate and callback-produced grad evidence
  - Safe Phase 4 dry-run wrapper using DGX Spark run_safe 100G, isolated v3.0-9B run roots, and FROZEN rechecks
affects: [04-04-full-run, 04-05-sft-report, phase-5-export]

tech-stack:
  added: []
  patterns:
    - Fail-closed dry-run report gates with explicit full_run_allowed=false on any missing evidence
    - Fixed-argv Bash wrapper for DGX Spark memory-capped dry-run execution

key-files:
  created:
    - tsc_cycle/v3_gates/sft_dry_run_v3.py
    - scripts/run_v3_phase4_dry_run.sh
  modified: []

key-decisions:
  - "Keep immediate gradient abort ownership in Plan 04-02 GradNormAbortCallback; this plan consumes grad_gate.json and fails closed if it is missing or failing."
  - "Do not execute the long GPU dry-run during implementation; verify the wrapper/evaluator contract with CPU-fast tests and bash syntax checks only."

patterns-established:
  - "Dry-run approval requires sample_count=500, OOD pass rate >=0.95, elapsed_seconds<=3600, native think leak count 0, and grad_gate.json with observed_steps>=200 and grad_norm_p99<3.0."
  - "Phase 4 dry-run wrapper sources scripts/dgx_spark/env.sh, invokes scripts/dgx_spark/run_safe.sh 100G -- with a fixed python -m tsc_cycle.student.train argv, then invokes the dry-run evaluator."

requirements-completed:
  - SFT-04
  - SFT-06
  - SFT-07
  - SFT-08

duration: 4 min
completed: 2026-05-09
---

# Phase 04 Plan 03: Dry-Run Gate and Safe Wrapper Summary

**500-sample dry-run approval now fails closed on missing OOD lint evidence, native-think leakage, missing/failing grad_gate.json, or unsafe DGX wrapper execution.**

## Performance

- **Duration:** 4 min
- **Started:** 2026-05-09T14:50:58Z
- **Completed:** 2026-05-09T14:54:58Z
- **Tasks:** 2 completed
- **Files modified:** 2 created

## Accomplishments

- Added `tsc_cycle/v3_gates/sft_dry_run_v3.py` with pure `evaluate_dry_run_gate(report)` plus CLI/report helpers for deterministic OOD sample recovery, model generation, SOLUTION parsing, hard-constraint lint, native-think leakage detection, and callback artifact consumption.
- Added `scripts/run_v3_phase4_dry_run.sh` as an executable fixed-argv wrapper that sources DGX env, uses `run_safe.sh 100G --`, writes only under `runs/v3.0-9B-{utc}`, exports `WANDB_PROJECT=tsc-cycle-v3-9b`, and fails closed unless the dry-run report is green.
- Verified CPU-fast dry-run gate, grad gate, FROZEN, artifact, and wrapper syntax contracts without launching the long GPU dry-run/full-run.

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement dry-run gate evaluator and OOD lint report** - `e6d42a5` (feat)
2. **Task 2: Add safe Phase 4 dry-run wrapper** - `76c4e47` (feat)

**Plan metadata:** pending final docs commit

## Files Created/Modified

- `tsc_cycle/v3_gates/sft_dry_run_v3.py` - Fail-closed dry-run evaluator/CLI reading OOD raw inputs from `labeled_merged.jsonl` + `ood_val.index.jsonl`, generating 500 outputs, linting parsed SOLUTIONs, and consuming `grad_gate.json`.
- `scripts/run_v3_phase4_dry_run.sh` - DGX-safe dry-run wrapper that freezes/rechecks v1.0 evidence, launches trainer through memory-capped `run_safe.sh 100G --`, and invokes the dry-run gate before any full run can proceed.

## Decisions Made

- Kept SFT-06 trainer abort logic in `tsc_cycle/student/sft_v3.py`; `sft_dry_run_v3.py` only consumes the callback-produced artifact and refuses full-run approval without it.
- Did not run `/home/samuel/TSC_CYCLE/scripts/run_v3_phase4_dry_run.sh` because the user explicitly prohibited starting long GPU dry-run/full-run during this implementation pass.

## Deviations from Plan

None - plan executed exactly as written.

## Verification

- Task 1 RED baseline failed as expected before implementation with missing `tsc_cycle.v3_gates.sft_dry_run_v3`.
- Task 1 verification passed: `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest /home/samuel/TSC_CYCLE/tests/test_v3_sft_dry_run.py /home/samuel/TSC_CYCLE/tests/test_v3_sft_grad_gate.py -q`
- Task 1 acceptance grep criteria passed for `sample_count.*500`, `0.95`, `full_run_allowed`, `grad_gate.json`, `constraint_lint`, `labeled_merged.jsonl`, `ood_val.index.jsonl`, `model.generate`, `prediction_input`, and `3600`.
- Task 2 verification passed: `bash -n /home/samuel/TSC_CYCLE/scripts/run_v3_phase4_dry_run.sh && /home/samuel/TSC_CYCLE/.venv/bin/python -m pytest /home/samuel/TSC_CYCLE/tests/test_v3_sft_frozen.py /home/samuel/TSC_CYCLE/tests/test_v3_sft_artifacts.py -q`
- Task 2 acceptance criteria passed for executable bit, literal `run_safe.sh 100G --`, wandb project, `FROZEN.md`, `grad_gate.json`, and `3600`.
- Plan-level verification passed: `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest /home/samuel/TSC_CYCLE/tests/test_v3_sft_dry_run.py /home/samuel/TSC_CYCLE/tests/test_v3_sft_grad_gate.py /home/samuel/TSC_CYCLE/tests/test_v3_sft_frozen.py /home/samuel/TSC_CYCLE/tests/test_v3_sft_artifacts.py -q && bash -n /home/samuel/TSC_CYCLE/scripts/run_v3_phase4_dry_run.sh`

## Known Stubs

None found in files created by this plan.

## Issues Encountered

- Existing unrelated modified/untracked files were present before execution and were left untouched.
- The final long-run gate command remains intentionally unexecuted in this plan because it would start the 500-sample GPU dry-run.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for 04-04: full SFT must consume `dry_run_report.json` and proceed only when it has `ok=true` and `full_run_allowed=true` with 500 OOD generated outputs, pass rate >=0.95, elapsed <=3600, and passing `grad_gate.json` evidence.

## Self-Check: PASSED

- Found created files on disk: `tsc_cycle/v3_gates/sft_dry_run_v3.py`, `scripts/run_v3_phase4_dry_run.sh`, and `04-03-SUMMARY.md`.
- Found task commits in git history: `e6d42a5`, `76c4e47`.
- Verified plan-level pytest suite and wrapper syntax passed.

---
*Phase: 04-qlora-sft-9b-batch-1*
*Completed: 2026-05-09*
