# Stack Research — TSC-CYCLE v3.0 (Qwen3.5-9B 基座切换)

**Domain:** LLM 蒸馏（GPT-5.5 high → Qwen3.5-9B）QLoRA SFT 训练 + GGUF 部署
**Hardware target:** NVIDIA DGX Spark（GB10 Blackwell sm_121、aarch64、CUDA 13、128GB unified memory，训练上限 100GB）
**Researched:** 2026-05-08
**Overall confidence:** **HIGH**（本机已存在 Qwen3.5-ready 环境 + llama.cpp Qwen3.5 已注册 + 模型 config.json 全字段已下载校核；显存估算为 MEDIUM）

---

## Executive Recommendation（一句话）

**完全沿用 v1.0 训练栈（`/home/samuel/TSC_CYCLE/.venv` 已具备 transformers 5.8.0 + peft 0.19.1 + trl 1.3.0 + bitsandbytes 0.48.0 + torch 2.11.0+cu130，原生支持 Qwen3.5）**，零环境变更；
9B 训练 batch_size=1 + grad_accum=16/32（effective 16/32）在 100GB 上限内显存预算约 **35–55 GB peak**（4-bit base ~5.0 GB + LoRA r=64 trainable ~80 MB + activations 主导，受 GatedDeltaNet 24/32 linear-attention 层影响显著小于纯 dense attention 的 9B）；
GGUF 路径走本机 `/home/samuel/projects/EvoProgTSC/llama.cpp/convert_hf_to_gguf.py`（**已注册 `Qwen3_5ForConditionalGeneration` 和 `Qwen3_5ForCausalLM`**，line 5036），`Qwen3_5TextModel` 继承 `_LinearAttentionVReorderBase` 处理 GatedDeltaNet 张量重排，无需 fork 或 PR cherry-pick。

**关键 unknown（dry-run 必须验证）：**
1. 用 `Qwen3_5ForConditionalGeneration` 但只想训文本时，base model load 是否会拉起 vision tower（约 1.6 GB extra params，浪费但不致命）— 需在 dry-run 阶段检测并裁掉。
2. PEFT `target_modules` 在 GatedDeltaNet 的 linear_attention 层与 full_attention 层命名是否一致 —— 推荐 dry-run 用 `target_modules="all-linear"` 或 `model.named_modules()` 枚举一次后落定显式列表。
3. bitsandbytes 4-bit 是否会量化 GatedDeltaNet 的 1D conv（`linear_conv_kernel_dim=4`）—— bnb 默认只换 `nn.Linear`，conv 层会保持 bf16，对显存影响轻微（<200 MB）但需 verify。

---

## Recommended Stack

### Core Technologies（已锁，零变更）

| Technology | Version (本机已装) | Purpose | Why Recommended |
|------------|-------------------|---------|-----------------|
| **Python** | 3.12 | Runtime | dgx-spark-setup 锁；cu130 aarch64 wheel 对应 cp312 |
| **PyTorch** | `2.11.0+cu130` | DL 框架 | 本机 `/home/samuel/TSC_CYCLE/.venv` 已装；aarch64 cu130 wheel 工作；GB10 bf16 原生 |
| **Transformers** | `5.8.0` | HF 模型加载 + SFT 上游 | **Qwen3.5 最低需要 transformers >= 5.2.0**（`qwen3_5` model_type 在 v5.2 加入），本机 5.8.0 满足且高于最低；已验证可 import 全部 `qwen3_5*` config |
| **TRL** | `1.3.0` | `SFTTrainer` 蒸馏训练 | 与 transformers 5.x 兼容（v5 引入的 fused MoE expert 重构对 9B dense 不影响；本项目不用 MoE 变体）|
| **PEFT** | `0.19.1` | LoRA / QLoRA adapter | transformers 5.x 兼容；r=64 配置成熟；PEFT 0.19.x 含 `target_parameters` 但 9B dense 仍用 `target_modules` 路径 |
| **bitsandbytes** | `0.48.0` | 4-bit NF4 量化加载基座 | 与 v1.0 同；aarch64 wheel 工作；sm_121 走 PTX JIT；**dense 9B 不在「MoE QLoRA 4-bit not recommended」警告范围内**（Unsloth 文档明确该警告只针对 MoE 变体） |
| **Accelerate** | dgx-spark-setup 锁定（≥1.6.0） | 分布式/混合精度 | 单卡 bf16 路径稳 |
| **Datasets** | ≥3.1.0 | SFT 数据 IO | 标准 HF 栈 |
| **Triton** | 与 PyTorch 2.11 cu130 捆绑 | 内核 JIT | 必须 `export TRITON_PTXAS_PATH=/usr/local/cuda/bin/ptxas` 否则 `sm_121a` 报错 |
| **OpenAI Python SDK** | `>=1.50.0` | 教师 API 客户端 | v1.0 已用，零变更 |

**结论：本里程碑不需要 install / upgrade 任何包。** v1.0 实际跑的环境（5.8.0 / 0.19.1 / 1.3.0 / 0.48.0）已经领先于 CLAUDE.md 中冻结描述的 4.56.2 + 0.22.x + 0.15.x —— v1.0 升级路径在 phase 4 期间被静默升过，新栈已稳定运行端到端 6h SFT + GGUF + eval。本项目的「环境锁定」从此对齐到本机 venv 实际状态，而非 CLAUDE.md 文本快照。

### Supporting Libraries（v1.0 沿用）

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **llama.cpp** | 本机已 build：`/home/samuel/projects/EvoProgTSC/llama.cpp` | merge 后 HF→GGUF→Q4_K_M | **关键验证：line 5036 注册 `@ModelBase.register("Qwen3_5ForConditionalGeneration", "Qwen3_5ForCausalLM")` → `Qwen3_5TextModel(_LinearAttentionVReorderBase)`**，GatedDeltaNet 张量 V 重排在 base class 处理；同时 line 1490 `qwen35` pre-tokenizer hash 已注册；line 4747 注册了 multimodal `Qwen3_5ForConditionalGeneration` for VL，但 `Qwen3_5TextModel` 走纯 text 路径处理 9B-Base |
| **safetensors** | ≥0.4.0 | 权重序列化 | merge LoRA 后保存 bf16 |
| **wandb** | ≥0.18.1 | 训练观测 | 6h 训练强烈建议开 |
| **rich** | ≥14.0.0 | 控制台日志 | dgx-spark-setup 默认 |
| **jsonschema** | ≥4.20.0 | 教师输出硬约束 lint | v1.0 沿用 |
| **pydantic** | ≥2.5.0 | 数据 schema | v1.0 沿用 |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| **uv** | 包管理 | 本里程碑预期不调用 |
| **systemd-run --scope** | OOM 防护 | **9B 训练比 4B 更必要**：`MemoryMax=100G MemorySwapMax=0` |
| **swap off** | OOM 防护前置 | `sudo swapoff -a`；DGX Spark 必做 |

---

## Installation（无需任何安装）

```bash
# 直接进入项目 venv（已 Qwen3.5-ready）
source /home/samuel/TSC_CYCLE/.venv/bin/activate

# 验证（必须全部 OK）
python -c "
import torch, transformers, peft, trl, bitsandbytes
print('torch', torch.__version__)
print('transformers', transformers.__version__)  # 期望 >=5.2.0
print('peft', peft.__version__)
print('trl', trl.__version__)
print('bnb', bitsandbytes.__version__)
from transformers import AutoConfig
cfg = AutoConfig.from_pretrained('Qwen/Qwen3.5-9B')
print('model_type', cfg.model_type, 'arch', cfg.architectures)
"

# llama.cpp（已 build，已支持 Qwen3.5）
grep -n 'Qwen3_5ForCausalLM' /home/samuel/projects/EvoProgTSC/llama.cpp/convert_hf_to_gguf.py
# 期望输出：5036:@ModelBase.register("Qwen3_5ForConditionalGeneration", "Qwen3_5ForCausalLM")
```

**训练前必做的环境变量**（v1.0 沿用）：

```bash
export TORCH_CUDA_ARCH_LIST="12.1a"
export TRITON_PTXAS_PATH=/usr/local/cuda/bin/ptxas
export PATH="/usr/local/cuda/bin:$PATH"
export LD_LIBRARY_PATH="/usr/local/cuda/lib64:$LD_LIBRARY_PATH"
export TOKENIZERS_PARALLELISM=false
```

**训练 wrapper（必做，9B 更必要）**：

```bash
sudo systemd-run --scope \
  -p MemoryMax=100G \
  -p MemorySwapMax=0 \
  -p OOMScoreAdjust=500 \
  bash -lc 'cd ~/TSC_CYCLE && source .venv/bin/activate && python -m sft.train ...'
```

---

## Qwen3.5-9B 架构关键事实（直接源自 `Qwen/Qwen3.5-9B/config.json`）

| 字段 | 值 | 含义 / 影响 |
|------|----|------------|
| `architectures` | `["Qwen3_5ForConditionalGeneration"]` | 多模态 wrapper；纯文本训练应通过 `Qwen3_5ForCausalLM` 或 `Qwen3_5TextModel` 入口（transformers 5.x 已注册），或加载完整后扔掉 vision tower |
| `model_type` | `qwen3_5` | text 子配置 model_type 为 `qwen3_5_text`；vision 子配置 `qwen3_5` |
| `num_hidden_layers` | 32 | 与 v1.0 4B 同 |
| `hidden_size` | 4096 | dense 部分 ≈ 9B 总参数的主体 |
| `intermediate_size` | 12288 | MLP 维度 |
| `num_attention_heads` | 16 | full_attention 层每层 16 head |
| `num_key_value_heads` | 4 | GQA（4:1）|
| `head_dim` | 256 | full_attention 层每 head 256-dim |
| **`full_attention_interval`** | **4** | **每 4 层中 1 层是 full_attention，3 层是 linear_attention（GatedDeltaNet）** |
| **`layer_types`** | 24× linear_attention + 8× full_attention | 显式列出每层；KV cache 只在 8 个 full_attention 层产生，linear 层走 recurrent state |
| `linear_num_value_heads` | 32 | GatedDeltaNet 的 V head 数（影响 V 重排，已由 `_LinearAttentionVReorderBase` 处理）|
| `linear_num_key_heads` | 16 | GatedDeltaNet K head |
| `linear_value_head_dim` / `linear_key_head_dim` | 128 / 128 | linear attention head dim |
| `linear_conv_kernel_dim` | 4 | 1D conv kernel；bnb 不会量化（保持 bf16）|
| `vocab_size` | 248320（tokenizer 真实 248044 + 33 added/special） | **比 Qwen3 的 151936 大 ~63%**；embedding+lm_head 显存占用显著上升（见下表）|
| `max_position_embeddings` | 262144 | YaRN 可扩到 1M；本项目用 ≤4096 即可 |
| `mtp_num_hidden_layers` | 1 | MTP head；SFT 时可冻结，导出时可丢 |
| `vision_config` | depth=27, hidden=1152 | **vision tower ~0.4B 参数**；纯文本训练需在 load 时跳过或加载后丢弃（见下文） |
| `dtype` | `bfloat16` | 训练目标精度一致 |
| `attn_output_gate` | `true` | 输出门控（small ops，SDPA 路径 OK）|
| `rope_parameters.mrope_interleaved` | `true` | M-RoPE for VL；纯文本 inference 不影响 |
| `transformers_version` (config) | `4.57.0.dev0` | **作者 lint** —— Qwen 团队期望 transformers >=4.57.0 dev 或更高；transformers stable 5.2.0+ 满足 |

**自定义思考标签 tokenizer 验证（已实测，HIGH）：**

```
'<start_working_out>'  -> ids [27, 2388, 78307, 5878, 29] (5 tokens)
'<end_working_out>'    -> ids [27, 400, 78307, 5878, 29]  (5 tokens)
'<SOLUTION>'           -> ids [18288, 44442, 29]          (3 tokens)
'</SOLUTION>'          -> ids [510, 50, 44442, 29]        (4 tokens)
'<think>'              -> id  [248068]                    (1 token)  ← 与 v1.0 同样是单 token，禁用
'</think>'             -> id  [248069]                    (1 token)  ← 同上
```

→ **MEMORY 中记录的「自定义标签必须拆 sub-token」要求继续满足**。注意 `<think>` 在 Qwen3.5 中 token id 是 248068（v1.0 Qwen3 中是 151667），**任何硬编码 think token id 的代码必须改成查表**，但本项目根本不用 native `<think>`，只在禁用 chat_template 的 thinking 模式时间接相关。

---

## 显存预算（9B + QLoRA r=64 + batch=1 + bf16 grads + paged AdamW8bit）

参考 Unsloth 官方表格：**Qwen3.5-9B bf16 LoRA peak ≈ 22 GB**（DGX A100/H100 single-card 估算）。本项目走 4-bit QLoRA（base 量化更狠），峰值更低，但 DGX Spark unified memory 把 OS / 数据 cache 也算进 100 GB 上限，需要更保守。

### 静态权重 / Optimizer / Activation 分项估算

| 分项 | 计算 | 估算 (GB) | 把握 |
|------|------|----------|------|
| **4-bit NF4 base weights** (dense 8.5B + linear-attn params) | 9B × 0.5 byte = 4.5 GB；double_quant overhead ~0.1 GB | **~4.6 GB** | HIGH |
| **Embedding + LM head**（vocab=248320，tied=false，hidden=4096，**bnb 不量化** ） | 2 × (248320 × 4096 × 2 byte) = 4.06 GB | **~4.1 GB**（fp16/bf16，bnb 不会自动量化 embedding/lm_head）| HIGH — **关键差异 vs 4B** |
| **GatedDeltaNet conv1d + RMSNorm + small ops** (bf16, not quantized) | ~0.3 GB | **~0.3 GB** | MEDIUM |
| **Vision tower**（如果误加载）| 0.4B × 2 byte = 0.8 GB | **0** if 跳过；**+0.8 GB** if 误加载 | HIGH |
| **LoRA r=64 trainable params** (q/k/v/o/gate/up/down on full+linear-attn linears, ~32 layers × 7 modules × 4096 × 64 × 2 = 233M params) | bf16: 233M × 2 byte | **~0.5 GB** trainable | MEDIUM（实际取决于 target_modules 命中 GatedDeltaNet projections 的多少；如只命中 full_attention 8 层，trainable 降至 ~0.15 GB）|
| **LoRA gradients** | 同 trainable | **~0.5 GB** | MEDIUM |
| **AdamW8bit optimizer state** (paged) | trainable × 2 (m, v) × 1 byte (8bit) ≈ 233M × 2 | **~0.5 GB** | HIGH (paged optimizer = bnb.optim.PagedAdamW8bit) |
| **Activations** (gradient_checkpointing=True, batch=1, seq=2048, full attention layers 8/32 dominate but linear_attn cheaper) | dense 9B at seq=2048 batch=1 with grad_ckpt ≈ 6–10 GB；GatedDeltaNet 24/32 层走 recurrent state，激活峰值约 **3–5 GB** | **~5–10 GB** | LOW-MEDIUM — **9B + GatedDeltaNet hybrid 缺乏在 Spark 上的 batch=1 公开测量** |
| **KV cache during forward** (only 8 full_attention 层 × 2 (k,v) × seq × n_kv_heads × head_dim × 2 byte) | 8 × 2 × 2048 × 4 × 256 × 2 = 67 MB；linear_attn 层 recurrent state ≈ 1 MB/层 × 24 = 24 MB | **~0.1 GB**（极小，因为 GQA + 仅 8 层） | HIGH |
| **HF/Triton/CUDA workspace, ipc, temp buffers** | DGX Spark 通常 1–3 GB | **~2 GB** | MEDIUM |
| **🟰 Peak total（不含 vision）** | sum | **≈ 18–25 GB peak training memory** | MEDIUM |
| **🟰 + 数据 / OS / cache headroom** | DGX Spark unified memory 训练时 OS 至少占 5–10 GB | **总系统占用 ~30–40 GB** | MEDIUM |

**结论**：9B + QLoRA r=64 + batch=1 + grad_accum 16 + max_seq_length=2048 在 DGX Spark 100GB 上限内**有充足余量（>50 GB）**。grad_accum 上限不受显存限制，受 6h 训练预算限制 —— effective batch 16–32 即可，再大反而拉长训练时间。

**与 v1.0 4B 实测对比锚点**（v1.0 跑通）：4B + r=64 + batch=4/seq=2048 实测 ~30–40 GB peak。9B 切到 batch=1 再加 GatedDeltaNet 24/32 层缓解，预计 peak **不会显著高于** v1.0 4B + batch=4 的水平 —— 可能落在 25–45 GB，HIGH 把握落在 100GB 上限内。

### 推荐 SFT 配置

```python
SFTConfig(
    output_dir="runs/qwen3_5-9b-tsc-r64",
    num_train_epochs=2,
    per_device_train_batch_size=1,           # 用户明确要求
    gradient_accumulation_steps=16,          # effective batch 16；6h 预算下 sweet spot
    gradient_checkpointing=True,             # 必开
    learning_rate=5e-5,                      # 9B 比 4B 学习率降一档
    lr_scheduler_type="cosine",
    warmup_ratio=0.03,
    bf16=True,
    max_seq_length=2048,                     # 与 v1.0 同
    logging_steps=10,
    save_strategy="epoch",
    eval_strategy="epoch",
    optim="paged_adamw_8bit",                # 必用 paged，9B + bnb 缺它会 OOM 抖动
    report_to="wandb",
    packing=False,                           # 与 v1.0 同
)
```

---

## Key Configuration Decisions

### Model Loading（强制 SDPA + 跳过 vision tower）

```python
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
import torch

bnb_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_use_double_quant=True,
    bnb_4bit_compute_dtype=torch.bfloat16,
)

# 关键：用 AutoModelForCausalLM，让 transformers 5.x 自动选 Qwen3_5ForCausalLM
# （而不是 Qwen3_5ForConditionalGeneration），跳过 vision tower
# 如果 AutoModelForCausalLM 仍拉起 vision，回退到显式 import：
#   from transformers import Qwen3_5ForCausalLM
#   model = Qwen3_5ForCausalLM.from_pretrained(...)
model = AutoModelForCausalLM.from_pretrained(
    "Qwen/Qwen3.5-9B-Base",            # 优先用 -Base，无 chat_template / 无 thinking 偏置
    quantization_config=bnb_config,
    attn_implementation="sdpa",         # 不要 flash_attention_2
    torch_dtype=torch.bfloat16,
    device_map={"": 0},
    trust_remote_code=False,            # transformers 5.x 已原生支持，不需要
)

# Dry-run 必做：检查是否有 vision params
for n, p in model.named_parameters():
    assert "visual" not in n.lower() and "vision" not in n.lower(), \
        f"Vision tower 误加载：{n}；必须改用 Qwen3_5ForCausalLM 显式 import"

tokenizer = AutoTokenizer.from_pretrained("Qwen/Qwen3.5-9B-Base")
tokenizer.padding_side = "right"
```

### QLoRA r=64 配置（target_modules 含 GatedDeltaNet projections）

```python
from peft import LoraConfig

# Dry-run：先 print(model) 找出实际命名
# Qwen3.5 GatedDeltaNet 层的命名（基于 transformers 5.x 实现，待 dry-run 验证）：
#   - full_attention 层：q_proj / k_proj / v_proj / o_proj
#   - linear_attention 层：可能是 in_proj / out_proj / b_proj / a_proj 等 GatedDeltaNet 自定义命名
# 最稳妥 = "all-linear"，让 PEFT 自动命中所有 nn.Linear

lora_config = LoraConfig(
    r=64,
    lora_alpha=128,                      # 经验：alpha = 2 * r
    lora_dropout=0.05,
    bias="none",
    task_type="CAUSAL_LM",
    target_modules="all-linear",         # ← 切到 all-linear；显式列表在 dry-run 后回收
    modules_to_save=None,                # 不要把 embed_tokens / lm_head 放进去
                                         # （embedding 248K × 4096 = 2 GB trainable，6h 预算撑不住）
)
```

> **注意**：v1.0 显式列了 `["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]` —— 在 Qwen3.5 上**这只会命中 8 个 full_attention 层 + 32 个 MLP 层，会漏掉 24 个 linear_attention 层的 GatedDeltaNet projections**，蒸馏效果会打折扣。**v3.0 必须 dry-run 后扩展列表或直接 `all-linear`**。

### 自定义思考标签 tokenizer 测试（v3.0 必跑）

```python
for tag in ["<start_working_out>", "<end_working_out>", "<SOLUTION>", "</SOLUTION>"]:
    ids = tokenizer.encode(tag, add_special_tokens=False)
    assert len(ids) > 1, f"{tag} 在 Qwen3.5 tokenizer 中是单 token，禁用"
    print(tag, "→", ids, "(", len(ids), "tokens )")

# 已离线验证：4 个标签都拆成 3-5 sub-token，与 v1.0 行为一致
```

---

## GGUF 导出 Pipeline（已验证 llama.cpp 注册）

### 第一步：merge LoRA → bf16 HF 权重

```python
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch

# 注意：用 Qwen3_5ForCausalLM（纯文本路径），merge 时 CPU
base = AutoModelForCausalLM.from_pretrained(
    "Qwen/Qwen3.5-9B-Base",
    torch_dtype=torch.bfloat16,
    device_map="cpu",
)
peft_model = PeftModel.from_pretrained(base, "runs/qwen3_5-9b-tsc-r64/checkpoint-final")
merged = peft_model.merge_and_unload()
merged.save_pretrained("runs/merged-bf16-9b", safe_serialization=True)
AutoTokenizer.from_pretrained("Qwen/Qwen3.5-9B-Base").save_pretrained("runs/merged-bf16-9b")
```

### 第二步：HF → GGUF f16

```bash
cd /home/samuel/projects/EvoProgTSC/llama.cpp
python convert_hf_to_gguf.py \
  /home/samuel/TSC_CYCLE/runs/merged-bf16-9b \
  --outfile /home/samuel/TSC_CYCLE/runs/tsc-cycle-9b-f16.gguf \
  --outtype f16
```

> ✅ **已验证**：本机 `convert_hf_to_gguf.py:5036` 注册了 `@ModelBase.register("Qwen3_5ForConditionalGeneration", "Qwen3_5ForCausalLM")` → `Qwen3_5TextModel(_LinearAttentionVReorderBase)`，`_LinearAttentionVReorderBase` 处理 GatedDeltaNet 张量 V 重排（继承自 `Qwen3NextModel`，与 Qwen3-Next 使用同一 hybrid 处理路径）。同时 line 1490 `qwen35` pre-tokenizer hash 注册 → tokenizer 元数据完整序列化。

### 第三步：fp16 → Q4_K_M

```bash
/home/samuel/projects/EvoProgTSC/llama.cpp/llama-quantize \
  /home/samuel/TSC_CYCLE/runs/tsc-cycle-9b-f16.gguf \
  /home/samuel/TSC_CYCLE/runs/tsc-cycle-9b-q4_k_m.gguf \
  Q4_K_M
```

预计 GGUF 大小：f16 ≈ **18 GB**（9B × 2 byte），q4_K_M ≈ **5.5 GB**（v1.0 4B q4_K_M 是 2.4 GB，9B 线性外推 5.4 GB）。

### Tokenizer 注意事项

- v1.0 tokenizer-safety 要求继续满足（已离线验证）
- vocab=248K 比 Qwen3 大幅扩展，convert_hf_to_gguf 序列化 tokenizer 时间略长（仍 <1 min）
- **q4_K_M 后必须重跑 5-prompt smoke test 检查思考段+SOLUTION 段是否齐全** —— GatedDeltaNet 24/32 层在 q4_K_M 下的 fidelity 是 v3.0 主要量化风险，在 v1.0 dense Qwen3 上未触发过

---

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| **TRL 1.3 + PEFT 0.19 + transformers 5.8 + bnb 0.48**（本机栈） | **Unsloth Qwen3.5 fine-tune docs** | Unsloth 官方有 Qwen3.5 fine-tune 教程，bf16 LoRA peak 22 GB；但 (a) 仍需切换 venv 并装 Unsloth 自带的 transformers/triton patches；(b) DGX Spark 上 GPT-OSS / Qwen3-Next 类模型需要 monkey-patch（[Issue #4867](https://github.com/unslothai/unsloth/issues/4867)），Qwen3.5 hybrid 是否需要补丁未在官方 Spark blog 中明确；(c) GGUF wrapper 在 9B 量级仍可能触发 [Issue #3861](https://github.com/unslothai/unsloth/issues/3861) 边缘 bug。**只有在 batch=1 + grad_ckpt 仍然 OOM 时才考虑切**（极不可能）|
| **AutoModelForCausalLM**（推荐入口） | **显式 `Qwen3_5ForCausalLM` import** | 如果 dry-run 发现 AutoModelForCausalLM 误选了 `Qwen3_5ForConditionalGeneration` 拉起 vision tower，回退到显式 import；transformers 5.x 已原生注册两个类 |
| **target_modules="all-linear"** | 显式列表 `["q_proj", "k_proj", ...]` | dry-run 后用 `model.named_modules()` 枚举出 GatedDeltaNet 实际 projection 命名再回收成显式列表，省 ~1–2% 训练时间且更可控 |
| **Qwen3.5-9B-Base** | Qwen3.5-9B（Instruct） | -Base 没有 chat_template 偏置和 native thinking 训练，更适合从零教自定义思考格式；Instruct 版本 RL 调过原生 `<think>` 输出会与本项目自定义标签竞争 |
| **本机 llama.cpp**（已注册 Qwen3.5） | mainline llama.cpp 重新 pull | 本机版本已含 Qwen3_5/Qwen3_5Moe 完整支持 + Qwen3-Next `_LinearAttentionVReorderBase` 基类；除非遇 GatedDeltaNet 量化崩塌需要拿最新 PR fix，否则不动 |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| **重装 transformers / peft / trl** | 本机 venv 已是 Qwen3.5-ready 状态（5.8.0 / 0.19.1 / 1.3.0） | 零安装；只 dry-run 验证 |
| **transformers 4.56.2**（CLAUDE.md 文本快照值） | 不支持 `qwen3_5` model_type，加载 Qwen3.5-9B 会报「architecture not recognized」| 沿用本机 5.8.0 |
| **Qwen3.5-9B-Instruct 的 `<think>` 原生模式** | 与 Qwen3 同样的语义冲突（id=248068/248069 单 token，预训练有偏置） | 沿用 v1.0 自定义标签方案 + Qwen3.5-9B-Base |
| **`Qwen3_5ForConditionalGeneration` 加载然后 ignore vision** | 浪费 ~0.8 GB 显存 + vision_config 的 mrope_section 配置可能干扰 RoPE | 用 `Qwen3_5ForCausalLM` 入口 |
| **`target_modules` 沿用 v1.0 列表** | 漏掉 GatedDeltaNet linear_attention 层的 24/32 projections，蒸馏覆盖打 75% 折扣 | dry-run 后扩展或 `all-linear` |
| **flash-attn / vLLM** | v1.0 同样禁用 | SDPA + transformers.generate / llama.cpp |
| **`add_special_tokens=True` 把自定义标签加 vocab** | 同 v1.0；vocab=248K 已大，添加更多 token 触发 lm_head resize 会让 trainable 暴涨 | 文本标签 BPE 拆分 |
| **packing=True** | 同 v1.0 | `packing=False` |
| **swap 开启 + 不用 systemd-run** | DGX Spark unified memory + 9B 训练比 4B 更易触发死亡螺旋 | swap off + `MemoryMax=100G` |
| **target_modules 加 embed_tokens / lm_head** | 248K vocab × 4096 hidden 加 LoRA 在 r=64 下 trainable 暴增 ~30M+，6h 预算撑不住 | 严禁 |

---

## Stack Patterns by Variant

**如果 9B + batch=1 + grad_accum=16 在 dry-run 显示 6h 完不成**：
- 把 `gradient_accumulation_steps` 降到 8，effective batch 8（牺牲 batch 稳定性换 step 数）
- 不要把 batch_size 升到 2（用户明确要求 batch=1）
- 缩 `max_seq_length` 到 1536（reality.log prompt 长度大多 <1024）

**如果显存意外接近 100GB 上限**：
- 关 `bnb_4bit_use_double_quant`（省 ~0.1 GB，对 9B 杯水车薪）
- 切 `optim="paged_adamw_32bit"` → `paged_adamw_8bit`（如果还没切）
- 把 `target_modules` 从 `all-linear` 收回到只有 q/k/v/o + GatedDeltaNet 的 in/out_proj，跳过 MLP gate/up/down

**如果 q4_K_M 在 9B + GatedDeltaNet 上崩塌（v1.0 没遇到的新风险）**：
- 立刻回 q5_K_M（5.5 bpw，9B 约 6.8 GB）
- 加 imatrix（用 200 训练样本作校准集）：
  - `llama-imatrix -m tsc-cycle-9b-f16.gguf -f calibration.txt -o imatrix.dat`
  - `llama-quantize --imatrix imatrix.dat tsc-cycle-9b-f16.gguf tsc-cycle-9b-q4_k_m-imat.gguf Q4_K_M`

**如果 dry-run 发现 `_LinearAttentionVReorderBase` 处理与 transformers 5.8 实际 weight 命名错位**（低概率）：
- 拉本地 llama.cpp 到上游 master：`cd /home/samuel/projects/EvoProgTSC/llama.cpp && git pull && make`
- 重新跑 convert + quantize；本机已 build 的 cuda 二进制无需重 build

---

## Version Compatibility（v3.0 实证）

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| `torch 2.11.0+cu130` | `transformers 5.8.0`, `bnb 0.48.0`, `peft 0.19.1`, `trl 1.3.0` | 本机 venv 已 import 验证；GB10 bf16 原生 |
| `transformers >= 5.2.0` | `Qwen3.5` 全系列（`qwen3_5`, `qwen3_5_text`, `qwen3_5_moe`） | **关键最低版本**；本机 5.8.0 满足 |
| `transformers 5.8.0` | `peft 0.19.1`, `trl 1.3.0` | dense 9B 不踩 v5.x MoE expert 融合的 LoRA target_modules 坑（[trl#5222](https://github.com/huggingface/trl/issues/5222)）|
| `bnb 0.48.0` | `torch 2.11+cu130 aarch64`, dense Qwen3.5-9B | dense 模型 4-bit 路径稳；MoE 变体（35B-A3B / 122B-A10B）才需「bf16 LoRA only」warning |
| `local llama.cpp` (含 Qwen3_5/Qwen3_5Moe 注册) | merged bf16 HF safetensors | line 5036 / 5042 已注册；GatedDeltaNet 走 `_LinearAttentionVReorderBase` |
| `openai >= 1.50` | gpt-5.5 + reasoning_effort | v1.0 沿用 |

---

## Open Questions / Dry-Run Verification Checklist

| # | Unknown | Verification | Severity |
|---|---------|--------------|----------|
| 1 | `AutoModelForCausalLM.from_pretrained("Qwen/Qwen3.5-9B-Base")` 是否拉起 vision tower？| Load + `for n, _ in model.named_parameters(): assert 'vis' not in n.lower()` | MEDIUM — 浪费 0.8GB，不致命，但应避免 |
| 2 | PEFT `target_modules="all-linear"` 在 GatedDeltaNet 24/32 层的覆盖范围 | `model = get_peft_model(...); print(sum(p.numel() for p in model.parameters() if p.requires_grad))`；与显式 v1.0 列表对比 | HIGH — 影响蒸馏质量 |
| 3 | bitsandbytes 是否量化 GatedDeltaNet 的 1D conv（`linear_conv_kernel_dim=4`）| Load 后 `print(type(model.model.layers[0].self_attn.conv1d))` 期望仍是 `Conv1d` 而非 bnb Linear4bit | LOW |
| 4 | `Qwen3_5ForCausalLM` 是否在 transformers 5.8.0 注册（vs 仅 5.x main）| `from transformers import Qwen3_5ForCausalLM` 能 import 即 OK | MEDIUM |
| 5 | GatedDeltaNet 24/32 层在 q4_K_M 下 SOLUTION 段格式保真度 | 5-prompt smoke test on f16 vs q4_K_M GGUF，对比 SOLUTION 段 JSON 完整性 | HIGH — v3.0 主要新风险 |
| 6 | 9B 的 `chat_template` (含或不含 thinking) 与自定义 prompt builder 是否冲突 | 用 `Qwen3.5-9B-Base`（裸 base 无 chat_template）从根上回避 | LOW（已有方案）|
| 7 | 实际 9B + batch=1 + grad_accum=16 + seq=2048 单 step 时间 | dry-run 跑 50 step 测吞吐，外推 6h 内能跑 epoch 数 | HIGH — 决定 num_train_epochs 是否可设 2 |

---

## Reference Implementation 评估

| 项 | 状态 |
|----|------|
| 训练框架 | TRL 1.3 + PEFT 0.19 + transformers 5.8 + bnb 0.48（与 v1.0 实际 venv 一致；与 v1.0 STACK.md 文本快照不一致） |
| 环境复用 | `/home/samuel/TSC_CYCLE/.venv` 已 Qwen3.5-ready；不需要再克隆 dgx-spark-setup venv |
| Python | 3.12 |
| PyTorch | `2.11.0+cu130` |
| Attention | SDPA |
| 内存防护 | swap off + systemd-run --scope MemoryMax=100G（9B 比 4B 更必要） |
| 量化方向 | GGUF（f16 + q4_K_M）via 本机 llama.cpp（已注册 Qwen3.5） |

**结论**：v3.0 不引入任何新栈，只切基座。CLAUDE.md 中 STACK section 的版本号文本（4.56.2 / 0.22.x / 0.15.x）与本机 venv 实际状态（5.8.0 / 1.3.0 / 0.19.1）已偏离 —— 建议 v3.0 完成时同步刷新 CLAUDE.md 该 section。

**明确不参考**：
- `https://github.com/waybarrios/dgx-spark-finetune-llm`（用户排除）
- Unsloth Qwen3.5 路径（除非主线 OOM；当前显存预算下毫无必要）
- Qwen3.6 系列（最小 27B，超出 6h + 100GB 预算）

---

## Sources

- [`/home/samuel/projects/EvoProgTSC/llama.cpp/convert_hf_to_gguf.py:5036`](file:///home/samuel/projects/EvoProgTSC/llama.cpp/convert_hf_to_gguf.py) — HIGH（本机已 build；`Qwen3_5ForConditionalGeneration` + `Qwen3_5ForCausalLM` 注册；`Qwen3_5TextModel(_LinearAttentionVReorderBase)`）
- [`/home/samuel/TSC_CYCLE/.venv`](file:///home/samuel/TSC_CYCLE/.venv) `python -c "..."` 实测 — HIGH（transformers 5.8.0 / peft 0.19.1 / trl 1.3.0 / bnb 0.48.0 / torch 2.11.0+cu130）
- [Qwen/Qwen3.5-9B/config.json](https://huggingface.co/Qwen/Qwen3.5-9B/raw/main/config.json) — HIGH（架构字段全部直接拉取：32 layers / full_attention_interval=4 / vocab=248320 / head_dim=256 / hidden=4096 / Qwen3_5ForConditionalGeneration）
- [Qwen3.5-9B HF model card](https://huggingface.co/Qwen/Qwen3.5-9B) — HIGH（multimodal、Apache-2.0、262K context、`transformers[serving] @ git+main`）
- [transformers `qwen3_5` doc](https://huggingface.co/docs/transformers/main/model_doc/qwen3_5) — HIGH（`Qwen3_5Config` / `Qwen3_5ForConditionalGeneration` / `Qwen3_5TextModel`；最低 transformers 5.2.0）
- [stable-learn.com Qwen3.5 family overview](https://stable-learn.com/en/qwen35-native-multimodal-agent-model/) — MEDIUM（确认 9B 是 dense + GatedDeltaNet hybrid，不是 MoE；release 2026-03-02）
- [Unsloth Qwen3.5 fine-tune docs](https://unsloth.ai/docs/models/qwen3.5/fine-tune) — HIGH（bf16 LoRA peak 9B = 22 GB；MoE QLoRA 4-bit not recommended 警告只针对 MoE）
- [PEFT MoE LoRA target_parameters issue (trl#5222)](https://github.com/huggingface/trl/issues/5222) — MEDIUM（transformers v5 fused MoE expert 改 target_parameters；9B dense 不踩此坑）
- [llama.cpp issue #20099 — Qwen3.5-35B-A3B SSM metadata](https://github.com/ggml-org/llama.cpp/issues/20099) — MEDIUM（`qwen35moe.ssm.*` GGUF 字段证明 hybrid 已 wired into mainline，本机分支同步路径）
- [vLLM Qwen3.5 recipes](https://docs.vllm.ai/projects/recipes/en/latest/Qwen/Qwen3.5.html) — MEDIUM（`--language-model-only` 跳过 vision tower 的官方做法，思路迁移到 transformers 端）
- [`/home/samuel/.claude/skills/dgx-spark-training/SKILL.md`](file:///home/samuel/.claude/skills/dgx-spark-training/SKILL.md) — HIGH（v1.0 沿用唯一权威 skill）
- [github.com/natolambert/dgx-spark-setup](https://github.com/natolambert/dgx-spark-setup) — HIGH（v1.0 沿用上游）
- ~~waybarrios/dgx-spark-finetune-llm~~ — **NOT USED**（用户排除）

---

## Confidence Summary

| Recommendation | Confidence | Rationale |
|---|---|---|
| 沿用本机 venv，零安装升级 | **HIGH** | 本机 venv 实测已 transformers 5.8.0 / peft 0.19.1 / trl 1.3.0 / bnb 0.48.0；v1.0 已用同栈端到端跑通 |
| transformers >= 5.2.0 是 Qwen3.5 最低版本 | **HIGH** | HF 官方文档 + 多个 issue 报错信息一致；本机 5.8.0 高于此 |
| 本机 llama.cpp 直接 convert+quantize Qwen3.5-9B | **HIGH** | line 5036 / 5042 已注册 4 个架构 + line 1490 注册 `qwen35` pre-tokenizer hash；GatedDeltaNet 走 `_LinearAttentionVReorderBase`（继承自 Qwen3-Next 处理） |
| 自定义思考标签在 Qwen3.5 tokenizer 上仍是多 sub-token | **HIGH** | 实测 4 个标签全部拆 3-5 sub-token；`<think>` token id 变到 248068 但本项目不使用 |
| 9B + QLoRA r=64 + batch=1 + grad_accum=16 在 100GB 内 | **MEDIUM-HIGH** | Unsloth 9B bf16 LoRA peak 22 GB 锚点；4-bit 更低；GatedDeltaNet 24/32 层无 KV cache；分项估算 18-25 GB peak，余量充足；但缺 Spark 上 9B-hybrid batch=1 实测 |
| 6h 内完成 9B + 2 epoch SFT | **MEDIUM** | 4B 在 v1.0 6h 完成 ~3000 sample × 2 epoch；9B 单 step 时间约 2.2-2.5×（参数 ~2.2× + linear-attn 加速抵消部分），单 epoch 仍可在 3h 内完成；**dry-run 50 step 测吞吐确认** |
| `target_modules` 必须从 v1.0 显式列表扩到 all-linear | **HIGH** | v1.0 列表只命中 full_attention 8/32 层，漏 24 个 GatedDeltaNet 层；不修复直接跑等于只蒸馏 25% 参数 |
| q4_K_M 在 GatedDeltaNet hybrid 上不崩塌 | **LOW** | 9B + Q4_K_M 在 dense 模型上一般 OK，但 GatedDeltaNet 24/32 层在 q4 下的 fidelity 是 v3.0 新风险，无 v1.0 经验可参考；**必跑 5-prompt smoke + 全 OOD eval 对比 fp16** |
| 用 Qwen3.5-9B-Base 而非 Instruct | **HIGH** | -Base 无 chat_template / 无 thinking RL 偏置，避免与自定义标签竞争（v1.0 已验证此模式工作） |

---
*Stack research for: TSC-CYCLE v3.0 milestone — Qwen3.5-9B base swap on DGX Spark GB10*
*Researched: 2026-05-08*
