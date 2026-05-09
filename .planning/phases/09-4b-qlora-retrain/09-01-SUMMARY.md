---
phase: 09-4b-qlora-retrain
plan: 01
subsystem: testing
tags: [pytest, red-contracts, qwen3-4b, qlora, smoke-gate, dgx-spark, v4]

requires:
  - phase: 08-v3-4b-dataset-rebuild
    provides: Green Phase 8 dataset handoff under data/v4/phase8 and artifacts/v4/phase8
provides:
  - RED pytest contracts for SFT4B-01 Qwen3-4B QLoRA configuration and raw-text data handoff
  - RED pytest contracts for SFT4B-02 pre-train smoke gates covering tokenizer leakage, protocol parsing, one-step training, and hard-constraint lint
  - RED pytest contracts for SFT4B-03 DGX-safe wrapper behavior and v4.0-4B run-root isolation
  - RED pytest contracts for SFT4B-04 aggregate training report and Phase 10 handoff evidence
affects: [phase9-implementation, phase10-gguf-export, SFT4B]

tech-stack:
  added: []
  patterns:
    - Lazy imports keep RED contracts CPU-fast and avoid model/GPU loading
    - RED verification passes only when pytest exits non-zero because downstream Phase 9 implementation modules/scripts are missing

key-files:
  created:
    - tests/test_v4_phase9_sft_contracts.py
    - tests/test_v4_phase9_smoke_gate.py
    - tests/test_v4_phase9_training_wrappers.py
    - tests/test_v4_phase9_report.py
    - .planning/phases/09-4b-qlora-retrain/09-01-SUMMARY.md
  modified: []

key-decisions:
  - "Phase 9 starts with executable RED contracts only; no production code, GPU launch, model load, dependency install, vLLM, or flash-attn path was introduced."
  - "RED success is defined as pytest returning non-zero for missing Phase 9 implementation contracts, while existing parser/lint fixtures still execute successfully."

patterns-established:
  - "Phase 9 helper imports are lazy inside tests so future implementation failures point to contract gaps rather than import-time CUDA/model side effects."
  - "Wrapper tests inspect script text to block unsafe training before any DGX runtime command can execute."

requirements-completed: [SFT4B-01, SFT4B-02, SFT4B-03, SFT4B-04]

duration: 3min
completed: 2026-05-09
---

# Phase 09 Plan 01: 4B QLoRA RED Contract Summary

**CPU-fast RED pytest contracts locking Qwen3-4B raw-text QLoRA, smoke gates, DGX-safe wrappers, and Phase 10 handoff evidence before implementation**

## Performance

- **Duration:** 3 min
- **Started:** 2026-05-09T18:27:09Z
- **Completed:** 2026-05-09T18:30:00Z
- **Tasks:** 3
- **Files modified:** 5

## Accomplishments

- Created `tests/test_v4_phase9_sft_contracts.py` to require Qwen3-4B model identity, r=64 LoRA, NF4/bf16/SDPA/raw-text training args, v4 tokenized data paths, green Phase 8 handoff evidence, and isolated `runs/v4.0-4B-*` roots.
- Created `tests/test_v4_phase9_smoke_gate.py` to define the pre-train smoke evaluator contract for Phase 8 handoff, native `<think>` leakage, correct `</end_working_out>` protocol, one-step trainer evidence, SOLUTION parsing, and hard-constraint lint.
- Created `tests/test_v4_phase9_training_wrappers.py` to require future Phase 9 smoke/full-training wrappers to route through `scripts/dgx_spark/run_safe.sh 100G --`, use the fixed project venv/module argv, write only under v4.0-4B run roots, and avoid installs, eval, vLLM, flash-attn, Unsloth, and Axolotl.
- Created `tests/test_v4_phase9_report.py` to require aggregate report evidence for loss curve, duration, VRAM peak, adapter hash, data manifest hash, Phase 8 artifact hashes, SFT4B coverage, and Phase 10 handoff.
- Ran each planned RED verification command and the overall verification command; all returned non-zero as expected because production Phase 9 modules/scripts are intentionally not implemented in this plan.

## Task Commits

Each task was committed atomically:

1. **Task 1: Write RED SFT config and data contract tests** - `97e2239` (test)
2. **Task 2: Write RED pre-train smoke gate tests** - `fb7bbc6` (test)
3. **Task 3: Write RED wrapper and aggregate report tests** - `5839289` (test)

**Plan metadata:** pending final docs commit

## Files Created/Modified

- `tests/test_v4_phase9_sft_contracts.py` - RED contract for `tsc_cycle.student.sft_v4` constants, helper kwargs, v4 Phase 8 handoff, run-root validation, split loading, and hash/report helper expectations.
- `tests/test_v4_phase9_smoke_gate.py` - RED contract for `tsc_cycle.v4_gates.phase9_smoke.evaluate_pretrain_smoke_report` and its false-green blockers.
- `tests/test_v4_phase9_training_wrappers.py` - RED text contract for future Phase 9 smoke/full training wrappers and DGX-safe run isolation.
- `tests/test_v4_phase9_report.py` - RED contract for `tsc_cycle.v4_gates.phase9_report.evaluate_phase9_report` and Phase 10 handoff validation.
- `.planning/phases/09-4b-qlora-retrain/09-01-SUMMARY.md` - This execution summary.

## Verification

- `cd /home/samuel/TSC_CYCLE && set +e; /home/samuel/TSC_CYCLE/.venv/bin/python -m pytest -q tests/test_v4_phase9_sft_contracts.py; code=$?; test "$code" -ne 0`
  - Result: passed RED verification; pytest exit code `1`; 7 failures due to missing `tsc_cycle.student.sft_v4`.
- `cd /home/samuel/TSC_CYCLE && set +e; /home/samuel/TSC_CYCLE/.venv/bin/python -m pytest -q tests/test_v4_phase9_smoke_gate.py; code=$?; test "$code" -ne 0`
  - Result: passed RED verification; pytest exit code `1`; one parser/lint fixture passed and 7 failures were due to missing `tsc_cycle.v4_gates.phase9_smoke`.
- `cd /home/samuel/TSC_CYCLE && set +e; /home/samuel/TSC_CYCLE/.venv/bin/python -m pytest -q tests/test_v4_phase9_training_wrappers.py tests/test_v4_phase9_report.py; code=$?; test "$code" -ne 0`
  - Result: passed RED verification; pytest exit code `1`; failures were due to missing `scripts/run_v4_phase9_train.sh`, `scripts/run_v4_phase9_smoke.sh`, and `tsc_cycle.v4_gates.phase9_report`.
- `cd /home/samuel/TSC_CYCLE && set +e; /home/samuel/TSC_CYCLE/.venv/bin/python -m pytest -q tests/test_v4_phase9_sft_contracts.py tests/test_v4_phase9_smoke_gate.py tests/test_v4_phase9_training_wrappers.py tests/test_v4_phase9_report.py; code=$?; test "$code" -ne 0`
  - Result: passed overall RED verification; pytest exit code `1`; 25 failed and 1 passed, with failures confined to intended missing Phase 9 implementation contracts.

## Decisions Made

- Kept all implementation imports lazy and inside helper functions so importing test modules does not load CUDA, the 4B model, or future training stacks.
- Used compact tmp_path JSON placeholders for contract fixtures; no Arrow writer, GPU command, model load, or dependency install was introduced.
- Treated non-zero pytest as the positive RED gate because this plan intentionally defines contracts before downstream production code exists.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- The repository already had many unrelated modified/untracked files before this plan. They were left untouched; only the four new Phase 9 test files and this summary were staged/committed for this plan.

## User Setup Required

None - no external service configuration required.

## Known Stubs

None. The created files are intentional RED tests, not production stubs; they fail against missing downstream contracts by design.

## Threat Flags

None - this plan introduced local pytest contracts only. It added no network endpoints, auth paths, new file-access runtime behavior, schema migration, GPU launch, or model-loading path.

## TDD Gate Compliance

- RED gate commits exist for each task: `97e2239`, `fb7bbc6`, `5839289`.
- GREEN implementation commits are intentionally absent because Plan 09-01 scope is RED contracts only; Plans 09-02 through 09-04 are expected to satisfy these tests.

## Next Phase Readiness

- Plan 09-02 can implement `tsc_cycle.student.sft_v4` and `tsc_cycle.v4_gates.phase9_smoke` against these RED contracts.
- Plan 09-03 can implement `scripts/run_v4_phase9_smoke.sh`, `scripts/run_v4_phase9_train.sh`, and full training reporting without guessing safety requirements.
- Plan 09-04 can implement `tsc_cycle.v4_gates.phase9_report` and produce the Phase 10 handoff evidence.

## Self-Check: PASSED

- Found `tests/test_v4_phase9_sft_contracts.py`.
- Found `tests/test_v4_phase9_smoke_gate.py`.
- Found `tests/test_v4_phase9_training_wrappers.py`.
- Found `tests/test_v4_phase9_report.py`.
- Found `.planning/phases/09-4b-qlora-retrain/09-01-SUMMARY.md`.
- Found task commit `97e2239` in git history.
- Found task commit `fb7bbc6` in git history.
- Found task commit `5839289` in git history.

---
*Phase: 09-4b-qlora-retrain*
*Completed: 2026-05-09*
