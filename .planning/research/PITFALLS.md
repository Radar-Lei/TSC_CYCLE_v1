# Pitfalls Research — TSC-CYCLE

**Domain:** GPT-5.5 high → Qwen3-4B-Thinking-2507 蒸馏（QLoRA SFT），自定义思考标签，DGX Spark GB10 aarch64 CUDA 13，GGUF 部署
**Researched:** 2026-05-07
**Confidence:** HIGH（每条 pitfall 都有本机产物 / `dgx-spark-setup` 上游 / MEMORY 历史 lesson 锚点）

> **基础来源**：本文档以 `MEMORY.md`「Qwen3 `<think>`/`</think>` 是 added tokens」+ `debugging.md`「GRPO reward 全负根因 = 模型从不输出 `</think>` 用乱码替代」两条已发生事故为锚点，扩展到 Thinking-2507（已被 RL 调到原生 `<think>`，比 4B-Base 更难"忘掉"原生标签）+ DGX Spark + GPT-5.5 教师 + GGUF 全链路。
> **训练栈权威源**：`/home/samuel/dgx-spark-setup` + `/home/samuel/.claude/skills/dgx-spark-training/SKILL.md`（natolambert 上游）。**不参考** waybarrios。

---

## Critical Pitfalls

### Pitfall 1: Thinking-2507 拒绝放弃原生 `<think>`，自定义标签 SFT 失败

**What goes wrong:**
学生模型在 SFT 后**继续输出原生 `<think>...</think>`**，而不是训练目标 `<start_working_out>...</end_working_out><SOLUTION>...</SOLUTION>`。或者更糟——按照 `debugging.md` 已记录的事故模式：模型学会了输出 `<start_working_out>` 和 `<end_workin`（前缀），但 `</end_working_out>`/`</SOLUTION>` 闭合标签**用乱码字符替代**（Thai、Polish、CJK 等罕见 BPE 序列），因为模型 vocab 中已有的 token 151668（`</think>`）的 logit 权重压过了"分多 sub-token 拼出 `</end_working_out>`"的概率。

Thinking-2507 比 Qwen3-4B-Base 更严重：它已经被官方 RL 训练强化过 `<think>` 用法（model card 明示原生 chat template 强制 `<think>` 起始），先验更强。

**Why it happens:**
1. Qwen3 tokenizer 中 `<think>`(151667)/`</think>`(151668) 是单 token added tokens，预训练+RL 后语义稳固（MEMORY 已验证）。
2. 自定义 `<start_working_out>` 等是文本，BPE 会拆成 5–9 个 sub-token，单步生成时累积概率天然弱于单 token `</think>`。
3. 如果训练时**没有**显式让 chat_template 输出 `<start_working_out>` 起始，且**没有**禁用原生 chat_template 的 `<think>` 注入，模型会同时看到两套信号互相打架。
4. 3000 样本 + 2 epochs + r=64 的"轻量"配置可能不足以覆盖 Thinking-2507 的 RL 先验。

**How to avoid:**
- **训练前必跑标签 sanity test**（已在 STACK.md，强制纳入 Phase 1 verify）：
  ```python
  for tag in ["<start_working_out>","<end_working_out>","<SOLUTION>","</SOLUTION>"]:
      ids = tokenizer.encode(tag, add_special_tokens=False)
      assert len(ids) > 1, f"{tag} 是单 token，会与 native <think> 冲突"
  # 同时验证原生 think 仍是单 token，防止 tokenizer 被改坏
  assert tokenizer.convert_tokens_to_ids("<think>") == 151667
  assert tokenizer.convert_tokens_to_ids("</think>") == 151668
  ```
- **完全绕开 Thinking-2507 的 chat_template**：训练数据用**纯 raw text** 格式，不调用 `tokenizer.apply_chat_template()`。Prompt 拼接顺序为：先放 system 段（角色与硬约束说明），再放 user 段（输入 JSON），然后直接以 `<start_working_out>` 作为 assistant 段起手，全程不出现任何形如尖括号包裹的 system / user / assistant 角色标签，避免触发 Qwen3 原生 chat template 的 `<think>` 注入。
- **Loss masking**：只对 assistant response（`<start_working_out>` 之后到 `</SOLUTION>` 闭合）算 loss，prompt 部分 mask 掉。这是 Thinking-2507 unlearn 原生 `<think>` 的关键——不要让模型在输入侧再看到任何 `<think>` 上下文。
- **在 prompt 末尾显式预填 `<start_working_out>` 作为 assistant 起手**（teacher-forcing 起点），让模型从一开始就走自定义标签轨道。
- **首 epoch 结束跑 inference smoke test**：取 5 个验证样本，看 `</end_working_out>` 和 `</SOLUTION>` 是否完整出现；若仍缺失 → 立即增加 epoch 至 3，且 `lora_alpha` 拉到 192（r=64 × 3）增强 LoRA 信号强度。
- **如果到 epoch 2 还在输出 `<think>`**：fallback 方案是把 `<think>` 和 `</think>` 加入 `bad_words_ids`（仅推理期屏蔽），但这是治标不治本，应该回头加 epoch。

**Warning signs:**
- 训练 loss 下降但 eval 时生成的 raw 文本里出现 `<think>` 或 `</think>`（grep 训练 log 任意 sample 输出）。
- `</end_working_out>` 出现率 < 95%（在同分布 val 上统计）；首 epoch 结束 < 50% 是红色警报。
- 生成结尾是 Thai/Polish/CJK 乱码字符（与 `debugging.md` 完全同模式）。
- `</SOLUTION>` 缺失率 > 5%（结构化输出无法解析）。
- `tokenizer.encode("<start_working_out>", add_special_tokens=False)` 返回 `len==1`（说明 tokenizer 被错误地 `add_tokens()` 污染，立即 abort）。

**Phase to address:** training（主要）+ data-gen（确保训练样本 100% 用自定义标签，且 prompt 不含 `<think>`）

---

### Pitfall 2: 教师 GPT-5.5 输出违反硬约束（min/max/整数/相位覆盖）

**What goes wrong:**
GPT-5.5 high 即使 `reasoning_effort=high` + JSON Schema strict + 显式 prompt 列出 4 条硬约束，仍会在小比例样本上：
- `final < min_green` 或 `final > max_green`（边界饱和度场景）
- `final` 是浮点数（`50.0` 而不是 `50`，JSON Schema `"type": "integer"` 在 strict 模式下应能拦截，但 schema 误写或 SDK 降级时会漏）
- 缺相位（4 相位输入只输出 3 个）
- 多相位（脑补出 `phase_id=5`）
- 相位顺序乱（输入 1,2,3,4 输出 1,3,2,4）— 我们的输出格式是 dict 不是 list，**很容易漏检顺序错误**
- 最坏：`<start_working_out>` 段空白，或 `<SOLUTION>` 段输出额外解释文字（"Note: this assumes..."）破坏纯 JSON

3000 样本中即使违反率 2%，也是 60 个坏样本——足够把 SFT 模型带歪到学会"min_green 是 soft suggestion"。

**Why it happens:**
1. Reasoning models 在长链思考中会"自我说服"突破约束（"等待车辆这么多，给 90 秒应该没问题"，无视 max_green=80）。
2. JSON Schema strict 不能约束语义关系（schema 不知道 `final` 必须 ≥ `min_green`，因为 `min_green` 是输入字段）。
3. 教师 prompt 中"决策提示（非硬约束）"的措辞会被 GPT-5.5 误读为"硬约束也是 soft 的"。
4. Reality.log 中存在的旧 lmstudio 模型违反案例可能被 GPT-5.5 推理过程"参考"，如果 prompt 不小心透露了它们。

**How to avoid:**
- **硬约束 lint 在客户端做，不依赖 schema**（`tsc_cycle/teacher/labeler.py`）：解析 SOLUTION JSON 后立即跑 `validate_constraints(input_sample, parsed_output)`，检查 4 条硬约束。
- **失败样本丢弃，不重试同一 prompt**（PROJECT.md 锁定）。重试同一 prompt 在边界饱和度样本上倾向于反复违反同一约束 → 浪费 token + 拉偏分布。改为标记 `rejected` 写入 JSONL，重新 sample 一个新 input 补足 3000。
- **跟踪违反类型分布**：每 100 个样本统计违反类型；若 max_green 超界 > 5%，prompt 加一句"任何超过 max_green 的输出都将被自动丢弃"（社会工程学，对 reasoning model 有效）。
- **Prompt 中绝不包含 reality.log 的 RAW/REASONING/PARSED 字段**（PROJECT.md 已锁，但代码必须 audit）—这些是旧 lmstudio 输出，会 prime GPT-5.5 复制偏差。
- **用 dict 输出 + 客户端 reorder 校验**：解析后按输入 `phase_waits` 顺序重组，发现键集合不匹配 → 丢弃。
- **接受 ~3-5% 丢弃率作为 healthy**：3000 目标 → 实际请求 ~3150 样本。**违反率 > 8% 视为 prompt 工程问题**，停下来改 prompt 而不是闷头烧 token。

**Warning signs:**
- `teacher_outputs.jsonl` rejected 计数 > 8% on first 200 samples。
- 同一 input_id 重试 3 次仍违反同一约束（说明这类输入对 GPT-5.5 系统性困难，应**减少**这类输入在 generator 中的权重而非反复重试）。
- `<SOLUTION>` 段含非 JSON 文本（regex `r"<SOLUTION>([^<]*)</SOLUTION>"` 捕获内容 `json.loads` 抛 `JSONDecodeError`）。
- API cost 已花 50% 但有效样本只 ~30%（说明违反率/重试率失控）。

**Phase to address:** teacher-label

---

### Pitfall 3: "OOD val" 其实在分布内 / OOD 维度退化

**What goes wrong:**
划分 80/10/10 (train/同分布 val/OOD val) 后，OOD val 的"分布外"维度可能：
- **secretly in-distribution**：OOD generator 用 `np.random.uniform(min_green=10, max_green=120)` 看似更宽，但**采样后过滤掉 reality.log 出现过的组合**这一步漏掉，导致 OOD set 里 60% 样本碰巧落在 reality.log 范围。
- **退化到不可解**：把 `min_green=200, max_green=10` 等不一致输入放进 OOD（min > max），教师拒答→样本数不足→评测显著性差。
- **phase_count 集中在 4**：reality.log 主要是 4 相位（已知），如果 OOD 也只到 3–5 相位，没有 2 相位 / 6 相位极端，"OOD" 名不副实。
- **capacity / min / max 之间的隐式相关性泄漏**：reality.log 里 capacity 大的相位 max_green 也大（业务上合理），合成 generator 复制了这一相关性 → OOD val 即便每个边际分布更宽，联合分布与 train 一致 → 模型用学到的相关性蒙混过关。

**Why it happens:**
1. "OOD" 一词没在 PROJECT.md 形式化定义，每人理解不同。
2. 只检查每维边际分布，不检查联合分布 / 相关结构。
3. 数据生成代码没有显式"必须违反某 reality.log 统计量"约束。
4. 同分布 val 与 train 用同一 sampler、不同 seed 划分，但合成数据的可枚举空间小（4 相位 × 整数秒），可能产生 sample-level duplicate（同一 input 出现在 train 和 val），用 `sample_id = hash(canonical_json(input))` 去重才能发现。

**How to avoid:**
- **形式化 OOD 定义**（写在 `data/ood_spec.md`）：每个 OOD 样本必须满足以下至少一项：
  - phase_count ∈ {2, 3, 6, 7}（reality.log 主要是 4–5）
  - max_green > 100 或 min_green < 15（reality.log 范围之外）
  - pred_saturation 跨度（max - min over phases）> 0.5（reality.log 平均 < 0.1）
  - capacity 与 max_green 反相关（打破业务相关性）
- **训练前跑分布 audit**：scipy KS 检验，OOD val 每维 vs train 应 reject H0（p<0.01）；若不 reject → OOD generator 没工作。
- **sample_id 去重**：`hash(canonical_json(input))` 保证 train ∩ val ∩ OOD = ∅。在划分代码末尾 `assert len(set(train_ids) & set(val_ids)) == 0`。
- **OOD 可解性检查**：OOD generator 出来的样本必须先过约束一致性 lint（min ≤ max、capacity > 0），再过教师；教师拒答率 > 30% 视为 OOD 退化为不可解，不是真 OOD。
- **OOD val ≥ 200 样本**：3000 × 10% = 300 是上限，扣除 lint 拒答和教师拒答后 ≥ 200 才有统计显著性。
- **报告同分布 val vs OOD val 的差距**：硬约束满足率 OOD - 同分布 < 5pp 是健康；> 15pp 表示 OOD 太极端或模型严重过拟合。

**Warning signs:**
- 同分布 val 和 OOD val 评测分数差 < 2pp（OOD 不够 OOD）或 > 30pp（OOD 太极端 / 模型崩塌）。
- KS test p-value > 0.1 在任一维度（OOD 与 train 边际分布无显著差异）。
- `len(train_ids ∩ val_ids) > 0`（划分 bug，必须 abort）。
- OOD val 教师标签拒答率 > 30%（OOD 不可解）。

**Phase to address:** data-gen + eval

---

### Pitfall 4: DGX Spark 训练栈隐藏陷阱

**What goes wrong:**
即使复用 `/home/samuel/dgx-spark-setup/.venv`，训练仍然在以下点上崩盘：

(a) **flash-attn 偷偷被 import**：transformers 默认尝试 `flash_attention_2`，model card 写明 Qwen3-Thinking 推荐 flash-attn，loader 可能 fallback 到 sdpa 但**先抛 WARN+CUDA init 副作用**，最差情况 site-packages 里残留某个老的 `flash_attn` 包导致 `libcudart.so.12: cannot open shared object file` 训练直接失败。

(b) **bitsandbytes aarch64 sm_121 PTX JIT 第一步惩罚**：bnb 0.48 没有 sm_121 native cubin，只能 PTX JIT。JIT 编译发生在第一个 forward pass，单步可能 30–90 秒，若 trainer 设置了 `dataloader_num_workers > 0`，多个 worker 同时触发 JIT 可能触发 cuda init 竞态报错（社区有 issue 但不稳定复现）。

(c) **UMA OOM 整机僵死**：DGX Spark 128GB unified memory，swap 默认开启时，OOM 走 swap 死亡螺旋——SSH 卡死、显示器黑屏，必须**硬重启**。曾耗一天调试。

(d) **gradient_checkpointing × custom-tag chat template**：如果误用 `apply_chat_template`，再开 gradient_checkpointing，某些 transformers 版本会在 recompute 时丢失 attention mask 对齐（特别是当我们手工 pad `<start_working_out>` 起手时），梯度 NaN。

(e) **`attn_implementation` 没显式设**：默认 `auto`，aarch64 上时灵时不灵；某些 Qwen3 配置文件硬编码 `flash_attention_2` 优先。

(f) **复制 venv 的 shebang 失效**：`pip install` 进 copied venv 后，`bin/transformers-cli` 等 console scripts 的 shebang 仍指向 `/home/samuel/dgx-spark-setup/.venv/bin/python`，从 `/home/samuel/TSC_CYCLE/.venv/bin/transformers-cli` 调用时实际跑的还是源 venv，安装的新包"看不见"。SKILL.md 已警告。

(g) **不在 `run_safe.sh` / systemd-run scope 内运行**：直接 `python -m sft.train` → OOM 整机僵死。

**Why it happens:**
DGX Spark 是早期生态，CUDA 13 + aarch64 + sm_121 三重稀有组合；很多包只在 cu12 + x86 测试。

**How to avoid:**
- **训练脚本顶部强制 SDPA + 拒绝 flash-attn**：
  ```python
  import os
  os.environ.setdefault("TRANSFORMERS_NO_FLASH_ATTENTION", "1")
  # ... model load ...
  model = AutoModelForCausalLM.from_pretrained(
      ..., attn_implementation="sdpa",  # 显式，不靠 auto
  )
  # 启动后 assert
  assert "flash" not in str(type(model.model.layers[0].self_attn)).lower()
  ```
- **训练前 import sentinel**：`python -c "import flash_attn"` 必须 ImportError；若不 → `uv pip uninstall flash-attn flash_attn`。
- **强制走 `run_safe.sh`**（dgx-spark-training skill 提供）：
  ```bash
  scripts/dgx_spark/run_safe.sh 100G -- python -m sft.train --config config/config.yaml
  ```
  内部用 `systemd-run --scope -p MemoryMax=100G -p MemorySwapMax=0`，OOM 只杀本进程不僵死整机。
- **swap 关闭 + 验证**：`sudo swapoff -a && free -h | grep Swap`（Total 应为 0）。
- **`dataloader_num_workers=0` 或 1**：避免 bnb JIT 多 worker 竞态；4B + 3000 样本 + seq_len 2048 数据加载不是瓶颈。
- **bnb JIT 预热**：训练正式 step 前跑 `model(**dummy_batch)` 一次（不计 loss），把 PTX JIT 时间挪到 step 0 之外，避免被算入 wall-clock budget 和首步 OOM 风险。
- **始终用 `python -m sft.train` 不用 `transformers-cli`**：避开 copied venv 的 shebang 陷阱（SKILL.md 强调）。
- **`scripts/dgx_spark/verify.py` 必须在每次开训前跑一次**：检查 CUDA 13、`ptxas` 路径、SDPA、swap、关键包版本。
- **`gradient_checkpointing=True` 时显式设 `gradient_checkpointing_kwargs={"use_reentrant": False}`**：避免 reentrant 模式下的 mask 对齐 bug。

**Warning signs:**
- 训练 log 出现 `libcudart.so.12` → 立即 abort，flash-attn 漏装/残留。
- step 0 等待 > 60 秒 → bnb JIT 中（正常），但 > 180s → 检查 `ptxas` 路径（`echo $TRITON_PTXAS_PATH` 应是 `/usr/local/cuda/bin/ptxas`）。
- `nvidia-smi` 显示 GPU mem ~98GB 持续 → UMA 危险区，再涨就僵死，立即下 batch size。
- SSH 响应延迟 > 5s → 整机进入 swap 死亡螺旋，**立即** `kill -9` 训练进程，否则下一步是硬重启。
- 训练首 step 出现 `RuntimeError: CUDA error: an illegal memory access` → 通常是 sm_121 sm_120 cubin 选择问题，重启 + 显式 `TORCH_CUDA_ARCH_LIST="12.1a"`。
- `pip list` 在 `/home/samuel/TSC_CYCLE/.venv` 显示某包，但 `python -c "import X"` 报 ModuleNotFoundError → copied venv shebang 问题，强制 `python -m`。

**Phase to address:** training（顶级；training Phase 的 entry criterion 必须包含 verify.py 通过 + `swap=0` + `run_safe.sh` 包裹）

---

### Pitfall 5: QLoRA → GGUF 转换链断裂

**What goes wrong:**

(a) **LoRA merge dtype 错乱**：merge 时 base 是 4-bit NF4（bnb），`peft_model.merge_and_unload()` 在 bnb 量化层上行为未定义；正确做法是**先重新加载 bf16 全精度 base**再挂 LoRA。错版本会得到 nan 权重 → GGUF 文件能写但推理输出乱码。

(b) **fp16 数值漂移**：如果训练用 bf16 但 merge 后保存 fp16，bf16 (range ±3.4e38, 7-bit mantissa) → fp16 (range ±6.5e4, 10-bit mantissa)，mantissa 提升但 **range 缩小** 1e34 倍。Qwen3 某些 layer norm 或 RoPE 缩放在某些 batch 上输出 > 6.5e4，fp16 直接 inf → 整个 sequence 输出 garbage。

(c) **llama.cpp tokenizer 重生成不带 added tokens 的预训练 embedding**：即使我们在训练时 **没有** `add_tokens()` 自定义标签（保持文本路径），原生 `<think>`(151667) 和 `</think>`(151668) **仍在 vocab 里**且 GGUF 会保留它们的 embedding。如果学生模型在某些边缘 prompt 下被 sampling 到这些 token id（top-p 没排除），输出仍会冒出 `<think>` 即便训练目标是自定义标签。

(d) **q4_K_M 在长 thinking trace 上质量崩塌**：4-bit 量化对长依赖（500+ token thinking 段中引用前面的输入字段值）特别敏感，单层小误差累积导致末尾 SOLUTION JSON 中数字偏离 fp16 输出 5–20 秒（远超容差）。

(e) **没有 imatrix 校准**：默认 q4_K_M 用统一重要性，不针对 TSC 任务的 token 分布优化。

(f) **convert_hf_to_gguf.py 不识别 added_tokens**：如果错误地把自定义标签加进 vocab，convert 脚本能写出 GGUF 但 llama.cpp inference 时这些新 token 走未训练的 fallback embedding，输出乱码。

**Why it happens:**
1. PEFT 文档没有 prominently 警告 "merge 前必须 reload base 为非量化"。
2. bf16 ↔ fp16 转换的 range 问题在 ~99% 样本上看不到，只在长 sequence + 极端值时出现。
3. 原生 `<think>` 仍在 vocab 是 Qwen3 tokenizer 设计，convert 脚本忠实保留。
4. Q4_K_M 的"+0.1754 ppl"是 Llama-3-8B 上 generic 文本的数字，TSC 这种 schema-strict 任务的 perplexity 退化没有公开 benchmark。

**How to avoid:**
- **Merge 必须重新加载 bf16 base**（STACK.md 已锁，纳入 export 脚本 assertion）：
  ```python
  base = AutoModelForCausalLM.from_pretrained(
      "Qwen/Qwen3-4B-Thinking-2507",
      torch_dtype=torch.bfloat16,
      device_map="cpu",                    # CPU merge 防显存挤占
  )
  # NOT: load 4-bit base then merge
  peft_model = PeftModel.from_pretrained(base, checkpoint_dir)
  merged = peft_model.merge_and_unload()
  ```
- **保存为 bf16 而非 fp16，再 convert**（关键决策修订）：
  ```python
  merged.save_pretrained("runs/merged-bf16", safe_serialization=True)
  # convert_hf_to_gguf.py 支持 --outtype bf16
  ```
  GGUF "fp16" 实质上是 ggml f16 类型，但 convert 脚本可以从 bf16 source 直接产 bf16 GGUF（`--outtype bf16`），llama.cpp 现代版本（>=2024-Q4）原生支持 bf16 推理，避免 range 问题。如果一定要 fp16，先 sanity check："dump 一个 forward pass 的所有 hidden state max abs，应 < 65000"。
- **GGUF 导出后做 generation parity test**：
  - 取 20 个固定 prompt（同分布 val 子集），固定 seed=42, temperature=0.0 (greedy)
  - HF bf16 vs GGUF bf16 vs GGUF q4_K_M 三路对比
  - 输出 token ID 必须 ≥ 99% 一致到 SOLUTION 段开头，或最少 SOLUTION JSON 数值 100% 一致
  - 任一路不一致 → 调查（不是验收标准失败就是 bug）
- **bad_words_ids 推理期屏蔽原生 `<think>`/`</think>`**（GGUF 推理用 llama.cpp `--logit-bias`）：
  ```bash
  llama-cli -m tsc-cycle-4b-q4_k_m.gguf \
    --logit-bias 151667-100 --logit-bias 151668-100 \
    -p "..."
  ```
  防止 q4_K_M 后 logit 噪声偶发偏向原生 token。
- **q4_K_M 崩塌时上 imatrix**：用 256 个训练样本（input + assistant target）做校准文件，跑 `llama-imatrix` → `llama-quantize --imatrix imatrix.dat`。
- **绝不 `add_tokens()` 自定义标签**（PROJECT.md + STACK.md 已锁，但 export 脚本必须 assert：`assert len(merged.config.vocab_size) == 151936`，原始 Qwen3 vocab 大小）。
- **convert 后 sanity test tokenizer**：
  ```bash
  llama-tokenize -m tsc-cycle-4b-q4_k_m.gguf "<start_working_out>"
  # 应输出 ≥5 个 token ids，不应是单 ID
  ```

**Warning signs:**
- Merged 模型 forward 一次输出 NaN / Inf → merge dtype bug。
- GGUF fp16 vs HF bf16 在同 prompt 下 SOLUTION 数值差 > 0 秒 → 转换链有问题（greedy 应字节级一致）。
- q4_K_M vs fp16 SOLUTION MAE > 3 秒（fp16 vs teacher 通常 < 2 秒，q4_K_M 应不显著恶化）→ 量化崩塌。
- llama.cpp inference 输出含 `<think>` token id 151667（用 `llama-cli --log-disable=0` 看 token-by-token） → bad_words 没工作。
- 推理时 `</SOLUTION>` 缺失率 q4_K_M > fp16 5pp → 长 thinking 末尾退化。
- `merged.config.vocab_size != 151936` → 训练时被错误 resize 了 embedding，必须回训。

**Phase to address:** export + eval

---

### Pitfall 6: 评测假阳性 / 假阴性

**What goes wrong:**

(a) **硬约束满足率被 trivial case 灌水**：如果某 OOD 样本 min_green=max_green=30（区间退化为单点），输出 30 必然满足；这种样本占 30% → 报告 "硬约束满足率 95%" 听起来很好但毫无信息。

(b) **Reasoning 质量 auto-grader 用 GPT-5.5 自己评，引入循环偏差**：自评比独立 grader 平均高估 10–15pp。

(c) **eval split 泄漏**：训练 / 同分布 val / OOD val 划分用 `np.random.shuffle(seed=42)`，但合成数据生成时没有 sample_id hash，partial duplicate（input 一样 output 不一样的边界样本）跨集出现。

(d) **OOD val 在 trivial 维度移位**：例如 OOD 只是把 capacity 从 30–50 扩到 60–70，min/max_green 范围照旧 → 模型用学到的 (min, max, pred_sat) 关系蒙混过关，capacity 本来就是非约束输入。

(e) **三模型变体（HF bf16 / GGUF fp16 / GGUF q4_K_M）seed 不同**：评测脚本对每路独立 `random.seed(time.time())` → 数值差异可能来自 sampling noise 而非量化退化。

(f) **训练时 inference 与 eval inference temperature 不一致**：训练时用 temperature=1.0 监控生成质量，eval 用 temperature=0.0；硬约束满足率 eval 看起来好，部署时用户用 temperature=0.7 → 实际效果差。

(g) **评测只看 mean，不看 tail**：MAE=2.3s 但 p99=25s，部署时偶尔出 max_green+10 的 final 是灾难。

**Why it happens:**
1. PROJECT.md 没有定义 trivial-case 排除标准。
2. Auto-grader 简单上 GPT-5.5 是最容易的实现，但有偏。
3. 快速 prototype 时 split 与 generator 解耦，缺 sample_id。

**How to avoid:**
- **Trivial-case 排除**：评测前过滤 `min_green == max_green` 或 `max_green - min_green < 5` 的样本（或单独报告这类的满足率，明确标注"trivial"）。
- **Auto-grader 用独立模型**：reasoning 质量评分用 Claude / Gemini / 本地 70B，不用 GPT-5.5（避免 self-grading bias）。或者**只报告硬约束满足率 + 与教师 MAE 这两个客观指标**，主观 reasoning 质量评分作为 secondary signal。
- **sample_id 全程使用**：
  ```python
  sample_id = hashlib.sha256(canonical_json(input_dict).encode()).hexdigest()[:16]
  # 划分前 assert: len(set(all_ids)) == len(all_ids)
  # 划分后 assert: train_ids.isdisjoint(val_ids); val_ids.isdisjoint(ood_ids)
  ```
- **OOD spec 显式列出非 trivial 维度**（见 Pitfall 3）。
- **三变体共用相同 seed + greedy decoding 做主评测**：`temperature=0.0`、`do_sample=False`、`seed=42`；变体差异**只能**来自权重精度。Sampling-based 评测作为 secondary（看鲁棒性）。
- **统一 inference config 文档**：写在 `eval/config.yaml`，所有评测/部署 inference 必须读取此文件。
- **报告分布而非点估**：硬约束满足率（mean、p5、p95），与教师差值（MAE、p99 absolute error、max abs error），按 phase_count 分桶。
- **Eval split 创建后立即冻结**：写到 `data/splits.json` 提交 git；后续任何重新生成必须 hash 校验。

**Warning signs:**
- 硬约束满足率 OOD ≥ 同分布（不可能正常发生，说明 OOD 退化或 split 泄漏）。
- 三变体在 greedy 模式下 SOLUTION 不完全一致（说明 seed/sampling 失控）。
- Reasoning auto-grader 给出的分数与 MAE 不相关（Pearson r < 0.3）→ grader 有问题。
- p99 absolute error > 5x MAE（长尾失控）。
- 同一 sample_id 出现在 train 和 val 中（直接 abort）。

**Phase to address:** eval

---

### Pitfall 7: GPT-5.5 API 成本超预算 / 速率失控

**What goes wrong:**

(a) **reasoning_effort=high 的 reasoning tokens 计费**：reasoning tokens 不显示给用户但**计费**（按 output token 价）。GPT-5.5 high 在 TSC 任务上 reasoning_tokens 可能 1000–3000 / 样本，3000 样本 = 3M–9M tokens 仅 reasoning。如果按 GPT-5.5 输出 token ~$30/M（推测，参考 o3 family），仅 reasoning 就 $100–270。加上 input + 显式输出，**3000 样本可能 $200–500**。

(b) **≤10 worker concurrency 撞 RPM/TPM**：OpenAI tier-2 账户 GPT-5.5 可能 limit 500 RPM / 30k TPM。10 workers 同步发 + 长 reasoning（30s/req）→ 平均 20 RPM 没问题，但首 30s 一起发起 10 req 撞瞬时 burst → 429 → 重试风暴 → 大量样本失败 + 加倍 token 消费。

(c) **SDK 静默降档 reasoning_effort**：旧版 `openai` SDK (<1.40) 对 `reasoning_effort` 字段处理不同；某些 chat.completions endpoint 接受但忽略；Responses API 才严格。如果学生模型表现差，根因可能是教师其实跑的是 medium 而非 high。

(d) **教师 prompt 意外含 reality.log 标签 priming**：开发时方便 debug，prompt 里塞了 reality.log 的几个示例（`few-shot`）—如果示例输出本身违反约束（旧 lmstudio 教师有 bug），GPT-5.5 会**复制偏差**（mode collapse 到旧错误模式）。

(e) **断点续跑没做，中断重新全跑**：API 错误中断 → 重启 → 又烧一遍 token。

**Why it happens:**
1. Reasoning model 计费不透明，开发者通常按 output token 估算，遗漏 reasoning tokens（实际可能 3–5x output）。
2. ThreadPoolExecutor 不感知 RPM；OpenAI SDK 自动重试 + ThreadPool 重试 = 双重重试。
3. SDK API drift 在 minor version 间发生，文档滞后。
4. Few-shot 是直觉，但对 reasoning model 是反模式（reasoning 本身就是 chain-of-thought，再 prime 反而压制创造性）。

**How to avoid:**
- **Token budget 测算 + 实测**：先跑 50 个样本（预算 $5–10）测得 avg input / output / reasoning tokens；线性外推 3000 样本总成本。**预算超 $300 必须 PROJECT.md owner 显式确认**。
- **Concurrency 自适应**：`max_workers=5` 起步（不是 10），观测 30 分钟无 429 再升到 8。**永远不到 10 是 fine**（PROJECT.md 是上限不是目标）。
- **客户端 RPM/TPM 限速器**：用 `aiolimiter` 或自写 token bucket，限 8 RPM + 25k TPM（留 buffer 给 reasoning tokens），优先于 ThreadPool 自然限速。
- **断点续跑 JSONL**（STACK.md 已锁）：每个样本完成立即 `fout.write(...) + fout.flush() + os.fsync()`；启动时读已有 sample_id set，跳过。
- **SDK 版本锚定 + 显式校验**：`openai>=1.50.0`；每次启动 print SDK 版本到 log。**用 Responses API（`client.responses.create(reasoning={"effort": "high"})`）而非 chat.completions**——Responses API 严格校验 reasoning 字段，chat.completions 老路径可能静默忽略。
  - **smoke test**：跑 1 个样本，要求 GPT-5.5 自报 `reasoning_effort` 在 reasoning 末尾；或观察 reasoning_tokens 字段（Responses API 返回 `usage.reasoning_tokens`），应 ≥ 500。如果 < 100 几乎肯定降档了。
- **Prompt 严格不含 reality.log 字段**：teacher prompt 模板单独评审，grep 模板源码不含 `RAW`/`REASONING`/`PARSED`/`<SOLUTION>{".*":` 等 reality.log 特征字符串。
- **不用 few-shot**（reasoning 模型反模式）：zero-shot + 详细约束描述 + JSON Schema 输出 = 最佳实践。
- **API key 用单独 budget-capped key**：在 OpenAI dashboard 给本项目设 `usage_limit=$500`，超额自动停。

**Warning signs:**
- 50 sample smoke test 总价 > $10（外推 3000 → > $600，超出隐含预算）。
- `usage.reasoning_tokens` < 100（降档）；或不在 response 里（用了错 API endpoint）。
- 429 错误率 > 1% on full run → 立即降 worker。
- 同一 sample_id 在 JSONL 中出现两次（断点续跑 dedup 失败）。
- prompt 字符串中出现 reality.log 风格的 `RAW:` / `REASONING:` 字段（grep 立刻 abort）。

**Phase to address:** teacher-label

---

### Pitfall 8: 6 小时训练预算超时

**What goes wrong:**

(a) **Thinking-2507 unlearn 原生 `<think>` 需要 ≥ 3 epochs**：MEMORY 记 4B-Base 上 2 epochs OK，但 Thinking-2507 经过 RL 强化先验更强，2 epochs 可能不足（参见 Pitfall 1）。3 epochs × 3000 样本 × 2048 seq_len × QLoRA r=64 在 GB10 上约 4.5–5h，留给 checkpoint I/O 的 buffer 只剩 1h。

(b) **seq_len × batch trade-off 在 GB10 上不直观**：UMA 共享 → 大 batch 大 seq 同时挤压 CPU 端 dataloader、optimizer state、gradient checkpoint activation。STACK.md 推算 `batch=4, seq=2048` peak ~30–40GB，但若 thinking trace 长尾达 3500 token，padding 到 max_seq_length=2048 就**截断**了 SOLUTION 段（见 (d)），或必须升到 4096 → batch 减半 → step 数翻倍。

(c) **checkpoint I/O 占 wall clock**：4B QLoRA adapter 只 ~200MB，但 base 4-bit copy 也存的话每 epoch ~3GB；写入 NVMe 还好，但若 `save_strategy="steps", save_steps=100` + `save_total_limit` 不设，磁盘 I/O 阻塞 GPU。

(d) **tokenizer max_length 截断长教师 reasoning**：GPT-5.5 high 的 thinking + 显式 `<start_working_out>...` 段加起来可能 2500–4000 token。截断到 2048 → 训练样本 SOLUTION 段被砍掉 → 模型学到"thinking 之后就结束"。

(e) **bnb PTX JIT 首步 30–90s**（Pitfall 4 已述）算入 budget。

(f) **evaluation 阶段挤占训练时间**：`eval_strategy="epoch"` + 300 val 样本 × generate 完整序列（含 thinking）每个 ~30s → 每 epoch eval 约 2.5h，把训练撑到 10h+。

**Why it happens:**
1. Naive 估算只看 train forward+backward，忽略 eval generate / I/O / JIT。
2. 没有 dry-run 测时间。
3. PROJECT.md 6h 是端到端目标，但具体子项预算没拆。

**How to avoid:**
- **拆解 6h budget**（写在 `runs/budget.md`）：
  - JIT 预热: 5 min
  - 实际 training: 4h（3 epochs × 80 min/epoch）
  - In-training eval: 30 min（**只跑 loss eval，不跑 generate**；generate eval 留到训练完后单独跑）
  - Checkpoint I/O: 15 min（每 epoch 一次，fp16 LoRA adapter 200MB，saves 600MB total）
  - Buffer: 70 min
- **`eval_strategy="epoch"` 用 loss only**：`SFTConfig(eval_strategy="epoch", per_device_eval_batch_size=4, predict_with_generate=False)`。Generate-based 评测放到训练后单独 eval phase。
- **检测样本长度分布，决定 max_seq_length**：data-gen 完成后跑 `tokenizer(samples, return_length=True)` 统计 p99，设 `max_seq_length = ceil(p99 * 1.05 / 256) * 256`，而不是猜 2048。如果 p99 = 3000 → 必须 3072，否则 SOLUTION 截断。
- **截断策略：left-truncate prompt，保 SOLUTION**：DataCollator 自定义，超长样本砍 prompt 头部（input JSON 可缩），永不砍 assistant response。或直接 **drop > max_seq_length 的样本**（< 5% 是可接受成本）。
- **JIT 预热放在 `train()` 之前**：
  ```python
  with torch.no_grad():
      _ = model(input_ids=torch.zeros(1, 64, dtype=torch.long, device=0))
  trainer.train()
  ```
- **Dry-run 100 step**：训练前跑 100 step，外推总时间，确认 < 6h；若不 → 砍 epoch / 砍 seq_len。
- **`save_strategy="epoch"` + `save_total_limit=2`**：磁盘 cap，不存中间步。
- **`logging_steps=20`**（不是 1）：减少 wandb / stdout I/O 开销。
- **如果 3 epochs 撞 6h**：优先砍 OOD val generate eval（移到训练后），保 epoch；不要砍 epoch，会回到 Pitfall 1。

**Warning signs:**
- Dry-run 100 step 推算总时间 > 5h → 提前调整 config。
- Epoch 1 wall time > 100 min → 对应总时间 > 5h，砍 eval 或减 batch accumulation。
- 磁盘 free space 训练中跌 > 10GB → checkpoint 失控。
- max_seq_length=2048 时数据加载 log 显示 `> 5% samples truncated` → SOLUTION 段在被砍。
- step 0 wall time > 180s → JIT 异常或 ptxas 路径错。

**Phase to address:** training

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| 跳过 verify.py 直接训练 | 省 10s | OOM 整机僵死，硬重启丢 wandb run，失 1–2h | **Never** |
| 用 reality.log 直接当训练输入 | 不用写 generator | 学生过拟合 reality.log 分布，OOD 完全失效，违反 Core Value | **Never** |
| Few-shot 教师 prompt | "看起来效果好"（实际是复制示例输出） | mode collapse 到示例偏差，教师能力压制 | **Never** for reasoning models |
| `save_strategy="steps", save_steps=50` | 更细 checkpoint 粒度 | 磁盘 I/O 占 wall clock，6h 撞墙 | 仅 debugging 阶段，正式训练禁用 |
| 不做 sample_id 去重 | 划分代码更短 | train/val 泄漏，eval 数字假高 | **Never** |
| 直接 `pip install vllm` 来推理 | "试试" | `libcudart.so.12` 失败，污染 venv | **Never**（PROJECT 已锁不用 vLLM） |
| 训练时直接用 `apply_chat_template` | 省 30 行代码 | 注入原生 `<think>` 到 prompt，模型继续输出原生标签 | **Never** for this project |
| 教师 reasoning_effort 降到 medium 省钱 | 省 ~50% cost | 学生达不到 Core Value，要么重训要么妥协 | **Never** |
| GGUF fp16 不与 HF bf16 做 parity test | 省 30 min eval | 部署后发现量化崩塌，回滚 | 仅当 HF bf16 评测已 fail（不会到这步） |
| 跳 imatrix 直接 q4_K_M | 省 20 min | q4_K_M 退化但归因到 SFT，反复重训 | 当 q4_K_M vs fp16 MAE 差 < 1s 时，可跳 |
| 用 ThreadPool 不加客户端限速 | 代码简单 | 429 风暴 + token 浪费 | 当账户 tier 已知足够大（实际不知道 → 必须限速） |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| OpenAI SDK | 用 `chat.completions.create(reasoning_effort="high")` | 用 `client.responses.create(reasoning={"effort":"high"})`，并断言 `usage.reasoning_tokens > 100` |
| Hugging Face transformers | 让 `attn_implementation` 自动选 | 显式 `attn_implementation="sdpa"` + 启动 assert 不是 flash_attention_2 |
| Hugging Face PEFT | `merge_and_unload()` 在 4-bit base 上跑 | 重新 load bf16 base 后再挂 LoRA 再 merge |
| TRL SFTTrainer | `apply_chat_template` 默认行为 | 自定义 formatting_func，绕开原生 chat template，避免 `<think>` 注入 |
| bitsandbytes | 升级到 0.49+（preview） | 锁 0.48.0（aarch64 sm_121 验证版） |
| llama.cpp convert | 假设 added_tokens 自动处理 | tokenize sanity check：`<start_working_out>` 必须 ≥ 5 sub-tokens |
| llama.cpp inference | 不设 logit-bias | 推理时 `--logit-bias 151667-100 --logit-bias 151668-100` 屏蔽原生 think |
| systemd-run | 忘记 `MemorySwapMax=0` | 同时设 MemoryMax + MemorySwapMax，否则 swap 死亡螺旋 |
| copied venv | 用 `bin/transformers-cli` 等 console scripts | 改用 `python -m transformers.cli ...` 或 `python -m sft.train` |
| reality.log | 当训练标签 / 当训练输入 | **只**作为输入分布统计先验，不入训练集 |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| bnb PTX JIT 首步 | step 0 卡 60–180s | dummy forward 预热在 train() 前 | 永远（首步），仅在多 worker 时可能 hang |
| UMA OOM 死亡螺旋 | SSH 卡 + GPU mem ~119GB | swap=0 + systemd-run MemoryMax=100G | batch×seq×model_size 接近 100GB 时 |
| ThreadPool RPM burst | 启动后 30s 内 429 | 客户端 token bucket 限速 8 RPM | 任何 ≥ 5 worker 立即并发启动 |
| max_seq_length 截断 | 训练 log "X samples truncated" + SOLUTION 缺失率高 | 实测样本长度 p99，设 max_seq = p99×1.05 | 任何 p99 > 设定 max_seq 的情况 |
| eval_strategy=epoch with generate | epoch wall time × 3 | predict_with_generate=False, eval 单独 phase | 任何 val ≥ 100 + 长 thinking |
| q4_K_M 长 thinking 退化 | SOLUTION 数值 q4 vs fp16 MAE > 3s | imatrix 校准 + parity test | 任何 thinking trace > 1500 token |
| 检查点磁盘 I/O 阻塞 | step 之间 GPU util 跌 < 30% 超 30s | save_strategy=epoch + save_total_limit=2 | save_steps 频率高 + adapter 大 |

---

## Security Mistakes（API 与权重相关）

| Mistake | Risk | Prevention |
|---------|------|------------|
| OpenAI key 写进 git | 泄漏后被滥用，本项目预算被 burn | `OPENAI_API_KEY` 走 env，`.gitignore` 包含 `.env`；用 budget-capped 子 key |
| GPT-5.5 prompt 含真实路口 ID / 时间 | 教师日志可能被 OpenAI 用于训练，业务信息泄漏 | crossing_id 输入前 hash 或匿名化（reality.log 已有 crossing_id=1，确认是测试值） |
| 训练 log / wandb 上传完整 prompt | 同上 + 第三方平台 | wandb 设 `WANDB_DISABLE_DATA_LOGGING=true`，只上传 metrics |
| GGUF 模型分享时含敏感 fine-tuning 数据 | 模型权重可能被 inversion attack 提取训练样本 | 公开发布前用 OOD test prompt 跑 membership inference 检测 |
| 教师标注 JSONL 进 git | 数据集 + 教师输出泄漏，且 OpenAI ToS 可能限制商业派生 | `.gitignore` 包含 `data/teacher_outputs.jsonl` 及 `runs/`；review OpenAI ToS for distillation policy |

---

## "Looks Done But Isn't" Checklist

- [ ] **训练完成**：经常缺 `</end_working_out>` 完整出现率检查 — 验证 generate 5 个 prompt 后 grep `</end_working_out>` 命中 5/5
- [ ] **教师标注完成**：经常缺最终 sample_id 唯一性 + 硬约束二次 lint — 验证 `sort -u` 和重新跑 validator 全通过
- [ ] **GGUF 导出完成**：经常缺 fp16 vs q4_K_M parity test — 验证 20 prompt greedy 输出 SOLUTION 段一致或差 < 1s
- [ ] **eval 完成**：经常缺 trivial-case 排除后的硬约束满足率 — 验证过滤 `min==max` 后重算
- [ ] **OOD val 通过**：经常缺 KS test 验证 OOD 真的 OOD — 每维 p < 0.01 vs train
- [ ] **训练栈就绪**：经常缺 verify.py + swap=0 + run_safe.sh 三件套 — 三个命令成功才算就绪
- [ ] **3000 样本完成**：经常缺扣除拒答后的 effective sample count — 验证 ≥ 2700 effective
- [ ] **模型可部署**：经常缺 `llama-cli` 端到端 inference 测试 — 用 q4_K_M 跑 1 个 reality.log 真实 prompt 验证输出格式 + 数值合理
- [ ] **Tokenizer 安全**：经常缺训练前 + GGUF 后双重 tag tokenize 检查 — 两次都验证 `<start_working_out>` 是多 sub-token
- [ ] **6h 预算确认**：经常缺 dry-run 100 step 外推 — 100 step wall time × (total_steps/100) 必须 < 6h

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| 模型继续输出原生 `<think>` (Pitfall 1) | MEDIUM (1–2h) | 1) `bad_words_ids=[151667,151668]` 临时屏蔽推理；2) 加第 3 epoch 重训；3) 仍不行则改 prompt 让 assistant 起手强制 `<start_working_out>` 预填 |
| 教师违反率 > 8% (Pitfall 2) | LOW (30 min) | 改 prompt 加严格约束话术；丢弃违反样本；不要重试同 prompt |
| OOD val 退化 (Pitfall 3) | MEDIUM (1h) | 重新生成 OOD（用 ood_spec.md 形式化定义）；重跑 KS test；保留 train/同分布 val 不动 |
| flash-attn 漏装 (Pitfall 4a) | LOW (5 min) | `uv pip uninstall flash-attn flash_attn`；`grep -r flash_attention site-packages/` 清理残留；重新 verify.py |
| UMA OOM 整机僵死 (Pitfall 4c) | HIGH (硬重启 + 1h) | 长按电源；重启后 swapoff、systemd-run wrapper；wandb resume |
| LoRA merge nan (Pitfall 5a) | LOW (15 min) | 重新 bf16 reload base；merge；再次保存 |
| q4_K_M 崩塌 (Pitfall 5d) | MEDIUM (45 min) | 用 256 训练样本生成 imatrix；重新 quantize 带 imatrix；再 parity test |
| split 泄漏 (Pitfall 6c) | HIGH (重训) | 重新划分（带 sample_id）；evaluation 数字全部作废；重训 |
| API 速率失控 (Pitfall 7b) | LOW (15 min) | 降 worker；加 token bucket；从 JSONL 续跑（断点已写） |
| 6h 超时 (Pitfall 8) | LOW–MEDIUM | wandb resume + reduce eval_steps；预留 buffer 还在；最差砍 epoch（接受 Pitfall 1 风险） |

---

## Pitfall-to-Phase Mapping

> 假设 roadmap 阶段约为：(P1) 环境与 verify → (P2) data-gen → (P3) teacher-label → (P4) training → (P5) export → (P6) eval

| Pitfall | Prevention Phase(s) | Verification |
|---------|---------------------|--------------|
| 1. 模型不输出自定义标签 | P2 (prompt 不含原生 think) + P4 (loss mask + chat template 绕开) | P4 epoch 1 末 5 prompt smoke test，5/5 含 `</end_working_out></SOLUTION>` |
| 2. 教师违反硬约束 | P3 (客户端 lint + 不重试 + Responses API) | P3 拒答率监控 < 8%；3000 样本完成后全量 lint 0 false negative |
| 3. OOD val 退化 | P2 (ood_spec 形式化) + P6 (KS test) | P6 启动前每维 KS p < 0.01；训练后 OOD - 同分布 满足率差 5–15pp |
| 4. DGX Spark 训练栈崩 | P1 (verify.py + swap=0 + run_safe.sh) + P4 (SDPA 显式 + dummy 预热) | P1 verify.py 全绿；P4 step 0 < 180s；训练全程无 `libcudart.so.12` |
| 5. QLoRA→GGUF 链断 | P5 (bf16 reload merge + parity test + tokenize sanity) | P5 GGUF tokenize sanity + 20 prompt parity（greedy SOLUTION 一致） |
| 6. 评测假阳/阴 | P2 (sample_id) + P6 (trivial 排除 + 独立 grader + 统一 seed) | P6 split disjoint assert + 三变体 greedy 一致性 + p99 报告 |
| 7. API 成本/速率失控 | P3 (50-sample smoke + token bucket + Responses API + 断点续跑) | P3 50 sample 实测成本外推 < $300；429 < 1%；reasoning_tokens > 100 |
| 8. 6h 训练超时 | P4 (dry-run 100 step + budget.md 拆解 + eval loss-only) | P4 dry-run 推算 < 5h；epoch 1 wall time < 100 min |

---

## Sources

- `/home/samuel/.claude/projects/-home-samuel-TSC-CYCLE/memory/MEMORY.md` — Qwen3 tokenizer added tokens lesson（HIGH，本项目已发生事故）
- `/home/samuel/.claude/projects/-home-samuel-TSC-CYCLE/memory/debugging.md` — GRPO reward 全负根因（HIGH，本项目已发生事故）
- `/home/samuel/dgx-spark-setup/README.md` — UMA OOM、libcudart.so.12、SDPA、swap、PTX JIT（HIGH，natolambert 上游本机权威源）
- `/home/samuel/.claude/skills/dgx-spark-training/SKILL.md` — copied venv shebang、`python -m`、verify.py、run_safe.sh、systemd-run scope（HIGH）
- `/home/samuel/TSC_CYCLE/.planning/PROJECT.md` — 锁定决策（HIGH）
- `/home/samuel/TSC_CYCLE/.planning/research/STACK.md` — 训练栈版本矩阵（HIGH）
- `/home/samuel/TSC_CYCLE/reality.log` — prompt 格式与硬约束语义（HIGH，业务真值）
- [Qwen/Qwen3-4B-Thinking-2507 — HF model card](https://huggingface.co/Qwen/Qwen3-4B-Thinking-2507) — 原生 `<think>` token id 151668、官方 RL 路径（HIGH）
- [bitsandbytes Releases](https://github.com/bitsandbytes-foundation/bitsandbytes/releases) — aarch64 sm_121 PTX JIT 状态（HIGH）
- [Unsloth issue #3861](https://github.com/unslothai/unsloth/issues/3861) — GGUF wrapper >50GB bug，间接验证我们走原生 llama.cpp 路径正确（MEDIUM）
- [Qwen llama.cpp quantization guide](https://qwen.readthedocs.io/en/latest/quantization/llama.cpp.html) — Q4_K_M + imatrix（HIGH）
- [OpenAI Responses API docs](https://platform.openai.com/docs/api-reference/responses) — `reasoning.effort` 字段、`usage.reasoning_tokens`（HIGH）
- **明确未引用**：waybarrios/dgx-spark-finetune-llm（按 milestone_context 排除）

---
*Pitfalls research for: TSC-CYCLE GPT-5.5 → Qwen3-4B-Thinking-2507 distillation on DGX Spark*
*Researched: 2026-05-07*
