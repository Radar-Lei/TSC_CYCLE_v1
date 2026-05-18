# Phase 19: 4B QLoRA Retrain & Export - Research

**Researched:** 2026-05-18
**Mode:** local codebase research

## Phase Requirements

Phase 19 covers TRAIN-01 and TRAIN-02:

- TRAIN-01: retrain `Qwen/Qwen3-4B-Thinking-2507` with the calibrated v4.2 dataset using the existing DGX Spark-safe QLoRA stack, without introducing a new base model or training framework.
- TRAIN-02: export the calibrated model to merged HF plus GGUF fp16 and q4_K_M artifacts with reproducible paths, hashes, and export reports.

## Upstream Phase 18 Inputs

Phase 18 produced and verified:

- `data/v4_2/phase18/labeled_calibrated.jsonl` — 4532 retained rows.
- `data/v4_2/phase18/splits/manifest.json` — train 3500, val 452, ood_val 580.
- `data/v4_2/phase18/splits/*.index.jsonl` — deterministic retained splits with provenance/hash fields.
- `artifacts/v4_2/phase18/reconstruction_report.json` — `ok: true`, post policy gate green, hard-constraint retained pass rate 1.0, calibrated JSONL sha256 `f60c263571c938c506db3dc919fdbd1528dba4e271764c8de106b4a626be0d00`.

Phase 18 did not produce tokenized Arrow files. Phase 19 must create or gate `data/v4_2/phase18/tokenized/*.arrow` before full QLoRA training.

## Existing Training Stack

Main code:

- `tsc_cycle/student/train.py` is the heavy executable training entrypoint. It supports `--phase v4` and uses Qwen3-4B, SDPA, NF4, bf16, LoRA r=64, batch 1 x gradient_accumulation 16.
- `tsc_cycle/student/sft_v4.py` contains lightweight v4 constants/config helpers and imports `datasets`/`transformers` at module import time.
- `scripts/run_v4_phase9_train.sh` launches full v4 training through `scripts/dgx_spark/run_safe.sh 100G -- ... tsc_cycle.student.train --phase v4`.
- `tsc_cycle/v4_gates/phase9_smoke.py` and `phase9_report.py` define pretrain smoke and final training report gates.

Current v4 constants are hard-coded to v4.0/Phase 8:

- `RUN_ROOT_PREFIX = "v4.0-4B-"`
- `TOKENIZED_DIR = data/v4/phase8/tokenized`
- `PHASE8_GATE_REPORT = artifacts/v4/phase8/phase8_gate_report.json`
- training reports name `phase8_data_manifest.json` and `phase8_artifact_hashes`.

For Phase 19, prefer adding v4.2-specific code paths and wrappers rather than mutating v4.0 behavior in place.

## Existing Export Stack

Main code:

- `tsc_cycle/student/export_gguf.py` performs heavy adapter merge and GGUF conversion/quantization.
- `tsc_cycle/v4_gates/phase10_export.py` provides lightweight export planning, phase9 handoff validation, output path safety, artifact report writing, and wrapper command evidence.
- `tsc_cycle/v4_gates/phase10_report.py` aggregates export/tokenizer/smoke gates.
- `scripts/run_v4_phase10_export.sh` invokes `tsc_cycle.student.export_gguf` using v4.0 run root.

Current export constants are hard-coded to `runs/v4.0-4B-20260509T184844Z` defaults. Phase 19 should add v4.2 run-root support while reusing the same merge and llama.cpp conversion implementation.

## Recommended Implementation Shape

Implement Phase 19 in two execution plans.

### Plan 19-01: v4.2 training handoff and report contracts

Add lightweight v4.2 gates/module/tests that:

- validate Phase 18 reconstruction report is green and covers DATA-01/DATA-02.
- tokenize `data/v4_2/phase18/labeled_calibrated.jsonl` into `data/v4_2/phase18/tokenized/train.arrow`, `val.arrow`, and `ood_val.arrow` using the existing v4 prompt/assistant protocol and tokenizer checks.
- expose v4.2 training constants: model `Qwen/Qwen3-4B-Thinking-2507`, run prefix `v4.2-4B-`, tokenized dir, Phase 18 report path, WANDB project reuse or v4.2-specific project.
- add `--phase v4_2` support to `tsc_cycle.student.train` using the same QLoRA stack and same locked LoRA/training arguments, but with Phase 18 handoff and v4.2 run/report names.
- add v4.2 wrapper script, e.g. `scripts/run_v4_phase19_train.sh`, that launches through `scripts/dgx_spark/run_safe.sh 100G --`.
- add a v4.2 phase19 report gate that validates model name, run root prefix, loss curve, VRAM, adapter hash, data manifest hash, Phase 18 artifact hashes, smoke evidence, and Phase 20 handoff.

### Plan 19-02: v4.2 export planning/report contracts

Add v4.2-specific export wrappers or extend current export gate to accept defaults for a v4.2 run root:

- default run root should be `runs/v4.2-4B-<timestamp>`.
- export report should validate merged HF safetensors/tokenizer, GGUF fp16, GGUF q4_K_M, hashes, llama.cpp tools, commands, and Phase 19 handoff.
- wrapper script should invoke existing `tsc_cycle.student.export_gguf` with v4.2 run root and report paths.
- aggregate/handoff report should record paths/hashes for merged HF, fp16 GGUF, q4_K_M GGUF, tokenizer parity, and smoke report inputs where available.

## Execution Considerations

Full training and GGUF export are long-running. The implementation should make launch and report gates deterministic before starting heavy work. If full training is launched, use the existing `scripts/dgx_spark/run_safe.sh 100G --` wrapper and write logs/PIDs under the v4.2 run root.

The environment note says vLLM is unavailable. Phase 19 should not add vLLM dependencies or routes.

## Risks

- **Dataset mismatch risk:** Existing `--phase v4` checks Phase 8, not Phase 18. Phase 19 must not train a v4.2 run while reporting Phase 8 data hashes.
- **Tokenization gap:** Phase 18 has JSONL/splits but no Arrow tokenized data. Must add tokenization before training.
- **Long-running training risk:** Full retrain can take many hours. Keep scripts resumable and reports explicit.
- **Export path risk:** Existing export defaults are v4.0. v4.2 must not overwrite v4.0 run artifacts.
- **Prompt/protocol drift risk:** Reuse `prompt_builder` unchanged and test native `<think>` leakage checks.

## Validation Strategy

Add tests for:

1. v4.2 constants and parser defaults point to Phase 18 data and `v4.2-4B-` run roots.
2. Phase 18 handoff requires green reconstruction report and matching dataset/split hashes.
3. tokenization creates train/val/ood_val Arrow files with prompt/assistant hashes, no native think IDs, and expected split counts.
4. training report gate accepts only v4.2 run roots, Phase 18 data manifest hashes, adapter files, model name, and requirements TRAIN-01.
5. export planning rejects v4.0/frozen roots and records merged HF/GGUF paths/hashes for TRAIN-02.

Targeted tests:

`/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest tests/test_v4_phase19_training_export.py -q`

Adjacent regression:

`/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest tests/test_v4_phase19_training_export.py tests/test_v4_phase18_calibrated_dataset_rebuild.py tests/test_v4_phase9_sft_contracts.py tests/test_v4_phase10_gguf_contracts.py -q`
