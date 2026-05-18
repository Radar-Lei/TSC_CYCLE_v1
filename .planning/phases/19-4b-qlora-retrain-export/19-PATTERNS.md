# Phase 19: 4B QLoRA Retrain & Export - Pattern Map

**Mapped:** 2026-05-18
**Files analyzed:** Phase 9 training, Phase 10 export, Phase 18 dataset rebuild, tests
**Analogs found:** 5 / 5

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|
| `tsc_cycle/student/sft_v42.py` | lightweight training constants/helpers | Phase 18 report/tokenized data -> training evidence | `tsc_cycle/student/sft_v4.py` | role-match |
| `tsc_cycle/v4_gates/phase19_training.py` | CLI/report gate + tokenization handoff | calibrated JSONL/splits -> tokenized Arrow/report | `tsc_cycle/v4_gates/dataset_rebuild.py` + `phase9_report.py` | role-match |
| `tsc_cycle/student/train.py` | heavy training entrypoint | tokenized Arrow -> LoRA adapter/training report | existing `--phase v4` branch | exact |
| `tsc_cycle/v4_gates/phase19_export.py` | export planning/report gate | adapter -> merged HF/GGUF evidence | `tsc_cycle/v4_gates/phase10_export.py` | role-match |
| `tests/test_v4_phase19_training_export.py` | contract tests | fixtures -> reports/wrappers | `tests/test_v4_phase9_sft_contracts.py` + `tests/test_v4_phase10_gguf_contracts.py` | exact |

## Patterns to Reuse

### Training config lock

Use `tsc_cycle/student/sft_v4.py` for:

- `MODEL_NAME = "Qwen/Qwen3-4B-Thinking-2507"`
- LoRA config r=64, alpha=64, dropout=0, target all-linear.
- training args: bf16, SDPA, NF4, gradient checkpointing, packing false, no chat template.
- run-root validation with prefix checks and shell metachar rejection.

For v4.2, copy semantics but change run prefix and data/report paths.

### Heavy training entrypoint

Use `tsc_cycle/student/train.py` existing `--phase v4` branch. Add a sibling `--phase v4_2` branch that calls the same `load_qlora_model_and_tokenizer`, `build_trainer`, `bnb_warmup`, `trainer.train`, adapter save, and report writing flow, but reads v4.2 constants/gates.

### Tokenization

Use Phase 8 dataset rebuild tokenization patterns:

- `build_user_prompt(input_obj)` + `build_full_assistant(reasoning, solution)`.
- tokenize raw prompt+assistant with `add_special_tokens=False`.
- check native think token IDs before truncation.
- write Arrow splits with sample_id/input_ids/attention_mask/labels/raw_length/truncated/prompt_hash/assistant_hash.

Use Phase 18 split indexes to determine membership; do not re-randomize.

### Report gates

Use `phase9_report.py` for final training report shape:

- model config gate.
- loss curve, duration, VRAM gates.
- adapter hash gate.
- data manifest hash gate.
- handoff gate.

For v4.2, replace Phase 8 artifact hash requirement with Phase 18 reconstruction/tokenized artifact hash requirement and TRAIN-01 coverage.

### Export planning

Use `phase10_export.py` for:

- Phase 9/19 handoff validation.
- llama.cpp tool discovery.
- output path must stay under run root.
- merged HF, fp16 GGUF, q4_K_M GGUF report records.
- command evidence for convert and quantize.

For v4.2, keep implementation but default run prefix and report names should be Phase 19/v4.2.

### Tests

Follow lazy import and no heavy stack patterns from Phase 10 tests. Unit tests should target lightweight gates and wrappers, not import `torch`/`transformers` at collection time.

## Path Safety

Reject:

- frozen v1 root `runs/20260507T032419Z`.
- v4.0 run roots for v4.2 outputs unless explicitly used as read-only analog inputs.
- broad repo/data/artifacts roots.
- paths with shell metacharacters in run roots.

Accept defaults:

- `data/v4_2/phase18/tokenized`
- `artifacts/v4_2/phase19`
- `runs/v4.2-4B-<timestamp>`

## No New Dependencies

Do not add vLLM, flash-attn, Unsloth, Axolotl, or package installs. Use existing project dependencies and the existing DGX Spark-safe launch wrapper.
