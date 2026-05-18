---
phase: 19-4b-qlora-retrain-export
verified: 2026-05-18T23:29:51Z
status: passed
score: 6/6 must-haves verified
overrides_applied: 0
---

# Phase 19: 4B QLoRA Retrain & Export Verification Report

**Phase Goal:** Maintainer can retrain the latest 4B student on the calibrated v4.2 dataset using the existing DGX Spark-safe QLoRA stack, then export reproducible merged HF and GGUF artifacts.
**Verified:** 2026-05-18T23:29:51Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Maintainer can launch v4.2 QLoRA SFT for `Qwen/Qwen3-4B-Thinking-2507` through the existing DGX Spark-safe stack without introducing a new base model or training framework. | VERIFIED | `tsc_cycle/student/sft_v42.py` locks `MODEL_NAME` to Qwen/Qwen3-4B-Thinking-2507 and QLoRA settings; `tsc_cycle/student/train.py` has `--phase v4_2` branch; `scripts/run_v4_phase19_train.sh` launches through `scripts/dgx_spark/run_safe.sh 100G --` with no dependency install/unsupported runtime markers. |
| 2 | Maintainer can inspect the training report and confirm it references the calibrated v4.2 dataset, expected protocol, and reproducible run paths. | VERIFIED | `runs/v4.2-4B-20260518T111519Z/phase19_sft_report.json` validates with `ok: true`, `next_phase_allowed: true`, `requirements_covered: [TRAIN-01]`; validation confirms Phase 18 hashes, canonical tokenized Arrow hashes, model, LoRA/training args, adapter hash, loss curve (657 points), full completion (657/657 steps), and v4.2 run root. |
| 3 | Maintainer can export the calibrated adapter into merged HF, GGUF fp16, and GGUF q4_K_M artifacts with recorded paths, hashes, and export reports. | VERIFIED | `runs/v4.2-4B-20260518T111519Z/phase19_export_report.json` validates with `ok: true`, `next_phase_allowed: true`, `requirements_covered: [TRAIN-02]`; on-disk artifacts exist and hashes match report: merged HF safetensors, tokenizer/materializer, fp16 GGUF, q4_K_M GGUF. |
| 4 | Maintainer can train v4.2 from Phase 18 calibrated data using Qwen/Qwen3-4B-Thinking-2507 and the existing DGX Spark-safe QLoRA stack. | VERIFIED | Real run root `runs/v4.2-4B-20260518T111519Z` contains adapter files; `phase19_sft_report.json` records `mode: full`, `completed: true`, `duration_seconds: 14232.6626`, `vram_peak_gb: 8.6386`, model lock, QLoRA r=64/alpha=64/dropout=0, NF4/bf16/SDPA settings. |
| 5 | Phase 18 calibrated JSONL and preserved split indexes are tokenized into train/val/ood_val Arrow artifacts without prompt/protocol or native-think drift. | VERIFIED | `artifacts/v4_2/phase19/tokenization_report.json` is `ok: true`, covers TRAIN-01, records split counts train=3500/val=452/ood_val=580, native think IDs [151667,151668], native leak gate ok, and Arrow hashes; independent hashing of the three Arrow files matches the report. |
| 6 | Export reports record reproducible paths, sha256 hashes, llama.cpp command evidence, Phase 19 training handoff evidence, and TRAIN-02 coverage. | VERIFIED | Export report contains command arrays for `tsc_cycle.student.export_gguf`, `convert_hf_to_gguf.py --outtype f16`, and `llama-quantize ... Q4_K_M`; records llama.cpp tool paths, TRAIN-01 handoff hashes, TRAIN-02 coverage, and artifact hashes. |

**Score:** 6/6 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `tsc_cycle/student/sft_v42.py` | v4.2 QLoRA constants/defaults/run-root guards | VERIFIED | Exists and substantive; locks Phase 18 tokenized paths, Qwen3-4B model, QLoRA settings, v4.2 run prefix. |
| `tsc_cycle/v4_gates/phase19_training.py` | Phase 18 handoff tokenization and TRAIN-01 report gate | VERIFIED | Exists and substantive; validates Phase 18 report/hash/splits, writes tokenized manifest/report, validates full training evidence. |
| `tsc_cycle/student/train.py` | Heavy QLoRA entrypoint with v4_2 branch | VERIFIED | `--phase` choices include `v4_2`; branch imports `sft_v42`, validates pretrain inputs, uses existing trainer flow, and writes Phase 19 reports. |
| `scripts/run_v4_phase19_train.sh` | DGX Spark-safe v4.2 training launcher | VERIFIED | Uses repo venv and `scripts/dgx_spark/run_safe.sh 100G --`, passes `--phase v4_2`, canonical Phase 18 paths, and validates report after training. |
| `tests/test_v4_phase19_training_export.py` | Phase 19 training/export contract tests | VERIFIED | Substantive tests cover defaults, tokenization, report gates, wrappers, export paths/hashes; executed with adjacent export regression. |
| `data/v4_2/phase18/tokenized/*.arrow` and manifest | Real train/val/ood_val tokenized handoff | VERIFIED | train/val/ood_val Arrow files exist with report-matching sha256 and split counts. |
| `artifacts/v4_2/phase19/tokenization_report.json` | Tokenization evidence report | VERIFIED | `ok: true`, TRAIN-01, Phase 18 hashes, native-think leak gate, split counts/hashes. |
| `runs/v4.2-4B-20260518T111519Z/phase19_sft_report.json` | Completed TRAIN-01 training evidence | VERIFIED | Real file exists; independent validator returned `ok: true`, `next_phase_allowed: true`, `requirements_covered: [TRAIN-01]`. |
| `tsc_cycle/v4_gates/phase19_export.py` | Phase 19 export plan/report gate | VERIFIED | Exists and substantive; validates TRAIN-01 handoff, path safety, llama.cpp evidence, artifact hashes, TRAIN-02. |
| `tsc_cycle/student/export_gguf.py` | Existing heavy merge/GGUF implementation with phase19 defaults | VERIFIED | `--export-phase phase19` uses Phase 19 plan/report functions and v4.2 defaults while preserving phase10 defaults. |
| `scripts/run_v4_phase19_export.sh` | DGX Spark-safe v4.2 export launcher | VERIFIED | Validates training report, launches `tsc_cycle.student.export_gguf --export-phase phase19` via `run_safe.sh 100G --`, validates export report. |
| `runs/v4.2-4B-20260518T111519Z/phase19_export_report.json` | Completed TRAIN-02 export evidence | VERIFIED | Real file exists; independent validator returned `ok: true`, `next_phase_allowed: true`, `requirements_covered: [TRAIN-02]`. |
| `runs/v4.2-4B-20260518T111519Z/merged_hf/model.safetensors` | Merged HF weights | VERIFIED | Exists, size 8044981680, sha256 `ed7f6b8ca85beccc90ae6066e9e49ed4195df4258189d86874211ea1ec8b7b98`. |
| `runs/v4.2-4B-20260518T111519Z/gguf/model.fp16.gguf` | fp16 GGUF export | VERIFIED | Exists, size 8051284640, sha256 `e839698cfb4a66b5d9cc4045a34ea7472e76f4333cf108771bfe929d5c7459a8`. |
| `runs/v4.2-4B-20260518T111519Z/gguf/model.q4_K_M.gguf` | q4_K_M GGUF export | VERIFIED | Exists, size 2497280160, sha256 `2620e1b62b19dfca301c4a8fb183becd1e2da896e5d1d9c2410351a9e3441610`. |

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| `tsc_cycle/v4_gates/phase19_training.py` | `data/v4_2/phase18/labeled_calibrated.jsonl` | Phase 18 calibrated source dataset read/tokenization | WIRED | `Phase19TrainingConfig.DEFAULT_CALIBRATED_JSONL`; `validate_phase18_handoff` hashes it; `tokenize_phase18_handoff` reads rows and tokenizes. |
| `tsc_cycle/v4_gates/phase19_training.py` | `data/v4_2/phase18/splits/*.index.jsonl` | Preserved split membership controls Arrow outputs | WIRED | `_load_phase18_split_indexes` reads train/val/ood_val index JSONL; tokenization iterates split index rows and rejects missing membership. |
| `tsc_cycle/v4_gates/phase19_training.py` | `artifacts/v4_2/phase18/reconstruction_report.json` | Green Phase 18 report/hash validation before tokenization/training | WIRED | `validate_phase18_handoff` checks ok/next_phase_allowed, DATA coverage, dataset hash, split counts/IDs. |
| `tsc_cycle/student/train.py` | `tsc_cycle/student/sft_v42.py` | `--phase v4_2` branch imports v4.2 constants and existing QLoRA flow | WIRED | Branch imports `from tsc_cycle.student import sft_v42`, validates handoff/run root, calls shared `load_qlora_model_and_tokenizer` and `build_trainer`. |
| `tsc_cycle/v4_gates/phase19_export.py` | `runs/v4.2-4B-*/phase19_sft_report.json` | Training handoff validation before export plan/report acceptance | WIRED | `load_phase19_handoff` calls `validate_phase19_training_report`; export report validator revalidates TRAIN-01 handoff and matching hashes. |
| `tsc_cycle/v4_gates/phase19_export.py` | `tsc_cycle/student/export_gguf.py` | Export command evidence and heavy merge/GGUF path | WIRED | Export plan command evidence includes `-m tsc_cycle.student.export_gguf --export-phase phase19`; `export_gguf.py` imports `build_phase19_export_plan` and `write_phase19_export_report`. |
| `scripts/run_v4_phase19_export.sh` | `tsc_cycle/student/export_gguf.py` | DGX-safe heavy merge and GGUF conversion command | WIRED | Wrapper invokes `$PY -m tsc_cycle.student.export_gguf --export-phase phase19 ...` through `scripts/dgx_spark/run_safe.sh 100G --`. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|---|---|---|---|---|
| `tsc_cycle/v4_gates/phase19_training.py` tokenization | Tokenized rows and hashes | Phase 18 calibrated JSONL plus split index JSONL plus local Qwen tokenizer | Yes | FLOWING — report and manifest contain real split counts/hashes; Arrow files exist with matching hashes. |
| `tsc_cycle/student/train.py` v4_2 branch | Training report fields | Real Trainer state, saved adapter dir, tokenized manifest and Phase 18 hashes | Yes | FLOWING — validator recomputed adapter/data/report hashes and confirmed full-run steps. |
| `tsc_cycle/v4_gates/phase19_export.py` report | Artifact records and command evidence | Real merged HF/GGUF files plus llama.cpp tools plus training handoff validator | Yes | FLOWING — validator recomputed artifact hashes and revalidated TRAIN-01 handoff. |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Phase 19 tests and adjacent export regressions pass | `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest tests/test_v4_phase19_training_export.py tests/test_v4_phase10_gguf_contracts.py -q` | 17 passed | PASS |
| Real TRAIN-01 report validates | `/home/samuel/TSC_CYCLE/.venv/bin/python -m tsc_cycle.v4_gates.phase19_training validate-report --run-root runs/v4.2-4B-20260518T111519Z --report-path runs/v4.2-4B-20260518T111519Z/phase19_sft_report.json` | `ok: true`, `next_phase_allowed: true`, `fatal_failures: []`, TRAIN-01 | PASS |
| Real TRAIN-02 report validates | `/home/samuel/TSC_CYCLE/.venv/bin/python -m tsc_cycle.v4_gates.phase19_export --run-root runs/v4.2-4B-20260518T111519Z --report runs/v4.2-4B-20260518T111519Z/phase19_export_report.json --evaluate-only` | `ok: true`, `next_phase_allowed: true`, `fatal_failures: []`, TRAIN-02 | PASS |
| Key artifact hashes match reports | Python sha256 spot-check over Arrow, adapter, merged HF, tokenizer, and GGUF files | All expected files exist and hashes match report/summary values | PASS |

### Probe Execution

No phase-declared `probe-*.sh` files were found in the Phase 19 plan/summary. Step 7c skipped.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| TRAIN-01 | `19-01-PLAN.md` | Maintainer can retrain `Qwen/Qwen3-4B-Thinking-2507` with the calibrated v4.2 dataset using the existing DGX Spark-safe QLoRA stack and without introducing a new base model or training framework. | SATISFIED | Training wrapper/source/report validation prove Qwen3-4B, existing QLoRA settings, DGX-safe run wrapper, Phase 18 calibrated/tokenized data, real adapter, and accepted TRAIN-01 report. |
| TRAIN-02 | `19-02-PLAN.md` | Maintainer can export the calibrated model to merged HF plus GGUF fp16 and q4_K_M artifacts with reproducible paths, hashes, and export reports. | SATISFIED | Export report validation proves merged HF, fp16 GGUF, q4_K_M GGUF, paths, hashes, llama.cpp commands, TRAIN-01 handoff, and TRAIN-02 coverage. |

No orphaned Phase 19 requirements found in `.planning/REQUIREMENTS.md`; traceability maps exactly TRAIN-01 and TRAIN-02 to Phase 19.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---:|---|---|---|
| Multiple Phase 19 source files | various | Empty list/dict initializers and helper `return {}`/`return []` branches | Info | Reviewed as normal accumulator/default/error handling patterns, not user-visible stubs. No unreferenced TBD/FIXME/XXX markers found. |
| `tsc_cycle/v4_gates/phase19_training.py` | 485 | `v4.2-4B-placeholder` in expected step helper | Info | Internal placeholder run-root for calculating expected training args only; not a runtime artifact path. |

### Human Verification Required

None.

### Gaps Summary

No blocking gaps found. The phase goal is achieved: actual code paths and runtime artifacts support retraining the 4B QLoRA model on Phase 18 calibrated/tokenized data, accepted TRAIN-01 training evidence exists, and accepted TRAIN-02 merged HF/fp16 GGUF/q4_K_M GGUF export evidence exists with reproducible paths and hashes.

---

_Verified: 2026-05-18T23:29:51Z_
_Verifier: Claude (gsd-verifier)_
