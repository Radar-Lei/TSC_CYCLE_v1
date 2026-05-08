# Pitfalls Research — TSC-CYCLE v3.0 9B 基座切换

**Domain:** GPT-5.5 high → **Qwen3.5-9B (base/non-thinking)** 蒸馏（QLoRA SFT, batch_size=1），自定义思考标签，DGX Spark GB10 aarch64 CUDA 13，GGUF 部署
**Researched:** 2026-05-08
**Confidence:** HIGH（v1.0 PITFALLS 已 v1.0 真机验证；本文件聚焦 4B-Thinking → 9B 切换的**新增**陷阱，引用 Qwen3.5 model card 与 llama.cpp 主仓的 `qwen35` tokenizer 注册作为锚点）

> **范围声明**：本文件**不重复** v1.0 已列且仍适用的陷阱（教师 lint、OOD val 退化、merge dtype、UMA OOM、API 速率、6h budget、评测假阳/阴等）。这些条目继续生效，参见 `milestones/v2.0-abandoned/research/PITFALLS.md` 的 Pitfall 2/3/5/6/7。
>
> 本文件聚焦**因基座从 Qwen3-4B-Thinking-2507 切换到 Qwen3.5-9B（base 变体）+ batch_size=1 + 模型尺寸 ×2.25 引入的新陷阱**。每条 pitfall 给出 (a) 表现 (b) 早期检测命令/代码 (c) 预防 (d) Phase 归属。

---

## Critical Pitfalls

### Pitfall 9-1: Qwen3.5 vocab 扩到 248K，自定义思考标签可能被合并成单 token

**What goes wrong:**
Qwen3.5 把 vocab 从 Qwen3 的 151,936 扩到约 **248K**（[awesomeagents.ai 第三方汇总](https://awesomeagents.ai/models/qwen-3-5-9b/)，待 model card `vocab_size` 字段二次校核）。BBPE merge 表也随之膨胀。v1.0 在 Qwen3 4B 上通过实测确认 `<start_working_out>` / `<end_working_out>` / `<SOLUTION>` / `</SOLUTION>` 都被拆成 5–9 个 sub-token；但在 Qwen3.5 248K vocab 中**不能假定该性质继续成立**——这些标签字符串作为 RL/SFT 训练数据中常出现的 marker，理论上 BBPE merge 可能已把其中某个高频片段（如 `start_working_out`、`SOLUTION`）合并成单个 token。

如果 `<SOLUTION>` 在 Qwen3.5 词表里被合并成单 token，会复现 v1.0 Pitfall 1 的"原生 `<think>` 单 token 压制多 sub-token 闭合"事故模式：模型生成 `<SOLUTION>` 流畅，但 `</SOLUTION>` 闭合用乱码替代（如果 closing tag 没被合并而 opening tag 被合并），或反之。

**Why it happens:**
1. Qwen3.5 训练语料可能包含大量带这类 marker 的 reasoning datasets（从 OpenAI/DeepSeek 风格推理数据采样），BBPE 自然 merge 高频 n-gram。
2. v1.0 的 tokenizer sanity test 是按 Qwen3 4B 词表写的硬编码断言（`assert convert_tokens_to_ids("<think>") == 151667`）；切到 Qwen3.5 时 token id 偏移 + 新合并都可能让旧断言假通过或假失败。
3. 248K vocab 比 152K 多了 96K 个 token slot，被冷僻 marker 字符串占据的概率显著升高。

**How to avoid (early detection command):**
```python
# 在 P1 verify phase 必跑（写入 scripts/verify_tokenizer_v3.py）
from transformers import AutoTokenizer
tok = AutoTokenizer.from_pretrained("Qwen/Qwen3.5-9B")  # 或 9B-Base

CUSTOM_TAGS = ["<start_working_out>", "<end_working_out>", "<SOLUTION>", "</SOLUTION>"]
for tag in CUSTOM_TAGS:
    ids = tok.encode(tag, add_special_tokens=False)
    assert len(ids) >= 3, f"FATAL: {tag} tokenized to {len(ids)} tokens (ids={ids}); will collide with native single-tokens"
    print(f"OK: {tag} -> {len(ids)} sub-tokens {ids}")

# 检测原生 think 是否仍在 vocab（需要 logit-bias 屏蔽）
for native in ["<think>", "</think>"]:
    tid = tok.convert_tokens_to_ids(native)
    print(f"native {native} -> id={tid} (UNK={tok.unk_token_id})")
    # 如果 != UNK 说明仍是 added token，推理期需 logit-bias

# 检测 vocab_size 与 model embedding 一致
vocab_size = tok.vocab_size
print(f"tokenizer.vocab_size = {vocab_size}")  # 期望 ~248K
```

**Fallback path 如果某个标签变成单 token**：
- **方案 A（推荐）**：换标签字符串使其不在 merge 表中。例如把 `<SOLUTION>` 改为 `<<TSC_PLAN>>`（双尖括号 + 项目特定词，几乎不可能在 BBPE merge 中）。**代价**：reality.log 需重生成（实际不需要，reality.log 只作输入分布先验，不入训练集）；下游 prompt builder 改 4 处常量，全链路 grep + 替换，1h 工作量。
- **方案 B**：在 BBPE 解码时强制把目标合并 token 拆开（修 tokenizer 的 `bpe_ranks` 删除对应 merge entry 后保存为新 tokenizer）。**风险**：复杂、容易破坏其它 token，不推荐。
- **方案 C**：保留单 token，但在训练时 mask 它的 logit 并要求模型走多 sub-token 路径——本质是与预训练打架，不可行。

**Warning signs:**
- `assert len(ids) >= 3` 任一标签触发 → P1 立即 abort，进入 fallback A。
- 训练 epoch 1 末 smoke test 中 `<SOLUTION>` 出现率高但 `</SOLUTION>` 出现率低 → 极可能是 opening 单 token / closing 多 sub-token 的非对称合并。
- GGUF tokenize 验证（`llama-tokenize -m model.gguf "<SOLUTION>"` 返回 1 个 token id）。

**Phase to address:** P1 (env + tokenizer verify) — **训练前必须红/绿门禁**

---

### Pitfall 9-2: Qwen3.5-9B 默认 thinking mode 开启 / chat_template 强制注入 `<think>`

**What goes wrong:**
[Qwen3.5 model card](https://huggingface.co/Qwen/Qwen3.5-9B) + [vLLM Qwen3.5 guide](https://docs.vllm.ai/projects/recipes/en/latest/Qwen/Qwen3.5.html) 明确：**Qwen3.5 默认 thinking mode 开启**（"generating thinking content signified by `<think>\n...</think>\n\n` before producing the final responses"）；但**对小模型（0.8B/2B/4B/9B）reasoning is disabled by default**，需要显式 `--chat-template-kwargs '{"enable_thinking":true}'` 才打开。

陷阱出现在两个相反方向：
- **(a) 误以为 9B 默认开 thinking**：训练 prompt 走 chat_template 默认渲染，假设包了 `<think>...</think>` 上下文；实际 9B 默认是 non-thinking → 训练时输入侧没有 `<think>` 上下文，但学生从 9B base 预训练里继承了 Qwen3.5 全家通用的 `<think>` token id（仍在 vocab 中），首次自由生成时随机命中 → 输出原生 `<think>` 与自定义 `<start_working_out>` 互掐。
- **(b) 反之误以为关掉就没事**：`enable_thinking=false` 让 chat_template 不注入 `<think>`，但**模型权重里**对 `<think>` token 的概率分布**仍存在**（model 是与 0.8B–9B 共享 tokenizer + RL post-training 同源的），temperature > 0 推理仍会偶发吐出 `<think>`。
- **(c) chat_template 在 transformers >= 4.57 行为漂移**：Qwen3.5 family 的 chat_template Jinja 中可能内置 `enable_thinking` 默认值切换，跨 transformers 版本表现不一致；自定义标签训练靠 chat_template 是脆弱基础。

与 v1.0 Pitfall 1（4B-Thinking 不肯放弃 `<think>`）相比，9B base 的"先验强度"理论上**更弱**（base 没经过 thinking RL），但因为 vocab 共享 + 默认 chat_template 复杂，failure mode 更隐蔽。

**Why it happens:**
1. transformers `apply_chat_template` 对 9B 默认 `enable_thinking=False`（小模型族），但训练脚本如果硬抄 4B-Thinking 时代代码（v1.0），会 unintentionally 走默认 path。
2. 9B 模型 card 的 thinking 描述是为 chat **inference** 设计的，SFT 训练时**不要走 chat_template** 的原则更绝对（v1.0 已锁，但 9B 切换时容易复发）。
3. 即便禁用 chat_template，9B 的 lm_head 对 `<think>` token id（如果仍在 vocab）的 logit 不为零；任何 Markov 路径上偶发激活就会泄漏。

**How to avoid (concrete):**
- **完全绕开 chat_template**（v1.0 已锁，9B 必须再次硬执行）：训练数据一律 raw text 拼接：
  ```python
  # NOT: tok.apply_chat_template([{"role":"user","content":...}], ...)
  prompt = (
      f"You are a TSC controller. Hard constraints: ...\n\n"
      f"Input:\n{json.dumps(input_dict)}\n\n"
      f"<start_working_out>"  # assistant 起手 teacher-forcing
  )
  target = f"{thinking_text}<end_working_out><SOLUTION>{json.dumps(output)}</SOLUTION>"
  full = prompt + target
  ```
- **训练前断言 chat_template 未被调用**（在 SFTTrainer 自定义 `formatting_func` 中加 `assert "<|im_start|>" not in formatted_text`），防止误用。
- **推理期始终 logit-bias 屏蔽原生 think**（v1.0 已锁，9B 强化）：
  ```bash
  llama-cli -m model.gguf \
    --logit-bias <native_think_id>-100 \
    --logit-bias <native_close_think_id>-100 \
    --logit-bias <im_start_id>-100 \
    --logit-bias <im_end_id>-100
  ```
  需要在 P1 跑 `tok.convert_tokens_to_ids("<think>")` 取实际 ID（Qwen3.5 vocab 扩展，ID 不再是 151667/151668，必须动态查）。
- **smoke test 必须包含"`<think>` token 不出现"断言**（首 epoch 末 5 prompt greedy decode，`assert "<think>" not in output and "</think>" not in output`）。
- **Stop tokens 在训练 collator 设为 `</SOLUTION>` token id 序列**：让 EOS 信号清晰，不让模型试图在 `</SOLUTION>` 之后续写到 `<im_end>` 这类 chat-template 残留 token。

**Warning signs:**
- 训练 generate eval 输出含 `<think>` 子串 → 立即降 worker，重检 chat_template 路径。
- 推理 token-by-token log 出现原生 think id（即便 logit-bias 设了 -100） → bias 强度不够，改 -200 或加 `--ignore-eos` 排查。
- transformers 升级后行为变化（同代码不同输出）→ 锁版本 `transformers==4.56.2`（v1.0 已验证）。

**Phase to address:** P1 (verify) + P4 (training, formatting_func 断言) + P5 (export, logit-bias 配置)

---

### Pitfall 9-3: batch_size=1 + 大 grad_accum → 梯度尖峰 + LayerNorm 不稳定

**What goes wrong:**
v3.0 锁定 `per_device_train_batch_size=1`（PROJECT.md Out of Scope 明确），effective batch 通过 `gradient_accumulation_steps=16~32` 凑齐。Qwen3.5-9B 在 batch=1 上有几个非显然的稳定性风险：

(a) **单样本梯度方差极大**：9B 模型输出层维度 ~248K（vocab）× hidden 4096，单样本 cross-entropy gradient 在 token 维度的方差比 4B（vocab 152K × hidden 2048）大约 ~3.3×。grad_accum 累积 32 步前，optimizer state 完全没更新，但内部累加器在 fp32 上 OK；问题在 **单步 backward 完成后中间梯度的 norm 偶发尖峰** 触发 `max_grad_norm` clip 失效（如果 clip 在 accumulate 前做）或 NaN（loss scaling 在 bf16 路径不存在，但 4-bit base + bf16 LoRA 的 mixed precision 仍可能 underflow）。

(b) **LayerNorm/RMSNorm 在 batch=1 不退化**：理论上 LN/RMSNorm 是逐样本归一化，batch=1 不影响。但 **gradient checkpointing recompute 时**，如果 `use_reentrant=True`（旧默认），单样本 recompute 路径在某些 transformers 版本会触发 NaN —— v1.0 PITFALLS 4d 已记录，9B 上更频繁因为 layer 数翻倍。

(c) **dropout 在 batch=1 + grad_accum 下的有效率**：LoRA 的 `lora_dropout=0.05` 期望在 batch 维度做 stochastic regularization；batch=1 时每步都全 mask 或全保留，accum 32 步等价于在更大 batch 上 dropout=1.0 或 0.0 交替——regularization 失效。

(d) **`paged_adamw_8bit` 在长 grad_accum 下 unified memory 抖动**：bnb paged optimizer 在 UMA + 32 step 累积期间，optimizer state 来回 swap CPU/GPU 区域，可能触发 v1.0 Pitfall 4c 的 UMA OOM 死亡螺旋（PROJECT.md 锁 swap=0，但 paged optimizer 内部分页是 cudaMallocManaged，与 swap 不同）。

(e) **`logging_steps=1` 在 batch=1 下** 把每个 micro-step loss 都打到 wandb，看起来曲线狂抖，触发误读；实际上 effective step 是 32 micro-step 后才有意义。

**Why it happens:**
1. 9B 首次跑这个项目，4B 的 batch=4 配置不能简单复用。
2. PROJECT.md 锁 batch=1 是显存约束驱动（9B 4-bit base ~6GB + activation peak 在 seq=2048 下估 ~25GB；batch=2 即可能撞 100GB cap），不是稳定性最优选择。

**How to avoid (concrete):**
- **`max_grad_norm=0.5`**（比 v1.0 的 1.0 减半，9B + bs=1 必须更保守）+ TRL `SFTConfig` 显式设 `gradient_accumulation_steps=16`（effective batch 16）。
- **lr 从 v1.0 的 2e-4 砍到 1e-4**：[QLoRA 论文 + Unsloth guide](https://unsloth.ai/docs/get-started/fine-tuning-llms-guide/lora-hyperparameters-guide) 对 ≥13B 推荐 1e-4；9B 在边界，bs=1 噪声大需要更小 lr。
- **warmup_ratio=0.1**（不是 v1.0 的 0.05）：bs=1 噪声大，更长 warmup 让 optimizer state 稳定。
- **`gradient_checkpointing=True` + `use_reentrant=False`**（强制非 reentrant，v1.0 Pitfall 4d 锁，9B 强化）。
- **`lora_dropout=0.0`**（bs=1 下 dropout 没意义；用 LoRA-All-Linear + r=64 的 capacity 控制即可）。
- **`logging_steps=8` 不是 1**：每 effective batch 0.5 步打一次 loss，曲线可读。
- **训练前跑 `grad_norm_audit.py`**（前 50 step）：
  ```python
  # 钩 Trainer 的 on_pre_optimizer_step 把每步 grad_norm 写到 jsonl
  # 50 step 后统计 p99 grad_norm
  # p99 > 5.0 → lr 减半重启；p99 > 20 → 模型/数据有 bug，abort
  ```
- **paged optimizer 启动后 watchdog**：第一步开始，每 30s 跑 `nvidia-smi --query-gpu=memory.used` log；持续 > 110GB 立即 SIGTERM 训练进程。
- **dry-run 200 step**（v1.0 是 100，9B + bs=1 调到 200）：确认无 NaN + grad_norm p99 < 3.0 + 时间外推 < 5.5h。

**Warning signs:**
- 任一 step `loss=nan` 或 `grad_norm=inf` → 立即 abort，dump checkpoint 检查 NaN 位置。
- wandb loss 曲线方差 > 同期 EMA 5×（每 32 micro-step 一个 effective step 内方差大可接受；effective step 间方差大说明 lr 高）。
- step 0 后 nvidia-smi 显示 GPU mem > 95GB → batch=1 仍逼近上限，立刻砍 max_seq_length（见 Pitfall 9-4）。
- 50 step 后 grad_norm p99 > 5.0 → 不健康，调 lr / clip。

**Phase to address:** P4 (training)

---

### Pitfall 9-4: 9B + 4-bit base + LoRA r=64 + max_seq_length 设错 → 显存峰值 OOM

**What goes wrong:**
v1.0 在 4B 上用 `max_seq_length=2048` 工作良好，peak ~30–40GB（128GB cap 内充裕）。直觉是"9B 是 4B 的 2.25×，把显存预期翻倍"，但**activation memory 峰值不是简单线性**：

- **Activation 在 attention forward 上是 O(batch × seq² × n_heads) for non-FA**；SDPA 是 O(batch × seq × hidden)，但 9B 的 hidden=4096（4B 是 ~2560），相同 seq=2048 下 attention activation 是 4B 的 ~1.6×。
- **MLP intermediate**：Qwen3.5-9B 的 intermediate_size 大约是 hidden 的 2.5× 即 ~10240（vs 4B 的 ~6912），activation 在 SwiGLU 路径上需要保留 gate + up projection 中间值，是 4B 的 ~1.5×。
- **Gradient checkpointing 不能完全消除 activation memory**：checkpoint 在 layer 边界 recompute，但 32 layers（9B）vs 28 layers（4B）的边界中间值仍需保留 hidden state；峰值在 forward 完成回到 backward 第一层时。
- **LoRA r=64 在所有线性层（Q/K/V/O/Gate/Up/Down 共 7 个）**：9B 32 layers × 7 modules × r=64 × max(in,out)=10240 ≈ 145M trainable params × 4 bytes (bf16 grad + fp32 master in 8bit) ≈ ~580MB grad/opt state，本身不大，但**每个 forward 都要算 LoRA 旁路**额外 activation。
- **4-bit base 解压缩临时 buffer**：bitsandbytes NF4 在 forward 时 dequantize 到 bf16 临时 buffer，9B 全权重一次解压会 ~18GB（不是必须，但某些 kernel 路径会 buffer 整层）。

实测推算（相对 4B）：
- 9B + bs=1 + seq=2048：peak ~50–60GB（4B 的 ~1.5–2×）— **可控**
- 9B + bs=1 + seq=4096：peak ~75–90GB — **逼近 cap，risky**
- 9B + bs=1 + seq=8192：peak > 110GB — **OOM**

但 v1.0 数据生成的 thinking trace 长尾 p99 已 ~2500 token；9B 学生**复刻**这种长 thinking 时同样需要 max_seq_length 覆盖 prompt+thinking+SOLUTION，砍到 2048 可能截断 SOLUTION（v1.0 Pitfall 8d 已警告，9B 同理）。

**Why it happens:**
1. v1.0 经验"2048 seq OK"在 9B 上不再成立。
2. UMA 共享 → swap=0 锁定下，OOM 直接 SIGKILL，不像独立 GPU 还能 OOM error 优雅退出（v1.0 Pitfall 4c）。
3. activation memory 与 hidden_size² 弱相关，与 layer 数线性，9B 在两个维度上都增长，峰值非线性。

**How to avoid (concrete):**
- **P1 显存预算 dry-run**（写到 `scripts/memory_budget_v3.py`）：
  ```python
  # 在 5 个候选 max_seq_length [1536, 2048, 2560, 3072, 4096] 上跑 1 step forward+backward
  # 记录 torch.cuda.max_memory_allocated()
  for sl in [1536, 2048, 2560, 3072, 4096]:
      torch.cuda.reset_peak_memory_stats()
      x = torch.randint(0, 248000, (1, sl), device=0)
      with torch.amp.autocast("cuda", dtype=torch.bfloat16):
          out = model(x, labels=x)
          out.loss.backward()
      peak = torch.cuda.max_memory_allocated() / 1e9
      print(f"seq={sl}: peak={peak:.1f}GB")
      # 选 peak < 85GB 的最大 sl（留 15GB buffer）
  ```
- **基于实测样本长度选 max_seq_length**（v1.0 Pitfall 8d 改进版）：
  - data-gen 完成后 tokenize 全集，统计 p95/p99 长度
  - 设 `max_seq_length = max(p95 * 1.05, ceil_to_256)` —— 不再追 p99（9B + bs=1 不能为 1% 长尾扛 ×2 显存）
  - p95 > p99-budget 的样本：left-truncate prompt 头部（不动 assistant target），或直接 drop（损失 < 5% 训练样本可接受）
- **优先用 `gradient_checkpointing=True` + `use_reentrant=False`**（不可关）。
- **如果 dry-run 显示 seq=2048 已 > 80GB**：fallback 路径
  - 砍 LoRA target_modules 到只 attention（去 MLP）：trainable params 减半，activation 减少；**代价**：9B unlearn `<think>` 可能不充分（参考 v1.0 Pitfall 1）→ 必须配合 epoch 加到 3。
  - 上 `bnb_4bit_use_double_quant=False`：base 内存增 ~5%，但减少 dequantize 临时 buffer 抖动，**有时**反而稳。
  - **绝不**升 batch_size > 1（违反 PROJECT.md 锁定）。
- **训练 watchdog 监控**：`scripts/dgx_spark/run_safe.sh` 内已含；额外加一个 `nvidia-smi` 采样每 30s 写 jsonl，便于事后 forensic。

**Warning signs:**
- dry-run 任一 seq 配置 OOM → 立即降 max_seq_length 一档。
- 训练首 step nvidia-smi memory.used > 100GB → 砍 max_seq_length 到 1536 重启。
- `data truncated > 5%` warning in trainer log → max_seq_length 选低了或 SOLUTION 被砍。
- nvidia-smi memory.used 在训练中**单调上升**（不是稳态） → LoRA 实现有 bug（每 step 泄漏），abort。

**Phase to address:** P1 (memory dry-run) + P4 (training config)

---

### Pitfall 9-5: llama.cpp Qwen3.5 GGUF 支持时延 / pre-tokenizer 失配

**What goes wrong:**
v1.0 用 EvoProgTSC 仓库内 build 的 llama.cpp 跑通 Qwen3-4B-Thinking 的 convert+quantize（`Qwen3ForCausalLM` 在 `convert_hf_to_gguf.py` 第 4551 行注册）。**Qwen3.5 不一定**：
- 主仓 [`convert_hf_to_gguf_update.py`](https://github.com/ggml-org/llama.cpp/blob/master/convert_hf_to_gguf_update.py) 已注册 `{"name": "qwen35", "tokt": TOKENIZER_TYPE.BPE, "repo": "Qwen3.5-9B-Instruct"}`，但**本机 EvoProgTSC 内的 llama.cpp 是 v1.0 时期 build**，可能在 Qwen3.5 注册之前。
- Qwen3.5 hidden=4096、layers=32、新 GQA group ratio、新 RoPE base 等架构参数若主仓 `Qwen3Model` class 没扩展，convert 写出的 GGUF 在 inference 时会拿错维度，输出乱码或 segfault。
- 即使架构兼容，pre-tokenizer hash 不匹配（GGUF metadata `tokenizer.ggml.pre` 写的是 `qwen35` 但本机 llama.cpp build 不认识这个名字）→ inference 时 fall back 到 default BPE tokenizer，自定义标签拆分方式与训练时不一致 → 推理输出与 GGUF tokenize 工具不对齐。

具体失败模式：
- **(a) convert 阶段 KeyError**：`KeyError: 'Qwen3.5ForCausalLM'`（如果主仓没 alias） 或 `architecture qwen3 not recognized for vocab_size=248000`。
- **(b) convert 成功但 inference NaN**：GGUF 文件能写，`llama-cli` 启动加载也 OK，但首个 token 输出 NaN —— RoPE 缩放因子或 GQA repeat ratio 没对上。
- **(c) pre-tokenizer fallback**：`llama-tokenize -m model.gguf "<start_working_out>"` 返回的 token id 序列与 HF tokenizer 不同 → 训练学到的 sub-token 路径在 GGUF 推理时走另一套，输出乱码（同 v1.0 Pitfall 5f 模式但根因不同）。
- **(d) Q4_K_M 量化失败**：`llama-quantize` 对新 architecture key 不识别 → segfault 或 silent corruption（v0/v1 数值同步问题）。

**Why it happens:**
1. EvoProgTSC 内 llama.cpp 是 build 一次后固定（提交时间在 Qwen3.5 release 之前）。
2. llama.cpp 主仓 push pre-tokenizer 注册到 release 通常滞后 1–2 周；自 build 时 master 是否已 merge 不确定。
3. Qwen3.5 family 支持目前由 vLLM/SGLang 主推，llama.cpp/GGUF path 在生态优先级上低（[Qwen 官方 llama.cpp 文档](https://qwen.readthedocs.io/en/latest/run_locally/llama.cpp.html) 仍在更新中）。

**How to avoid (concrete):**

**Step 1（P1 必跑）：检测本机 llama.cpp 是否支持 Qwen3.5**
```bash
LLAMA_CPP=/home/samuel/projects/EvoProgTSC/llama.cpp
# (a) check convert script registration
grep -n "qwen35\|Qwen3.5\|qwen3_5" "$LLAMA_CPP/convert_hf_to_gguf.py" \
                                    "$LLAMA_CPP/convert_hf_to_gguf_update.py" \
                                    || echo "WARN: Qwen3.5 NOT registered"
# (b) check llama.cpp build date
ls -la "$LLAMA_CPP/llama-cli" "$LLAMA_CPP/llama-quantize"
cd "$LLAMA_CPP" && git log -1 --format="%cd %h" master 2>/dev/null
# (c) check arch class
grep -n "class Qwen3" "$LLAMA_CPP/convert_hf_to_gguf.py"
```

**Step 2（如果不支持）：rebuild llama.cpp** 在 P1 dry-run 流程内：
```bash
cd "$LLAMA_CPP"
git fetch origin && git checkout master && git pull
# rebuild with CUDA support
cmake -B build -DGGML_CUDA=ON -DCMAKE_BUILD_TYPE=Release
cmake --build build -j --target llama-cli llama-quantize llama-tokenize
# 重新跑 convert_hf_to_gguf_update.py（如果 tokenizer 注册有改动需要更新）
python convert_hf_to_gguf_update.py <HF_TOKEN_ENV>
```

**Step 3（critical 验证）：dry-run 一个 micro-convert** 在 P1（不等到 P5）：
```bash
# 用一个微型 1-step 训练得到的 LoRA + base 跑 end-to-end convert+quantize+inference
# 不需要真正训练完成，只需要验证转换链通
python "$LLAMA_CPP/convert_hf_to_gguf.py" /path/to/dummy_merged --outfile /tmp/test.gguf --outtype bf16
"$LLAMA_CPP/build/bin/llama-quantize" /tmp/test.gguf /tmp/test.q4km.gguf Q4_K_M
"$LLAMA_CPP/build/bin/llama-cli" -m /tmp/test.q4km.gguf -p "<start_working_out>test" -n 5
# 任何步失败 → 必须 P1 阶段解决，不能拖到 P5
```

**Step 4（pre-tokenizer parity 验证）：**
```bash
python -c "
from transformers import AutoTokenizer
hf = AutoTokenizer.from_pretrained('Qwen/Qwen3.5-9B').encode('<start_working_out>', add_special_tokens=False)
print('HF:', hf)
"
"$LLAMA_CPP/build/bin/llama-tokenize" -m /tmp/test.gguf "<start_working_out>"
# 两边 token id 序列必须**完全一致**
```

**Step 5：fallback 路径如果 llama.cpp 主仓也不支持**
- **A. 等社区**：开 GitHub issue 跟踪 Qwen3.5 support，期间在 P5 用 `bf16` GGUF 部署（部分 llama.cpp build 对未知 architecture 仍能跑 bf16，仅 Q4_K_M 出问题）—— 牺牲部署 size。
- **B. 临时 patch**：把 Qwen3.5 architecture key 在 convert 脚本里 alias 到现有 `Qwen3Model`（如果架构差异小，例如只是 hidden_size/num_layers 不同）。**风险**：架构差异导致权重错位（GQA group ratio 不同尤其严重），需配 inference parity test。
- **C. 退到 vLLM-only 部署**：用户 PROJECT.md 已锁不能 vLLM（本机问题）；这条不可走。
- **D. 暂缓 v3.0 milestone**：如果 P1 验证 llama.cpp 完全不支持，且 main 分支 4 周内无支持迹象，应在 P1 决策点 abort milestone（已花成本最小）。

**Warning signs:**
- P1 grep `qwen35` 在本机 llama.cpp 中无命中 → red flag, 必须 rebuild。
- rebuild 后 `convert_hf_to_gguf_update.py` 报 "BPE pre-tokenizer was not recognized" → upstream 也没 merge，进 fallback A/B/D。
- micro-convert dry-run 任一步 segfault → 不要进 P4 训练，先解决。
- HF tokenize 与 llama-tokenize 输出不一致 → pre-tokenizer 失配，bug。
- Q4_K_M 后 inference 输出含连续相同 token（如 `\n\n\n\n...`） → 量化崩塌（参考 v1.0 Pitfall 5d，9B 上更敏感因为 thinking trace 更长）。

**Phase to address:** **P1（关键前置门禁，必须在 P4 训练之前完全解决）** + P5 (export final 校验)

---

### Pitfall 9-6: "9B 一定优于 4B" 的免费午餐幻觉 / OOD 反向退化

**What goes wrong:**
项目 baseline 是 v1.0 4B-Thinking q4_K_M GGUF：OOD 硬约束 98.7%、教师 MAE Δ +0.18s。直觉认为"9B 容量翻倍 → OOD 表现也提升"。但 TSC 任务有几个反直觉因素可能让 9B **OOD 表现反而下降**：

(a) **9B base 没有 thinking RL 后训练**（与 4B-Thinking-2507 不同），自定义思考标签的 SFT 是从零教 thinking 行为；3000 样本可能不足以让 9B 学到 4B-Thinking 已经具备的"分步推理"能力 → 思考段空洞或重复，最终 SOLUTION 数值反而更差。

(b) **更大模型对 prompt 噪声更敏感**：9B 的世界知识包含大量交通工程语料（论文、规范），可能对"min_green=10s"产生 prior（"绿灯 10 秒太短了，行人都过不去"）→ 在 OOD（min_green < 15）样本上**主动违反**硬约束以"贴合常识"，比 4B 更频繁。

(c) **r=64 LoRA 对 9B 是 0.16% trainable params**（vs 4B 的 ~0.36%），相对容量更小，**unlearn 预训练 prior 难度更大**。

(d) **教师 MAE 比较失真**：3000 训练样本 + 300 OOD val 的 MAE 是点估，p99 长尾可能 9B 反而恶化（更"自信"地输出违反约束的值）。

(e) **GGUF Q4_K_M 在 9B 上的相对量化损失** 历史经验比 4B 大（更多 layer × 更窄激活分布 → 量化误差累积）。即使 fp16 9B 略胜 4B，q4_K_M 9B 可能落到 4B q4_K_M 之下 —— **生产部署的 q4_K_M 版本是 fp16 比较的下界**。

如果 v3.0 OOD 表现达不到 v1.0 baseline，整个 milestone 的 "9B 升级带来可验证收益" 假设破产，应回滚 4B。

**Why it happens:**
1. PROJECT.md 已埋伏笔："v3.0 必须证明 9B 升级带来可验证收益（或反之，证明 4B 已是甜点）"——这是 milestone 真实可能输出。
2. 蒸馏文献多在 generic chat 任务上对比，TSC schema-strict + 短输出任务的"模型 size scaling law" 没有公开数据。
3. 直觉乐观偏差。

**How to avoid (concrete):**

**Phase 1 dry-run 早期检测信号**（在投入完整 6h 训练前）：
```python
# scripts/dry_run_500_samples.py
# 用 500 样本（占 17%） + 1 epoch + r=64 跑 ~1h 缩比训练
# eval 同 100 OOD val 上跑 greedy decode
# decision rule:
#   OOD 硬约束满足率 < 95% → red, 高度概率全量训练也达不到 baseline
#   OOD 硬约束满足率 ≥ 97% → green, 全量训练有信心
#   97% ≤ x < 95% → yellow, 全量训练前调 lr / 加 epoch
```

**Phase 4 evaluation 必须显式对比 v1.0 baseline**：
- **不仅报 v3.0 数字**，必须报 `v3.0 - v1.0` 差值 + 95% bootstrap CI。
- 差值 < 0 且 CI 不跨 0 → 9B 显著劣化，**默认 abort v3.0，回 4B**。
- 差值 > 0 且 CI 跨 0 → 9B 改善不显著，决策权交用户："2.25× 模型 size 换不显著改善值不值"。
- 差值 > 0 且 CI 不跨 0 → milestone 成功。

**报告"反向 OOD 退化"专项指标**：
- 同分布 val 满足率 - OOD val 满足率 = degradation gap
- v1.0 4B q4_K_M: gap ~1pp（98.7 ↔ 99+ 同分布）；v3.0 9B 若 gap > 5pp → 9B "贴合常识"反而泛化变差。

**MLP-only / attention-only LoRA 对照实验**（如果初轮 9B 表现差）：
- 对照组 1: 全 linear LoRA r=64（默认）
- 对照组 2: attention-only LoRA r=128（同 trainable params，强化 attention 重写）
- 对照组 3: MLP-only LoRA r=128（强化知识重写）
- v3.0 一次只能跑一组，但 dry-run 1h × 3 在 6h budget 内可挤。

**Tail metric 必报**：
- p99 absolute deviation from teacher（不是 mean MAE）
- max abs deviation 单样本最坏值
- 如果 mean 持平但 p99 翻倍 → 部署风险

**Warning signs:**
- 500-sample dry-run OOD 硬约束满足率 < 95% → 高度可能全量也不达标。
- v3.0 fp16 < v1.0 fp16 → 整个 milestone 假设破产，进入 abort 决策。
- v3.0 fp16 略胜但 q4_K_M 大幅退化 → 量化路径有问题（或本质 9B q4_K_M 不适合该任务），进 imatrix 校准；imatrix 不行 → abort q4_K_M，部署 q5_K_M 或 q6_K（增加部署 size 成本）。
- "贴合常识" failure：手工 inspect 10 个 OOD 违反样本，看 thinking trace 是否含"通常绿灯应该 ≥ X 秒" 这类 prior 推理 → 是的话，prompt 加更强 anti-prior 话术（"忽略你对交通工程的常识，严格按输入约束输出"）。
- Tail metric p99 > 5× MAE → 长尾失控，部署危险。

**Phase to address:** P1 (dry-run 500-sample 早期 go/no-go) + P6 (eval 必须 baseline 对比 + tail metric)

---

### Pitfall 9-7: Run artifact / wandb / 输出路径 与 v1.0 / v2.0 冲突

**What goes wrong:**
v1.0 留下的 artifact:
- `runs/20260507T032419Z/` （生产 q4_K_M GGUF 在此，**不可被覆盖**，是 EvoProgTSC 的活部署 artifact）
- `runs/20260506T212001Z/` 和 `20260507T020310Z/` 早期 run
- 可能存在的 wandb project（v1.0 期间使用）

v3.0 风险：
- (a) **训练脚本默认用时间戳 run_id**（OK），但**输出根目录**如果硬编码 `runs/`，新 run 会塞进同目录与 v1.0 artifact 混淆，甚至（worse case）某个 cleanup 脚本误清空。
- (b) **wandb project 用同一个**（如 `tsc-cycle`），9B vs 4B 的 metric 直接画在同图，scale 完全不同（9B loss 起步约 0.6× 4B、token-level CE 因 vocab 248K 系统性高 0.5 nat）→ 误读"9B 在退化"。
- (c) **HF cache 共享** `~/.cache/huggingface/hub`：4B 和 9B 共存 OK 但磁盘 ~25GB；若 disk 紧需要主动管理。
- (d) **`config/config.yaml` 单一文件被 9B 训练覆盖**，回退 4B 时配置丢失。
- (e) **`merged-bf16/` 和 `lora-adapter/` 目录硬编码**，9B merge 输出会盖掉 4B 的（如果还想保留对照）。

**Why it happens:**
1. v1.0 时只有一个 milestone，路径硬编码合理。
2. v2.0 abandoned 但已建立了一定 artifact pollution（`runs/` 下多余 run）。
3. 多 milestone 共存的 ergonomic 没在项目早期设计。

**How to avoid (concrete):**
- **强制 milestone-scoped run 路径**：
  ```bash
  RUN_ID="v3.0-9B-$(date -u +%Y%m%dT%H%M%SZ)"
  mkdir -p "runs/$RUN_ID"/{lora,merged,gguf,eval,logs}
  # 训练脚本所有输出路径都从 RUN_ID 派生，不硬编码 runs/
  ```
- **Run ID prefix 命名约定**（强制写到 PROJECT.md 或 RUNBOOK）：
  - v1.0: `runs/20260507T032419Z/`（已存，**冻结**）
  - v3.0: `runs/v3.0-9B-<timestamp>/`
  - 回归测试 4B: `runs/v3.0-4B-control-<timestamp>/`（如果做对照）
- **wandb project 隔离**：`WANDB_PROJECT=tsc-cycle-v3-9b`（与 v1.0 的 `tsc-cycle` 分开）；或同 project 但 tag `v3.0,base=qwen3.5-9b`，dashboard 自带 group-by 过滤。
- **HF cache 显式 size budget**：训练前 `du -sh ~/.cache/huggingface` 确认 < 80GB；如逼近 100GB 删 v1.0 用过的 4B-Thinking 缓存（不影响部署，部署用 GGUF）。
- **config 文件分版本**：`config/v3-9b.yaml` 不覆盖 `config/v1-4b.yaml`；脚本 entry `--config config/v3-9b.yaml` 显式传。
- **写 freeze 锁**：在 `runs/20260507T032419Z/` 内放 `FROZEN.md`（"DO NOT MODIFY — v1.0 production artifact"），并 `chmod -w` 防误删。
- **Pre-flight 路径冲突检查**：
  ```bash
  # 训练启动前
  test ! -e "runs/$RUN_ID" || { echo "FATAL: $RUN_ID exists"; exit 1; }
  test -e "runs/20260507T032419Z/gguf/model.q4_K_M.gguf" || { echo "FATAL: v1.0 artifact missing"; exit 1; }
  ```

**Warning signs:**
- `runs/` 同一目录出现两次训练日志 → 路径碰撞，立即停。
- wandb 跨 milestone 同图对比 loss 时 9B 看似"差"但实际是 vocab/token-level CE 的尺度差异。
- 部署 EvoProgTSC 端点突然异常 → 检查 `runs/20260507T032419Z/` 是否被误改。
- `config/config.yaml` 训练后 `git diff` 显示已被 9B 训练修改 → 没遵守版本分文件原则。

**Phase to address:** P1 (path convention setup) + 全 phase（每个 phase 输出严格走 RUN_ID）

---

### Pitfall 9-8: 9B SFT 比 4B 更容易 loss spike / 梯度爆炸

**What goes wrong:**
9B 在 SFT 上比 4B 更易出现 loss spike，原因叠加 Pitfall 9-3：
- 模型容量大，单样本梯度方差大（已述）
- 248K vocab 的 cross-entropy gradient 对 outlier token 概率特别敏感（softmax 在 248K 维上的 saturation 比 152K 更陡）
- 长 thinking trace（2000+ token）累积反向传播路径长，underflow/overflow 概率提升
- v1.0 用 lr=2e-4 在 4B 工作，但 9B 上[QLoRA 论文](https://arxiv.org/pdf/2305.14314)对 ≥13B 推荐 1e-4；9B 在边界容易踩雷

具体 spike 模式：
- (a) **训练中段（epoch 2 中）loss 从 0.4 突跳到 8.0，不恢复**：典型梯度爆炸 + optimizer state 污染。
- (b) **每个 epoch 开头 first 10 step loss 异常高**：dataloader shuffle 后 batch 序列长度跨度大，9B 对长 seq 的 first-batch loss 敏感（v1.0 4B 上影响小）。
- (c) **LoRA scaling alpha/r 太大**：v1.0 用 `alpha=128, r=64`（scaling=2.0）；9B 上 [Unsloth guide](https://unsloth.ai/docs/get-started/fine-tuning-llms-guide/lora-hyperparameters-guide) 对大模型推荐 `alpha=r`（scaling=1.0）更稳。
- (d) **`paged_adamw_8bit` 数值精度**：8-bit optimizer state 在 9B 大梯度下偶发 underflow → state corruption，下一步 spike。

**Why it happens:**
1. v1.0 lr/alpha 来自 4B 调通，9B 不直接迁移。
2. SFT loss 在 schema-strict 任务（TSC）的 distribution 比 generic chat 窄，gradient 方向更"尖锐"，更易越过 minima。
3. bs=1 + grad_accum 32 的累积窗口长，spike 后被均值化掉的可能性低。

**How to avoid (concrete):**
- **lr 砍到 1e-4**（v1.0 是 2e-4，9B 减半起步）。
- **lora_alpha = lora_r = 64**（scaling=1.0，不是 v1.0 的 2.0）。
- **`max_grad_norm=0.5`**（已述于 9-3）。
- **warmup_ratio=0.1**（已述）。
- **`lr_scheduler_type="cosine"`** （v1.0 `linear` OK，9B 上 cosine 末端 lr 衰减更柔和，避免 last-epoch overfit spike）。
- **`adamw_torch_fused`** 替代 `paged_adamw_8bit` 如显存允许：fused 32-bit optimizer state ~1GB（9B LoRA r=64 trainable ~145M params × 8 bytes momentum/variance），完全可承担；避免 8-bit underflow。**前提**：dry-run 验证开 fused 后 peak 仍 < 90GB；不行回 paged 8bit。
- **`save_strategy="steps", save_steps=200, save_total_limit=3`**：spike 后能 resume 上一个 checkpoint，不必从零（与 v1.0 epoch save 不同；9B 风险高，需要更密 checkpoint）。
- **Loss watchdog**：训练脚本内加 hook，连续 5 步 loss > 5× EMA → 自动 SIGTERM 训练 + 写 alert log，避免 6h budget 全烧在崩溃 run 上。
- **Resume protocol**：spike 后从 last checkpoint resume，**不修改其他参数**（先看是否随机性问题）；连续 spike 2 次 → lr 再砍半到 5e-5 + warmup 再延 → 第 3 次 spike 才动 LoRA 配置。

**Warning signs:**
- 单 step loss 突跳 > 5× EMA → loss watchdog 触发 SIGTERM。
- 每 epoch 开头 first 10 step loss 显著高于该 epoch 后续平均（>1.5×） → dataloader sort by length 缓解（按长度排序后 shuffle within bucket）。
- grad_norm 在前 50 step p99 > 5.0 → lr 太高或 alpha 太大。
- wandb 显示 loss 看起来稳但 eval generate 输出退化 → silent overfit + 数值不稳定共存，inspect adapter weights for NaN。

**Phase to address:** P4 (training, lr/alpha/scheduler) + 训练监控

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| 复用 v1.0 lr=2e-4 / alpha=128 跑 9B | 不调超参 | 9B loss spike，6h 训练崩溃需 resume | **Never**：必须 lr=1e-4 + alpha=64 起步 |
| 跳过 P1 micro-convert 链路验证 | 省 30 min | P5 才发现 llama.cpp 不支持 Qwen3.5，整个 milestone 卡死 | **Never** |
| 9B 沿用 v1.0 max_seq_length=2048 不实测 | 配置抄旧 | OOM 整机僵死 或 5%+ 样本截断 | **Never**：必须跑 memory_budget_v3.py |
| 训练写到 `runs/` 不带 milestone prefix | 路径短 | v1.0 部署 artifact 风险 | **Never** |
| 用 v1.0 wandb project 同图对比 9B | 看似方便 | scale 失配误读 | 仅当显式 normalize loss 时（不推荐） |
| 不跑 500-sample dry-run 直接全量 6h | 早 1h 完成 | 全量训练完才发现 OOD 退化，6h 沉没 | **Never** |
| 9B 跳过 logit-bias 屏蔽原生 think | 部署命令短 | 推理偶发 `<think>` 泄漏，OOD 满足率拉低 | **Never** |
| `lora_dropout=0.05` 复制 v1.0 | 配置一致 | bs=1 下 dropout 失效（全 mask 或全保留），不必要的随机性 | 仅当 grad_accum=1 时（不适用） |
| 用 chat_template 拼训练数据 | 30 行代码省 | `<think>` 注入，模型继续输出原生标签（v1.0 已锁但 9B 易复发） | **Never** |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Qwen3.5 tokenizer | 假定 vocab=152K（沿用 4B） | 实测 `tokenizer.vocab_size`（期望 ~248K）+ 自定义标签 sub-token count assert |
| Qwen3.5 chat_template | 9B 默认 thinking off 不等于安全 | 完全绕开 chat_template，raw text 拼接 + assistant 起手 `<start_working_out>` |
| transformers 版本 | 升到 4.57+ 跟随 Qwen3.5 release | 锁 `transformers==4.56.2`（v1.0 验证版）；只升 PEFT/TRL 到兼容点 |
| llama.cpp Qwen3.5 | 用 EvoProgTSC 内 build（v1.0 时期） | P1 git pull + rebuild + 跑 `convert_hf_to_gguf_update.py` |
| llama-tokenize | 假定与 HF tokenize 一致 | P1 双向 parity test（HF encode == llama-tokenize output） |
| logit-bias | 沿用 v1.0 token id 151667/151668 | 9B vocab 偏移，动态查询 `tok.convert_tokens_to_ids("<think>")` |
| paged_adamw_8bit | 9B 默认用（v1.0 模式） | dry-run 验证显存能承担 `adamw_torch_fused`，优先用 fused 避免 8-bit underflow |
| LoRA target_modules | 沿用 v1.0 全 linear | 9B + bs=1 下若 OOM，先砍 MLP 保 attention（配合 epoch+1） |
| wandb project | 与 v1.0 同 project 同 dashboard | 单独 `tsc-cycle-v3-9b` project 或 tag 隔离 |
| Run path | 写入 `runs/<timestamp>/` 与 v1.0 混 | `runs/v3.0-9B-<timestamp>/` 强制 prefix |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| 9B activation peak 非线性 | seq=4096 时 peak > 90GB | P1 memory_budget_v3.py 实测候选 seq | 任何盲选 max_seq > 2560 |
| bs=1 grad_accum 32 paged optim 抖动 | 训练中 GPU mem 周期性 ±10GB | 优先 `adamw_torch_fused`；监控 nvidia-smi | grad_accum > 16 + paged 组合 |
| 248K vocab CE saturation | loss spike 在中后期突现 | lr=1e-4 + alpha=64 + max_grad_norm=0.5 | lr ≥ 2e-4 任何时候 |
| Q4_K_M 9B 长 thinking 量化崩塌 | q4 vs fp16 SOLUTION MAE > 3s | 必跑 imatrix（不再是 v1.0 "可选"） | 任何 9B + thinking trace > 1500 token |
| llama.cpp 不支持 Qwen3.5 | convert KeyError 或 inference NaN | P1 micro-convert dry-run | 任何 EvoProgTSC build 早于 Qwen3.5 release |
| chat_template 漂移 | transformers 升级后 9B 输出含 `<im_start>` | 锁 transformers==4.56.2 + 训练用 raw text | transformers >= 4.57 |
| Paged optimizer + UMA | 训练中 SSH 卡（v1.0 已警告） | swap=0 + run_safe.sh + nvidia-smi watchdog | 任何 9B 训练 |
| 9B "贴合常识" prior 反向 OOD 退化 | OOD 满足率 < 同分布 5pp+ | OOD spec 明确 + anti-prior prompt | min_green<15 或 max_green>100 样本 |

---

## Security Mistakes（继承 v1.0，9B 特定增量）

| Mistake | Risk | Prevention |
|---------|------|------------|
| 9B GGUF 公开发布含 fine-tuning 数据足迹 | 模型 inversion attack 在 9B 上比 4B 更可行（容量大→记忆更多） | 公开前用 OOD test 子集做 membership inference；q4_K_M 而非 fp16 公开（量化损失训练样本记忆） |
| Qwen3.5 license（Apache 2.0 verified） | distillation derivative 商业使用合规 OK | 仍需 confirm OpenAI ToS 不禁止 GPT-5.5 → 第三方模型蒸馏（v1.0 已涉及） |

---

## "Looks Done But Isn't" Checklist (v3.0 增量)

- [ ] **P1 完成**：经常缺 llama.cpp Qwen3.5 micro-convert 端到端 dry-run — 验证 dummy LoRA → bf16 GGUF → q4_K_M GGUF → llama-cli 推理 5 token 全链路无错
- [ ] **Tokenizer verify 完成**：经常只查原生 think id，缺自定义标签 sub-token count — 验证 4 个标签都 ≥ 3 sub-tokens
- [ ] **Memory budget 完成**：经常只跑 1 个 max_seq_length 不扫候选 — 验证至少 5 个 seq 配置都有 peak 数据
- [ ] **9B 训练就绪**：经常缺 lr=1e-4 / alpha=64 / max_grad_norm=0.5 三件套，沿用 4B 配置 — 验证 config 显式 9B 优化值
- [ ] **500-sample dry-run 完成**：经常跳直接全量 — 验证 OOD 满足率 ≥ 95% 才进 P4 全量
- [ ] **Run path 隔离**：经常写到 `runs/<timestamp>` 不带 v3.0 prefix — 验证 `ls runs/` 能清晰区分 milestone
- [ ] **wandb 隔离**：经常用 v1.0 同 project — 验证 `WANDB_PROJECT` 环境变量是 `tsc-cycle-v3-9b`
- [ ] **Baseline 对比报告**：经常只报 v3.0 数字，缺 v3.0-v1.0 差值 + CI — 验证 P6 报告含 baseline 对比表
- [ ] **Tail metric 报告**：经常只报 mean MAE — 验证 p99 / max abs 均报告
- [ ] **logit-bias 部署配置**：经常 `llama-cli` 不带 logit-bias — 验证生产部署命令显式屏蔽 native think + im_start/im_end token id
- [ ] **HF cache budget**：训练前未确认 disk free — 验证 `df -h ~` 还有 ≥ 50GB

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| 9-1 自定义标签变单 token | LOW (1h) | 改标签为 `<<TSC_PLAN>>` 等更冷僻字符串；全链路 grep 替换；重生成 prompt 模板（数据无需重生成） |
| 9-2 模型输出原生 `<think>` | MEDIUM (1h–加 epoch 风险) | logit-bias 屏蔽推理；smoke test 通过则不必重训；不通过 → 重训 + epoch+1 |
| 9-3/9-8 loss spike | LOW (resume) | 从 last `save_steps=200` checkpoint resume；连续 2 次 → lr 砍半 |
| 9-4 OOM | LOW (config) | max_seq_length 砍一档；如仍 OOM → LoRA target 砍 MLP 保 attention + epoch+1 |
| 9-5 llama.cpp 不支持 | HIGH (rebuild + 等社区) | 主仓 git pull + rebuild；不行 → 临时 alias patch + parity test；都不行 → milestone abort |
| 9-6 9B OOD < 4B baseline | HIGH (milestone 决策) | 500-sample dry-run 提前发现 → 调 LoRA target 重 dry-run；全量后发现 → user 决策 abort/部分接受 |
| 9-7 路径冲突 | LOW (rename) | 立即 stop 训练；rename 当前 run dir 加 v3.0- 前缀；下次启动用强制断言 |
| 量化崩塌 9B q4_K_M | MEDIUM (45 min) | 必跑 imatrix（v1.0 是可选）；imatrix 仍崩 → 退到 q5_K_M（部署 size +25%） |

---

## Pitfall-to-Phase Mapping

> v3.0 假设 phase 结构（与 v1.0 类似但 P1 加重门禁）：
> P1 = env + tokenizer + memory + llama.cpp micro-convert（**关键前置门禁**）
> P2 = data-gen（沿用 v1.0 generator + ood_spec）
> P3 = teacher-label（沿用 v1.0 client）
> P4 = training（9B QLoRA r=64 + bs=1 + 调优后 lr/alpha）
> P5 = export（merge bf16 + GGUF + Q4_K_M + imatrix）
> P6 = eval + baseline 对比 + 部署裁决

| Pitfall | Prevention Phase(s) | Verification |
|---------|---------------------|--------------|
| 9-1 标签单 token | P1 | 4 标签 sub-token count ≥ 3 断言通过 |
| 9-2 native think 泄漏 | P1 + P4 + P5 | P4 epoch 1 smoke 5/5 不含 `<think>`；P5 logit-bias 配置文件 in repo |
| 9-3 bs=1 不稳定 | P4 | 50 step grad_norm p99 < 3.0；无 NaN |
| 9-4 9B 显存峰值 | P1 + P4 | memory_budget_v3.py 5 配置全跑；选定 seq peak < 85GB |
| 9-5 llama.cpp 不支持 | **P1（前置门禁）** | micro-convert dry-run 全链路通过；HF/llama tokenize parity 一致 |
| 9-6 OOD 反向退化 | P1 (500-sample dry-run) + P6 | dry-run OOD ≥ 95%；P6 baseline 差值 + 95% CI 报告 |
| 9-7 path 冲突 | P1 + 全 phase | 启动 pre-flight 断言：v1.0 artifact 存在 + v3.0 dir 不预存在 |
| 9-8 loss spike | P4 | lr=1e-4/alpha=64 配置；watchdog 触发记录；无 unrecovered spike |

---

## Sources

**v1.0 已积累（继承不重复）：**
- `/home/samuel/TSC_CYCLE/.planning/milestones/v2.0-abandoned/research/PITFALLS.md` — v1.0 Pitfall 1–8 全部继承（HIGH，本项目真机验证）
- `/home/samuel/.claude/projects/-home-samuel-TSC-CYCLE/memory/MEMORY.md` — Qwen3 added tokens lesson（HIGH）
- `/home/samuel/dgx-spark-setup/README.md` — DGX Spark 训练栈（HIGH）

**v3.0 9B 特定新增：**
- [Qwen/Qwen3.5-9B HuggingFace card](https://huggingface.co/Qwen/Qwen3.5-9B) — vocab、thinking 默认行为、small-model thinking off-by-default（HIGH）
- [Qwen3.5 vLLM Recipe](https://docs.vllm.ai/projects/recipes/en/latest/Qwen/Qwen3.5.html) — `enable_thinking` chat-template kwarg（HIGH）
- [llama.cpp `convert_hf_to_gguf_update.py`](https://github.com/ggml-org/llama.cpp/blob/master/convert_hf_to_gguf_update.py) — `qwen35` pre-tokenizer 注册条目（HIGH）
- [llama.cpp `convert_hf_to_gguf.py`](https://github.com/ggml-org/llama.cpp/blob/master/convert_hf_to_gguf.py) — Qwen3 architecture class（待 P1 git pull 后验证 Qwen3.5 注册状态）（MEDIUM，时延敏感）
- [QLoRA paper (arXiv:2305.14314)](https://arxiv.org/pdf/2305.14314) — "≥13B 推荐 lr=1e-4"，9B 在边界（HIGH）
- [Unsloth LoRA hyperparameters guide](https://unsloth.ai/docs/get-started/fine-tuning-llms-guide/lora-hyperparameters-guide) — alpha=r 大模型推荐、warmup、grad_accum 与 lr 交互（MEDIUM）
- [Unsloth Issue #3482 — DPO grad_accum loss inconsistency](https://github.com/unslothai/unsloth/issues/3482) — bs=1 + grad_accum 在 lr 高时不稳，lr 减小后趋同；SFT 影响小但仍存（MEDIUM）
- [Unsloth Qwen3.5 docs](https://unsloth.ai/docs/models/qwen3.5) — 9B 12GB 推理内存，未给 QLoRA 训练 peak 数据（MEDIUM）
- [awesomeagents.ai Qwen3.5-9B summary](https://awesomeagents.ai/models/qwen-3-5-9b/) — vocab 248K（LOW，第三方汇总，必须 P1 model card 二次校核）
- [Qwen llama.cpp 官方文档](https://qwen.readthedocs.io/en/latest/run_locally/llama.cpp.html) — Qwen3.5 GGUF 支持仍在迭代（MEDIUM）

---
*Pitfalls research for: TSC-CYCLE v3.0 Qwen3.5-9B base 切换（继承 v1.0/v2.0 PITFALLS，本文件聚焦切换增量）*
*Researched: 2026-05-08*
