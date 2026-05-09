# Milestone v3.0 Requirements — 9B 基座切换

**Version:** v3.0
**Goal:** 把学生模型基座从 Qwen3-4B-Thinking-2507 切换到 Qwen3.5-9B，配套扩展训练数据到 10K 规模，重做端到端蒸馏 pipeline，证明 9B 学生在硬约束/教师 MAE/思考格式稳定性上相对 v1.0 baseline 有可验证提升或证明 4B 已是甜点。
**Created:** 2026-05-08

---

## v3.0 Requirements

### ENV — 环境验证（沿用 /dgx-spark-training v1.0 已验证栈）

- [ ] **ENV-01**: 本机 `/home/samuel/TSC_CYCLE/.venv` 加载 `Qwen/Qwen3.5-9B` 成功（`Qwen3_5ForCausalLM` + bnb 4-bit NF4 + SDPA forward smoke pass）
- [ ] **ENV-02**: 本机 `/home/samuel/projects/EvoProgTSC/llama.cpp` micro-convert dry-run pass（dummy LoRA → bf16 GGUF → q4_K_M GGUF → llama-cli 推理 5 token 无 segfault）
- [ ] **ENV-03**: 训练运行严格在 `systemd-run --scope -p MemoryMax=100G -p MemorySwapMax=0` 内，swap 关闭

### TOK — Tokenizer 兼容性硬门禁

- [ ] **TOK-01**: 4 个自定义思考标签（`<start_working_out>` / `<end_working_out>` / `<SOLUTION>` / `</SOLUTION>`）在 Qwen3.5 tokenizer 下均拆为 ≥3 sub-tokens（不被 248K vocab BPE merge 合并成单 token）
- [ ] **TOK-02**: 动态查表 native `<think>` / `</think>` 在 Qwen3.5 vocab 中的 token id 写入 `tokenizer_audit.json`，禁止硬编码 v1.0 的 151667/151668
- [x] **TOK-03**: HF `AutoTokenizer.encode` ↔ `llama-tokenize` 在 100 个测试 prompt 上 100% parity
- [ ] **TOK-04**: 训练数据组装绕开 chat_template，raw text 直接拼 `<start_working_out>...`（避免 native `<think>` 注入）

### MEM — 显存预算实测

- [ ] **MEM-01**: `memory_budget_v3.py` 实测 5 候选 max_seq_length ∈ {1536, 2048, 2560, 3072, 4096} 下的 peak memory；选 peak<85GB 最大值作为训练配置
- [ ] **MEM-02**: 9B + r=64 LoRA + bs=1 + grad_ckpt(use_reentrant=False) 训练 100 steps 在 100GB cap 内不 OOM
- [ ] **MEM-03**: 用 `Qwen3_5ForCausalLM` 而非 `Qwen3_5ForConditionalGeneration` 加载（跳过 vision tower，断言加载后 `model.named_parameters()` 不含 `vision*` 名空间）

### DATAGEN — 数据扩量到 10K（GPT-5.5 high 教师只标新增 7K）

- [x] **DATAGEN-01**: 合成输入生成器扩展分布到三类：(a) 同分布密集填充 (b) OOD / 边界（min_green<15s, max_green>120s, 极端饱和度等）(c) v1.0 高 MAE / lint reject targeted 案例
- [x] **DATAGEN-02**: 生成 ≥7K 新输入（去重后），与 v1.0 现有 3K 不重叠
- [x] **DATAGEN-03**: GPT-5.5 high + reasoning_effort="high"，并发 ≤10 worker，指数退避，复用 `EvoProgTSC/client.py` 既有重试/降级逻辑
- [x] **DATAGEN-04**: 教师输出过硬约束 lint（min_green ≤ final ≤ max_green、整数秒、相位顺序、覆盖全相位）；lint 失败样本丢弃不重生成
- [x] **DATAGEN-05**: 进度持久化 JSONL append；支持断点续跑（不重复调用 GPT-5.5）
- [x] **DATAGEN-06**: v3.0 训练集 = v1.0 valid `labeled.jsonl` (read-only) ∪ 新增 lint pass samples，目标 ≥9000 valid samples
- [x] **DATAGEN-07**: v1.0 `data/labeled.jsonl` 内容字节级不变（git diff clean，仅以 read-only mount 方式被引用）

### DATA — 训练数据集构建

- [x] **DATA-01**: 80/10/10 split (train/val/ood_val)，seed=42；OOD val 包含 v1.0 OOD val 全集 + 新增 OOD subset，便于跨里程碑可比 subset 评测
- [x] **DATA-02**: retokenize 用 Qwen3.5 tokenizer，输出到 `data/tokenized/v3/{train,val,ood_val}.arrow`
- [x] **DATA-03**: 截断率 ≤5%（max_seq_length 由 MEM-01 决定）
- [x] **DATA-04**: split 索引文件持久化（含哈希），便于评测复现

### SFT — QLoRA 训练（batch_size=1，跑到收敛）

- [x] **SFT-01**: QLoRA r=64, alpha=64, lora_dropout=0.0, target_modules="all-linear"（覆盖 GatedDeltaNet 24 linear-attention 层 + 8 full-attention 层全部 projections）
- [x] **SFT-02**: lr=1e-4 (cosine schedule with warmup), max_grad_norm=0.5, optimizer=`adamw_torch_fused`（避免 paged_adamw_8bit underflow）
- [x] **SFT-03**: batch_size=1 + gradient_accumulation_steps=16 (effective batch 16); packing=False; gradient_checkpointing(use_reentrant=False)
- [x] **SFT-04**: 500-sample 1h dry-run early-exit gate：OOD 硬约束满足率 ≥95% 才进全量训练；否则 abort 调参
- [x] **SFT-05**: 全量训练**不设 6h 上限**，启用 early-stopping callback（val loss patience=3，监控间隔 200 steps）；最大 epoch 上限 5
- [x] **SFT-06**: 训练 200 steps 后 grad_norm p99<3.0 且无 NaN；任一断言失败立即 abort
- [x] **SFT-07**: run artifact 命名隔离 `runs/v3.0-9B-{utc_timestamp}/`；wandb project=`tsc-cycle-v3-9b`（与 v1.0 隔离）
- [x] **SFT-08**: v1.0 production artifact `runs/20260507T032419Z/` 标记 FROZEN.md + `chmod -w`，禁止 v3.0 流程触碰

### GGUF — 导出 + 量化（imatrix 必跑）

- [ ] **GGUF-01**: LoRA → merge → bf16 HF safetensors → fp16 GGUF（`convert_hf_to_gguf.py`）→ q4_K_M GGUF（`llama-quantize`）全链路 pass
- [ ] **GGUF-02**: imatrix 校准必跑（v3.0 升为强制；GatedDeltaNet 24/32 层 q4_K_M 保真度未在 v1.0 dense 模型上验证）；imatrix 校准集 100-200 样本来自训练集
- [ ] **GGUF-03**: 5-prompt smoke 三精度（HF bf16 / fp16 GGUF / q4_K_M GGUF）均生成合法 SOLUTION 段（含完整思考起止标签）
- [ ] **GGUF-04**: HF tokenize ↔ llama-tokenize parity 验证（与 TOK-03 共用 fixture）
- [ ] **GGUF-05**: q4_K_M 崩塌时 fallback 路径明确：升级到 q5_K_M（+25% size）

### EVAL — 4 variant matrix + 三阈值决策门

- [ ] **EVAL-01**: 4 variant matrix 评测：(a) hf_bf16_v3 (b) gguf_q4_v3 (c) gguf_q4_v1_baseline（read-only mount，不重跑）(d) optional gguf_fp16_v3
- [ ] **EVAL-02**: v1.0 baseline 的 generation cache 直接 mount 引用，禁止重新生成（保持跨里程碑严格可比）
- [ ] **EVAL-03**: 决策门三阈值并存：`q4_v3 vs fp16_v3 ≥ 0.95` ∧ `q4_v3 vs q4_v1 ≥ 1.00` ∧ `q4_v3 hard_constraint_pass ≥ 98%`
- [ ] **EVAL-04**: 报告含 v3-v1 差值 + 95% bootstrap CI + p99/max-abs tail metrics（不只看均值）
- [ ] **EVAL-05**: `decision.md` 给出 GO / NO-GO / 用户决策三态结论；NO-GO 可能意味"4B 已是甜点"，是有效里程碑产出

---

## Future Requirements

- 在线 / RL 优化（GRPO 等）— v4.0 候选
- 自动化 q4_K_M → q5_K_M 量化分级（基于评测结果自动 fallback）
- thinking on-off 双跑评测（量化 reasoning 模式对决策的边际收益）

## Out of Scope

- Qwen3.6 系列基座（系列最小 27B，与"小模型本地部署"Core Value 冲突）
- 模型原生 `<think>...</think>` 标签（v1.0 已验证语义冲突）
- 全参 SFT（9B 在 100GB 不可行）
- vLLM 推理（本机不可用）
- 引入新训练栈（Unsloth on Spark / Axolotl / 升级 PyTorch）
- batch_size > 1（用户明确锁定）
- 重新标注 v1.0 已 lint pass 的 3K 老数据（保跨里程碑可比 + 控成本）
- 教师改用别家 API（锁 GPT-5.5 high）

## Traceability

All 39 v3.0 requirements mapped to exactly one phase. Coverage: 39/39 ✓

| REQ ID | Phase | Status |
|--------|-------|--------|
| ENV-01 | Phase 1 | Pending |
| ENV-02 | Phase 1 | Pending |
| ENV-03 | Phase 1 | Pending |
| TOK-01 | Phase 1 | Pending |
| TOK-02 | Phase 1 | Pending |
| TOK-03 | Phase 1 | Complete |
| TOK-04 | Phase 1 | Pending |
| MEM-01 | Phase 1 | Pending |
| MEM-02 | Phase 1 | Pending |
| MEM-03 | Phase 1 | Pending |
| DATAGEN-01 | Phase 2 | Complete |
| DATAGEN-02 | Phase 2 | Complete |
| DATAGEN-03 | Phase 2 | Complete |
| DATAGEN-04 | Phase 2 | Complete |
| DATAGEN-05 | Phase 2 | Complete |
| DATAGEN-06 | Phase 2 | Complete |
| DATAGEN-07 | Phase 2 | Complete |
| DATA-01 | Phase 3 | Complete |
| DATA-02 | Phase 3 | Complete |
| DATA-03 | Phase 3 | Complete |
| DATA-04 | Phase 3 | Complete |
| SFT-01 | Phase 4 | Complete |
| SFT-02 | Phase 4 | Complete |
| SFT-03 | Phase 4 | Complete |
| SFT-04 | Phase 4 | Complete |
| SFT-05 | Phase 4 | Complete |
| SFT-06 | Phase 4 | Complete |
| SFT-07 | Phase 4 | Complete |
| SFT-08 | Phase 4 | Complete |
| GGUF-01 | Phase 5 | Pending |
| GGUF-02 | Phase 5 | Pending |
| GGUF-03 | Phase 5 | Pending |
| GGUF-04 | Phase 5 | Pending |
| GGUF-05 | Phase 5 | Pending |
| EVAL-01 | Phase 6 | Pending |
| EVAL-02 | Phase 6 | Pending |
| EVAL-03 | Phase 6 | Pending |
| EVAL-04 | Phase 6 | Pending |
| EVAL-05 | Phase 6 | Pending |
