---
phase: 01
slug: tokenizer-llama-cpp
status: research_complete
created: 2026-05-08
---

# Phase 1 Research — 环境 + Tokenizer + 显存 + llama.cpp 四合一硬门禁

## Scope

Phase 1 是 v3.0 的 abort gate：在任何 7K 教师标注、retokenize、9B SFT、GGUF 导出成本发生前，必须用本机真实环境证明 Qwen3.5-9B 路径可行。任一 fatal gate 失败时后续 Phase 2–6 不应执行。

Covered requirements: ENV-01, ENV-02, ENV-03, TOK-01, TOK-02, TOK-03, TOK-04, MEM-01, MEM-02, MEM-03.

## Current Codebase Findings

### Existing DGX Spark support

- `scripts/dgx_spark/env.sh` and `scripts/dgx_spark/run_safe.sh` already exist and are the right execution wrapper pattern.
- `scripts/dgx_spark/run_safe.sh` already enforces `sudo systemd-run --scope`, `MemoryMax`, `MemorySwapMax=0`, inherited CUDA/Triton env, and a minimum `MemAvailable` preflight.
- `scripts/dgx_spark/verify.py` checks CUDA availability, bf16 matmul, `TRITON_PTXAS_PATH`, and rejects upstream `flash_attn` on aarch64.
- Risk: `verify.py` currently imports `vllm`; project instructions say vLLM is temporarily unavailable, so Phase 1 plans should avoid making vLLM import a hard requirement.

### Existing tokenizer checks

- `tsc_cycle/tokenizer_check.py` is the central tokenizer invariant module, but it is v1.0/4B-specific:
  - docstring names `Qwen3-4B-Thinking-2507`.
  - native think IDs are hardcoded as `151667` / `151668`.
  - expected vocab size is hardcoded as `151936`.
  - custom tags only require `>=2` sub-tokens, while v3.0 requires `>=3`.
- `tsc_cycle/student/tokenize_sanity.py` repeats hardcoded native think IDs and v1.0 artifact defaults. It is a GGUF metadata tokenizer parity probe, not the requested Phase 1 HF ↔ `llama-tokenize` 100-prompt parity gate.
- `tsc_cycle/student/dataset.py` imports hardcoded native IDs from `tokenizer_check.py`; this should use dynamic audit results or tokenizer-derived forbidden IDs after Phase 1.

### Existing model/training assumptions

- `tsc_cycle/student/train.py` defaults to `MODEL_NAME = "Qwen/Qwen3-4B-Thinking-2507"`; Phase 1 must introduce Qwen3.5-9B smoke and later Phase 4 must update defaults.
- `train.py` already uses `AutoModelForCausalLM`, bnb NF4, bf16 compute, SDPA, PEFT LoRA, and `gradient_checkpointing_kwargs={"use_reentrant": False}` — these are the correct patterns to preserve.
- `train.py` currently uses batch size 4, grad_accum 8, lora_alpha 128, dropout 0.05, and target modules list. v3.0 later requires batch size 1, grad_accum 16, alpha 64, dropout 0.0, and target_modules="all-linear"; Phase 1 only needs smoke/dry-run gates, not full Phase 4 training refactor.
- `train.py` currently does not assert absence of `vision*` parameter names. Phase 1 must add a smoke script that asserts `not any(name.startswith("vision") or ".vision" in name for name, _ in model.named_parameters())` after loading Qwen3.5-9B.

### Existing GGUF/export assumptions

- `tsc_cycle/student/export_gguf.py` defaults to `/home/samuel/projects/EvoProgTSC/llama.cpp`, `convert_hf_to_gguf.py`, and `llama-quantize` — exactly the Phase 1/5 reference path.
- It is v1.0-oriented (`base-model` default 4B, output `bf16` GGUF), but its subprocess pattern is reusable.
- Phase 1 micro-convert should not require full 9B training output. It should create a tiny/dummy LoRA adapter or a minimal copied HF fixture sufficient to exercise: merge/convert/quantize/`llama-cli` 5-token inference. If dummy LoRA on 9B is too expensive, the plan must still keep the command under run_safe and treat any failure as fatal evidence.
- There are multiple llama.cpp paths in existing code: `/home/samuel/projects/EvoProgTSC/llama.cpp` in export/eval and `/home/samuel/llama.cpp/build/bin/llama-server` in parity code. Phase 1 must explicitly verify the mandated EvoProgTSC path binaries: `convert_hf_to_gguf.py`, `llama-quantize`, `llama-cli`, and `llama-tokenize` if present.

### Existing parity/eval code

- `tsc_cycle/student/parity_prompts.py` can select deterministic prompts from `data/labeled.jsonl`, but defaults to v1.0 run paths.
- `tsc_cycle/eval/parity.py`, `tsc_cycle/eval/run_eval.py`, and `tsc_cycle/eval/generate_gguf.py` use llama.cpp execution patterns. They are useful analogs but not direct Phase 1 deliverables.

## Recommended Implementation Shape

### Plan A — Phase 1 hard-gate scripts + runbook

Create a dedicated `tsc_cycle/v3_gates/` package (or `tsc_cycle/student/` scripts if minimizing new package surface) with five small CLI entrypoints:

1. `env_smoke_v3.py`
   - Inputs: `--model Qwen/Qwen3.5-9B`, `--out runs/v3.0-gates/env_smoke.json`.
   - Verifies `.venv` can import torch/transformers/peft/bitsandbytes without vLLM.
   - Loads `AutoTokenizer` and `AutoModelForCausalLM` with bnb NF4, bf16, `attn_implementation="sdpa"`, `device_map={"": 0}`.
   - Confirms architecture class name contains `Qwen3_5` or config model_type/architectures identify Qwen3.5 causal LM.
   - Runs one forward pass on a tiny prompt.
   - Asserts no parameter name contains `vision`.
   - Writes JSON with model id, architecture, torch CUDA, GPU name, forward loss/logits shape, and `vision_param_count`.

2. `tokenizer_audit_v3.py`
   - Inputs: `--model Qwen/Qwen3.5-9B`, `--out artifacts/v3/tokenizer_audit.json`.
   - Dynamically encodes four custom tags with `add_special_tokens=False`; asserts each length `>=3`.
   - Dynamically encodes `<think>` and `</think>`; writes actual IDs from Qwen3.5 tokenizer, not v1.0 constants.
   - Writes tokenizer length/vocab size, special token map, added vocab hits for custom tags, and failure list.
   - Should update or supersede `tsc_cycle/tokenizer_check.py` so downstream code can consume dynamic native IDs.

3. `tokenizer_parity_v3.py`
   - Inputs: `--model Qwen/Qwen3.5-9B`, `--prompts data/parity/v3_tokenizer_prompts.jsonl`, `--llama-tokenize /home/samuel/projects/EvoProgTSC/llama.cpp/llama-tokenize`, `--out artifacts/v3/tokenizer_parity.json`.
   - Builds 100 deterministic prompts using `data/labeled.jsonl` plus synthetic edge prompts if fewer than 100 are available.
   - Compares HF `AutoTokenizer.encode(..., add_special_tokens=False)` against `llama-tokenize` output for the same text.
   - Important planning risk: `llama-tokenize` usually needs a GGUF tokenizer/model file, not a HF model id. The plan should first verify the local binary CLI syntax (`--help`) and, if it requires a GGUF, generate/use the Phase 1 micro-converted GGUF tokenizer fixture before parity.
   - Writes mismatches with prompt id, first differing index, HF IDs, llama IDs; requires 100/100 exact match.

4. `memory_budget_v3.py`
   - Inputs: `--model Qwen/Qwen3.5-9B`, `--seqs 1536 2048 2560 3072 4096`, `--out artifacts/v3/memory_budget.json`.
   - For each max_seq candidate, load 9B NF4 + LoRA r=64 + gradient checkpointing `use_reentrant=False`, run a controlled train micro-step or short loop, record `torch.cuda.max_memory_allocated/reserved`, elapsed time, success/OOM status.
   - Select largest `max_seq_length` whose measured peak is `<85GB`.
   - Must be run through `scripts/dgx_spark/run_safe.sh 100G -- python -m ...`.
   - A separate 100-step dry-run can reuse this module with `--steps 100 --seq selected` and must stay inside 100GB cap.

5. `gguf_microconvert_v3.py`
   - Inputs: `--model Qwen/Qwen3.5-9B`, `--llama-cpp /home/samuel/projects/EvoProgTSC/llama.cpp`, `--out runs/v3.0-gates/gguf_microconvert`.
   - Verifies required llama.cpp files/binaries exist.
   - Creates a minimal LoRA adapter and merge target or a documented dummy path sufficient to exercise conversion.
   - Runs `convert_hf_to_gguf.py` to bf16/fp16 GGUF, `llama-quantize ... Q4_K_M`, then `/home/samuel/projects/EvoProgTSC/llama.cpp/llama-cli -m <q4> -n 5 -p ...`.
   - Writes summary JSON with binary paths, output GGUF paths/sizes, command return codes, and inference tail.

A small orchestration shell `scripts/run_v3_phase1_gates.sh` should run all gates in order and stop on first failure.

### Fatal vs non-fatal gates

Fatal:
- CUDA/bnb/SDPA Qwen3.5-9B forward fails.
- Loaded class/architecture is not causal LM or contains `vision*` parameters.
- Any custom tag tokenizes to fewer than 3 sub-tokens.
- Native `<think>`/`</think>` IDs are hardcoded or missing from audit JSON.
- HF ↔ llama-tokenize parity is not 100/100.
- No max_seq candidate has peak `<85GB`.
- 100-step dry-run OOMs inside 100GB cap.
- llama.cpp convert/quantize/inference chain fails.
- Training wrapper cannot prove `systemd-run` memory scope + `MemorySwapMax=0` and swap disabled.

Non-fatal warnings:
- v1.0 docs/docstrings still mention 4B if not used by v3 execution path.
- `llama-server` parity path exists but is not used for Phase 1.
- `vllm` missing from environment, as project instructions explicitly say not to use it.

## Planning Recommendations

Split Phase 1 into 4–5 plans, not one monolith:

1. **Environment/model smoke gate** — implement dynamic Qwen3.5-9B load smoke and run_safe template verification. Covers ENV-01, ENV-03, MEM-03.
2. **Tokenizer audit + downstream dynamic native IDs** — remove/supersede hardcoded v1.0 IDs, write `tokenizer_audit.json`, prove custom tags `>=3`. Covers TOK-01, TOK-02, TOK-04.
3. **HF ↔ llama tokenizer parity fixture** — deterministic 100-prompt fixture and llama-tokenize comparison. Covers TOK-03 and shared GGUF-04 groundwork.
4. **Memory budget profiler** — implement max_seq sweep and 100-step dry-run gate. Covers MEM-01, MEM-02.
5. **llama.cpp micro-convert gate + all-gates runner** — exercise EvoProgTSC llama.cpp path and produce a single gate report. Covers ENV-02 and final phase-level verification.

Dependencies: Plan 1 before Plan 4; Plan 2 before Plan 3; Plan 5 can depend on Plan 2/3 if it supplies GGUF tokenizer fixture for `llama-tokenize`.

## Security / Safety Notes

- Do not run `sudo swapoff -a` without explicit user approval. Phase 1 scripts can detect and fail with instructions if swap is enabled.
- Long GPU jobs must run through `scripts/dgx_spark/run_safe.sh 100G -- ...`.
- Avoid `pip install vllm` and `pip install flash-attn`.
- Use `python -m ...` entrypoints because copied virtualenv console-script shebangs can point to `/home/samuel/dgx-spark-setup/.venv`.
- Scripts should not mutate `data/labeled.jsonl` or v1.0 run artifacts.

## Validation Architecture

Phase 1 validation should be artifact-driven and replayable.

Required artifacts:
- `artifacts/v3/phase1/env_smoke.json` — model load and forward evidence.
- `artifacts/v3/phase1/tokenizer_audit.json` — custom tag lengths and dynamic native think IDs.
- `artifacts/v3/phase1/tokenizer_parity_prompts.jsonl` — exact 100 prompts used for parity.
- `artifacts/v3/phase1/tokenizer_parity.json` — HF vs llama-tokenize parity result, 100/100 required.
- `artifacts/v3/phase1/memory_budget.json` — per-seq peak memory and selected max_seq.
- `artifacts/v3/phase1/train_100step.json` or log JSONL — 100-step dry-run evidence under run_safe 100G.
- `artifacts/v3/phase1/gguf_microconvert.json` — convert/quantize/llama-cli evidence.
- `artifacts/v3/phase1/phase1_gate_report.json` — aggregate pass/fail and fatal reason.

Verification commands:
- `source scripts/dgx_spark/env.sh && python scripts/dgx_spark/verify.py` should pass except vLLM must not be required.
- `scripts/dgx_spark/run_safe.sh 100G -- python -m tsc_cycle.v3_gates.env_smoke_v3 --model Qwen/Qwen3.5-9B --out artifacts/v3/phase1/env_smoke.json`.
- `python -m tsc_cycle.v3_gates.tokenizer_audit_v3 --model Qwen/Qwen3.5-9B --out artifacts/v3/phase1/tokenizer_audit.json`.
- `python -m tsc_cycle.v3_gates.tokenizer_parity_v3 --model Qwen/Qwen3.5-9B --out artifacts/v3/phase1/tokenizer_parity.json`.
- `scripts/dgx_spark/run_safe.sh 100G -- python -m tsc_cycle.v3_gates.memory_budget_v3 --model Qwen/Qwen3.5-9B --seqs 1536 2048 2560 3072 4096 --out artifacts/v3/phase1/memory_budget.json`.
- `scripts/dgx_spark/run_safe.sh 100G -- python -m tsc_cycle.v3_gates.memory_budget_v3 --model Qwen/Qwen3.5-9B --seq $(jq -r .selected_max_seq artifacts/v3/phase1/memory_budget.json) --steps 100 --out artifacts/v3/phase1/train_100step.json`.
- `scripts/dgx_spark/run_safe.sh 100G -- python -m tsc_cycle.v3_gates.gguf_microconvert_v3 --model Qwen/Qwen3.5-9B --out runs/v3.0-gates/gguf_microconvert`.
- `python -m tsc_cycle.v3_gates.phase1_report --artifacts artifacts/v3/phase1 --out artifacts/v3/phase1/phase1_gate_report.json`.

Nyquist sampling:
- Tokenizer parity must use exactly 100 prompts with deterministic seed and mixed ID/OOD/synthetic boundary coverage.
- Memory budget must sample all five specified max_seq candidates, not extrapolate.
- GGUF inference smoke can be only 5 tokens because this is a binary-chain/segfault gate, not quality evaluation.

## Key Pitfalls for Planner

- Do not preserve v1.0 native think IDs as constants for Qwen3.5. Dynamic lookup is a hard requirement.
- Do not use Qwen3.5 vision/conditional-generation classes; use `AutoModelForCausalLM` and assert no `vision*` params.
- Do not require vLLM import success in environment verification.
- Do not treat `llama-server` parity as equivalent to `llama-tokenize` parity; Phase 1 explicitly asks HF encode ↔ `llama-tokenize`.
- Do not let Phase 1 scripts silently continue after OOM or partial parity mismatch. These are abort gates.
- Do not add custom tags as special tokens or resize embeddings.
- Do not write to v1.0 frozen artifacts or `data/labeled.jsonl`.
