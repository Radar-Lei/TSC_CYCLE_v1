# Feature Landscape — TSC-CYCLE 蒸馏端到端流水线

**Domain:** GPT-5.5 high → Qwen3-4B-Thinking-2507 SFT 蒸馏（TSC 周期绿灯时长决策）
**Researched:** 2026-05-07
**Scope:** 单里程碑闭环（合成数据生成 → 教师标注 → 数据集装配 → QLoRA SFT → Merge/GGUF 导出 → 评测）

---

## Table Stakes（缺一项流水线无法跑通或无法验证 Core Value）

用户期望：跑完流水线就能拿到一个可部署的 GGUF，且数值合理、硬约束 100% 满足。任何下面缺项都会让"端到端"破洞。

### 1. 合成数据生成器（subsystem 1）

| Feature | 用户期望 | 复杂度 | 依赖 |
|---------|---------|--------|------|
| **从 reality.log 抽取分布先验** | 解析 `type=prompt` 日志条目，统计相位数、min/max_green、capacity、pred_wait、pred_saturation 的边际分布与组合模式 | Low | reality.log 解析器 |
| **可采样的输入生成器** | 给定样本数 N，按经验分布采样合法的 `phase_waits[]`；保证 `min_green < max_green`、`pred_saturation ≈ pred_wait / capacity` 的物理一致性 | Medium | 上一项 |
| **OOD 扩展策略** | 显式参数化 OOD：相位数 ∈ {2,3,4,5,6}（reality.log 仅 4）、min/max_green 范围扩展 ±50%、pred_saturation 扩展到 [0, 0.6]、相位间不对称组合 | Medium | 上一项 |
| **去重与 ID 分配** | 输入哈希去重（防止教师重复标注同一输入）；每条样本带唯一 `sample_id` | Low | — |
| **生成器自带 lint** | 生成时校验：min < max、整数 min/max、pred_wait≥0、capacity>0；生成失败的样本丢弃重采 | Low | — |

### 2. 教师标注客户端（subsystem 2）

| Feature | 用户期望 | 复杂度 | 依赖 |
|---------|---------|--------|------|
| **OpenAI 客户端封装** | 复用 EvoProgTSC `client.py` 模式：`reasoning_effort=high`、固定模型 `gpt-5.5`、固定 system+user prompt 模板（与 reality.log 完全一致） | Low | EvoProgTSC.client |
| **并发控制（≤10 worker）** | `concurrent.futures.ThreadPoolExecutor` 或 asyncio semaphore 限流到 10；不超过 API RPM/TPM | Low | — |
| **指数退避重试** | 429/5xx/超时自动重试，至少 3 次，base=2s，jitter；区分可重试与永久错误 | Low | — |
| **JSON-Schema 结构化输出（如可用）** | 优先用 `response_format=json_schema` 强约束；不可用则 fallback 到正则提取 | Low | OpenAI SDK 版本 |
| **输出格式校验** | 必须包含 `<start_working_out>...</end_working_out>` 后接 `<SOLUTION>{json}</SOLUTION>`；缺标签或顺序错误 → 标记为 `format_invalid` | Low | — |
| **硬约束 lint** | 解析 SOLUTION JSON 后逐相位校验：键集合 = phase_ids、值是整数、min ≤ value ≤ max；任一不满足 → 标记 `constraint_invalid` | Low | — |
| **失败重新标注** | `format_invalid` / `constraint_invalid` 自动重新调用一次教师（最多 N=2 次再标）；最终仍失败则丢弃并记录到 `rejects.jsonl` | Medium | 上两项 |
| **断点续跑 / 幂等** | 已成功的 sample_id 跳过；中断后重启不重复消耗 API 配额 | Medium | sample_id |
| **API 成本/调用日志** | 每次调用记录 input/output tokens、reasoning tokens、耗时；汇总打印总成本估算 | Low | — |

### 3. 数据集装配（subsystem 3）

| Feature | 用户期望 | 复杂度 | 依赖 |
|---------|---------|--------|------|
| **JSONL 在盘格式** | 每行一个样本：`{sample_id, input_json, prompt_text, teacher_reasoning, teacher_solution, split, source}` | Low | subsystem 2 |
| **80/10/10 split** | 80% train / 10% in-distribution val / 10% OOD val；OOD val 必须从"OOD 标记"的输入子集划入，不可随机污染 | Low | OOD 标记字段 |
| **Split 确定性** | 用 `sample_id` 哈希分桶 + 固定随机种子，复跑可复现 | Low | — |
| **训练样本拼装** | 把 input prompt（与 reality.log 严格一致的 system+user）+ 教师 `<start_working_out>...</end_working_out><SOLUTION>...</SOLUTION>` 拼成完整 chat-template 文本；记录 prompt boundary 用于 loss masking | Medium | 自定义 chat template |
| **数据统计报表** | 生成时打印：每 split 数量、相位数分布、min/max_green 分布、教师拒绝率 | Low | — |

### 4. 训练循环（subsystem 4）

| Feature | 用户期望 | 复杂度 | 依赖 |
|---------|---------|--------|------|
| **Qwen3-4B-Thinking-2507 加载** | HF Transformers + bitsandbytes 4-bit 量化加载（QLoRA 标准）；DGX Spark aarch64 走 SDPA 注意力（禁用 flash-attn） | Medium | dgx-spark venv |
| **Tokenizer 安全校验** | 启动时 assert：`<start_working_out>` 等 4 个标签都被拆成 ≥2 sub-tokens、且不命中 151667/151668；任一失败立即中止训练 | Low | — |
| **自定义 chat template** | 不使用 Qwen3 原生 `<think>` 模板；自己拼装 system+user→assistant，assistant 端用自定义标签包裹 | Medium | subsystem 3 |
| **Loss masking（prompt 不计 loss）** | 仅在 assistant 段（含两对自定义标签）反传 loss，prompt 段 label=-100 | Medium | chat template |
| **QLoRA r=64 配置** | LoRA r=64, alpha=128, dropout=0.05, target_modules=all-linear 或 q/k/v/o + gate/up/down；optimizer=paged_adamw_8bit | Medium | — |
| **2 epochs 训练** | memory 验证 1 epoch 不够；首轮固定 2 epochs；lr=2e-4 cosine、warmup_ratio=0.03 | Low | — |
| **Checkpoint 保存** | 每 epoch 末尾 + 最佳 val loss 各保存一份；可恢复训练 | Low | — |
| **Val loss 评估** | 每 epoch 末跑 in-distribution val 的 loss + 1 batch 生成样本（人眼/正则核对格式） | Low | — |
| **6h 时间预算守护** | 训练日志带 ETA；预估超 6h 时打印告警 | Low | — |

### 5. Merge + 导出（subsystem 5）

| Feature | 用户期望 | 复杂度 | 依赖 |
|---------|---------|--------|------|
| **LoRA merge → fp16 HF** | `peft.merge_and_unload()` → `save_pretrained(safe_serialization=True)`；保存 tokenizer + chat_template | Low | subsystem 4 |
| **llama.cpp fp16 GGUF 转换** | 调 `convert_hf_to_gguf.py --outtype f16`；复用 EvoProgTSC 已 build 的 cuda llama.cpp | Low | llama.cpp build |
| **q4_K_M 量化** | `llama-quantize fp16.gguf q4_K_M.gguf q4_K_M`；保留 fp16 原文件 | Low | 上一项 |
| **冒烟推理验证** | 导出后用 `llama-cli` 跑 1 条 reality.log 输入，肉眼确认输出 `<start_working_out>...</end_working_out><SOLUTION>{...}</SOLUTION>` 完整 | Low | — |

### 6. 评测套件（subsystem 6）

| Feature | 用户期望 | 复杂度 | 依赖 |
|---------|---------|--------|------|
| **评测引擎抽象** | 同一份评测代码可对 (a) HF fp16、(b) GGUF fp16、(c) GGUF q4_K_M 三种 backend 跑 | Medium | subsystem 5 |
| **硬约束满足率** | 在 in-dist val + OOD val 上：解析输出 → JSON → 逐相位校验 4 条硬约束（min/max/integer/phase 覆盖）→ 输出 % 通过 | Low | constraint linter（与 subsystem 2 共用） |
| **MAE vs 教师** | 仅在 hard-constraint 通过的样本上计算每相位 `|student_final - teacher_final|` 的均值/分位数 | Low | — |
| **OOD 性能** | OOD val 单独报一份指标，与 in-dist 分开对比，量化泛化 gap | Low | OOD split |
| **Reasoning 引用质量** | 解析 `<start_working_out>...</end_working_out>`，正则/关键字检测是否引用 `pred_saturation` / `min_green` / `max_green` 等关键字段；输出引用率 % | Medium | — |
| **fp16 vs q4_K_M 对比** | 同一 val 集分别评，输出量化前后 4 项指标的差值；用于判定是否量化崩塌 | Low | 上面所有项 |
| **评测报告 markdown** | 一键生成 `eval_report.md`，包含表格 + 失败样本前 10 个 | Low | — |

---

## Differentiators（提升质量、可复现、可观测）

用户期望：第二轮迭代/调试时不抓瞎、能复现、能定位问题。

| Feature | 价值 | 复杂度 | 优先级 |
|---------|------|--------|--------|
| **全局随机种子** | numpy/torch/random/transformers 一处设种；数据采样、split、训练初始化都种好 | Low | High |
| **运行配置版本化** | 每次 run 落盘 `config.yaml`（数据规模、教师模型版本、QLoRA 超参、git commit hash） | Low | High |
| **Run 目录约定** | `runs/{timestamp}_{git_sha}/` 内含 config / dataset 引用 / ckpts / eval_report；不污染仓库根 | Low | High |
| **结构化日志** | JSONL 日志（数据生成 / 教师标注 / 训练 step / 评测）；可 grep/jq | Low | Medium |
| **教师 cache 层** | 输入 hash → 教师输出本地 KV 存储（jsonl/sqlite）；同一输入再调直接命中 | Medium | Medium |
| **数据卡 / 数据集 README** | 数据生成完后自动写 `dataset_card.md`：分布直方图、相位数计数、教师拒绝率 | Low | Medium |
| **Tokenizer 单元测试** | pytest 检查 4 个自定义标签的拆分行为 + 不命中 Qwen3 added tokens；CI/pre-train hook | Low | High |
| **OOD 分层评测** | OOD val 内部按"扰动维度"再分层（相位数 OOD / 范围 OOD / 饱和度 OOD），分别报指标 | Medium | Medium |
| **教师答案的 self-consistency 子集** | 对一小部分（~50）样本让教师标 3 次，挑选硬约束都满足且 SOLUTION 完全一致的版本；增强标签质量 | Medium | Low |
| **训练曲线监控** | TensorBoard 或简单 matplotlib 把 train/val loss 画出来，回头排查过拟合 | Low | Medium |
| **生成期 sanity 抽查** | 训练中每 N step 用 fixed prompt 抽样生成一条，落盘到 `gen_samples.jsonl`，肉眼可读 | Low | Medium |
| **失败样本归档** | 教师拒绝、学生硬约束失败的样本单独存档到 `rejects/`，便于后续诊断分布 | Low | Medium |
| **GGUF 量化分级对比（可选）** | 顺手再导一份 q5_K_M / q8_0 做对比，找最佳精度/体积权衡点 | Low | Low |

---

## Anti-Features（明确不做，列出来是为了防止偷偷加进 scope）

| Anti-Feature | 不做的原因 | 替代做法 |
|--------------|-----------|---------|
| **使用 Qwen3 原生 `<think>...</think>` 标签** | memory 已验证：151667/151668 是 added tokens，预训练有先入语义，自定义占用会导致输出乱码 | 一律用 `<start_working_out>` / `<end_working_out>` / `<SOLUTION>` / `</SOLUTION>` |
| **GRPO / RL 微调** | PROJECT.md 显式 Out of Scope；本里程碑只蒸馏 SFT；reward 函数和稳定性留给后续 | 仅 SFT；下次里程碑再考虑 GRPO |
| **vLLM 部署/推理** | 本机环境不支持 vLLM（CLAUDE.md 明确） | llama.cpp / GGUF |
| **flash-attn CUDA 12 wheels** | DGX Spark GB10 是 aarch64 + CUDA 13，flash-attn 不兼容 | SDPA / Triton |
| **全参 SFT** | 6h + 显存预算下 QLoRA r=64 已足够；全参收益不确定 | QLoRA r=64 |
| **用 reality.log 的 `<SOLUTION>` 当训练标签** | 旧 lmstudio 教师有偏，会让学生学到错误先验 | 一律用新 GPT-5.5 high 标注 |
| **直接在 reality.log 输入上训练（不扩展）** | 分布太窄，无法满足 OOD Core Value | 必须采样 + OOD 扩展 |
| **多教师 ensemble / 切换其它 API** | PROJECT.md 锁定 GPT-5.5 high；引入第二个教师会引入分布噪声 | 单教师 |
| **降低 reasoning_effort** | 蒸馏只在最强教师上有最大收益 | 固定 high |
| **训练时下采样标签 token / 修剪 reasoning 长度** | 思考链是要学的核心；裁剪会破坏蒸馏价值 | 不裁剪，max_seq_len 调大即可 |
| **Qwen3.5-4B / Qwen3.6 学生** | 架构兼容性未验证（GatedDeltaNet+MoE）；3.6 没 4B | 锁定 Qwen3-4B-Thinking-2507 |
| **训练时即时调用教师（online distillation）** | 增加 API 依赖，不可复现，且无法批训练 | offline：先标注存盘再训练 |
| **超过 3000 样本的首轮规模** | 预算/时间设计点；先打通闭环 | 首轮 3000，之后扩量 |
| **Web UI / 图形化数据查看器** | scope 蔓延 | jupyter notebook 或 jsonl + jq |
| **多 GPU 分布式训练** | DGX Spark 单机；QLoRA 4B 单卡足够 | 单卡 |
| **DPO / KTO 偏好学习** | 与本里程碑无关 | 不做 |

---

## Feature Dependencies

```
[reality.log 解析]
        ↓
[分布先验] ──→ [合成输入生成器] ──→ [输入 lint]
                                         ↓
                                  [教师标注客户端]
                                  ├── prompt 模板（与 reality.log 一致）
                                  ├── 并发/重试
                                  └── 输出格式 + 硬约束 lint  ←──┐
                                         ↓                       │
                                  [JSONL 数据集 + 80/10/10 split]│
                                         ↓                       │
                  [tokenizer 安全检查]──→[chat template 拼装]    │
                                         ↓                       │
                                  [QLoRA r=64 SFT 训练]          │
                                         ↓                       │
                                  [LoRA merge → fp16 HF]         │
                                         ↓                       │
                              [llama.cpp GGUF fp16 → q4_K_M]     │
                                         ↓                       │
                                  [评测套件]──────────────────────┘
                                  共用：constraint linter
```

**关键依赖**：
- 评测的"硬约束满足率"模块 **必须复用** 教师标注客户端的 lint 代码 → 单一真理源（`constraints.py`）
- 训练的 chat template 与教师 prompt 模板必须严格同步 → 抽到 `prompts.py` 共用
- 教师 cache、sample_id、split 都依赖同一份 input hash 算法 → 抽到 `hashing.py` 共用
- Tokenizer 安全检查在数据装配 + 训练 + 评测三处都要跑（fail-fast）

---

## MVP Recommendation

**首轮必须打通的最小闭环（Table Stakes 全部 + 极少量 Differentiator）**：

1. reality.log 解析 → 合成输入生成器（含 OOD 扩展）
2. 教师并发标注 + 双重 lint（格式 + 硬约束）+ cache（differentiator，但教师调用贵，必上）
3. JSONL 数据集 + 确定性 80/10/10 split
4. Tokenizer 安全测试（pytest）
5. QLoRA r=64 + 自定义 chat template + loss masking + 2 epochs
6. Merge → fp16 HF → GGUF fp16 → q4_K_M
7. 评测套件 4 项 × (fp16, q4_K_M) 两 backend
8. Run 目录约定 + config 落盘（differentiator，复跑必备）

**首轮可推迟的 differentiators**：
- 教师 self-consistency 多次采样（先用单次教师答案验证流水线）
- OOD 分层评测（先看总体 OOD 指标，再细分）
- TensorBoard / 训练曲线（用日志 + matplotlib 事后画即可）
- q5_K_M / q8_0 多档量化（首轮只导 fp16 + q4_K_M）

**首轮明确不做（已在 Anti-Features）**：GRPO、原生 `<think>`、vLLM、全参、reality.log 标签、多教师。

---

## Sources

- `/home/samuel/TSC_CYCLE/.planning/PROJECT.md`（项目定义、约束、Out of Scope）
- `/home/samuel/TSC_CYCLE/reality.log`（prompt 与输出协议真值）
- `/home/samuel/.claude/projects/-home-samuel-TSC-CYCLE/memory/MEMORY.md`（Qwen3 tokenizer 教训、2 epochs 经验）
- `/home/samuel/.claude/CLAUDE.md`（DGX Spark / 无 vLLM 约束）
- EvoProgTSC `evoprog/llm/client.py`（教师客户端可复用模式）
- `/home/samuel/dgx-spark-setup` + `/dgx-spark-training` skill（DGX Spark 训练栈唯一权威源；上游 natolambert/dgx-spark-setup）

**Confidence: HIGH** — 所有特征都基于 PROJECT.md 显式 Active Requirements / Constraints / Out of Scope 反推；Anti-features 全部在 PROJECT.md 中显式列出；表设计与现有 memory（tokenizer、2 epochs）和 reality.log 实测协议对齐。
