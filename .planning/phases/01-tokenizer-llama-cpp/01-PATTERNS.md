---
phase: 01
slug: tokenizer-llama-cpp
status: complete
created: 2026-05-08
---

# Phase 1 Pattern Map

## Candidate Files and Closest Analogs

| New/Modified File | Role | Closest Existing Analog | Pattern to Reuse |
|---|---|---|---|
| `tsc_cycle/tokenizer_check.py` | Shared tokenizer invariants | same file | Keep `CheckResult(ok, details)` return shape; replace v1.0 constants with dynamic lookup and ≥3 custom tag requirement. |
| `tsc_cycle/v3_gates/env_smoke_v3.py` | 9B model load + forward hard gate | `tsc_cycle/student/train.py` | Reuse `BitsAndBytesConfig(load_in_4bit=True, nf4, bf16)`, `AutoModelForCausalLM.from_pretrained(... attn_implementation="sdpa")`, warmup forward shape. |
| `tsc_cycle/v3_gates/tokenizer_audit_v3.py` | Writes `tokenizer_audit.json` | `tsc_cycle/tokenizer_check.py`, `tsc_cycle/student/dataset.py` | Reuse custom tag constants from `prompt_builder.py`; avoid duplicated protocol strings. |
| `tsc_cycle/v3_gates/tokenizer_parity_v3.py` | HF ↔ llama-tokenize 100-prompt parity | `tsc_cycle/student/parity_prompts.py`, `tsc_cycle/student/tokenize_sanity.py` | Deterministic prompt selection, JSONL fixture writing, explicit mismatch diagnostics. |
| `tsc_cycle/v3_gates/memory_budget_v3.py` | Max-seq memory sweep + 100-step dry-run | `tsc_cycle/student/train.py` | Reuse model/LoRA preparation, gradient checkpointing `use_reentrant=False`, Trainer-style batch creation where possible. |
| `tsc_cycle/v3_gates/gguf_microconvert_v3.py` | llama.cpp convert/quantize/infer hard gate | `tsc_cycle/student/export_gguf.py` | Reuse `LLAMA_CPP`, `CONVERT`, `QUANTIZE`, subprocess `check=True`, JSON summary. |
| `tsc_cycle/v3_gates/phase1_report.py` | Aggregate pass/fail report | `tsc_cycle/eval/decision.py` | Deterministic JSON report with explicit thresholds and failure reasons. |
| `scripts/run_v3_phase1_gates.sh` | Runs gates in order | `scripts/run_pipeline.sh`, `scripts/dgx_spark/run_safe.sh` | Shell `set -euo pipefail`; call Python via `.venv/bin/python -m`; long GPU gates through run_safe. |
| `tests/test_tokenizer_check.py` | Unit tests for dynamic tokenizer helpers | `tests/test_prompt_builder.py`, `tests/test_hashing.py` | Pytest direct function checks; no network/model downloads in unit tests. |

## Concrete Existing Code Excerpts

### Model load pattern from `tsc_cycle/student/train.py`

```python
bnb_cfg = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_compute_dtype=torch.bfloat16,
    bnb_4bit_use_double_quant=True,
)
model = AutoModelForCausalLM.from_pretrained(
    args.model,
    quantization_config=bnb_cfg,
    attn_implementation="sdpa",
    torch_dtype=torch.bfloat16,
    device_map={"": 0},
)
model.config.use_cache = False
model = prepare_model_for_kbit_training(
    model,
    use_gradient_checkpointing=True,
    gradient_checkpointing_kwargs={"use_reentrant": False},
)
```

### Tokenizer constants pattern from `tsc_cycle/prompt_builder.py`

```python
TAG_THINK_OPEN = "<start_working_out>"
TAG_THINK_CLOSE = "<end_working_out>"
TAG_SOLUTION_OPEN = "<SOLUTION>"
TAG_SOLUTION_CLOSE = "</SOLUTION>"
```

Use these imports everywhere; do not duplicate literals except for native rejection targets `<think>` / `</think>`.

### Existing tokenizer check shape from `tsc_cycle/tokenizer_check.py`

```python
@dataclass
class CheckResult:
    ok: bool
    details: dict
```

Preserve this for backward compatibility, but make native IDs dynamic.

### run_safe memory guard from `scripts/dgx_spark/run_safe.sh`

```bash
exec sudo systemd-run --scope \
    --uid="$(id -un)" \
    --gid="$(id -gn)" \
    -p "MemoryMax=$MEMORY_MAX" \
    -p MemorySwapMax=0 \
    --same-dir \
    ...
```

Long Qwen3.5-9B gates must use this wrapper.

### GGUF subprocess pattern from `tsc_cycle/student/export_gguf.py`

```python
LLAMA_CPP = Path(os.environ.get("LLAMA_CPP_DIR", "/home/samuel/projects/EvoProgTSC/llama.cpp"))
CONVERT = LLAMA_CPP / "convert_hf_to_gguf.py"
QUANTIZE = LLAMA_CPP / "llama-quantize"
subprocess.run(cmd, check=True)
```

Add `llama-cli` and `llama-tokenize` path checks in Phase 1.

### Deterministic prompt selection from `tsc_cycle/student/parity_prompts.py`

```python
rng_id = random.Random(seed)
rng_ood = random.Random(seed + 1)
id_picks = rng_id.sample(id_bucket, n_id)
ood_picks = rng_ood.sample(ood_bucket, n_ood)
```

Reuse this deterministic split for 100 tokenizer parity prompts.

## Pitfalls to Avoid

- Do not keep `NATIVE_THINK_OPEN_ID = 151667` / `151668` as Qwen3.5 truth.
- Do not import or require vLLM in Phase 1 environment readiness.
- Do not use native `<think>` as a training/protocol tag.
- Do not use `llama-server` as a substitute for the requested `llama-tokenize` parity gate.
- Do not run 9B GPU gates outside `scripts/dgx_spark/run_safe.sh 100G -- ...`.
- Do not mutate `data/labeled.jsonl` or frozen v1.0 run artifacts.
