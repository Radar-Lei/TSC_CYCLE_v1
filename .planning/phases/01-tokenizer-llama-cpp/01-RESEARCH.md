# Phase 1: 环境 + Tokenizer + 显存 + llama.cpp 四合一硬门禁 - Research

**Researched:** 2026-05-08 [VERIFIED: project memory currentDate]
**Domain:** DGX Spark CUDA 13 / Qwen3.5-9B HF 加载 / tokenizer parity / QLoRA 显存实测 / llama.cpp GGUF 门禁 [VERIFIED: .planning/ROADMAP.md]
**Confidence:** HIGH for environment/stack, MEDIUM for memory peak until Phase 1 dry-run produces measurements [VERIFIED: local probes + cited docs]

## User Constraints

### Locked Decisions
- Phase 1 必须覆盖 ENV-01, ENV-02, ENV-03, TOK-01, TOK-02, TOK-03, TOK-04, MEM-01, MEM-02, MEM-03。 [VERIFIED: .planning/REQUIREMENTS.md]
- 目标模型门禁按 `Qwen/Qwen3.5-9B` 执行，且成功条件要求 `Qwen3_5ForCausalLM` + bnb 4-bit NF4 + SDPA 1-step forward smoke pass。 [VERIFIED: .planning/ROADMAP.md]
- `model.named_parameters()` 加载后不得包含 `vision*` 名空间。 [VERIFIED: .planning/ROADMAP.md]
- 4 个自定义思考标签 `<start_working_out>` / `<end_working_out>` / `<SOLUTION>` / `</SOLUTION>` 必须在 Qwen3.5 tokenizer 下拆为 ≥3 sub-tokens。 [VERIFIED: .planning/REQUIREMENTS.md]
- native `<think>` / `</think>` token id 必须动态写入 `tokenizer_audit.json`，禁止硬编码 v1.0 的 151667/151668。 [VERIFIED: .planning/REQUIREMENTS.md]
- HF `AutoTokenizer.encode` ↔ `llama-tokenize` 必须在 100 个测试 prompt 上 100% parity。 [VERIFIED: .planning/REQUIREMENTS.md]
- 训练数据组装必须绕开 chat_template，raw text 直接拼 `<start_working_out>...`。 [VERIFIED: .planning/REQUIREMENTS.md]
- `memory_budget_v3.py` 必须实测 max_seq_length ∈ {1536, 2048, 2560, 3072, 4096}，选择 peak <85GB 的最大值。 [VERIFIED: .planning/REQUIREMENTS.md]
- 9B + r=64 LoRA + bs=1 + gradient checkpointing `use_reentrant=False` 必须 100 steps 在 100GB cap 内不 OOM。 [VERIFIED: .planning/REQUIREMENTS.md]
- 训练运行必须在 `systemd-run --scope -p MemoryMax=100G -p MemorySwapMax=0` 内，且 swap 关闭。 [VERIFIED: .planning/REQUIREMENTS.md]
- 本机 `/home/samuel/projects/EvoProgTSC/llama.cpp` micro-convert dry-run 必须 pass：dummy LoRA → bf16 GGUF → q4_K_M GGUF → `llama-cli` 推理 5 token 无 segfault。 [VERIFIED: .planning/ROADMAP.md]
- 任一 fatal gate 失败应立即 milestone abort，不应进入数据扩量或训练成本阶段。 [VERIFIED: .planning/ROADMAP.md]

### Claude's Discretion
- 无 Phase 1 CONTEXT.md；本轮未发现上游 `01-CONTEXT.md`。 [VERIFIED: gsd-sdk init.phase-op + filesystem probe]

### Deferred Ideas (OUT OF SCOPE)
- vLLM 推理、flash-attn、Unsloth/Axolotl 新训练栈、全参 SFT、batch_size > 1、Qwen3.6 系列均不属于本 Phase 1 执行范围。 [VERIFIED: .planning/REQUIREMENTS.md + /home/samuel/TSC_CYCLE/CLAUDE.md]

## Project Constraints (from CLAUDE.md)

- 回复和项目说明必须使用简体中文。 [VERIFIED: /home/samuel/TSC_CYCLE/CLAUDE.md]
- Git commit message 不得包含 `Co-Authored-By`。 [VERIFIED: /home/samuel/TSC_CYCLE/CLAUDE.md]
- 本机是 DGX Spark，暂时不能使用 vLLM。 [VERIFIED: /home/samuel/TSC_CYCLE/CLAUDE.md]
- DGX Spark 训练必须遵循 `/dgx-spark-training` 约束：不安装 upstream flash-attn cu12，使用 SDPA，加入 swap/OOM 防护，复用已知良好 venv。 [VERIFIED: /home/samuel/TSC_CYCLE/CLAUDE.md + /home/samuel/.claude/skills/dgx-spark-training/SKILL.md]
- 不要直接读取或发送整个 PDF，应按页拆分。 [VERIFIED: /home/samuel/TSC_CYCLE/CLAUDE.md]
- GSD 工作流要求不要在无 GSD 入口的情况下做直接代码改动；本任务是 `/gsd-plan-phase` 派生研究，允许写 Phase research artifact。 [VERIFIED: /home/samuel/TSC_CYCLE/CLAUDE.md + gsd-sdk init.phase-op]

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| ENV-01 | `/home/samuel/TSC_CYCLE/.venv` 加载 `Qwen/Qwen3.5-9B`，`Qwen3_5ForCausalLM` + bnb 4-bit NF4 + SDPA forward smoke pass | Use `AutoModelForCausalLM`, `BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_compute_dtype=torch.bfloat16)`, `attn_implementation="sdpa"`; assert class/config and no vision params. [CITED: HF bitsandbytes docs; VERIFIED: local venv package probe] |
| ENV-02 | EvoProgTSC llama.cpp micro-convert dry-run pass | Local `convert_hf_to_gguf.py` registers `Qwen3_5ForCausalLM`; `llama-quantize` and `llama-cli` exist; `llama-tokenize` is missing in EvoProgTSC build and must be built or pointed to `/home/samuel/llama.cpp/build/bin/llama-tokenize`. [VERIFIED: local filesystem + local convert script grep] |
| ENV-03 | `systemd-run` memory scope + swap off | Existing `scripts/dgx_spark/run_safe.sh` already uses `sudo systemd-run --scope`, `MemoryMax`, `MemorySwapMax=0`, inherited CUDA/Triton env, and preflight memory check. [VERIFIED: scripts/dgx_spark/run_safe.sh] |
| TOK-01 | 4 个自定义标签均拆为 ≥3 sub-tokens | Existing `tsc_cycle/tokenizer_check.py` only requires ≥2 and is v1.0-hardcoded; Phase 1 must add Qwen3.5 dynamic audit. [VERIFIED: codebase read + requirements] |
| TOK-02 | native `<think>`/`</think>` dynamic token IDs written to audit JSON | Existing code hardcodes 151667/151668 and must be superseded by tokenizer-derived IDs. [VERIFIED: tsc_cycle/tokenizer_check.py] |
| TOK-03 | HF encode ↔ `llama-tokenize` 100 prompt parity | llama.cpp tokenize source supports `--model`, `--prompt`, `--ids`, `--no-bos`, `--no-parse-special`; it requires a model file loaded vocab-only. [CITED: llama.cpp tools/tokenize source via WebFetch] |
| TOK-04 | raw text assembly, no chat_template | Existing `prompt_builder.py` already builds raw protocol text and tests assert no legacy tag; Phase 1 should add no-chat-template regression tests for v3 gates. [VERIFIED: prompt_builder.py + tests/test_prompt_builder.py] |
| MEM-01 | Sweep 5 max_seq candidates and select largest peak<85GB | Must be measured, not estimated; use `torch.cuda.reset_peak_memory_stats()` and artifact JSON. [CITED: PyTorch CUDA memory APIs are standard; ASSUMED: exact API availability in torch 2.11] |
| MEM-02 | 100-step dry-run in 100GB cap | Run via `scripts/dgx_spark/run_safe.sh 100G -- python -m ...`; record peak memory and OOM status as artifact. [VERIFIED: run_safe.sh] |
| MEM-03 | Use `Qwen3_5ForCausalLM`, not conditional generation, and assert no vision namespace | HF model card states `Qwen/Qwen3.5-9B` is a causal LM with vision encoder and examples use `AutoModelForImageTextToText`, so the causal-LM/no-vision path is the critical gate. [CITED: Qwen/Qwen3.5-9B HF model card] |
</phase_requirements>

## Summary

Phase 1 should be planned as an abort-gate suite, not as normal feature work: each gate must produce replayable JSON/log artifacts and stop on first fatal failure. [VERIFIED: .planning/ROADMAP.md] The highest-risk gates are (1) proving `Qwen/Qwen3.5-9B` can be loaded as a text-only `Qwen3_5ForCausalLM` despite the HF model card describing a vision encoder, (2) replacing v1.0 hardcoded native think token IDs with dynamic Qwen3.5 audit results, and (3) building or locating a usable `llama-tokenize` binary because the mandated EvoProgTSC llama.cpp root currently lacks that binary. [CITED: Qwen HF model card; VERIFIED: local probes]

The existing codebase already has useful v1.0 patterns: raw prompt protocol, dataset loss masking, DGX Spark `run_safe.sh`, and GGUF export subprocess structure. [VERIFIED: prompt_builder.py, dataset.py, run_safe.sh, export_gguf.py] However, v1.0 tokenizer checks are unsafe for v3.0 because they hardcode Qwen3-4B vocab size and native think token IDs. [VERIFIED: tokenizer_check.py]

**Primary recommendation:** Implement Phase 1 as five dedicated gate modules under a small `tsc_cycle/v3_gates/` package plus one `scripts/run_v3_phase1_gates.sh` orchestrator; produce `artifacts/v3/phase1/*` JSON outputs and abort immediately on any fatal gate. [VERIFIED: codebase structure; ASSUMED: package name accepted by user]

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| DGX Spark environment smoke | Local runtime / OS | Python package layer | CUDA, swap, systemd scope, and venv imports are machine/runtime invariants, not model logic. [VERIFIED: dgx-spark-training skill] |
| Qwen3.5 model load smoke | Python model layer | Local runtime / GPU | `AutoModelForCausalLM` + bnb + SDPA proves HF/runtime compatibility before training. [CITED: HF bitsandbytes docs] |
| Tokenizer audit | Python data-prep layer | llama.cpp tokenizer layer | HF tokenizer produces training IDs; llama.cpp must match deployment IDs. [VERIFIED: requirements + llama tokenize docs] |
| Memory budget sweep | Python training layer | OS memory scope | Peak memory depends on model/LoRA/sequence choices but must be run inside 100GB systemd cap. [VERIFIED: requirements + run_safe.sh] |
| GGUF micro-convert | Export/deployment tooling | Python model artifact layer | llama.cpp conversion/quantization/inference owns GGUF deployment compatibility. [VERIFIED: export_gguf.py + local llama.cpp probes] |
| Gate report aggregation | Project orchestration | — | Planner needs a single pass/fail artifact with fatal reason before Phase 2. [ASSUMED] |

## Standard Stack

### Core
| Library / Tool | Version | Purpose | Why Standard |
|----------------|---------|---------|--------------|
| Python | 3.12.3 in `/home/samuel/TSC_CYCLE/.venv` | Gate runtime | Project venv is the target path named by ENV-01. [VERIFIED: `/home/samuel/TSC_CYCLE/.venv/bin/python` probe] |
| PyTorch | 2.11.0+cu130, published 2026-03-23 | CUDA/bf16 execution and memory stats | DGX Spark CUDA 13 target uses cu130 torch in the existing venv. [VERIFIED: local venv probe + PyPI JSON] |
| Transformers | 5.8.0, published 2026-05-05 | Qwen3.5 loading/tokenizer | Installed target venv version is current enough for Qwen3.5 gates. [VERIFIED: local venv probe + PyPI JSON; CITED: Qwen HF card says latest transformers required] |
| PEFT | 0.19.1, published 2026-04-16 | LoRA/QLoRA test adapters | PEFT docs recommend `prepare_model_for_kbit_training` for quantized LoRA and `target_modules="all-linear"` for QLoRA-style coverage. [VERIFIED: local venv probe + PyPI JSON; CITED: PEFT docs] |
| bitsandbytes | 0.48.0 installed; 0.49.2 is current PyPI | 4-bit NF4 base loading | HF docs state bitsandbytes supports CUDA 11.8–13.0 and Linux aarch64 NVIDIA backend; project pins 0.48.0. [VERIFIED: local venv probe + PyPI JSON; CITED: HF bitsandbytes docs] |
| Accelerate | 1.13.0, published 2026-03-04 | device map / quantized loading support | bitsandbytes integration depends on Accelerate for large-model dispatch. [VERIFIED: local venv probe + PyPI JSON; CITED: HF bitsandbytes docs] |
| llama.cpp | version 8460 `b1c70e2e5` for `llama-quantize` | GGUF convert/quantize/inference | Mandated local deployment toolchain path exists and convert script registers `Qwen3_5ForCausalLM`. [VERIFIED: local binary/version + convert script grep] |
| systemd-run | systemd 255 | Memory-capped training scope | Existing wrapper uses `systemd-run --scope` with `MemoryMax` and `MemorySwapMax=0`. [VERIFIED: local command + run_safe.sh] |

### Supporting
| Library / Tool | Version | Purpose | When to Use |
|----------------|---------|---------|-------------|
| safetensors | 0.7.0 | Safe HF checkpoint serialization | Use for dummy/merged artifacts in GGUF micro-convert. [VERIFIED: local venv probe] |
| pytest | 9.0.3 | Fast unit/regression tests | Use for non-GPU checks around token audit parsing, report aggregation, and prompt formatting. [VERIFIED: local venv probe + pyproject.toml] |
| jq | 1.7 | Shell artifact extraction | Optional for orchestrator reading selected max_seq. [VERIFIED: local command probe] |
| uv | 0.9.10 | Environment management | Avoid installs in Phase 1 unless missing dependencies must be repaired. [VERIFIED: local command probe; VERIFIED: dgx-spark-training skill] |
| `/home/samuel/llama.cpp/build/bin/llama-tokenize` | present | Tokenizer parity fallback | Use only if planner accepts fallback or until EvoProgTSC tree builds `llama-tokenize`; preferred fix is building in mandated tree. [VERIFIED: local filesystem probe] |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Existing HF + PEFT + bnb stack | Unsloth / Axolotl | Out of scope and contradicts project decision to avoid introducing a new training stack in v3.0. [VERIFIED: .planning/REQUIREMENTS.md] |
| `AutoModelForCausalLM` | `AutoModelForImageTextToText` / `Qwen3_5ForConditionalGeneration` | HF model card examples use image-text classes, but Phase 1 success requires no vision namespace; use image-text path only as diagnostic, not pass path. [CITED: Qwen HF model card; VERIFIED: requirements] |
| EvoProgTSC `llama-tokenize` | `/home/samuel/llama.cpp/build/bin/llama-tokenize` | Global fallback exists, but Phase 1 should preferably build the missing tool in `/home/samuel/projects/EvoProgTSC/llama.cpp` to keep all llama.cpp gates on the mandated tree. [VERIFIED: local probes] |
| Hand-parsed GGUF tokenizer metadata | `llama-tokenize --ids` | Existing v1.0 `tokenize_sanity.py` rebuilds tokenizer from GGUF metadata, but TOK-03 explicitly requires `llama-tokenize` parity. [VERIFIED: tokenize_sanity.py + requirements] |

**Installation:**
```bash
# No package install should be part of the happy path. [VERIFIED: /home/samuel/TSC_CYCLE/.venv probe]
source /home/samuel/TSC_CYCLE/.venv/bin/activate
python -m pytest -q
```

**Version verification performed:**
- `/home/samuel/TSC_CYCLE/.venv/bin/python` imports: torch 2.11.0+cu130, transformers 5.8.0, peft 0.19.1, bitsandbytes 0.48.0, accelerate 1.13.0, datasets 4.8.5, trl 1.3.0, safetensors 0.7.0, pytest 9.0.3. [VERIFIED: local venv probe]
- PyPI current versions checked by PyPI JSON: transformers 5.8.0, peft 0.19.1, bitsandbytes 0.49.2, trl 1.3.0, accelerate 1.13.0, datasets 4.8.5, safetensors 0.7.0, pytest 9.0.3. [VERIFIED: PyPI JSON]

## Architecture Patterns

### System Architecture Diagram

```text
Phase 1 gate runner
  |
  |-- preflight: source scripts/dgx_spark/env.sh + verify no forbidden flash-attn/vLLM dependency
  |       |
  |       v
  |   ENV gate: systemd-run scope dry-run + Qwen3.5 CausalLM NF4 SDPA forward
  |       |         |
  |       |         +--> fail if class/config not text causal LM or any vision parameter exists
  |       v
  |   TOKENIZER audit: HF tokenizer custom tags + native think IDs
  |       |         |
  |       |         +--> writes tokenizer_audit.json, fail on custom tag len < 3 or hardcoded IDs
  |       v
  |   GGUF tokenizer fixture: convert minimal HF artifact to GGUF
  |       |
  |       v
  |   TOKENIZER parity: 100 deterministic prompts -> HF encode vs llama-tokenize --ids
  |       |         |
  |       |         +--> fail on any mismatch; record first-diff diagnostics
  |       v
  |   MEMORY sweep: seq 1536/2048/2560/3072/4096 under run_safe 100G
  |       |         |
  |       |         +--> choose largest peak <85GB; fail if none
  |       v
  |   100-step dry-run under run_safe 100G
  |       |
  |       v
  |   GGUF micro-convert: dummy LoRA -> bf16/f16 GGUF -> Q4_K_M -> llama-cli -n 5
  |       |
  |       v
  |   aggregate phase1_gate_report.json -> PASS or fatal abort reason
```

### Recommended Project Structure

```text
tsc_cycle/
├── v3_gates/                  # Phase 1 dedicated hard-gate CLIs [ASSUMED]
│   ├── env_smoke.py           # ENV-01, MEM-03
│   ├── tokenizer_audit.py     # TOK-01, TOK-02, TOK-04
│   ├── tokenizer_parity.py    # TOK-03
│   ├── memory_budget.py       # MEM-01, MEM-02
│   ├── gguf_microconvert.py   # ENV-02
│   └── phase1_report.py       # aggregate pass/fail
scripts/
└── run_v3_phase1_gates.sh     # ordered fail-fast gate runner [ASSUMED]
artifacts/v3/phase1/           # JSON artifacts consumed by planner/verifier [ASSUMED]
```

### Pattern 1: Fail-fast gates with JSON evidence
**What:** Each gate writes a JSON artifact containing inputs, versions, pass/fail, peak metrics if relevant, and fatal reason. [ASSUMED]
**When to use:** Every Phase 1 requirement because this phase decides whether the milestone should continue. [VERIFIED: ROADMAP.md]
**Example:**
```python
# Source: project pattern recommendation [ASSUMED]
result = {"gate": "tokenizer_audit", "ok": ok, "fatal_reasons": fatal_reasons, "details": details}
out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
if not ok:
    raise SystemExit(1)
```

### Pattern 2: Quantized causal-LM load with bnb NF4 + SDPA
**What:** Use `BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=torch.bfloat16)` and load with `AutoModelForCausalLM.from_pretrained(..., attn_implementation="sdpa")`. [CITED: HF bitsandbytes docs; CITED: Context7 Transformers snippets]
**When to use:** ENV-01 smoke and MEM-01/MEM-02 memory budget gates. [VERIFIED: requirements]
**Example:**
```python
# Source: Hugging Face bitsandbytes + Transformers docs [CITED: huggingface.co/docs/transformers/quantization/bitsandbytes]
bnb_cfg = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_use_double_quant=True,
    bnb_4bit_compute_dtype=torch.bfloat16,
)
model = AutoModelForCausalLM.from_pretrained(
    "Qwen/Qwen3.5-9B",
    quantization_config=bnb_cfg,
    attn_implementation="sdpa",
    torch_dtype=torch.bfloat16,
    device_map={"": 0},
)
```

### Pattern 3: Dynamic tokenizer safety audit
**What:** Encode all protocol tags with `add_special_tokens=False`, write actual native `<think>` IDs, and never import v1.0 constants for Qwen3.5. [VERIFIED: tokenizer_check.py hardcodes v1.0 IDs]
**When to use:** TOK-01/TOK-02/TOK-04 and later dataset code. [VERIFIED: requirements]
**Example:**
```python
# Source: project requirement pattern [VERIFIED: .planning/REQUIREMENTS.md]
for tag in CUSTOM_TAGS:
    ids = tokenizer.encode(tag, add_special_tokens=False)
    assert len(ids) >= 3, {"tag": tag, "ids": ids}

native = {
    "<think>": tokenizer.encode("<think>", add_special_tokens=False),
    "</think>": tokenizer.encode("</think>", add_special_tokens=False),
}
```

### Pattern 4: llama-tokenize parity from a GGUF model file
**What:** `llama-tokenize` requires `--model MODEL_PATH` and one prompt source; `--ids` prints a Python-style numeric list. [CITED: llama.cpp tools/tokenize source]
**When to use:** TOK-03 after a minimal GGUF tokenizer fixture exists. [VERIFIED: requirement]
**Example:**
```bash
# Source: llama.cpp tools/tokenize source [CITED: github.com/ggml-org/llama.cpp/blob/master/tools/tokenize/tokenize.cpp]
/home/samuel/llama.cpp/build/bin/llama-tokenize \
  --model artifacts/v3/phase1/tokenizer_fixture.gguf \
  --prompt "<start_working_out>..." \
  --ids --no-bos --log-disable
```

### Anti-Patterns to Avoid
- **Keeping `NATIVE_THINK_OPEN_ID = 151667` for Qwen3.5:** Qwen3.5 IDs must be dynamically audited; v1.0 constants are explicitly forbidden. [VERIFIED: requirements + tokenizer_check.py]
- **Treating missing vLLM import as fatal:** Project instructions say vLLM is temporarily unavailable and Phase 1 does not need it. [VERIFIED: CLAUDE.md]
- **Using chat_template for SFT text:** TOK-04 locks raw text assembly; chat_template can inject native chat/thinking tokens. [VERIFIED: requirements; ASSUMED: exact Qwen3.5 chat_template behavior can vary]
- **Using `Qwen3_5ForConditionalGeneration` as pass path:** HF card shows image-text examples, but Phase 1 success requires no vision namespace. [CITED: Qwen HF model card; VERIFIED: roadmap]
- **Testing tokenizer parity with GGUF metadata rebuild only:** Existing code does this, but requirement explicitly says `llama-tokenize`. [VERIFIED: tokenize_sanity.py + requirements]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| 4-bit Qwen3.5 loading | Custom quantization kernels | bitsandbytes `BitsAndBytesConfig` | HF docs support 4-bit/NF4 and CUDA 13/aarch64; training should add only PEFT parameters. [CITED: HF bitsandbytes docs] |
| LoRA on quantized model | Manual adapter modules | PEFT `prepare_model_for_kbit_training` + `LoraConfig` | PEFT docs define the QLoRA/k-bit training preparation path. [CITED: PEFT docs] |
| Tokenizer parity | Regex parsing of llama-cli logs | `llama-tokenize --ids` | tokenize tool has explicit IDs output mode and vocab-only loading. [CITED: llama.cpp tokenize source] |
| Memory containment | Ad-hoc shell limits | `scripts/dgx_spark/run_safe.sh 100G -- ...` | Existing wrapper uses systemd `MemoryMax` and `MemorySwapMax=0`. [VERIFIED: run_safe.sh] |
| GGUF conversion | Custom HF→GGUF writer | llama.cpp `convert_hf_to_gguf.py` + `llama-quantize` | Local script registers `Qwen3_5ForCausalLM` and quantize binary exists. [VERIFIED: local script grep + binary probe] |
| Prompt protocol | Chat template manipulation | `tsc_cycle.prompt_builder` raw text | Existing tests lock required tags and reject legacy close tag. [VERIFIED: prompt_builder.py + tests] |

**Key insight:** Phase 1 is about proving external/runtime compatibility, so custom replacements hide the very failures this phase is supposed to expose. [ASSUMED]

## Common Pitfalls

### Pitfall 1: Qwen3.5 multimodal wrapper accidentally loads vision state
**What goes wrong:** `Qwen/Qwen3.5-9B` model card describes a causal LM with vision encoder and shows `AutoModelForImageTextToText`; loading the wrong class may include vision parameters. [CITED: Qwen HF model card]
**Why it happens:** The success criteria intentionally demand `Qwen3_5ForCausalLM` and no `vision*` params, which differs from the model-card example path. [VERIFIED: ROADMAP.md]
**How to avoid:** Use `AutoModelForCausalLM`; assert class/config architecture and scan `model.named_parameters()` for `vision`, `visual`, or multimodal namespaces. [VERIFIED: requirements; ASSUMED: namespace variants include visual]
**Warning signs:** `AutoProcessor`, `AutoModelForImageTextToText`, `vision_config`, or parameter names containing `vision`/`visual` appear in ENV-01 output. [CITED: Qwen HF model card; ASSUMED]

### Pitfall 2: v1.0 tokenizer constants survive into v3.0
**What goes wrong:** `tsc_cycle/tokenizer_check.py` hardcodes native think IDs 151667/151668 and expected vocab 151936. [VERIFIED: tokenizer_check.py]
**Why it happens:** v1.0 code treated Qwen3-4B tokenizer invariants as constants. [VERIFIED: tokenizer_check.py]
**How to avoid:** Replace gate logic with per-model dynamic audit JSON and downstream helper functions that read IDs from audit or tokenizer. [ASSUMED]
**Warning signs:** Any v3 gate imports `NATIVE_THINK_OPEN_ID`/`NATIVE_THINK_CLOSE_ID` from `tsc_cycle.tokenizer_check`. [VERIFIED: codebase]

### Pitfall 3: `llama-tokenize` is not available in the mandated llama.cpp tree
**What goes wrong:** `/home/samuel/projects/EvoProgTSC/llama.cpp` contains `convert_hf_to_gguf.py`, `llama-quantize`, and `llama-cli`, but no `llama-tokenize` binary was found. [VERIFIED: local filesystem probe]
**Why it happens:** The tool source exists under `tools/tokenize`, but the local tree appears not to have built that target. [VERIFIED: local find]
**How to avoid:** Plan an early build/locate step for `llama-tokenize`; use `/home/samuel/llama.cpp/build/bin/llama-tokenize` only as a documented fallback or rebuild the EvoProgTSC tree with the tokenize target. [VERIFIED: local fallback probe; ASSUMED: build target available]
**Warning signs:** TOK-03 uses a metadata-rebuild script or skips `llama-tokenize` because binary is missing. [VERIFIED: requirements]

### Pitfall 4: Memory budget is estimated instead of measured
**What goes wrong:** Planner chooses max_seq_length from prior 4B intuition rather than running all five required candidates. [VERIFIED: requirements demand all five]
**Why it happens:** Existing training script has no v3 memory sweep and v1.0 defaults differ. [VERIFIED: train.py]
**How to avoid:** Make MEM-01 a standalone gate that runs each candidate under `run_safe.sh 100G`, resets peak memory stats, records success/OOM, and selects max peak<85GB. [ASSUMED]
**Warning signs:** `memory_budget.json` lacks any of 1536/2048/2560/3072/4096 or contains extrapolated values. [VERIFIED: requirements]

### Pitfall 5: Environment verify fails because it imports vLLM
**What goes wrong:** Existing `scripts/dgx_spark/verify.py` imports `vllm`, but project instructions say vLLM is temporarily unavailable and Phase 1 must not depend on it. [VERIFIED: verify.py + CLAUDE.md]
**Why it happens:** The DGX skill template includes vLLM as a general environment check. [VERIFIED: dgx-spark-training skill]
**How to avoid:** For Phase 1, create a v3-specific env smoke that treats vLLM as non-required and only hard-fails CUDA, torch, transformers, bnb, peft, SDPA, Triton ptxas, and forbidden flash-attn. [ASSUMED]
**Warning signs:** ENV-01 fails solely on vLLM import even though Qwen3.5 HF path is not tested. [VERIFIED: CLAUDE.md]

## Code Examples

### ENV-01 minimal smoke structure
```python
# Source: HF bitsandbytes docs + Phase requirements [CITED: huggingface.co/docs/transformers/quantization/bitsandbytes; VERIFIED: .planning/REQUIREMENTS.md]
inputs = tokenizer("<start_working_out> smoke", return_tensors="pt").to("cuda")
with torch.no_grad():
    out = model(**inputs)
assert tuple(out.logits.shape[:2]) == tuple(inputs["input_ids"].shape)
vision_names = [n for n, _ in model.named_parameters() if "vision" in n.lower() or "visual" in n.lower()]
assert not vision_names, vision_names[:20]
```

### MEM-01 peak memory measurement loop
```python
# Source: Phase requirement; PyTorch CUDA memory stats pattern [VERIFIED: .planning/REQUIREMENTS.md; ASSUMED: API exactness]
for seq in [1536, 2048, 2560, 3072, 4096]:
    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats()
    batch = torch.randint(0, len(tokenizer), (1, seq), device="cuda")
    out = model(input_ids=batch, labels=batch)
    out.loss.backward()
    peak_gb = torch.cuda.max_memory_reserved() / (1024 ** 3)
```

### TOK-03 llama-tokenize output parsing
```python
# Source: llama.cpp tokenize source says --ids prints Python-style numeric list [CITED: github.com/ggml-org/llama.cpp/blob/master/tools/tokenize/tokenize.cpp]
cmd = [llama_tokenize, "--model", str(gguf), "--prompt", prompt, "--ids", "--no-bos", "--log-disable"]
ids = ast.literal_eval(subprocess.check_output(cmd, text=True).strip())
assert ids == hf_tokenizer.encode(prompt, add_special_tokens=False)
```

### raw text protocol, not chat_template
```python
# Source: existing project prompt builder [VERIFIED: tsc_cycle/prompt_builder.py]
prompt = build_user_prompt(input_obj)
assistant = build_full_assistant(reasoning, solution)
full = prompt + "\n" + assistant + tokenizer.eos_token
enc = tokenizer(full, add_special_tokens=False)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Qwen3-4B hardcoded think IDs 151667/151668 | Qwen3.5 dynamic tokenizer audit JSON | v3.0 Phase 1 | Prevents false pass/fail after vocab/model switch. [VERIFIED: requirements + tokenizer_check.py] |
| v1.0 GGUF metadata tokenizer sanity | `llama-tokenize --ids` parity on 100 prompts | v3.0 Phase 1 | Matches explicit TOK-03 requirement and deployment binary behavior. [VERIFIED: requirements; CITED: llama tokenize source] |
| Single max_seq assumption | Five-candidate measured sweep with peak<85GB selection | v3.0 Phase 1 | Turns memory budget into hard evidence before 100-step dry-run. [VERIFIED: requirements] |
| General DGX verify imports vLLM | Phase-specific no-vLLM env smoke | v3.0 Phase 1 | Avoids contradicting local constraint that vLLM is temporarily unavailable. [VERIFIED: CLAUDE.md + verify.py] |
| Qwen3 CausalLM convert only | Local llama.cpp registers `Qwen3_5ForCausalLM` and `Qwen3_5ForConditionalGeneration` | Local script already updated before this research | Enables Qwen3.5 GGUF micro-convert gate. [VERIFIED: local convert_hf_to_gguf.py grep] |

**Deprecated/outdated:**
- `tsc_cycle/tokenizer_check.py` v1.0 constants are outdated for Qwen3.5. [VERIFIED: tokenizer_check.py + requirements]
- `scripts/dgx_spark/verify.py` treating vLLM import as required is outdated for this project’s current constraint. [VERIFIED: verify.py + CLAUDE.md]
- Metadata-only GGUF tokenizer checks are insufficient for TOK-03 because Phase 1 explicitly names `llama-tokenize`. [VERIFIED: requirements]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Use `tsc_cycle/v3_gates/` as package name for Phase 1 gate modules. | Summary / Project Structure | Planner may choose a different module location; low technical risk. |
| A2 | Gate report aggregation should be a dedicated module. | Responsibility Map | Planner may fold aggregation into shell; artifact schema could be less testable. |
| A3 | `vision` and `visual` substrings cover relevant multimodal parameter namespaces. | Pitfall 1 / ENV example | A hidden namespace could slip through; planner should also record full class/config. |
| A4 | EvoProgTSC llama.cpp can build the tokenize target from existing source. | Pitfall 3 | If build system is incomplete, planner must use global fallback or update build. |
| A5 | PyTorch CUDA memory stats API names are available in torch 2.11. | MEM patterns | If API changed, memory gate needs minor code adjustment. |

## Open Questions (RESOLVED)

1. **RESOLVED — `AutoModelForCausalLM.from_pretrained("Qwen/Qwen3.5-9B")` must prove `Qwen3_5ForCausalLM` without vision parameters at runtime.**
   - What we know: Phase success requires this exact outcome. [VERIFIED: ROADMAP.md]
   - What’s unclear: HF model card describes vision encoder and image-text examples. [CITED: Qwen HF model card]
   - Resolution: Plan 01 requires `env_smoke_v3.py` to hard-fail unless model class/config proves Qwen3.5 causal LM and `vision_param_count == 0`; any failure aborts the milestone before Phase 2. [RESOLVED]

2. **RESOLVED — TOK-03 may use only a recorded `llama-tokenize` binary with explicit provenance and GGUF input.**
   - What we know: Global binary exists; EvoProgTSC path lacks `llama-tokenize`. [VERIFIED: local probes]
   - What’s unclear: Whether user considers global llama.cpp acceptable for tokenizer parity while ENV-02 mandates EvoProgTSC micro-convert path. [ASSUMED]
   - Resolution: Plan 03 requires `tokenizer_parity_v3.py` to record binary provenance, require `--gguf`, and invoke `llama-tokenize --model <gguf> --prompt <text> --ids --no-bos --log-disable`; Plan 06 passes the GGUF produced by Plan 05. [RESOLVED]

3. **RESOLVED — real peak memory is intentionally deferred to the MEM-01 runtime sweep gate.**
   - What we know: Requirement demands measurement and peak<85GB selection. [VERIFIED: REQUIREMENTS.md]
   - What’s unclear: Actual Qwen3.5-9B hybrid memory behavior on DGX Spark under bnb 4-bit + LoRA r=64. [ASSUMED]
   - Resolution: Plan 04 requires running all five candidates `{1536, 2048, 2560, 3072, 4096}` and selecting the largest with measured peak `<85GB`; no planning-time estimate is accepted. [RESOLVED]

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| `/home/samuel/TSC_CYCLE/.venv` | ENV-01/MEM gates | ✓ | Python 3.12.3; torch 2.11.0+cu130; transformers 5.8.0 | — [VERIFIED: local probe] |
| NVIDIA GPU | ENV-01/MEM gates | ✓ | NVIDIA GB10, driver 580.126.09 | None [VERIFIED: nvidia-smi] |
| CUDA/Triton ptxas path | ENV-01/MEM gates | ✓ via env script | `/usr/local/cuda/bin/ptxas` expected | Fail with repair instruction [VERIFIED: env.sh + skill] |
| `systemd-run` | ENV-03/MEM-02 | ✓ | systemd 255 | None; required for cap [VERIFIED: local command] |
| swap disabled | ENV-03 | ✓ at probe time | `swapon --show` empty | If enabled, request user approval for `sudo swapoff -a` [VERIFIED: local probe] |
| `scripts/dgx_spark/run_safe.sh` | ENV-03/MEM gates | ✓ | project script | — [VERIFIED: file read] |
| `/home/samuel/projects/EvoProgTSC/llama.cpp/convert_hf_to_gguf.py` | ENV-02 | ✓ | local script with Qwen3_5 registrations | None unless update llama.cpp [VERIFIED: local grep] |
| `/home/samuel/projects/EvoProgTSC/llama.cpp/llama-quantize` | ENV-02 | ✓ | version 8460 `b1c70e2e5` | Rebuild llama.cpp [VERIFIED: local command] |
| `/home/samuel/projects/EvoProgTSC/llama.cpp/llama-cli` | ENV-02 | ✓ | version 8460 `b1c70e2e5` | Rebuild llama.cpp [VERIFIED: local command] |
| `/home/samuel/projects/EvoProgTSC/llama.cpp/llama-tokenize` | TOK-03 | ✗ | — | Build target in EvoProgTSC tree or use `/home/samuel/llama.cpp/build/bin/llama-tokenize` [VERIFIED: local probes] |
| `jq` | Script convenience | ✓ | 1.7 | Python JSON parsing [VERIFIED: local command] |
| `uv` | Environment repair | ✓ | 0.9.10 | Avoid install unless repair needed [VERIFIED: local command] |

**Missing dependencies with no fallback:**
- None confirmed, but lack of an EvoProgTSC-tree `llama-tokenize` is blocking if the planner interprets TOK-03 as requiring the same llama.cpp tree. [VERIFIED: local probes; ASSUMED: interpretation]

**Missing dependencies with fallback:**
- `llama-tokenize` under `/home/samuel/projects/EvoProgTSC/llama.cpp`: fallback is building from existing source or using `/home/samuel/llama.cpp/build/bin/llama-tokenize`. [VERIFIED: local probes]

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 [VERIFIED: local venv probe] |
| Config file | `pyproject.toml` with `testpaths=["tests"]`, `addopts="-q"` [VERIFIED: pyproject.toml] |
| Quick run command | `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest -q tests/test_prompt_builder.py tests/test_hashing.py` [VERIFIED: pyproject.toml + tests present] |
| Full suite command | `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest -q` [VERIFIED: pyproject.toml] |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| ENV-01 | Qwen3.5 CausalLM NF4 SDPA forward smoke | GPU smoke/integration | `scripts/dgx_spark/run_safe.sh 100G -- /home/samuel/TSC_CYCLE/.venv/bin/python -m tsc_cycle.v3_gates.env_smoke_v3 --model Qwen/Qwen3.5-9B` | ❌ Wave 0 |
| ENV-02 | llama.cpp micro-convert + quantize + 5-token inference | integration | `scripts/dgx_spark/run_safe.sh 100G -- /home/samuel/TSC_CYCLE/.venv/bin/python -m tsc_cycle.v3_gates.gguf_microconvert_v3` | ❌ Wave 0 |
| ENV-03 | systemd memory scope and swap disabled | smoke | `scripts/dgx_spark/run_safe.sh 100G -- /home/samuel/TSC_CYCLE/.venv/bin/python -c 'print("scope ok")'` | ✅ wrapper exists |
| TOK-01 | Custom tags split into ≥3 tokens | unit/smoke | `/home/samuel/TSC_CYCLE/.venv/bin/python -m tsc_cycle.v3_gates.tokenizer_audit_v3 --model Qwen/Qwen3.5-9B` | ❌ Wave 0 |
| TOK-02 | Native think IDs dynamic in JSON | unit/smoke | same as TOK-01; assert JSON fields exist and are not v1.0 hardcoded constants | ❌ Wave 0 |
| TOK-03 | 100 prompt HF ↔ llama-tokenize parity | integration | `/home/samuel/TSC_CYCLE/.venv/bin/python -m tsc_cycle.v3_gates.tokenizer_parity_v3 --n 100 --gguf runs/v3.0-gates/gguf_microconvert/tokenizer.gguf --require-gguf` | ❌ Wave 0 |
| TOK-04 | Raw text assembly, no chat_template | unit | `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest -q tests/test_prompt_builder.py` plus new no-chat-template tests | ⚠️ partial |
| MEM-01 | Sweep all five max_seq candidates | GPU integration | `scripts/dgx_spark/run_safe.sh 100G -- /home/samuel/TSC_CYCLE/.venv/bin/python -m tsc_cycle.v3_gates.memory_budget --seqs 1536 2048 2560 3072 4096` | ❌ Wave 0 |
| MEM-02 | 100-step dry-run in 100GB cap | GPU integration | `scripts/dgx_spark/run_safe.sh 100G -- /home/samuel/TSC_CYCLE/.venv/bin/python -m tsc_cycle.v3_gates.memory_budget --steps 100 --seq $(...)` | ❌ Wave 0 |
| MEM-03 | No `vision*` params and causal LM class | GPU smoke | same as ENV-01 with additional parameter namespace assertion | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** pytest quick run for non-GPU changes; GPU gates only when implementing their gate module. [ASSUMED]
- **Per wave merge:** Full pytest suite plus completed gate smoke with `--dry-run`/small fixture where possible. [ASSUMED]
- **Phase gate:** All five hard gates pass and `artifacts/v3/phase1/phase1_gate_report.json` has `ok=true`. [ASSUMED]

### Wave 0 Gaps
- [ ] `tsc_cycle/v3_gates/env_smoke_v3.py` — covers ENV-01, MEM-03. [ASSUMED]
- [ ] `tsc_cycle/v3_gates/tokenizer_audit_v3.py` — covers TOK-01, TOK-02, TOK-04. [ASSUMED]
- [ ] `tsc_cycle/v3_gates/tokenizer_parity_v3.py` — covers TOK-03. [ASSUMED]
- [ ] `tsc_cycle/v3_gates/memory_budget_v3.py` — covers MEM-01, MEM-02. [ASSUMED]
- [ ] `tsc_cycle/v3_gates/gguf_microconvert_v3.py` — covers ENV-02. [ASSUMED]
- [ ] `tsc_cycle/v3_gates/phase1_report.py` and `scripts/run_v3_phase1_gates.sh` — phase-level aggregation. [ASSUMED]
- [ ] Tests for dynamic think IDs and no hardcoded 151667/151668 in v3 path. [ASSUMED]
- [ ] Build or locate `llama-tokenize` for the mandated llama.cpp tree. [VERIFIED: missing binary]

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|------------------|
| V2 Authentication | no | No user auth/session in Phase 1 local scripts. [VERIFIED: phase scope] |
| V3 Session Management | no | No web session state. [VERIFIED: phase scope] |
| V4 Access Control | yes | Avoid writing v1.0 frozen artifacts; use explicit output dirs and fail if target exists. [VERIFIED: STATE.md] |
| V5 Input Validation | yes | Validate JSON gate artifacts, tokenizer IDs, CLI paths, prompt counts, and memory thresholds. [ASSUMED] |
| V6 Cryptography | no | No crypto implementation; use existing SHA/hash tests only if prompt fixture IDs need determinism. [VERIFIED: tests/test_hashing.py] |
| V8 Data Protection | yes | Do not mutate `data/labeled.jsonl` or v1.0 run artifacts during gates. [VERIFIED: STATE.md] |

### Known Threat Patterns for local ML gate scripts

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Command injection via user-provided paths | Tampering / Elevation | Build subprocess commands as argument lists, not shell strings. [ASSUMED] |
| Accidental overwrite of production v1.0 artifacts | Tampering | Use `artifacts/v3/phase1/` and `runs/v3.0-gates/`; preflight fail if output exists unless `--overwrite` is explicit. [VERIFIED: STATE.md; ASSUMED] |
| Unsafe sudo use | Elevation | `run_safe.sh` uses fixed systemd-run invocation; do not add arbitrary sudo shell commands. [VERIFIED: run_safe.sh] |
| Poisoned model/cache path | Spoofing / Tampering | Record model ID, config architecture, commit/revision if available, and resolved artifact paths in JSON outputs. [ASSUMED] |
| Native `<think>` leakage into training/inference protocol | Tampering of output format | Dynamic ID audit and later logit-bias/forbidden-ID checks. [VERIFIED: requirements] |

## Sources

### Primary (HIGH confidence)
- `/home/samuel/TSC_CYCLE/.claude/worktrees/agent-ad03d45cf4c0aa336/.planning/REQUIREMENTS.md` — Phase 1 requirements and out-of-scope constraints. [VERIFIED]
- `/home/samuel/TSC_CYCLE/.claude/worktrees/agent-ad03d45cf4c0aa336/.planning/ROADMAP.md` — Phase 1 goal and success criteria. [VERIFIED]
- `/home/samuel/TSC_CYCLE/.claude/worktrees/agent-ad03d45cf4c0aa336/.planning/STATE.md` — current milestone decisions and v1.0 frozen artifact context. [VERIFIED]
- `/home/samuel/TSC_CYCLE/CLAUDE.md` and worktree `CLAUDE.md` — project constraints. [VERIFIED]
- `/home/samuel/.claude/skills/dgx-spark-training/SKILL.md` — DGX Spark constraints and validation commands. [VERIFIED]
- `/home/samuel/TSC_CYCLE/.venv` import probe — actual target package versions. [VERIFIED]
- `/home/samuel/projects/EvoProgTSC/llama.cpp/convert_hf_to_gguf.py` grep — `Qwen3_5ForCausalLM` local support. [VERIFIED]
- Project code reads: `scripts/dgx_spark/run_safe.sh`, `env.sh`, `verify.py`, `tsc_cycle/tokenizer_check.py`, `prompt_builder.py`, `student/train.py`, `student/export_gguf.py`, tests. [VERIFIED]
- Context7 `/huggingface/transformers`, `/huggingface/peft`, `/bitsandbytes-foundation/bitsandbytes` — quantization and PEFT patterns. [VERIFIED]
- Hugging Face bitsandbytes docs — CUDA 13/aarch64 support, 4-bit NF4 config, PEFT-only training note. [CITED: https://huggingface.co/docs/transformers/quantization/bitsandbytes]
- PEFT quantization guide — `prepare_model_for_kbit_training`, `target_modules="all-linear"`, NF4 guidance. [CITED: https://huggingface.co/docs/peft/en/developer_guides/quantization]
- Qwen/Qwen3.5-9B model card — model card facts about vision encoder/examples, vocab/embedding size, latest transformers requirement. [CITED: https://huggingface.co/Qwen/Qwen3.5-9B]
- llama.cpp `tools/tokenize/tokenize.cpp` — `llama-tokenize` CLI behavior. [CITED: https://github.com/ggml-org/llama.cpp/blob/master/tools/tokenize/tokenize.cpp]

### Secondary (MEDIUM confidence)
- PyPI JSON API — current and installed-version publish dates. [VERIFIED: pypi.org JSON]
- Local `/home/samuel/llama.cpp/build/bin/llama-tokenize` fallback presence. [VERIFIED: local filesystem]

### Tertiary (LOW confidence)
- Memory peak estimates before running MEM-01 are intentionally not locked; only measured `memory_budget.json` should drive max_seq selection. [ASSUMED]

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — verified against target `/home/samuel/TSC_CYCLE/.venv`, PyPI JSON, Context7/HF docs. [VERIFIED]
- Architecture: HIGH for gate decomposition, MEDIUM for exact Qwen3.5 CausalLM/no-vision outcome until ENV-01 runs. [VERIFIED + CITED]
- Pitfalls: HIGH for codebase/v1.0 hardcoded-ID and missing-binary pitfalls, MEDIUM for Qwen3.5 model-load edge cases until smoke. [VERIFIED + CITED]
- Memory: MEDIUM/LOW until required measurements exist. [ASSUMED]

**Research date:** 2026-05-08 [VERIFIED: project memory]
**Valid until:** 2026-05-15 for Qwen3.5/Transformers/llama.cpp compatibility details; 2026-06-07 for local project structure if no major refactor occurs. [ASSUMED]
