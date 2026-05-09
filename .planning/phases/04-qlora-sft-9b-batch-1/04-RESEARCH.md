# Phase 04: QLoRA SFT (9B, batch=1, 跑到收敛) - Research

**Researched:** 2026-05-09 [VERIFIED: /home/samuel/TSC_CYCLE/.planning/STATE.md]  
**Domain:** DGX Spark 上的 Qwen/Qwen3.5-9B QLoRA SFT、Arrow IPC tokenized dataset consumption、dry-run/full-run training gates [VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/04-qlora-sft-9b-batch-1/04-CONTEXT.md]  
**Confidence:** HIGH for codebase/runtime constraints; MEDIUM for convergence behavior because full 9B training has not yet run in Phase 4 [VERIFIED: /home/samuel/TSC_CYCLE/artifacts/v3/phase1/memory_budget.json]

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
## Implementation Decisions

### Locked Training Stack
- **D-01:** 使用 HF Transformers + TRL + PEFT + bitsandbytes 路线；不引入 Unsloth、Axolotl、新 PyTorch 版本或 vLLM。
- **D-02:** 训练环境复用本项目 `.venv` / `/home/samuel/dgx-spark-setup/.venv` 的 DGX Spark 已验证栈，遵循 `/dgx-spark-training` skill。
- **D-03:** 注意力实现必须为 SDPA；禁止安装或依赖 upstream `flash-attn` CUDA 12 wheel。

### Locked Hyperparameters and Gates
- **D-04:** QLoRA 固定 `r=64`, `lora_alpha=64`, `lora_dropout=0.0`, `target_modules="all-linear"`。
- **D-05:** 训练固定 `batch_size=1`, `gradient_accumulation_steps=16`, `packing=False`, `gradient_checkpointing(use_reentrant=False)`。
- **D-06:** optimizer/scheduler 固定 `adamw_torch_fused`, `lr=1e-4`, cosine schedule with warmup, `max_grad_norm=0.5`。
- **D-07:** 500-sample dry-run gate 必须在进入全量训练前通过：OOD 硬约束满足率 ≥95%，前 200 step `grad_norm p99 < 3.0` 且无 NaN；失败则 abort，不进入 full run。
- **D-08:** 全量训练不设 6h 上限；使用 early-stopping callback，val loss patience=3，监控间隔 200 steps，最大 epoch 上限 5。

### Runtime Safety and Artifact Isolation
- **D-09:** 长训练必须通过 `scripts/dgx_spark/env.sh` 环境与 `scripts/dgx_spark/run_safe.sh 100G -- ...` 或等价 `systemd-run --scope -p MemoryMax=100G -p MemorySwapMax=0` 执行。
- **D-10:** Phase 4 输出路径使用 `runs/v3.0-9B-{utc_timestamp}/`，wandb project 使用 `tsc-cycle-v3-9b`，不得混入 v1.0 run 目录。
- **D-11:** `runs/20260507T032419Z/` 必须写入 `FROZEN.md` 并 `chmod -w`；Phase 4 流程只读引用，禁止写入。

### Claude's Discretion
- 具体训练脚本拆分、测试文件命名、dry-run 评测抽样实现、checkpoint 保存频率、日志字段和 manifest 结构由下游 researcher/planner 决定，但必须满足 SFT-01..SFT-08 和上面锁定决策。

### Deferred Ideas (OUT OF SCOPE)
## Deferred Ideas

None — discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SFT-01 | QLoRA r=64, alpha=64, lora_dropout=0.0, target_modules="all-linear"（覆盖 GatedDeltaNet 24 linear-attention 层 + 8 full-attention 层全部 projections） | 使用 PEFT `LoraConfig(target_modules="all-linear")`，并新增 `model.named_modules()`/LoRA adapter coverage report 作为 dry-run gate [CITED: https://github.com/huggingface/peft/blob/main/docs/source/developer_guides/quantization.md] [VERIFIED: /home/samuel/TSC_CYCLE/artifacts/v3/phase1/memory_budget.json] |
| SFT-02 | lr=1e-4 cosine warmup, max_grad_norm=0.5, optimizer=`adamw_torch_fused` | `TrainingArguments` 支持 `optim`, `max_grad_norm`, `lr_scheduler_type`, `warmup_ratio`，本项目现有 `train.py` 已使用 cosine/warmup 但缺 `optim` 和 `max_grad_norm=0.5` 显式锁定 [CITED: https://huggingface.co/docs/transformers/v4.56.2/en/main_classes/trainer] [VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/student/train.py] |
| SFT-03 | batch_size=1 + gradient_accumulation_steps=16; packing=False; gradient_checkpointing(use_reentrant=False) | 现有 Phase 1 memory gate 已用 bs=1/grad_accum=16/use_reentrant=False；Phase 4 trainer 必须从现有 bs=4/grad_accum=8 改为锁定值，并避免 TRL packing 或任何样本拼接 [VERIFIED: /home/samuel/TSC_CYCLE/artifacts/v3/phase1/memory_budget.json] [VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/student/train.py] |
| SFT-04 | 500-sample 1h dry-run early-exit gate：OOD 硬约束满足率 ≥95% 才进全量训练 | 需要新增 dry-run wrapper、500 sample selection、post-dry-run generation/lint report；现有 constraint linter 可复用，现有 trainer 只有 smoke generation 不计算 OOD pass rate [VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/constraint_lint.py] [VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/student/train.py] |
| SFT-05 | 全量训练不设 6h 上限，early-stopping callback val loss patience=3，监控间隔 200 steps，最大 epoch 5 | `EarlyStoppingCallback` 和 steps-based eval/save/best-model loading 可用；Phase 4 必须新增 `eval_strategy="steps"`, `eval_steps=200`, compatible `save_steps`, `load_best_model_at_end=True`, `metric_for_best_model="eval_loss"` [VERIFIED: project venv API inspection] [CITED: https://huggingface.co/docs/transformers/v4.56.2/en/main_classes/trainer] |
| SFT-06 | 训练 200 steps 后 grad_norm p99<3.0 且无 NaN；失败 abort | 需要新增 callback 从 Trainer logs/state 采集 `grad_norm`、loss NaN/Inf，并在 200 step 写 gate JSON；现有 trainer 未实现该 gate [VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/student/train.py] |
| SFT-07 | run artifact 命名隔离 `runs/v3.0-9B-{utc_timestamp}/`; wandb project=`tsc-cycle-v3-9b` | 现有 trainer 默认 `runs/{ts}/train`，必须改为 v3.0-9B 前缀并设置/校验 `WANDB_PROJECT=tsc-cycle-v3-9b` [VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/student/train.py] [VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/04-qlora-sft-9b-batch-1/04-CONTEXT.md] |
| SFT-08 | v1.0 production artifact `runs/20260507T032419Z/` 标记 FROZEN.md + chmod -w，禁止 v3.0 流程触碰 | 需要新增 FROZEN guard 脚本/test：写 `FROZEN.md`、递归移除写权限、训练 wrapper 启动前校验 v1.0 artifact mtime/hash 未变 [VERIFIED: /home/samuel/TSC_CYCLE/.planning/STATE.md] [VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/04-qlora-sft-9b-batch-1/04-CONTEXT.md] |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- 回答与项目文档应使用简体中文，且 git commit message 不应包含 `Co-Authored-By` 行 [VERIFIED: /home/samuel/TSC_CYCLE/CLAUDE.md].
- 本机是 DGX Spark，当前暂时不能使用 vLLM [VERIFIED: /home/samuel/TSC_CYCLE/CLAUDE.md].
- 项目学生模型路线从 Qwen3-4B-Thinking-2507 扩展到 v3.0 的 Qwen/Qwen3.5-9B，但训练栈仍要求 QLoRA、HF Transformers、PEFT/bitsandbytes 或已锁定栈；Phase 4 context 已锁定不引入 Unsloth/Axolotl/vLLM [VERIFIED: /home/samuel/TSC_CYCLE/CLAUDE.md] [VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/04-qlora-sft-9b-batch-1/04-CONTEXT.md].
- DGX Spark 训练必须遵循无 flash-attn cu12、SDPA、swap/OOM 防护、复用已知良好 venv 的约束 [VERIFIED: /home/samuel/TSC_CYCLE/CLAUDE.md] [VERIFIED: /home/samuel/TSC_CYCLE/scripts/dgx_spark/run_safe.sh].
- 任何思考标签训练必须验证自定义标签多 sub-token，且不得与原生 `<think>` 冲突；Phase 1 tokenizer audit 已验证 Qwen3.5 自定义标签均 ≥3 sub-tokens，native `<think>`/`</think>` IDs 为 248068/248069 [VERIFIED: /home/samuel/TSC_CYCLE/CLAUDE.md] [VERIFIED: /home/samuel/TSC_CYCLE/artifacts/v3/phase1/tokenizer_audit.json].
- 教师输出/学生输出必须满足 min/max/整数/相位顺序/相位覆盖硬约束，Phase 4 dry-run gate 应复用 `constraint_lint.validate` 计算 OOD hard-constraint pass rate [VERIFIED: /home/samuel/TSC_CYCLE/CLAUDE.md] [VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/constraint_lint.py].
- GSD 工作流要求在直接 repo 编辑前使用 GSD 入口；本任务由 Phase 04 research workflow 驱动，允许写入指定 research artifact [VERIFIED: /home/samuel/TSC_CYCLE/CLAUDE.md] [VERIFIED: gsd-sdk init.phase-op].

## Summary

Phase 4 应复用现有 `tsc_cycle/student/train.py` 的模型加载、bnb 4-bit NF4、SDPA、`prepare_model_for_kbit_training`、DataCollator、warmup/smoke patterns，但必须把它从 v1.0 的 4B/parquet/epoch-smoke trainer 改造成 v3.0 的 Qwen/Qwen3.5-9B/Arrow IPC/locked gate trainer [VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/student/train.py] [VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/v3_gates/dataset_rebuild_v3.py]. Phase 3 已产出 `data/tokenized/v3/{train,val,ood_val}.arrow`，schema 为 `sample_id,input_ids,attention_mask,labels,raw_length,truncated,prompt_hash,assistant_hash`，split sizes 为 train=7601、val=950、ood_val=950，truncation_rate=0.0，max_seq_length=2048 [VERIFIED: pyarrow schema inspection] [VERIFIED: /home/samuel/TSC_CYCLE/data/splits/v3/rebuild_report.json].

Phase 4 的主要新增不是“另写一个训练栈”，而是围绕已有 trainer 增加 fail-closed gates：FROZEN guard、Arrow IPC loader、LoRA coverage report、grad_norm/NaN 200-step gate、500-sample dry-run OOD lint gate、early-stopping full-run manifest、safe wrapper scripts [VERIFIED: /home/samuel/TSC_CYCLE/.planning/REQUIREMENTS.md] [VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/04-qlora-sft-9b-batch-1/04-CONTEXT.md]. 训练必须通过 `source scripts/dgx_spark/env.sh` 与 `scripts/dgx_spark/run_safe.sh 100G -- ...`，当前本机项目 `.venv`、run_safe、env、noninteractive sudo systemd-run、swap off 均可用 [VERIFIED: environment probe] [VERIFIED: /home/samuel/TSC_CYCLE/scripts/dgx_spark/env.sh] [VERIFIED: /home/samuel/TSC_CYCLE/scripts/dgx_spark/run_safe.sh].

**Primary recommendation:** 规划为 5 个执行计划：Wave 0 RED tests + FROZEN guard；Wave 1 Arrow loader/trainer config refactor；Wave 2 dry-run 500-sample gate；Wave 3 full-run wrapper/early-stopping manifest；Wave 4 aggregate SFT report and artifact isolation verification [VERIFIED: /home/samuel/TSC_CYCLE/.planning/ROADMAP.md] [VERIFIED: /home/samuel/TSC_CYCLE/.planning/REQUIREMENTS.md].

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Arrow IPC tokenized dataset loading | Data / Training Pipeline | Model Trainer | Phase 3 owns tokenization artifacts; Phase 4 should consume exact Arrow paths and hashes without rebuilding data [VERIFIED: /home/samuel/TSC_CYCLE/data/splits/v3/rebuild_report.json]. |
| Qwen3.5-9B QLoRA model setup | Model Trainer | DGX Runtime | Trainer owns `AutoModelForCausalLM`, BitsAndBytesConfig, PEFT LoRA config, and TrainingArguments [VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/student/train.py]. |
| Memory/OOM containment | OS / DGX Runtime | Wrapper Scripts | `run_safe.sh` launches `systemd-run --scope` with MemoryMax and MemorySwapMax; trainer must not invoke sudo/systemd itself [VERIFIED: /home/samuel/TSC_CYCLE/scripts/dgx_spark/run_safe.sh] [VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/v3_gates/memory_budget_v3.py]. |
| Dry-run OOD hard-constraint gate | Validation / Eval Harness | Model Trainer | Gate needs generation + parse + `constraint_lint.validate`; trainer emits adapter/checkpoint, validation harness decides pass/fail [VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/constraint_lint.py] [VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/prompt_builder.py]. |
| Grad norm / NaN abort | Model Trainer | Validation Report | Trainer callback sees logs/state during the first 200 optimizer steps and should stop training fail-closed [VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/student/train.py] [CITED: https://huggingface.co/docs/transformers/v4.56.2/en/trainer]. |
| Artifact isolation / FROZEN guard | Filesystem / Wrapper Scripts | Trainer | v1.0 artifact protection is a filesystem permission/hash concern before training starts; trainer should only write `runs/v3.0-9B-*` [VERIFIED: /home/samuel/TSC_CYCLE/.planning/STATE.md] [VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/04-qlora-sft-9b-batch-1/04-CONTEXT.md]. |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python | 3.12.3 in project `.venv` | Runtime for Phase 4 scripts | Project venv uses Python 3.12.3 and pyproject requires `>=3.12,<3.13` [VERIFIED: environment probe] [VERIFIED: /home/samuel/TSC_CYCLE/pyproject.toml]. |
| PyTorch | 2.11.0+cu130 in project `.venv` | CUDA/bf16 training backend | Phase 1 env smoke ran Qwen3.5-9B on torch 2.11.0+cu130 with CUDA 13.0 on NVIDIA GB10 [VERIFIED: /home/samuel/TSC_CYCLE/artifacts/v3/phase1/env_smoke.json]. |
| Transformers | 5.8.0 in project `.venv` | `AutoModelForCausalLM`, Trainer, TrainingArguments | Project venv exposes Trainer API fields needed for `optim`, `max_grad_norm`, `eval_strategy`, `gradient_checkpointing_kwargs`, and Qwen3.5 loading has already passed Phase 1 smoke [VERIFIED: project venv API inspection] [VERIFIED: /home/samuel/TSC_CYCLE/artifacts/v3/phase1/env_smoke.json]. |
| PEFT | 0.19.1 in project `.venv` | LoRA/QLoRA adapter injection | PEFT docs state `target_modules="all-linear"` applies LoRA to all linear layers for QLoRA-style training [VERIFIED: project venv package inspection] [CITED: https://github.com/huggingface/peft/blob/main/docs/source/developer_guides/quantization.md]. |
| bitsandbytes | 0.48.0 in project `.venv` | 4-bit NF4 quantized base model | Phase 1 env smoke and memory gate used 4-bit NF4 + bf16 compute + double quant successfully [VERIFIED: /home/samuel/TSC_CYCLE/artifacts/v3/phase1/env_smoke.json] [VERIFIED: /home/samuel/TSC_CYCLE/artifacts/v3/phase1/memory_budget.json]. |
| Accelerate | 1.13.0 in project `.venv` | Trainer/device integration | Project venv contains accelerate 1.13.0 and Trainer uses it under the hood for PyTorch training [VERIFIED: project venv package inspection] [ASSUMED]. |
| Datasets | 4.8.5 in project `.venv` | HF Dataset wrapper around Arrow tables | Hugging Face Datasets supports PyTorch formatting and Dataset use with DataLoader/Trainer; project venv contains datasets 4.8.5 [CITED: https://github.com/huggingface/datasets/blob/main/docs/source/use_with_pytorch.mdx] [VERIFIED: project venv package inspection]. |
| PyArrow | 24.0.0 in project `.venv` | Read Phase 3 Arrow IPC files | Phase 3 writes Arrow IPC with `pa.ipc.new_file`, and schema inspection confirms readable Arrow files [VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/v3_gates/dataset_rebuild_v3.py] [VERIFIED: pyarrow schema inspection]. |

### Supporting
| Library / Tool | Version | Purpose | When to Use |
|----------------|---------|---------|-------------|
| wandb | 0.26.1 in project `.venv` | Training telemetry | Use only with `WANDB_PROJECT=tsc-cycle-v3-9b`; otherwise set `report_to=["none"]` for deterministic local runs [VERIFIED: project venv package inspection] [VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/04-qlora-sft-9b-batch-1/04-CONTEXT.md]. |
| safetensors | 0.7.0 in project `.venv` | Adapter/checkpoint serialization dependency | Use through PEFT/HF save APIs; no custom safetensors writer needed in Phase 4 [VERIFIED: project venv package inspection]. |
| `scripts/dgx_spark/env.sh` | project script | CUDA/Triton/allocator env setup | Must be sourced by wrapper or transitively through `run_safe.sh` before GPU training [VERIFIED: /home/samuel/TSC_CYCLE/scripts/dgx_spark/env.sh]. |
| `scripts/dgx_spark/run_safe.sh` | project script | systemd MemoryMax=100G and MemorySwapMax=0 training scope | Use for dry-run and full-run commands; noninteractive sudo systemd-run is available now [VERIFIED: /home/samuel/TSC_CYCLE/scripts/dgx_spark/run_safe.sh] [VERIFIED: environment probe]. |
| pytest | 9.0.3 in project `.venv` | RED tests and fast gates | Use for Wave 0/CI style tests before long GPU runs [VERIFIED: project venv package inspection] [VERIFIED: /home/samuel/TSC_CYCLE/pyproject.toml]. |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| HF Trainer + PEFT | TRL `SFTTrainer` | `SFTTrainer` supports packing/chat-template automation, but Phase 4 already has pre-tokenized labels and must keep `packing=False`/raw text/no chat template; HF Trainer is simpler and avoids hidden preprocessing [VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/student/train.py] [CITED: https://context7.com/huggingface/trl/llms.txt]. |
| Direct Arrow IPC loader | Rebuild dataset from JSONL during training | Rebuilding would violate Phase 4’s dependency on Phase 3 exact tokenized artifacts and could change split/hash evidence [VERIFIED: /home/samuel/TSC_CYCLE/data/splits/v3/rebuild_report.json]. |
| `target_modules="all-linear"` | Explicit projection name list | Explicit list in existing v1.0 trainer misses Qwen3.5 architecture-specific linear layers; PEFT docs recommend `all-linear` for QLoRA-style coverage across architectures [VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/student/train.py] [CITED: https://github.com/huggingface/peft/blob/main/docs/source/developer_guides/quantization.md]. |

**Installation:**
```bash
# No package installation in Phase 4; reuse the existing project venv.
source /home/samuel/TSC_CYCLE/scripts/dgx_spark/env.sh
/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest tests/test_v3_sft_*.py -q
```
This phase should not run `pip install vllm`, `pip install flash-attn`, upgrade PyTorch, or switch training stacks [VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/04-qlora-sft-9b-batch-1/04-CONTEXT.md].

**Version verification:** PyPI latest versions on 2026-05-09 were transformers 5.8.0, trl 1.4.0, peft 0.19.1, bitsandbytes 0.49.2, accelerate 1.13.0, datasets 4.8.5, pyarrow 24.0.0, wandb 0.26.1, safetensors 0.7.0, torch 2.11.0 [VERIFIED: PyPI JSON API]. The project `.venv` contains transformers 5.8.0, trl 1.3.0, peft 0.19.1, bitsandbytes 0.48.0, accelerate 1.13.0, datasets 4.8.5, pyarrow 24.0.0, wandb 0.26.1, safetensors 0.7.0, torch 2.11.0+cu130 [VERIFIED: project venv package inspection]. Use installed project venv versions rather than upgrading to PyPI latest because D-01/D-02 lock the environment [VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/04-qlora-sft-9b-batch-1/04-CONTEXT.md].

## Architecture Patterns

### System Architecture Diagram

```text
Phase 3 artifacts
  data/tokenized/v3/train.arrow ─┐
  data/tokenized/v3/val.arrow ───┼─► Arrow IPC loader ─► HF Dataset columns(input_ids, attention_mask, labels)
  data/tokenized/v3/ood_val.arrow ┘                         │
                                                             ▼
FROZEN guard ─► v1.0 artifact readonly/hash check      Trainer bootstrap
                                                             │
                                                             ├─► Qwen/Qwen3.5-9B load: bnb 4-bit NF4 + SDPA + bf16
                                                             ├─► prepare_model_for_kbit_training(use_reentrant=False)
                                                             ├─► PEFT LoRA r=64 alpha=64 dropout=0 target_modules=all-linear
                                                             └─► LoRA coverage report / fail-closed
                                                                    │
                                                                    ▼
500-sample dry run under run_safe 100G
  ├─ first 200 optimizer steps ─► grad_norm p99 + NaN gate ─ fail ► abort
  └─ dry-run adapter/checkpoint ─► OOD generation + constraint_lint ─ pass ≥95%?
                                                                  │
                                            no ────────────────────┘ abort
                                            yes
                                             ▼
Full run under run_safe 100G
  ├─ eval every 200 steps on val.arrow
  ├─ early stopping patience=3 on eval_loss
  ├─ save best/final adapter under runs/v3.0-9B-{utc}/
  └─ manifest/report proves SFT-01..08 + artifact isolation
```
Diagram ownership and flow are derived from Phase 4 context, Phase 3 report, and current trainer code [VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/04-qlora-sft-9b-batch-1/04-CONTEXT.md] [VERIFIED: /home/samuel/TSC_CYCLE/data/splits/v3/rebuild_report.json] [VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/student/train.py].

### Recommended Project Structure

```text
tsc_cycle/
├── student/
│   ├── train.py                  # Refactor existing Phase 4 trainer entrypoint [VERIFIED: existing file]
│   ├── sft_v3.py                 # Recommended new helpers: Arrow loader, config validation, callbacks [RECOMMENDED]
│   └── dataset.py                # Keep v1.0 dataset utilities; do not use parquet path for v3 Arrow [VERIFIED: existing file]
├── v3_gates/
│   ├── sft_dry_run_v3.py         # Recommended dry-run OOD lint + grad_norm report [RECOMMENDED]
│   └── sft_report_v3.py          # Recommended aggregate SFT-01..08 report [RECOMMENDED]
scripts/
├── run_v3_phase4_dry_run.sh      # Recommended run_safe 100G dry-run wrapper [RECOMMENDED]
└── run_v3_phase4_full.sh         # Recommended run_safe 100G full-run wrapper [RECOMMENDED]
tests/
└── test_v3_sft_*.py              # Recommended RED tests for SFT invariants [RECOMMENDED]
runs/
└── v3.0-9B-{utc_timestamp}/      # Required isolated output root [VERIFIED: CONTEXT.md]
```

### Pattern 1: Consume Phase 3 Arrow IPC directly
**What:** Read `data/tokenized/v3/{train,val,ood_val}.arrow` with `pyarrow.ipc.open_file`, convert to `datasets.Dataset`, remove non-model columns only after writing/recording artifact metadata [VERIFIED: pyarrow schema inspection] [VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/v3_gates/dataset_rebuild_v3.py].  
**When to use:** Always in Phase 4 training and dry-run; do not read legacy `data/tokenized/train/data.parquet` [VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/student/train.py] [VERIFIED: /home/samuel/TSC_CYCLE/data/splits/v3/rebuild_report.json].  
**Example:**
```python
# Source: /home/samuel/TSC_CYCLE/tsc_cycle/v3_gates/dataset_rebuild_v3.py + pyarrow schema inspection
import pyarrow as pa
from datasets import Dataset

MODEL_COLUMNS = ["input_ids", "attention_mask", "labels"]

def load_arrow_split(path: str) -> Dataset:
    with pa.memory_map(path, "r") as source:
        table = pa.ipc.open_file(source).read_all()
    ds = Dataset(table)
    return ds.remove_columns([c for c in ds.column_names if c not in MODEL_COLUMNS])
```

### Pattern 2: QLoRA bootstrap mirrors Phase 1 memory gate
**What:** Use `BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_use_double_quant=True)`, `AutoModelForCausalLM.from_pretrained(..., attn_implementation="sdpa", torch_dtype=torch.bfloat16, device_map={"": 0})`, `prepare_model_for_kbit_training(... use_reentrant=False)`, and `LoraConfig(... target_modules="all-linear")` [VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/v3_gates/memory_budget_v3.py] [CITED: https://context7.com/bitsandbytes-foundation/bitsandbytes/llms.txt] [CITED: https://github.com/huggingface/peft/blob/main/docs/source/developer_guides/quantization.md].  
**When to use:** Both dry-run and full-run must share the same model setup to avoid passing memory gates with a different graph than full training [VERIFIED: /home/samuel/TSC_CYCLE/artifacts/v3/phase1/memory_budget.json].  
**Example:**
```python
# Source: /home/samuel/TSC_CYCLE/tsc_cycle/v3_gates/memory_budget_v3.py
bnb_cfg = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_compute_dtype=torch.bfloat16,
    bnb_4bit_use_double_quant=True,
)
model = AutoModelForCausalLM.from_pretrained(
    "Qwen/Qwen3.5-9B",
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
lora_cfg = LoraConfig(
    r=64,
    lora_alpha=64,
    lora_dropout=0.0,
    bias="none",
    target_modules="all-linear",
    task_type="CAUSAL_LM",
)
```

### Pattern 3: Trainer gates are callbacks plus JSON reports
**What:** Implement callbacks for grad_norm/NaN gate and early stopping; write JSON artifacts with `ok`, `gates`, `fatal_failures`, hyperparameters, package versions, input artifact hashes, and output paths [VERIFIED: existing v3 gate JSON pattern in /home/samuel/TSC_CYCLE/data/splits/v3/rebuild_report.json].  
**When to use:** Before dry-run starts, during first 200 optimizer steps, after dry-run OOD evaluation, and after full-run completion [VERIFIED: /home/samuel/TSC_CYCLE/.planning/REQUIREMENTS.md].  
**Example:**
```python
# Source: Transformers Trainer callback docs + SFT-06 requirement
class GradNormAbortCallback(TrainerCallback):
    def __init__(self, gate_steps: int = 200, p99_limit: float = 3.0):
        self.gate_steps = gate_steps
        self.p99_limit = p99_limit
        self.grad_norms = []
        self.fatal_failures = []

    def on_log(self, args, state, control, logs=None, **kwargs):
        logs = logs or {}
        if "loss" in logs and not math.isfinite(float(logs["loss"])):
            self.fatal_failures.append({"gate": "loss_finite", "reason": "loss is NaN/Inf"})
            control.should_training_stop = True
        if "grad_norm" in logs:
            self.grad_norms.append(float(logs["grad_norm"]))
        if state.global_step >= self.gate_steps and self.grad_norms:
            p99 = statistics.quantiles(self.grad_norms, n=100)[98]
            if p99 >= self.p99_limit:
                self.fatal_failures.append({"gate": "grad_norm_p99", "reason": f"p99={p99}"})
                control.should_training_stop = True
```

### Pattern 4: FROZEN guard before any trainer write
**What:** Create `runs/20260507T032419Z/FROZEN.md`, remove write permissions from v1.0 production artifact tree, record pre/post hashes or mtimes, and fail if Phase 4 would write outside `runs/v3.0-9B-*` [VERIFIED: /home/samuel/TSC_CYCLE/.planning/STATE.md] [VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/04-qlora-sft-9b-batch-1/04-CONTEXT.md].  
**When to use:** Wave 0 before dry-run and full-run wrappers [VERIFIED: /home/samuel/TSC_CYCLE/.planning/REQUIREMENTS.md].  
**Example:**
```python
# Source: SFT-08 requirement; use as planner-level implementation pattern
V1_ROOT = Path("runs/20260507T032419Z")
V3_PREFIX = "v3.0-9B-"

if not V1_ROOT.exists():
    raise SystemExit("SFT-08 fail: v1.0 artifact root missing")
(V1_ROOT / "FROZEN.md").write_text("Frozen for v3.0 Phase 4; read-only reference only.\n", encoding="utf-8")
# chmod should be handled carefully by wrapper/tests; training code must not write under V1_ROOT.
```

### Recommended Plan Slices

| Plan | Scope | Required Validation Command | Main Risk |
|------|-------|-----------------------------|-----------|
| 04-01 RED tests + FROZEN guard | Add tests for locked hyperparams, Arrow path usage, run root isolation, FROZEN marker/chmod, no legacy parquet path | `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest tests/test_v3_sft_config.py tests/test_v3_sft_frozen.py -q` [RECOMMENDED] | Tests may need fake tokenizer/model to avoid GPU and remain fast [ASSUMED]. |
| 04-02 Trainer refactor | Refactor `student/train.py` or helper module to load Arrow IPC, locked QLoRA config, LoRA coverage report, safe output root | `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest tests/test_v3_sft_arrow_loader.py tests/test_v3_sft_config.py -q` [RECOMMENDED] | Accidentally using legacy v1.0 defaults (`lora_alpha=128`, dropout=0.05, bs=4) would violate SFT-01/SFT-03 [VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/student/train.py]. |
| 04-03 Dry-run gate | Implement 500-sample dry-run wrapper/report with grad_norm p99 and OOD lint pass rate | `scripts/dgx_spark/run_safe.sh 100G -- /home/samuel/TSC_CYCLE/.venv/bin/python -m tsc_cycle.student.train --mode dry-run ...` [RECOMMENDED] | 1h dry-run may not produce stable OOD generation if adapter undertrained; gate should fail closed rather than silently proceed [VERIFIED: SFT-04]. |
| 04-04 Full-run | Implement full-run wrapper with eval every 200 steps, patience=3, max epoch=5, best adapter, wandb isolation | `scripts/dgx_spark/run_safe.sh 100G -- /home/samuel/TSC_CYCLE/.venv/bin/python -m tsc_cycle.student.train --mode full ...` [RECOMMENDED] | Long run is cross-night and should survive logging/checkpointing without writing v1.0 paths [VERIFIED: /home/samuel/TSC_CYCLE/.planning/ROADMAP.md]. |
| 04-05 Aggregate report | Emit `runs/v3.0-9B-{utc}/sft_manifest.json` and Phase 4 gate report proving SFT-01..08 | `/home/samuel/TSC_CYCLE/.venv/bin/python -m tsc_cycle.v3_gates.sft_report_v3 --run-dir runs/v3.0-9B-...` [RECOMMENDED] | Planner must not mark phase complete from adapter existence alone; gate report must verify all requirements [VERIFIED: established v3 report pattern in rebuild_report.json]. |

### Anti-Patterns to Avoid

- **Re-tokenizing from JSONL inside Phase 4:** It would bypass Phase 3’s split/hash/truncation evidence and risks different data than the approved Arrow artifacts [VERIFIED: /home/samuel/TSC_CYCLE/data/splits/v3/rebuild_report.json].
- **Using TRL packing or chat-template preprocessing:** It would contradict `packing=False` and raw-text/no-chat-template constraints; TRL docs show packing/chat-template automation exists, so avoid it unless disabled completely [CITED: https://context7.com/huggingface/trl/llms.txt] [VERIFIED: /home/samuel/TSC_CYCLE/artifacts/v3/phase1/tokenizer_audit.json].
- **Leaving v1.0 defaults in `train.py`:** Existing defaults are model=4B, batch_size=4, grad_accum=8, alpha=128, dropout=0.05, explicit projection target list, and data-dir parquet path; all conflict with Phase 4 locks [VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/student/train.py].
- **Running trainer directly without `run_safe.sh`:** Project wrapper enforces MemoryMax and MemorySwapMax; direct GPU execution bypasses DGX Spark safety contract [VERIFIED: /home/samuel/TSC_CYCLE/scripts/dgx_spark/run_safe.sh].
- **Assuming adapter output implies gate success:** SFT-04/SFT-06 require explicit OOD pass rate and grad_norm/NaN evidence; adapter existence alone is insufficient [VERIFIED: /home/samuel/TSC_CYCLE/.planning/REQUIREMENTS.md].

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| 4-bit quantized loading | Custom quantization or manual dtype casting | `transformers.BitsAndBytesConfig` + bitsandbytes NF4 | Existing Phase 1 smoke/memory gates already validated this path on Qwen3.5-9B and GB10 [VERIFIED: /home/samuel/TSC_CYCLE/artifacts/v3/phase1/env_smoke.json]. |
| QLoRA adapter injection | Manual monkey-patching linear layers | PEFT `LoraConfig(target_modules="all-linear")` + `get_peft_model` | PEFT docs define `all-linear` as QLoRA-style coverage across model architectures [CITED: https://github.com/huggingface/peft/blob/main/docs/source/developer_guides/quantization.md]. |
| Gradient clipping | Manual per-parameter clipping outside Trainer | `TrainingArguments(max_grad_norm=0.5)` | Transformers exposes `max_grad_norm` for gradient clipping in Trainer [CITED: https://huggingface.co/docs/transformers/v4.56.2/en/main_classes/trainer]. |
| Early stopping | Custom loop around epoch loss | Transformers `EarlyStoppingCallback` plus steps eval/save settings | Trainer supports callbacks and eval/save strategies; using them preserves Trainer state/checkpoint semantics [CITED: https://huggingface.co/docs/transformers/v4.56.2/en/trainer]. |
| Hard-constraint lint | Ad-hoc regex checks on generated JSON | `tsc_cycle.constraint_lint.validate` | Existing validator checks dict type, phase set/order, integer values, min/max constraints [VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/constraint_lint.py]. |
| Prompt parsing | New parser for `<SOLUTION>` | `prompt_builder.parse_assistant_output` | Existing parser knows project tags and rejects legacy `</end_working_out>` [VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/prompt_builder.py]. |
| DGX memory cap | Inline `ulimit` or Python memory checks | `scripts/dgx_spark/run_safe.sh 100G -- ...` | Wrapper uses systemd cgroup MemoryMax=100G and MemorySwapMax=0, which Python cannot enforce reliably [VERIFIED: /home/samuel/TSC_CYCLE/scripts/dgx_spark/run_safe.sh]. |
| Artifact manifests | Free-form text log only | JSON report with `ok`, `gates`, `fatal_failures`, hashes, paths | v3 gates already use machine-readable JSON report patterns consumed by planning/verification [VERIFIED: /home/samuel/TSC_CYCLE/data/splits/v3/rebuild_report.json]. |

**Key insight:** Phase 4 complexity is gate orchestration and artifact safety, not novel training algorithms; use standard HF/PEFT/bitsandbytes primitives and spend custom code only on project-specific guards/reports [VERIFIED: /home/samuel/TSC_CYCLE/.planning/REQUIREMENTS.md].

## Existing v1.0 Reuse vs Phase 4 Additions

| Area | Reuse | Must Change / Add |
|------|-------|-------------------|
| Model load | Existing `AutoModelForCausalLM`, bnb NF4, SDPA, bf16, `device_map={"":0}` pattern is reusable [VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/student/train.py]. | Default model must be `Qwen/Qwen3.5-9B`, and loader must assert class/model evidence from Phase 1 remains causal LM with no vision params [VERIFIED: /home/samuel/TSC_CYCLE/artifacts/v3/phase1/env_smoke.json]. |
| Tokenizer safety | Existing `boot_tokenizer_check` and dynamic native-think functions are reusable [VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/student/train.py] [VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/tokenizer_check.py]. | Use Qwen3.5 audit IDs dynamically; do not use imported v1 constants `NATIVE_THINK_OPEN_ID/CLOSE_ID` for v3 generation checks [VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/tokenizer_check.py] [VERIFIED: /home/samuel/TSC_CYCLE/artifacts/v3/phase1/tokenizer_audit.json]. |
| Dataset loader | Existing `DataCollatorForSeq2Seq` with label padding is reusable [VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/student/train.py]. | Replace parquet `data/tokenized/{train,val_id}/data.parquet` loading with Arrow IPC `data/tokenized/v3/{train,val,ood_val}.arrow` [VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/student/train.py] [VERIFIED: /home/samuel/TSC_CYCLE/data/splits/v3/rebuild_report.json]. |
| LoRA config | Existing `prepare_model_for_kbit_training` + PEFT injection is reusable [VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/student/train.py]. | Change alpha 128→64, dropout 0.05→0.0, explicit target list→`all-linear`; add coverage report [VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/student/train.py] [VERIFIED: /home/samuel/TSC_CYCLE/.planning/REQUIREMENTS.md]. |
| Training args | Existing bf16, gradient checkpointing, cosine scheduler, warmup, wandb optional report pattern is partially reusable [VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/student/train.py]. | Change bs 4→1, grad_accum 8→16, epochs max 5, add `optim="adamw_torch_fused"`, `max_grad_norm=0.5`, steps eval/save/early stopping, no 6h cap [VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/student/train.py] [VERIFIED: /home/samuel/TSC_CYCLE/.planning/REQUIREMENTS.md]. |
| Smoke generation | Existing `smoke_generate` verifies closing tags/native leak on 5 prompts [VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/student/train.py]. | Dry-run gate must evaluate OOD hard-constraint pass rate ≥95% over selected OOD prompts, not just tag closure [VERIFIED: /home/samuel/TSC_CYCLE/.planning/REQUIREMENTS.md]. |
| Output root | Existing default `runs/{ts}/train` is not reusable as-is [VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/student/train.py]. | Use `runs/v3.0-9B-{utc_timestamp}/` root with subdirs `dry_run/`, `full/`, `adapter/`, `reports/`, and manifest [VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/04-qlora-sft-9b-batch-1/04-CONTEXT.md]. |
| Wrappers | Existing run-safe wrapper script is reusable [VERIFIED: /home/samuel/TSC_CYCLE/scripts/dgx_spark/run_safe.sh]. | Add Phase 4 dry/full scripts that source env/run_safe, set wandb project, enforce FROZEN guard, and call exact venv python [RECOMMENDED]. |

## Phase 3 Arrow IPC Consumption Details

- Phase 3 tokenized outputs are `data/tokenized/v3/train.arrow`, `data/tokenized/v3/val.arrow`, and `data/tokenized/v3/ood_val.arrow` [VERIFIED: /home/samuel/TSC_CYCLE/data/splits/v3/rebuild_report.json].
- Each Arrow IPC file has list<int64> columns for `input_ids`, `attention_mask`, and `labels`, plus metadata columns `sample_id`, `raw_length`, `truncated`, `prompt_hash`, and `assistant_hash` [VERIFIED: pyarrow schema inspection].
- The training split has 7601 rows, val has 950 rows, and ood_val has 950 rows [VERIFIED: pyarrow schema inspection] [VERIFIED: /home/samuel/TSC_CYCLE/data/splits/v3/rebuild_report.json].
- Phase 3 max raw length is 1410 and max_seq_length is 2048, so Phase 4 does not need truncation or packing to fit selected sequence length [VERIFIED: /home/samuel/TSC_CYCLE/data/splits/v3/rebuild_report.json].
- The loader should preserve `sample_id`/hash metadata for dry-run reports before dropping non-model columns for Trainer [RECOMMENDED based on /home/samuel/TSC_CYCLE/data/splits/v3/rebuild_report.json].
- The trainer should use `val.arrow` for eval_loss early stopping and `ood_val.arrow` for hard-constraint generation/lint dry-run gate [VERIFIED: /home/samuel/TSC_CYCLE/.planning/REQUIREMENTS.md].

## Common Pitfalls

### Pitfall 1: Existing trainer defaults silently violate locked SFT requirements
**What goes wrong:** `train.py` defaults to 4B, bs=4, grad_accum=8, alpha=128, dropout=0.05, explicit target_modules list, and parquet paths [VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/student/train.py].  
**Why it happens:** v1.0 trainer was built for a different base model and data layout [VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/student/train.py].  
**How to avoid:** Add config validation that exits before model load unless all locked Phase 4 hyperparameters and paths match SFT-01..08 [RECOMMENDED].  
**Warning signs:** Output dir starts `runs/{ts}` instead of `runs/v3.0-9B-`, or logs show `bs=4x8`, `lora_alpha=128`, `lora_dropout=0.05` [VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/student/train.py].

### Pitfall 2: Step-1 memory success does not prove long-run safety
**What goes wrong:** Phase 1 shows seq=2560 passed step-1 but failed 100-step with systemd oom-kill; seq=2048 was selected because it passed both criteria [VERIFIED: /home/samuel/TSC_CYCLE/artifacts/v3/phase1/memory_budget.json].  
**Why it happens:** Training memory can grow after optimizer/caches/fragmentation across steps [VERIFIED: /home/samuel/TSC_CYCLE/artifacts/v3/phase1/memory_budget.json].  
**How to avoid:** Keep max_seq_length=2048 and run both dry-run and full-run under `run_safe.sh 100G` [VERIFIED: /home/samuel/TSC_CYCLE/artifacts/v3/phase1/memory_budget.json] [VERIFIED: /home/samuel/TSC_CYCLE/scripts/dgx_spark/run_safe.sh].  
**Warning signs:** Any attempt to increase sequence length to 2560/3072/4096 in Phase 4 [VERIFIED: /home/samuel/TSC_CYCLE/artifacts/v3/phase1/memory_budget.json].

### Pitfall 3: `all-linear` is correct but must be audited
**What goes wrong:** Planner may trust `target_modules="all-linear"` without proving it hit expected Qwen3.5 projections [CITED: https://github.com/huggingface/peft/blob/main/docs/source/developer_guides/quantization.md].  
**Why it happens:** Qwen3.5 uses a hybrid architecture with Gated DeltaNet and Gated Attention, so old Qwen3 projection names are insufficient [CITED: https://huggingface.co/Qwen/Qwen3.5-9B] [VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/student/train.py].  
**How to avoid:** Emit `lora_coverage.json` listing trainable LoRA module names/counts and fail if expected linear-attention/full-attention layers have zero adapters [RECOMMENDED].  
**Warning signs:** Trainable parameter count unexpectedly low or coverage report lacks delta/gated attention modules [RECOMMENDED].

### Pitfall 4: Early stopping requires compatible eval/save settings
**What goes wrong:** `load_best_model_at_end=True` with mismatched `eval_strategy`/`save_strategy` or incompatible step intervals can fail or load the wrong checkpoint [CITED: https://huggingface.co/docs/transformers/v4.56.2/en/main_classes/trainer].  
**Why it happens:** Transformers docs require save strategy to match eval strategy, and step save interval must be a round multiple of eval interval when loading best model [CITED: https://huggingface.co/docs/transformers/v4.56.2/en/main_classes/trainer].  
**How to avoid:** Use `eval_strategy="steps"`, `eval_steps=200`, `save_strategy="steps"`, `save_steps=200` or `400`, `load_best_model_at_end=True`, `metric_for_best_model="eval_loss"`, `greater_is_better=False` [CITED: https://huggingface.co/docs/transformers/v4.56.2/en/main_classes/trainer].  
**Warning signs:** Trainer warns about best model loading, or no `eval_loss` appears every 200 steps [CITED: https://huggingface.co/docs/transformers/v4.56.2/en/main_classes/trainer].

### Pitfall 5: Native `<think>` leakage can pass if v1.0 hard-coded IDs are reused
**What goes wrong:** Qwen3.5 native think IDs are 248068/248069, not v1.0 IDs, so hard-coded v1 checks would miss leakage [VERIFIED: /home/samuel/TSC_CYCLE/artifacts/v3/phase1/tokenizer_audit.json].  
**Why it happens:** Native think IDs are tokenizer/model specific [VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/tokenizer_check.py].  
**How to avoid:** Always call `native_think_token_ids(tokenizer)` from active Qwen3.5 tokenizer [VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/tokenizer_check.py].  
**Warning signs:** Code imports `NATIVE_THINK_OPEN_ID`/`NATIVE_THINK_CLOSE_ID` constants for v3 checks [VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/student/train.py].

### Pitfall 6: Dry-run OOD pass rate is an evaluation problem, not a training log metric
**What goes wrong:** Trainer loss/grad_norm can look healthy while generated SOLUTION violates min/max/order/coverage [VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/constraint_lint.py].  
**Why it happens:** SFT loss optimizes token prediction, not hard-constraint satisfaction directly [ASSUMED].  
**How to avoid:** After dry-run, generate on OOD sample prompts, parse with `parse_assistant_output`, lint with `constraint_lint.validate`, and require pass rate ≥95% [VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/prompt_builder.py] [VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/constraint_lint.py] [VERIFIED: /home/samuel/TSC_CYCLE/.planning/REQUIREMENTS.md].  
**Warning signs:** Dry-run report lacks per-sample violation counts or only reports loss [RECOMMENDED].

## Code Examples

Verified patterns from official sources and codebase:

### Locked `TrainingArguments` core
```python
# Source: https://huggingface.co/docs/transformers/v4.56.2/en/main_classes/trainer + SFT-02..06
training_args = TrainingArguments(
    output_dir=str(run_dir / "full"),
    num_train_epochs=5,
    per_device_train_batch_size=1,
    gradient_accumulation_steps=16,
    learning_rate=1e-4,
    lr_scheduler_type="cosine",
    warmup_ratio=0.03,
    optim="adamw_torch_fused",
    max_grad_norm=0.5,
    bf16=True,
    gradient_checkpointing=True,
    gradient_checkpointing_kwargs={"use_reentrant": False},
    eval_strategy="steps",
    eval_steps=200,
    save_strategy="steps",
    save_steps=200,
    load_best_model_at_end=True,
    metric_for_best_model="eval_loss",
    greater_is_better=False,
    report_to=["wandb"] if os.environ.get("WANDB_API_KEY") else ["none"],
    remove_unused_columns=False,
)
```

### Early stopping callback
```python
# Source: project venv API inspection + https://huggingface.co/docs/transformers/v4.56.2/en/trainer
from transformers import EarlyStoppingCallback

callbacks = [
    GradNormAbortCallback(gate_steps=200, p99_limit=3.0),
    EarlyStoppingCallback(early_stopping_patience=3),
]
```

### Dry-run OOD lint loop
```python
# Source: /home/samuel/TSC_CYCLE/tsc_cycle/prompt_builder.py + /home/samuel/TSC_CYCLE/tsc_cycle/constraint_lint.py
reasoning, solution = parse_assistant_output(decoded_text)
lint = validate(prediction_input, solution)
row = {
    "sample_id": sample_id,
    "ok": lint.ok,
    "violations": lint.violations,
}
```

### Safe wrapper command
```bash
# Source: /home/samuel/TSC_CYCLE/scripts/dgx_spark/run_safe.sh and env.sh
cd /home/samuel/TSC_CYCLE
source scripts/dgx_spark/env.sh
scripts/dgx_spark/run_safe.sh 100G -- \
  /home/samuel/TSC_CYCLE/.venv/bin/python -m tsc_cycle.student.train \
  --model Qwen/Qwen3.5-9B \
  --data-dir data/tokenized/v3 \
  --output-root runs/v3.0-9B-$(date -u +%Y%m%dT%H%M%SZ) \
  --batch-size 1 --grad-accum 16 --epochs 5
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| v1.0 4B `Qwen/Qwen3-4B-Thinking-2507` trainer defaults | v3.0 Qwen/Qwen3.5-9B with locked QLoRA r=64 batch=1 grad_accum=16 | Phase 4 v3.0 context on 2026-05-09 [VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/04-qlora-sft-9b-batch-1/04-CONTEXT.md] | Must refactor defaults and add gates before training [VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/student/train.py]. |
| Parquet split layout `data/tokenized/{train,val_id}/data.parquet` | Arrow IPC `data/tokenized/v3/{train,val,ood_val}.arrow` | Phase 3 completed on 2026-05-09 [VERIFIED: /home/samuel/TSC_CYCLE/.planning/STATE.md] | Trainer loader must change to Arrow IPC [VERIFIED: /home/samuel/TSC_CYCLE/data/splits/v3/rebuild_report.json]. |
| 6h training cap in earlier project constraint | No 6h cap for Phase 4 full-run; early stopping controls convergence | User decision locked in Phase 4 context [VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/04-qlora-sft-9b-batch-1/04-CONTEXT.md] | Planner should not add timeout kill for full-run; it should add safe-run and checkpoints [VERIFIED: /home/samuel/TSC_CYCLE/.planning/ROADMAP.md]. |
| Explicit Qwen projection list for LoRA | PEFT `target_modules="all-linear"` | Phase 4 SFT-01 lock [VERIFIED: /home/samuel/TSC_CYCLE/.planning/REQUIREMENTS.md] | Required to cover hybrid Qwen3.5 linear-attention/full-attention projections [CITED: https://github.com/huggingface/peft/blob/main/docs/source/developer_guides/quantization.md]. |
| Smoke-only generation | Dry-run hard-constraint OOD gate ≥95% plus grad_norm p99 gate | Phase 4 SFT-04/SFT-06 lock [VERIFIED: /home/samuel/TSC_CYCLE/.planning/REQUIREMENTS.md] | Full-run cannot begin from trainer loss alone [VERIFIED: /home/samuel/TSC_CYCLE/.planning/REQUIREMENTS.md]. |

**Deprecated/outdated:**
- `tsc_cycle/student/train.py` defaults are outdated for Phase 4 and should be treated as reusable scaffolding, not acceptable configuration [VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/student/train.py].
- `tsc_cycle/student/dataset.py` writes parquet and uses 4B `MODEL_NAME`, so it should not be the source of Phase 4 tokenization; Phase 4 should consume Phase 3 Arrow IPC outputs [VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/student/dataset.py] [VERIFIED: /home/samuel/TSC_CYCLE/data/splits/v3/rebuild_report.json].
- `flash-attn` and vLLM are out of scope/forbidden for this phase [VERIFIED: /home/samuel/TSC_CYCLE/CLAUDE.md] [VERIFIED: /home/samuel/TSC_CYCLE/.planning/REQUIREMENTS.md].

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Accelerate is used under the hood by Trainer for PyTorch training. | Standard Stack | Low; implementation does not call Accelerate APIs directly, but dependency/version reporting may be overemphasized. |
| A2 | SFT loss alone does not guarantee hard-constraint satisfaction. | Common Pitfalls | Medium; if wrong, dry-run lint would still be required by SFT-04, so planning impact is minimal. |
| A3 | Some ASVS category names/controls below are mapped from general ASVS knowledge rather than successfully extracted from OWASP page in this session. | Security Domain | Low for Phase 4 because this is offline training, but planner should not treat ASVS wording as compliance evidence. |

## Open Questions (RESOLVED)

1. **Dry-run 500-sample selection source — RESOLVED**
   - Final choice: Use exactly 500 deterministic OOD examples selected from `data/splits/v3/ood_val.index.jsonl`, with raw prediction inputs recovered from `data/v3/phase2/labeled_merged.jsonl` by `raw_index` and cross-checked by `sample_id`. The dry-run evaluator must not compute hard-constraint lint from `data/tokenized/v3/ood_val.arrow` token IDs alone; Arrow may be used only for sample/hash alignment evidence.
   - Evidence required: dry-run generated evidence JSONL includes `sample_id`, `raw_index`, `prediction_input`, `generated_text`, `parsed_solution`, and `lint_result` for each of the 500 examples, plus deterministic seed/hash.
2. **Exact checkpoint cadence beyond eval every 200 steps — RESOLVED**
   - Final choice: Use `eval_steps=200` and `save_steps=200` with compatible steps-based eval/save, `load_best_model_at_end=True`, `metric_for_best_model="eval_loss"`, `greater_is_better=False`, and `save_total_limit=3`.
3. **Whether to use `Trainer` or `SFTTrainer` after refactor — RESOLVED**
   - Final choice: Use the existing HF `Trainer`, not TRL `SFTTrainer`, because Phase 3 already produced pre-tokenized Arrow records with masked `labels`, and Phase 4 must avoid hidden packing/chat-template preprocessing.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| `/home/samuel/TSC_CYCLE/.venv/bin/python` | All Phase 4 Python commands | ✓ | Python 3.12.3 [VERIFIED: environment probe] | None; D-02 requires project/known-good venv [VERIFIED: CONTEXT.md]. |
| CUDA / NVIDIA GB10 | Qwen3.5-9B training | ✓ | CUDA 13.0 in Phase 1 smoke; NVIDIA-SMI 580.126.09 now [VERIFIED: /home/samuel/TSC_CYCLE/artifacts/v3/phase1/env_smoke.json] [VERIFIED: environment probe] | None; GPU training blocks without it [VERIFIED: SFT scope]. |
| `scripts/dgx_spark/env.sh` | CUDA_HOME, PATH, LD_LIBRARY_PATH, TRITON_PTXAS_PATH, allocator config | ✓ | project script [VERIFIED: /home/samuel/TSC_CYCLE/scripts/dgx_spark/env.sh] | None; required by D-09 [VERIFIED: CONTEXT.md]. |
| `scripts/dgx_spark/run_safe.sh` | MemoryMax=100G/MemorySwapMax=0 scope | ✓ | project script [VERIFIED: /home/samuel/TSC_CYCLE/scripts/dgx_spark/run_safe.sh] | Equivalent `systemd-run --scope -p MemoryMax=100G -p MemorySwapMax=0` allowed by D-09 [VERIFIED: CONTEXT.md]. |
| noninteractive sudo `/usr/bin/systemd-run` | run_safe launch | ✓ | systemd 255 / sudo 1.9.15p5 [VERIFIED: environment probe] | If unavailable, configure minimal sudoers for systemd-run as documented in run_safe.sh [VERIFIED: /home/samuel/TSC_CYCLE/scripts/dgx_spark/run_safe.sh]. |
| swap off | DGX Spark OOM safety | ✓ | `swapon --show` line count 0 [VERIFIED: environment probe] | None; swap must remain off for long run [VERIFIED: /home/samuel/TSC_CYCLE/artifacts/v3/phase1/run_safe_scope.json]. |
| wandb | SFT-07 telemetry isolation | ✓ | 0.26.1 in project venv [VERIFIED: project venv package inspection] | Use `report_to=["none"]` if `WANDB_API_KEY` absent; still set project when enabled [VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/student/train.py]. |
| Phase 3 Arrow files | Training/eval/OOD inputs | ✓ | train=7601, val=950, ood_val=950 [VERIFIED: pyarrow schema inspection] | None; rebuilding data is out of scope [VERIFIED: /home/samuel/TSC_CYCLE/data/splits/v3/rebuild_report.json]. |
| v1.0 production artifact root | FROZEN guard | ✓ | `runs/20260507T032419Z/` exists [VERIFIED: directory listing] | None; SFT-08 requires this exact root [VERIFIED: /home/samuel/TSC_CYCLE/.planning/STATE.md]. |

**Missing dependencies with no fallback:** None found during this research [VERIFIED: environment probe].

**Missing dependencies with fallback:** No blocking missing dependency found; wandb can be disabled if credentials are absent [VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/student/train.py].

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 in project `.venv` [VERIFIED: project venv package inspection] |
| Config file | `pyproject.toml` with `testpaths=["tests"]` and `addopts="-q"` [VERIFIED: /home/samuel/TSC_CYCLE/pyproject.toml] |
| Quick run command | `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest tests/test_v3_sft_config.py tests/test_v3_sft_frozen.py tests/test_v3_sft_arrow_loader.py -q` [RECOMMENDED] |
| Full suite command | `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest tests -q` [VERIFIED: /home/samuel/TSC_CYCLE/pyproject.toml] |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| SFT-01 | LoRA config is r=64/alpha=64/dropout=0/all-linear and coverage report exists | unit + GPU smoke | `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest tests/test_v3_sft_config.py::test_lora_config_locked_all_linear -q` | ❌ Wave 0 |
| SFT-02 | TrainingArguments lock lr/cosine/warmup/max_grad_norm/adamw_torch_fused | unit | `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest tests/test_v3_sft_config.py::test_training_args_optimizer_scheduler_locked -q` | ❌ Wave 0 |
| SFT-03 | batch=1/grad_accum=16/packing false/grad_ckpt non-reentrant | unit | `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest tests/test_v3_sft_config.py::test_batch_accum_checkpointing_locked -q` | ❌ Wave 0 |
| SFT-04 | Dry-run report requires 500 samples and OOD lint pass rate ≥95% before full-run | unit + integration | `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest tests/test_v3_sft_dry_run.py::test_dry_run_gate_fails_closed_below_threshold -q` | ❌ Wave 0 |
| SFT-05 | Full-run uses eval every 200 steps, patience=3, max epoch 5, no wall-clock cap | unit | `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest tests/test_v3_sft_config.py::test_early_stopping_config_locked -q` | ❌ Wave 0 |
| SFT-06 | Grad norm p99 and NaN gate aborts after first 200 steps | unit | `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest tests/test_v3_sft_grad_gate.py -q` | ❌ Wave 0 |
| SFT-07 | Run root `runs/v3.0-9B-*` and wandb project isolation | unit | `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest tests/test_v3_sft_artifacts.py::test_run_root_and_wandb_project_isolated -q` | ❌ Wave 0 |
| SFT-08 | `runs/20260507T032419Z/` FROZEN marker/chmod and no writes | unit | `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest tests/test_v3_sft_frozen.py -q` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest tests/test_v3_sft_*.py -q` after Wave 0 files exist [RECOMMENDED].
- **Per wave merge:** `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest tests -q` plus any non-GPU config report command [RECOMMENDED].
- **Phase gate:** Dry-run and full-run JSON reports must have `ok=true` and all SFT gates passing before `/gsd-verify-work` [VERIFIED: /home/samuel/TSC_CYCLE/.planning/REQUIREMENTS.md].

### Wave 0 Gaps
- [ ] `tests/test_v3_sft_config.py` — covers SFT-01, SFT-02, SFT-03, SFT-05, SFT-07 [RECOMMENDED].
- [ ] `tests/test_v3_sft_arrow_loader.py` — covers Phase 3 Arrow IPC consumption [RECOMMENDED].
- [ ] `tests/test_v3_sft_dry_run.py` — covers SFT-04 dry-run gate semantics [RECOMMENDED].
- [ ] `tests/test_v3_sft_grad_gate.py` — covers SFT-06 grad_norm/NaN fail-closed behavior [RECOMMENDED].
- [ ] `tests/test_v3_sft_frozen.py` — covers SFT-08 FROZEN guard and output path allowlist [RECOMMENDED].
- [ ] `scripts/run_v3_phase4_dry_run.sh` and `scripts/run_v3_phase4_full.sh` — cover safe wrapper invocation [RECOMMENDED].

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|------------------|
| V2 Authentication | no | Phase 4 is offline local training and does not add auth flows [VERIFIED: /home/samuel/TSC_CYCLE/.planning/ROADMAP.md] [ASSUMED category name]. |
| V3 Session Management | no | Phase 4 does not create web sessions or cookies [VERIFIED: /home/samuel/TSC_CYCLE/.planning/ROADMAP.md] [ASSUMED category name]. |
| V4 Access Control | yes | Filesystem allowlist: writes only under `runs/v3.0-9B-*`, v1.0 `runs/20260507T032419Z/` is FROZEN/read-only [VERIFIED: /home/samuel/TSC_CYCLE/.planning/REQUIREMENTS.md] [ASSUMED category name]. |
| V5 Input Validation | yes | Validate generated SOLUTION with `constraint_lint.validate`; validate report schemas and Arrow paths before training [VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/constraint_lint.py] [ASSUMED category name]. |
| V6 Cryptography | yes | Use SHA-256 artifact hashes from existing manifest/report patterns; do not invent crypto [VERIFIED: /home/samuel/TSC_CYCLE/data/splits/v3/rebuild_report.json] [ASSUMED category name]. |

### Known Threat Patterns for offline training stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Accidental overwrite of v1.0 production artifact | Tampering | FROZEN marker, chmod read-only, output root allowlist, pre/post hash/mtime check [VERIFIED: /home/samuel/TSC_CYCLE/.planning/REQUIREMENTS.md]. |
| Training on wrong dataset artifact | Tampering / Repudiation | Compare Arrow file hashes/paths against `data/splits/v3/rebuild_report.json` and `manifest.json` before trainer start [VERIFIED: /home/samuel/TSC_CYCLE/data/splits/v3/rebuild_report.json]. |
| Native `<think>` token leakage | Integrity | Dynamic tokenizer ID lookup and native-ID rejection [VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/tokenizer_check.py] [VERIFIED: /home/samuel/TSC_CYCLE/artifacts/v3/phase1/tokenizer_audit.json]. |
| OOM causing DGX instability | Denial of Service | `run_safe.sh 100G --` with MemorySwapMax=0 and swap disabled [VERIFIED: /home/samuel/TSC_CYCLE/scripts/dgx_spark/run_safe.sh] [VERIFIED: /home/samuel/TSC_CYCLE/artifacts/v3/phase1/run_safe_scope.json]. |
| Untrusted shell/env injection through wrapper args | Elevation / Tampering | Use fixed wrapper arguments, absolute project venv path, and no user-provided command string in phase scripts [RECOMMENDED based on /home/samuel/TSC_CYCLE/scripts/dgx_spark/run_safe.sh]. |

## Sources

### Primary (HIGH confidence)
- `/home/samuel/TSC_CYCLE/.planning/phases/04-qlora-sft-9b-batch-1/04-CONTEXT.md` — locked decisions D-01..D-11, Phase 4 boundary, canonical refs [VERIFIED].
- `/home/samuel/TSC_CYCLE/.planning/REQUIREMENTS.md` — SFT-01..SFT-08 and v3.0 traceability [VERIFIED].
- `/home/samuel/TSC_CYCLE/.planning/STATE.md` — Phase 1-3 status, baseline artifact path, current focus [VERIFIED].
- `/home/samuel/TSC_CYCLE/.planning/ROADMAP.md` — Phase 4 success criteria and dependency DAG [VERIFIED].
- `/home/samuel/TSC_CYCLE/CLAUDE.md` — project constraints and DGX Spark/vLLM/tokenizer/lint requirements [VERIFIED].
- `/home/samuel/TSC_CYCLE/tsc_cycle/student/train.py` — existing v1.0 trainer patterns and defaults [VERIFIED].
- `/home/samuel/TSC_CYCLE/tsc_cycle/student/dataset.py` — legacy dataset/tokenization/parquet layout [VERIFIED].
- `/home/samuel/TSC_CYCLE/tsc_cycle/v3_gates/memory_budget_v3.py` — Qwen3.5 QLoRA model setup and memory gate pattern [VERIFIED].
- `/home/samuel/TSC_CYCLE/tsc_cycle/v3_gates/dataset_rebuild_v3.py` — Arrow IPC writer and tokenized schema source [VERIFIED].
- `/home/samuel/TSC_CYCLE/scripts/dgx_spark/env.sh` and `/home/samuel/TSC_CYCLE/scripts/dgx_spark/run_safe.sh` — DGX runtime safety contract [VERIFIED].
- `/home/samuel/TSC_CYCLE/data/splits/v3/rebuild_report.json` — Phase 3 split/tokenization green report summarized by Python due file size [VERIFIED].
- `/home/samuel/TSC_CYCLE/artifacts/v3/phase1/{env_smoke.json,memory_budget.json,run_safe_scope.json,tokenizer_audit.json}` — Phase 1 Qwen3.5/DGX evidence [VERIFIED].
- Context7 `/huggingface/peft` — `target_modules="all-linear"` QLoRA docs [CITED].
- Context7 `/bitsandbytes-foundation/bitsandbytes` — 4-bit NF4/bf16/double quant docs [CITED].
- Context7 `/websites/huggingface_co_transformers_v4_56_2_en` — Trainer/TrainingArguments docs [CITED].
- Context7 `/huggingface/datasets` — PyTorch/Dataset formatting docs [CITED].
- Hugging Face model card `https://huggingface.co/Qwen/Qwen3.5-9B` — Qwen3.5 model architecture/card facts [CITED].

### Secondary (MEDIUM confidence)
- PyPI JSON API — latest registry versions/publish timestamps on 2026-05-09 [VERIFIED: PyPI JSON API].
- Project venv package inspection — installed versions and API field availability [VERIFIED: environment probe].

### Tertiary (LOW confidence)
- ASVS category wording where official page extraction did not return category names in this session [ASSUMED].

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — locked by CONTEXT.md and verified in project `.venv`/Phase 1 artifacts [VERIFIED: environment probe] [VERIFIED: /home/samuel/TSC_CYCLE/artifacts/v3/phase1/env_smoke.json].
- Architecture: HIGH — derived from current code paths, Phase 3 artifacts, and SFT requirements [VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/student/train.py] [VERIFIED: /home/samuel/TSC_CYCLE/data/splits/v3/rebuild_report.json].
- Pitfalls: HIGH for config/path/memory/tokenizer pitfalls verified in code/artifacts; MEDIUM for convergence/dry-run stability because full Phase 4 run has not happened yet [VERIFIED: /home/samuel/TSC_CYCLE/artifacts/v3/phase1/memory_budget.json].

**Research date:** 2026-05-09 [VERIFIED: /home/samuel/TSC_CYCLE/.planning/STATE.md]  
**Valid until:** 2026-05-16 for stack/runtime details because Qwen3.5/Transformers stack is fast-moving and local venv is the controlling source [ASSUMED].
