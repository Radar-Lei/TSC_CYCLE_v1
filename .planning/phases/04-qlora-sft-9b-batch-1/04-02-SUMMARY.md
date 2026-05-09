---
phase: 04-qlora-sft-9b-batch-1
plan: "02"
subsystem: training
tags: [qlora, sft, qwen3.5-9b, arrow-ipc, trainer-callbacks, dgx-spark]

requires:
  - phase: 04-01
    provides: Wave 0 RED pytest contracts for locked SFT config, Arrow loader, FROZEN guard, grad gate, and artifact evidence
  - phase: 03-dataset-rebuild-qwen3-5-retokenize-split
    provides: Phase 3 tokenized Arrow IPC train/val/ood_val artifacts
provides:
  - Phase 4 CPU-importable SFT helper module with locked QLoRA/training config and Arrow IPC loader
  - Callback-driven SFT-06 grad_norm/NaN abort gate with grad_gate.json evidence
  - Phase 4 trainer entrypoint wired to Arrow IPC, Qwen3.5-9B QLoRA, LoRA coverage, FROZEN guard, and early stopping callbacks
  - Minimal fail-closed SFT manifest evaluator needed by current artifact tests
affects: [04-03-dry-run-gate, 04-04-full-run, 04-05-sft-report, phase-5-export]

tech-stack:
  added: []
  patterns:
    - CPU-fast Phase 4 helper contracts before GPU training
    - Fail-closed JSON gate reports for trainer safety evidence
    - Direct Phase 3 Arrow IPC loading with metadata pruning for Trainer

key-files:
  created:
    - tsc_cycle/student/sft_v3.py
    - tsc_cycle/v3_gates/sft_report_v3.py
  modified:
    - tsc_cycle/student/train.py

key-decisions:
  - "Keep Phase 4 trainer on HF Trainer + PEFT + bitsandbytes, not TRL packing or alternate training stacks, because Phase 3 already produced pre-tokenized Arrow records."
  - "Expose locked values as CPU-importable helpers so config/path/grad-gate safety can be proven before any GPU run."
  - "Add a minimal fail-closed manifest evaluator in 04-02 because Task 2 verification imports it, while leaving full aggregate reporting to later Phase 4 plans."

patterns-established:
  - "GradNormAbortCallback writes reports/<mode>/grad_gate.json and sets control.should_training_stop on non-finite logs or p99 gate failure."
  - "validate_run_root accepts only runs/v3.0-9B-* style roots and rejects v1.0/generic/shell-metacharacter paths."
  - "Trainer construction always includes GradNormAbortCallback and EarlyStoppingCallback with eval/save every 200 steps."

requirements-completed:
  - SFT-01
  - SFT-02
  - SFT-03
  - SFT-05
  - SFT-06
  - SFT-07
  - SFT-08

duration: 6 min
completed: 2026-05-09
---

# Phase 04 Plan 02: Trainer Foundation Summary

**Qwen3.5-9B Phase 4 trainer foundation now loads Phase 3 Arrow IPC data, locks QLoRA/TrainingArguments safety values, guards v1.0 artifacts, and aborts via callback-written grad_gate.json evidence.**

## Performance

- **Duration:** 6 min
- **Started:** 2026-05-09T14:40:48Z
- **Completed:** 2026-05-09T14:47:12Z
- **Tasks:** 2 completed
- **Files modified:** 3

## Accomplishments

- Added `tsc_cycle/student/sft_v3.py` with locked Phase 4 constants, QLoRA kwargs, TrainingArguments kwargs, Arrow IPC loading, run-root validation, FROZEN guard, LoRA coverage reporting, and SFT-06 grad gate callback/reporting.
- Refactored `tsc_cycle/student/train.py` to use Qwen/Qwen3.5-9B, Phase 3 Arrow IPC splits, SDPA + bnb NF4 + PEFT all-linear LoRA, `GradNormAbortCallback`, and `EarlyStoppingCallback`.
- Added `tsc_cycle/v3_gates/sft_report_v3.py` as a fail-closed manifest evaluator required by the Task 2 artifact tests.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add Phase 4 SFT helper contracts and grad abort callback** - `d1318d7` (feat)
2. **Task 2: Refactor trainer entrypoint to use locked Phase 4 helpers and callbacks** - `92ccbf7` (feat)

**Plan metadata:** pending final docs commit

## Files Created/Modified

- `tsc_cycle/student/sft_v3.py` - Phase 4 helper contracts, Arrow loader, FROZEN/run-root guards, LoRA coverage report writer, and callback-driven grad gate writer.
- `tsc_cycle/student/train.py` - Trainer entrypoint now uses locked Qwen3.5-9B Phase 4 helpers, Arrow IPC train/val splits, GradNormAbortCallback, EarlyStoppingCallback, LoRA coverage, and mode manifests.
- `tsc_cycle/v3_gates/sft_report_v3.py` - Minimal fail-closed SFT manifest evaluator for artifact evidence tests.

## Decisions Made

- Kept model loading behind `main()` / trainer construction helpers so unit tests import Phase 4 contracts without CUDA or 9B model loading.
- Preserved existing HF Trainer approach rather than introducing TRL `SFTTrainer`, because current data is already tokenized with masked labels and packing must remain disabled.
- Implemented only the minimal `sft_report_v3.evaluate_sft_manifest` needed by current artifact tests; full aggregate Phase 4 reporting remains a later plan responsibility.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Made grep acceptance contracts machine-checkable**
- **Found during:** Task 1 (helper contracts)
- **Issue:** Helper constants satisfied tests but some acceptance `grep` checks could not see literal `expected_gated_deltanet_layers.*24` and `class GradNormAbortCallback` patterns.
- **Fix:** Emitted literal locked coverage values in report/config payloads and verified grep acceptance criteria.
- **Files modified:** `tsc_cycle/student/sft_v3.py`
- **Verification:** Task 1 pytest command passed; acceptance grep checks returned non-zero counts.
- **Committed in:** `d1318d7`

**2. [Rule 3 - Blocking] Added fail-closed SFT manifest evaluator for Task 2 artifact tests**
- **Found during:** Task 2 (trainer entrypoint verification)
- **Issue:** The plan's Task 2 verification included `tests/test_v3_sft_artifacts.py`, which imports `tsc_cycle.v3_gates.sft_report_v3`; without a minimal evaluator, Task 2 could not complete.
- **Fix:** Added `evaluate_sft_manifest()` with fail-closed checks for requirements, isolated run root, wandb project, dry/full reports, adapter path, Arrow hashes, LoRA coverage, and FROZEN evidence.
- **Files modified:** `tsc_cycle/v3_gates/sft_report_v3.py`
- **Verification:** Task 2 pytest command passed.
- **Committed in:** `92ccbf7`

---

**Total deviations:** 2 auto-fixed (2 blocking).
**Impact on plan:** Both fixes were required for the plan's own acceptance/verification gates. No long GPU training, paid API, vLLM, flash-attn, or alternate training stack was introduced.

## Verification

- Task 1 RED baseline failed as expected before implementation with missing `tsc_cycle.student.sft_v3`.
- Task 1 verification passed: `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest /home/samuel/TSC_CYCLE/tests/test_v3_sft_config.py /home/samuel/TSC_CYCLE/tests/test_v3_sft_arrow_loader.py /home/samuel/TSC_CYCLE/tests/test_v3_sft_frozen.py /home/samuel/TSC_CYCLE/tests/test_v3_sft_grad_gate.py -q`
- Task 2 verification passed: `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest /home/samuel/TSC_CYCLE/tests/test_v3_sft_config.py /home/samuel/TSC_CYCLE/tests/test_v3_sft_arrow_loader.py /home/samuel/TSC_CYCLE/tests/test_v3_sft_artifacts.py /home/samuel/TSC_CYCLE/tests/test_v3_sft_grad_gate.py -q`
- Plan-level verification passed: `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest /home/samuel/TSC_CYCLE/tests/test_v3_sft_config.py /home/samuel/TSC_CYCLE/tests/test_v3_sft_arrow_loader.py /home/samuel/TSC_CYCLE/tests/test_v3_sft_frozen.py /home/samuel/TSC_CYCLE/tests/test_v3_sft_grad_gate.py /home/samuel/TSC_CYCLE/tests/test_v3_sft_artifacts.py -q`

## Known Stubs

None found in files created/modified by this plan. The `sft_report_v3.py` evaluator is intentionally minimal for 04-02's tests; later Phase 4 plans own the full aggregate report workflow.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: manifest-file-evaluator | `tsc_cycle/v3_gates/sft_report_v3.py` | New fail-closed artifact manifest reader validates user-provided report paths and run roots; this supports Task 2 tests but is a new security-relevant filesystem validation surface not listed in the original file list. |

## Issues Encountered

- Existing unrelated modified/untracked files were present before execution and were left untouched.
- `tests/test_v3_sft_dry_run.py` remains outside this plan's verification scope; it is expected to be addressed by later Phase 4 dry-run gate plans.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for 04-03: implement the 500-sample dry-run gate wrapper/report using the helper contracts, callback evidence, and artifact paths introduced here. No GPU training was launched by this plan.

## Self-Check: PASSED

- Found created files on disk: `tsc_cycle/student/sft_v3.py`, `tsc_cycle/v3_gates/sft_report_v3.py`, and `04-02-SUMMARY.md`.
- Found task commits in git history: `d1318d7`, `92ccbf7`.
- Verified plan-level pytest suite passed.

---
*Phase: 04-qlora-sft-9b-batch-1*
*Completed: 2026-05-09*
