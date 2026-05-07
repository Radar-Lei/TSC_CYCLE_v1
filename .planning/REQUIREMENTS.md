# Requirements: TSC-CYCLE

**Defined:** 2026-05-07
**Core Value:** 学生模型在 OOD 输入上仍满足全部硬约束（min_green ≤ final ≤ max_green、整数秒、相位顺序、覆盖全相位），且数值决策接近 GPT-5.5 high 教师 — 不过拟合 reality.log。

## v1 Requirements

### Environment（ENV）— 训练环境与基础设施

- [ ] **ENV-01**: 调用 `/dgx-spark-training` skill 把 `/home/samuel/dgx-spark-setup/.venv` 克隆到 `/home/samuel/TSC_CYCLE/.venv`，注入 `scripts/dgx_spark/{env.sh,verify.py,run_safe.sh}`
- [ ] **ENV-02**: `python scripts/dgx_spark/verify.py` 全绿（CUDA 13、torch cu130、bnb、transformers、peft、trl、SDPA、Triton ptxas、swap=0）
- [ ] **ENV-03**: `flash_attn` 必须 ImportError；任何代码强制 `attn_implementation="sdpa"`，gate 在 verify 中
- [ ] **ENV-04**: 在 `pyproject.toml` 锚定增量包（`bitsandbytes==0.48.0`、`transformers>=4.56.2,<5.0`、`trl>=0.22.2`、`peft>=0.15.1`、`openai>=1.50.0`、`datasets`、`pyarrow`、`pydantic>=2`），不重装 torch / vllm
- [ ] **ENV-05**: 所有训练入口必须经由 `scripts/dgx_spark/run_safe.sh 100G --` 包裹（systemd-run scope MemoryMax=100G、MemorySwapMax=0）

### Foundations（FND）— 跨阶段共享模块

- [ ] **FND-01**: `prompt_builder.py` 单一来源，与 reality.log 协议一致，输出含 `<start_working_out>` 预填的 prompt（训练 / 教师 / 评测 三处共用）
- [ ] **FND-02**: `constraint_lint.py` 实现硬约束校验（min_green ≤ final ≤ max_green、整数、相位顺序、覆盖全相位、JSON 顶层 dict、键为字符串相位 ID）；返回结构化 violation 类型
- [ ] **FND-03**: `tokenizer_check.py` 断言自定义标签 `<start_working_out>` / `</end_working_out>` / `<SOLUTION>` / `</SOLUTION>` 都被 Qwen3-4B-Thinking-2507 tokenizer 拆成多个 sub-token；同时断言训练数据中不出现 token id 151667 / 151668（原生 `<think>` / `</think>`）
- [ ] **FND-04**: `hashing.py` 提供 `sample_id = sha256(canonical_input_json)`、`prompt_hash = sha256(prompt+model+effort)`，全程一致
- [ ] **FND-05**: `runs/{ts}/manifest.json` 记录 git sha、config hash、stage 状态、产物路径
- [ ] **FND-06**: 单元测试覆盖 prompt_builder / constraint_lint / tokenizer_check / hashing

### Data Generation（DGEN）— 合成输入

- [ ] **DGEN-01**: `distribution_fit.py` 从 `reality.log` 抽取分布先验（相位数分布、min_green / max_green / capacity 范围、pred_wait / pred_saturation 经验分布、相位组合模式），输出 `data/dist_prior.json`
- [ ] **DGEN-02**: `data/ood_spec.md` 形式化 OOD 扩展规则（更宽相位数、超出 reality.log 的 min/max 组合、稀有饱和度区间）
- [ ] **DGEN-03**: `sample_inputs.py` 生成 ~2700 条同分布输入 → `data/inputs.jsonl`，~300 条 OOD 输入 → `data/ood_inputs.jsonl`，每条带 `sample_id`
- [ ] **DGEN-04**: KS test 报告：同分布集每维 p>0.05；OOD 集每维 p<0.01（vs reality.log 经验分布）；输出 `data/dist_check_report.md`
- [ ] **DGEN-05**: 全数据集 `sample_id` 唯一无重复；trivial 样本（min == max）单独标记

### Teacher Labeling（TCH）— 教师标注

- [ ] **TCH-01**: `teacher_client.py` 派生自 EvoProgTSC `evoprog/llm/client.py` 模式：OpenAI Responses API、`model="gpt-5.5"`、`reasoning_effort="high"`、JSON Schema 结构化输出、指数退避重试、限速器（起步 ≤5 RPM）、ThreadPoolExecutor `max_workers ≤ 10`
- [ ] **TCH-02**: 每次响应必须断言 `usage.reasoning_tokens > 100`，否则视为静默降档，记录并丢弃
- [ ] **TCH-03**: `raw_responses/{prompt_hash}.json` 内容寻址缓存，atomic rename 写入；中断后续跑零损失
- [ ] **TCH-04**: 教师输出必须通过 `constraint_lint.py` 双重校验（格式 + 硬约束）；违反样本进入 `data/rejected.jsonl`，**不重试不重新生成**（避免 prompt 漂移成本失控）
- [ ] **TCH-05**: 50 样本 smoke test 在前；外推 3000 样本预算与时间，超出阈值 owner 确认
- [ ] **TCH-06**: 通过校验的样本聚合为 `data/labeled.jsonl`，包含 `sample_id` / 输入 / 教师完整响应（含思考过程）/ 解析后 SOLUTION JSON / `usage` 计费字段

### Dataset Build（DSET）— 数据集装配

- [ ] **DSET-01**: `data/labeled.jsonl` 按 `sample_id` 哈希做确定性 80/10/10 split：train / same-dist val / OOD val（OOD val 全部从 `ood_inputs.jsonl` 来源）
- [ ] **DSET-02**: train val 与 train 之间 `sample_id` 严格不重叠；OOD val 同源去重
- [ ] **DSET-03**: 一次性 tokenize → arrow（`data/tokenized/{train,val_id,val_ood}/`）；`max_length` 按 p99 实测设
- [ ] **DSET-04**: tokenize 阶段断言 `tokenizer_check` 全绿；assistant 段以外 `labels=-100`（loss masking 只算 assistant）
- [ ] **DSET-05**: 写 `data/dataset_card.md`：split 大小、token 长度分布、phase_count 分布、OOD 维度

### Training（TRN）— QLoRA SFT

- [ ] **TRN-01**: 学生基座 `Qwen/Qwen3-4B-Thinking-2507`；4-bit NF4 加载（bitsandbytes 0.48.0）；LoRA `r=64, alpha=128`，target_modules 覆盖 Q/K/V/O + gate/up/down
- [ ] **TRN-02**: **绕开** `tokenizer.apply_chat_template`；纯 raw text 拼接（system + user + 预填 `<start_working_out>` 作为 assistant 起手），避免 chat_template 注入原生 `<think>`
- [ ] **TRN-03**: 训练入口 boot 时跑 `tokenizer_check`（FND-03），失败立即退出
- [ ] **TRN-04**: TRL `SFTTrainer`：`bf16=True`、`packing=False`、`padding_side="right"`、`per_device_train_batch_size=4`、`gradient_accumulation_steps=8`、`gradient_checkpointing` 非 reentrant、`dataloader_num_workers=1`、`num_train_epochs=2`（首 epoch 末 smoke 决定是否升 3）
- [ ] **TRN-05**: bnb dummy forward 预热（吃掉 sm_121 PTX JIT 首步惩罚）；100 step dry-run 测速，外推单 epoch wall time，超 2.5h 自动收 batch / max_length
- [ ] **TRN-06**: 首 epoch 末 5 prompt smoke test：自定义标签闭合率 ≥80%、无 `<think>` token id 出现；不达标记录并提示加 epoch
- [ ] **TRN-07**: `loss_only` eval（避免 generate 把训练拖进 10h+）；`save_strategy="epoch"`、`save_total_limit=2`
- [ ] **TRN-08**: 训练全程在 `run_safe.sh 100G --` 包裹内运行；端到端单次 ≤6h

### Export（EXP）— Merge 与 GGUF 量化

- [x] **EXP-01**: merge 前 reload base model bf16 全精度（**不是** 4-bit），合并 LoRA 后 `save_pretrained` 到 `runs/{ts}/merged_bf16/`
- [x] **EXP-02**: 用本机 `EvoProgTSC/llama.cpp/convert_hf_to_gguf.py` 转 bf16 GGUF（`Qwen3ForCausalLM` 已注册 line 4551）；产出 `runs/{ts}/gguf/model.bf16.gguf`
- [x] **EXP-03**: 用本机 `EvoProgTSC/llama.cpp/build/bin/llama-quantize` 量化为 Q4_K_M（preset 15）；产出 `runs/{ts}/gguf/model.q4_K_M.gguf`
- [x] **EXP-04**: GGUF tokenize sanity：自定义标签 sub-token 与 HF tokenizer 一致
- [x] **EXP-05**: 20 prompt greedy parity 测试（HF bf16 vs GGUF bf16 vs GGUF q4_K_M），同 seed=42；q4_K_M MAE>3s 触发 imatrix 重量化预案 ⚠ MAE=4.51s, imatrix backlog

### Evaluation（EVL）— 评测套件

- [ ] **EVL-01**: 三 backend runner（HF bf16 / GGUF fp16 / GGUF q4_K_M），共用 prompt_builder + 同 seed greedy；生成结果写 `gen_cache/{variant}/{sample_id}.json`
- [ ] **EVL-02**: 在 same-dist val 与 OOD val 上跑（共 600 prompt × 3 variant = 1800 generations）
- [ ] **EVL-03**: 指标 1 — 硬约束满足率（`constraint_lint` 直接复用），按 phase_count 分桶；trivial 样本（min==max）单独排除后再报
- [ ] **EVL-04**: 指标 2 — 与教师 final 的 MAE / 完全一致率（hold-out 的教师标签）
- [ ] **EVL-05**: 指标 3 — OOD 泛化 gap（同分布 val vs OOD val 上的指标 1/2 差距）；按 OOD 维度（相位数 / 范围 / 饱和度）分桶
- [ ] **EVL-06**: 指标 4 — Reasoning 引用质量（自动检测思考内容中是否出现 `pred_saturation` / `min_green` / `max_green` / `pred_wait` 等关键字段名 + 数值；规则式打分，不依赖另一个 LLM）
- [ ] **EVL-07**: `report.md` 输出 4 指标 × 3 variant × 2 split 矩阵 + p99 + 失败案例 top-20 + 量化退化结论
- [ ] **EVL-08**: 部署 go/no-go gate：q4_K_M 在 OOD val 硬约束满足率 ≥ HF bf16 的 95%；否则启用 imatrix 重量化或回退 fp16 部署

## v2 Requirements

### Reinforcement Learning（RL）

- **RL-01**: 在 SFT checkpoint 之上跑 GRPO，针对硬约束满足率 / 教师 MAE 设计 reward
- **RL-02**: 多种 reward 配方对比（约束 only / 约束+MAE / 约束+MAE+reasoning 关键字）

### Self-Consistency / 多教师

- **SC-01**: 教师对同一 prompt 生成 K 个候选，取一致性最高者作为标签
- **SC-02**: 评估教师 self-consistency 与 student 一致性的相关性

### 多档量化

- **Q-01**: 增加 Q5_K_M / Q8_0 / IQ4_XS 等量化档位的 parity 评测
- **Q-02**: imatrix 校准集自动生成 + 重量化流水线

### 部署与服务化

- **DEP-01**: 通过 llama.cpp server 起 TSC 决策端点，集成到 EvoProgTSC
- **DEP-02**: 推理期 `--logit-bias` 屏蔽原生 `<think>` 151667/151668（如评测显示泄漏）

## Out of Scope

| Feature | Reason |
|---------|--------|
| 在线 / RL 优化（GRPO 等） | 本里程碑只做 SFT 蒸馏；RL 进 v2 |
| 教师改用其他 API（Claude / Gemini / 本地模型） | 锁定 GPT-5.5 high；reasoning_effort 不降档 |
| 把 reality.log 的 `<SOLUTION>` 当作训练标签 | 旧 lmstudio 教师有偏；教师为准 |
| Qwen3.5-4B / Qwen3.6 系列 | Qwen3.5-4B 架构新（GatedDeltaNet+MoE）DGX Spark 训练栈未验证；Qwen3.6 没有 4B |
| 模型原生 `<think>...</think>` 标签 | 与 memory 验证过的自定义标签方案冲突；reality.log 已是自定义标签 |
| 全参 SFT（fp16/bf16 全量微调） | 显存与 6h 预算下 QLoRA r=64 更稳；如效果不满意再升级 |
| vLLM 推理 / 部署 | 用户明确 "暂时没法使用 vllm"；最终走 llama.cpp / GGUF |
| Unsloth 训练栈 | 与原生 TRL+PEFT 重合度高、闭源调试链长；natolambert dgx-spark-setup 已锚定原生栈 |
| flash-attn cu12 / cu13 | aarch64 GB10 不可用；强制 SDPA |
| waybarrios/dgx-spark-finetune-llm 参考 | 用户明确排除（NVFP4/TRT-LLM 路径与 GGUF 目标不重合） |
| 教师约束违反样本重新生成 | 重试会加剧成本与 prompt 漂移；违反即丢弃 |
| imatrix 默认开启 | 仅在 q4_K_M parity MAE>3s 时触发 |
| TensorBoard / WandB 等可视化平台集成 | 首轮只要 train_log + report.md；可视化进 v2 |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| ENV-01 | Phase 1 | Pending |
| ENV-02 | Phase 1 | Pending |
| ENV-03 | Phase 1 | Pending |
| ENV-04 | Phase 1 | Pending |
| ENV-05 | Phase 1 | Pending |
| FND-01 | Phase 1 | Pending |
| FND-02 | Phase 1 | Pending |
| FND-03 | Phase 1 | Pending |
| FND-04 | Phase 1 | Pending |
| FND-05 | Phase 1 | Pending |
| FND-06 | Phase 1 | Pending |
| DGEN-01 | Phase 2 | Pending |
| DGEN-02 | Phase 2 | Pending |
| DGEN-03 | Phase 2 | Pending |
| DGEN-04 | Phase 2 | Pending |
| DGEN-05 | Phase 2 | Pending |
| TCH-01 | Phase 3 | Pending |
| TCH-02 | Phase 3 | Pending |
| TCH-03 | Phase 3 | Pending |
| TCH-04 | Phase 3 | Pending |
| TCH-05 | Phase 3 | Pending |
| TCH-06 | Phase 3 | Pending |
| DSET-01 | Phase 4 | Pending |
| DSET-02 | Phase 4 | Pending |
| DSET-03 | Phase 4 | Pending |
| DSET-04 | Phase 4 | Pending |
| DSET-05 | Phase 4 | Pending |
| TRN-01 | Phase 4 | Pending |
| TRN-02 | Phase 4 | Pending |
| TRN-03 | Phase 4 | Pending |
| TRN-04 | Phase 4 | Pending |
| TRN-05 | Phase 4 | Pending |
| TRN-06 | Phase 4 | Pending |
| TRN-07 | Phase 4 | Pending |
| TRN-08 | Phase 4 | Pending |
| EXP-01 | Phase 5 | Done |
| EXP-02 | Phase 5 | Done |
| EXP-03 | Phase 5 | Done |
| EXP-04 | Phase 5 | Done |
| EXP-05 | Phase 5 | Done (FLAG: imatrix backlog) |
| EVL-01 | Phase 6 | Pending |
| EVL-02 | Phase 6 | Pending |
| EVL-03 | Phase 6 | Pending |
| EVL-04 | Phase 6 | Pending |
| EVL-05 | Phase 6 | Pending |
| EVL-06 | Phase 6 | Pending |
| EVL-07 | Phase 6 | Pending |
| EVL-08 | Phase 6 | Pending |

**Coverage:**
- v1 requirements: 47 total
- Mapped to phases: 47 ✓
- Unmapped: 0 ✓

---
*Requirements defined: 2026-05-07*
*Last updated: 2026-05-07 after roadmap creation (per-REQ-ID traceability finalized)*
