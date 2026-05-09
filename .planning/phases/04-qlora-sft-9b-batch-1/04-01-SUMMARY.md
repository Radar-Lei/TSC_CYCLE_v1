---
phase: 04-qlora-sft-9b-batch-1
plan: "01"
subsystem: testing
tags: [pytest, qlora, sft, qwen3.5-9b, red-tests, dgx-spark]

requires:
  - phase: 01-environment-tokenizer-memory-llamacpp-gates
    provides: Qwen3.5 tokenizer, memory, run_safe, and environment gate evidence
  - phase: 03-dataset-rebuild-qwen3-5-retokenize-split
    provides: Phase 3 Arrow IPC tokenized train/val/ood_val artifacts
provides:
  - Phase 4 Wave 0 RED pytest contract for SFT-01 through SFT-08
  - Fail-closed tests for locked QLoRA config, Arrow IPC loading, dry-run/grad gates, FROZEN guard, and SFT manifest evidence
affects: [04-02-trainer-helpers, 04-03-dry-run-gate, 04-04-full-run, 04-05-sft-report]

tech-stack:
  added: []
  patterns:
    - CPU-fast pytest RED contract before GPU training implementation
    - Missing-module RED failures as explicit downstream implementation contract

key-files:
  created:
    - tests/test_v3_sft_config.py
    - tests/test_v3_sft_arrow_loader.py
    - tests/test_v3_sft_dry_run.py
    - tests/test_v3_sft_grad_gate.py
    - tests/test_v3_sft_frozen.py
    - tests/test_v3_sft_artifacts.py
  modified: []

key-decisions:
  - "Use missing Phase 4 helper modules as intentional RED failures so Plans 04-02..04-05 must implement the exact public contracts."
  - "Keep Wave 0 tests CPU-fast and avoid loading Qwen3.5-9B, vLLM, flash-attn, paid APIs, or long GPU training."

patterns-established:
  - "Phase 4 SFT gates are represented as pure-function pytest contracts before runtime training scripts exist."
  - "Artifact safety tests validate v3.0 run-root allowlists and v1.0 FROZEN evidence without mutating the real production artifact tree."

requirements-completed:
  - SFT-01
  - SFT-02
  - SFT-03
  - SFT-04
  - SFT-05
  - SFT-06
  - SFT-07
  - SFT-08

duration: 2 min
completed: 2026-05-09
---

# Phase 04 Plan 01: RED SFT Contract Summary

**CPU-fast RED pytest contract locks Qwen3.5-9B SFT config, Phase 3 Arrow loading, dry-run/grad gates, artifact isolation, and v1.0 FROZEN safety before implementation.**

## Performance

- **Duration:** 2 min
- **Started:** 2026-05-09T14:35:28Z
- **Completed:** 2026-05-09T14:38:03Z
- **Tasks:** 3 completed
- **Files modified:** 6 created

## Accomplishments

- Added locked-config RED tests for Qwen/Qwen3.5-9B, QLoRA r=64/alpha=64/dropout=0.0, all-linear coverage evidence, batch=1/grad_accum=16, adamw_torch_fused, grad clipping, steps eval/save, early stopping, and wandb/run-root isolation.
- Added Arrow IPC loader RED tests proving Phase 4 must consume Phase 3 `.arrow` artifacts and must not depend on legacy `data.parquet` layout.
- Added dry-run, grad gate, FROZEN guard, wrapper argv, and final manifest RED tests requiring fail-closed evidence before full SFT can proceed.

## Task Commits

Each task was committed atomically:

1. **Task 1: Write RED locked-config and Arrow loader tests** - `f925088` (test)
2. **Task 2: Write RED dry-run and grad gate tests** - `7d1d292` (test)
3. **Task 3: Write RED artifact isolation and FROZEN guard tests** - `f8b8234` (test)

**Plan metadata:** pending final docs commit

## Files Created/Modified

- `tests/test_v3_sft_config.py` - RED tests for SFT-01/SFT-02/SFT-03/SFT-05/SFT-07 locked helper contracts.
- `tests/test_v3_sft_arrow_loader.py` - RED tests for direct Phase 3 Arrow IPC consumption and legacy parquet rejection.
- `tests/test_v3_sft_dry_run.py` - RED tests for SFT-04 500-sample OOD pass-rate full-run gate.
- `tests/test_v3_sft_grad_gate.py` - RED tests for SFT-06 finite loss and grad_norm p99 fail-closed behavior.
- `tests/test_v3_sft_frozen.py` - RED tests for SFT-08 FROZEN guard, run-root allowlist, and fixed run_safe argv.
- `tests/test_v3_sft_artifacts.py` - RED tests for SFT-07/SFT-08 manifest coverage, artifact hashes, LoRA coverage path, and false-green prevention.

## Decisions Made

- Used missing imports (`tsc_cycle.student.sft_v3`, `tsc_cycle.v3_gates.sft_dry_run_v3`, `tsc_cycle.v3_gates.sft_report_v3`) as intentional RED state rather than adding implementation stubs in Wave 0.
- Wrote filesystem tests against `tmp_path` only; no real chmod or mutation was performed on `runs/20260507T032419Z/`.

## Deviations from Plan

### Auto-fixed Issues

None - plan executed exactly as written.

**Total deviations:** 0 auto-fixed.
**Impact on plan:** No scope creep; RED tests remain implementation-free.

## Verification

- Task 1 RED verification: `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest tests/test_v3_sft_config.py tests/test_v3_sft_arrow_loader.py -q` failed as expected with missing `tsc_cycle.student.sft_v3`.
- Task 2 RED verification: `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest tests/test_v3_sft_dry_run.py tests/test_v3_sft_grad_gate.py -q` failed as expected with missing `tsc_cycle.v3_gates.sft_dry_run_v3` and `tsc_cycle.student.sft_v3`.
- Task 3 RED verification: `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest tests/test_v3_sft_frozen.py tests/test_v3_sft_artifacts.py -q` failed as expected with missing `tsc_cycle.student.sft_v3` and `tsc_cycle.v3_gates.sft_report_v3`.
- Plan-level RED verification: `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest tests/test_v3_sft_*.py -q` failed as expected: 25 failures from missing downstream Phase 4 implementation modules.

## TDD Gate Compliance

- RED gate commits exist for all three Wave 0 tasks.
- This plan is intentionally RED-only (`type: execute` with `tdd="true"` tasks that create failing contract tests); no GREEN implementation commit is expected in 04-01 because Plans 04-02 through 04-05 provide the downstream implementations.

## Known Stubs

None found in created test files. The failures are intentional missing downstream implementation modules, not test stubs.

## Issues Encountered

None. Existing unrelated modified/untracked files were left untouched and noted separately in the phase deferred-items file.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for 04-02: implement `tsc_cycle.student.sft_v3` trainer helpers and entrypoint refactor until the locked config and Arrow loader tests turn green.

## Self-Check: PASSED

- Found all six RED test files on disk.
- Found `04-01-SUMMARY.md` on disk.
- Verified task commits exist: `f925088`, `7d1d292`, `f8b8234`.

---
*Phase: 04-qlora-sft-9b-batch-1*
*Completed: 2026-05-09*
