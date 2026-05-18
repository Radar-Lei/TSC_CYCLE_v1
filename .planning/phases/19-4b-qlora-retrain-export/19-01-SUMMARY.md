---
phase: 19-4b-qlora-retrain-export
plan: "01"
subsystem: training
tags: [qwen3-4b, qlora, phase18, tokenization, dgx-spark]

requires:
  - phase: 18-calibrated-dataset-rebuild
    provides: calibrated v4.2 JSONL, deterministic split indexes, and reconstruction report
provides:
  - v4.2 QLoRA constants and run-root guards for Phase 18 calibrated data
  - Phase 18 calibrated train/val/ood_val Arrow tokenized handoff artifacts
  - Phase 19 TRAIN-01 training report validator and DGX Spark-safe launcher
  - Real v4.2 QLoRA training completion under runs/v4.2-4B-20260518T111519Z with accepted TRAIN-01 report
affects: [phase19-export, phase20-evaluation, TRAIN-01]

tech-stack:
  added: []
  patterns:
    - v4.2-specific wrappers/gates preserve existing v4.0 behavior
    - tokenizer handoff validates Phase 18 hashes and native-think safety before training

key-files:
  created:
    - tsc_cycle/student/sft_v42.py
    - tsc_cycle/v4_gates/phase19_training.py
    - scripts/run_v4_phase19_train.sh
    - tests/test_v4_phase19_training_export.py
    - data/v4_2/phase18/tokenized/train.arrow
    - data/v4_2/phase18/tokenized/val.arrow
    - data/v4_2/phase18/tokenized/ood_val.arrow
    - data/v4_2/phase18/tokenized/manifest.json
    - artifacts/v4_2/phase19/tokenization_report.json
  modified:
    - tsc_cycle/student/train.py

key-decisions:
  - "Add v4.2-specific training constants and gates instead of mutating v4.0 defaults."
  - "Treat TRAIN-01 as complete only after the real adapter exists and phase19_sft_report.json validates."

patterns-established:
  - "Phase 19 gates validate Phase 18 calibrated JSONL, split counts, tokenized Arrow hashes, and TRAIN-01 coverage before accepting training evidence."

requirements-completed: [TRAIN-01]

duration: 34 min
completed: 2026-05-18
---

# Phase 19 Plan 01: v4.2 QLoRA Training Handoff Summary

**v4.2 QLoRA handoff tokenizes Phase 18 calibrated data and completed a real DGX-safe Qwen3-4B training run with accepted TRAIN-01 report evidence.**

## Performance

- **Duration:** 34 min
- **Started:** 2026-05-18T11:04:50Z
- **Completed:** 2026-05-18T11:38:02Z
- **Tasks:** 4 attempted / 4 executed
- **Files modified:** 9 committed files plus ignored runtime run directory

## Accomplishments

- Added `tsc_cycle/student/sft_v42.py` with Phase 18 tokenized defaults, `v4.2-4B-` run-root validation, Qwen3-4B model lock, and Phase 9-equivalent QLoRA settings.
- Extended `tsc_cycle/student/train.py` with a lazy `--phase v4_2` branch that reuses the existing heavy QLoRA primitives and writes Phase 19 report names.
- Added `tsc_cycle/v4_gates/phase19_training.py` for Phase 18 handoff validation, deterministic tokenization, tokenized manifest/report writing, and Phase 19 training report validation.
- Generated real default tokenized handoff artifacts:
  - `train.arrow`: 3500 rows, sha256 `38c0f2d69c67c79f3edb0a751e1a25ebf76897318df763ef1ec0db6e72fa6b45`
  - `val.arrow`: 452 rows, sha256 `860129d3c4f4eb9230154ca5427f73cc7f7023971ed4f7dafcb84ae5a852a9af`
  - `ood_val.arrow`: 580 rows, sha256 `44221e96a81ee3a11effc0e9f3bd228e72787432916b46fbc11749803ae0a29c`
- Completed real QLoRA training via `scripts/run_v4_phase19_train.sh`; run root `runs/v4.2-4B-20260518T111519Z`, adapter sha256 `7edad196a79d15649a40746865f0336e3b4aa1913be61661be122a1b5605fe5b`, data manifest sha256 `133f1d1cee35c0e9dff6385f681d5c991b28c663a00c6026aad34180d64516ee`.

## Task Commits

1. **Task 1 RED:** `0cac20c` (test) — failing v4.2 training defaults contract.
2. **Task 1 GREEN:** `8ec97b9` (feat) — v4.2 QLoRA constants and trainer phase branch.
3. **Task 2 RED:** `553d97e` (test) — failing Phase 18 tokenization contract.
4. **Task 2 GREEN:** `426c224` (feat) — Phase 18 tokenized split writer/gate.
5. **Task 3 RED:** `8417f8f` (test) — failing Phase 19 report gate contract.
6. **Task 3 GREEN:** `a6d39da` (feat) — training report validator and DGX-safe launcher.
7. **Task 4:** `ef236a5` (feat) — generated default tokenized handoff artifacts and launched real training.

## Files Created/Modified

- `tsc_cycle/student/sft_v42.py` — v4.2 training constants, run-root guards, QLoRA argument evidence, Phase 18 handoff checks.
- `tsc_cycle/v4_gates/phase19_training.py` — tokenization CLI, tokenized manifest/report, report validator, Phase 19 report writer.
- `tsc_cycle/student/train.py` — adds `--phase v4_2` dispatch while preserving `--phase v4` behavior.
- `scripts/run_v4_phase19_train.sh` — DGX Spark-safe full training launcher through `scripts/dgx_spark/run_safe.sh 100G --`.
- `tests/test_v4_phase19_training_export.py` — contracts for constants, tokenization, report gate, and wrapper safety.
- `data/v4_2/phase18/tokenized/*` — real tokenized train/val/ood_val Arrow artifacts and manifest.
- `artifacts/v4_2/phase19/tokenization_report.json` — tokenization evidence report.

## Verification Results

- PASS: `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest tests/test_v4_phase19_training_export.py -q` → 3 passed.
- PASS: `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest tests/test_v4_phase19_training_export.py tests/test_v4_phase18_calibrated_dataset_rebuild.py tests/test_v4_phase9_sft_contracts.py -q` → 15 passed.
- PASS: tokenization CLI on default Phase 18 artifacts wrote 3500/452/580 Arrow rows and `ok: true` tokenization report.
- PASS: `/home/samuel/TSC_CYCLE/.venv/bin/python -m tsc_cycle.v4_gates.phase19_training validate-report --run-root runs/v4.2-4B-20260518T111519Z --report-path runs/v4.2-4B-20260518T111519Z/phase19_sft_report.json` → `ok: true`, `next_phase_allowed: true`, `requirements_covered: ["TRAIN-01"]`.

## Decisions Made

- Add v4.2-specific modules/wrappers to avoid changing existing v4.0 Phase 9 defaults.
- Keep TRAIN-01 incomplete until a real adapter and accepted `phase19_sft_report.json` exist; that condition is now satisfied for `runs/v4.2-4B-20260518T111519Z`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Ran default tokenization from the repository root**
- **Found during:** Task 4 (Generate default handoff artifacts and complete v4.2 QLoRA training run)
- **Issue:** Running the new module without changing to `/home/samuel/TSC_CYCLE` resolved imports through the pre-existing `.claude/worktrees/...` path and could not see the new module.
- **Fix:** Executed tokenization from `/home/samuel/TSC_CYCLE`, preserving main-tree artifacts.
- **Files modified:** None beyond intended tokenized artifacts.
- **Verification:** Tokenization report `ok: true`; Phase 19 tests passed.
- **Committed in:** `ef236a5`

---

**Total deviations:** 1 auto-fixed (Rule 3)
**Impact on plan:** No scope creep; the adjustment ensured commands used the intended main working tree.

## Issues Encountered

- Real QLoRA training initially outlived the executor window and later completed when resumed against the same run root. Final evidence:
  - Run root: `runs/v4.2-4B-20260518T111519Z`
  - Adapter: `runs/v4.2-4B-20260518T111519Z/adapter/adapter_model.safetensors`
  - Report: `runs/v4.2-4B-20260518T111519Z/phase19_sft_report.json`
  - Duration: 14232.66 seconds
  - VRAM peak: 8.64 GB
  - Validation status: `ok: true`, `next_phase_allowed: true`.

## Known Stubs

None found in created/modified source or artifact files.

## Threat Flags

None — new trust-boundary handling matches the plan threat model for Phase 18 artifacts, tokenization, CLI path safety, and lightweight tests.

## TRAIN-01 Status

Complete. The real adapter directory exists and `runs/v4.2-4B-20260518T111519Z/phase19_sft_report.json` passes `python -m tsc_cycle.v4_gates.phase19_training validate-report --run-root runs/v4.2-4B-20260518T111519Z --report-path runs/v4.2-4B-20260518T111519Z/phase19_sft_report.json` with TRAIN-01 coverage.

## User Setup Required

None.

## Next Phase Readiness

Phase 19 Plan 02 is ready: the QLoRA job completed and the Phase 19 training report validator accepts the real `phase19_sft_report.json`.

## Self-Check: PASSED

- Verified summary file path exists after write.
- Verified task commits exist: `0cac20c`, `8ec97b9`, `553d97e`, `426c224`, `8417f8f`, `a6d39da`, `ef236a5`.
- Verified key created files exist: v4.2 source/gate/wrapper/test files, tokenized manifest/report, and three Arrow splits.
- Verified generated tokenization evidence and regression tests.

---
*Phase: 19-4b-qlora-retrain-export*
*Completed: 2026-05-18*
