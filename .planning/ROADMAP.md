# Roadmap: TSC-CYCLE

**Created:** 2026-05-07
**Granularity:** standard
**Phases:** 6
**Coverage:** 47/47 v1 requirements ✓

## Core Value

学生模型在 OOD 输入上仍满足全部硬约束（min_green ≤ final ≤ max_green、整数秒、相位顺序、覆盖全相位），且数值决策接近 GPT-5.5 high 教师 — 不过拟合 reality.log。

## Phases

- [x] **Phase 1: Environment + Foundations** — 克隆 dgx-spark venv、verify 全绿、prompt_builder/constraint_lint/tokenizer_check/hashing 模块就绪、dist_prior 落盘、5-prompt 教师 smoke 通
- [x] **Phase 2: Synthetic Data Generation** — 形式化 OOD spec、采样 ~2700 同分布 + ~300 OOD 输入、KS test 通过
- [x] **Phase 3: Teacher Labeling** — GPT-5.5 high 并发标注 ≥2700 有效样本、内容寻址缓存断点续跑、reject<20%、reasoning_tokens 真实校验
- [x] **Phase 4: Dataset Build + QLoRA SFT** — 80/10/10 split + arrow tokenize + Qwen3-4B-Thinking-2507 QLoRA r=64 训练 ≤6h，自定义标签 emission ≥80%
- [x] **Phase 5: Merge + GGUF Export** — bf16 reload merge、HF→GGUF bf16、quantize Q4_K_M、20-prompt parity（q4_K_M MAE ≤3s） (completed 2026-05-07)
- [ ] **Phase 6: Evaluation Suite** — 三 backend × 四指标 × 两 split 矩阵评测，输出 report.md + 部署 go/no-go 决策

## Phase Details

### Phase 1: Environment + Foundations
**Goal**: 训练环境通过 fail-fast 体检，跨阶段共享模块（prompt_builder / constraint_lint / tokenizer_check / hashing / manifest）单元测试全绿，分布先验落盘，5-prompt 教师 smoke test 端到端通
**Depends on**: Nothing (first phase)
**Requirements**: ENV-01, ENV-02, ENV-03, ENV-04, ENV-05, FND-01, FND-02, FND-03, FND-04, FND-05, FND-06
**Success Criteria** (what must be TRUE):
  1. `python scripts/dgx_spark/verify.py` 在 `/home/samuel/TSC_CYCLE/.venv` 下全绿（CUDA 13、torch cu130、bnb 0.48.0、SDPA、swap=0、Triton ptxas、`flash_attn` ImportError）
  2. `tokenizer_check.py` 断言四个自定义标签 `<start_working_out>` / `</end_working_out>` / `<SOLUTION>` / `</SOLUTION>` 都被 Qwen3-4B-Thinking-2507 tokenizer 拆为多 sub-token，且原生 `<think>`(151667)/`</think>`(151668) 仍是单 token
  3. `data/dist_prior.json` 由 `distribution_fit.py` 从 `reality.log` 写出（含相位数 / min_green / max_green / capacity / pred_wait / pred_saturation 边缘 + 组合先验）
  4. 5-prompt 教师 smoke test（含 50-sample 后续外推）成功：每条 `usage.reasoning_tokens > 100` 且通过 `constraint_lint`，3000 样本预算外推 ≤ 隐含上限
  5. prompt_builder / constraint_lint / tokenizer_check / hashing 单元测试全绿，`runs/{ts}/manifest.json` 写入（git sha + config hash + stage 状态）
**Plans**: TBD

### Phase 2: Synthetic Data Generation
**Goal**: 产出 ~2700 同分布 + ~300 OOD 输入，分布特性可量化验证（KS 报告 + sample_id 唯一性），训练前一切尚未烧 API token
**Depends on**: Phase 1
**Requirements**: DGEN-01, DGEN-02, DGEN-03, DGEN-04, DGEN-05
**Success Criteria** (what must be TRUE):
  1. `data/ood_spec.md` 形式化 OOD 扩展规则（更宽相位数 / 超出 reality.log 的 min/max 组合 / 稀有饱和度区间 / 业务相关性打破）
  2. `data/inputs.jsonl`（~2700 同分布）+ `data/ood_inputs.jsonl`（~300 OOD）写出，每条带 `sample_id = sha256(canonical_input_json)`
  3. `data/dist_check_report.md`：同分布每维 KS p>0.05，OOD 每维 KS p<0.01（vs reality.log 经验分布）
  4. 全数据集 `sample_id` 唯一无重复；trivial 样本（min == max）单独标记字段
**Plans**: TBD

### Phase 3: Teacher Labeling
**Goal**: 用 GPT-5.5 high + Responses API 给所有合成输入打教师标签，断点续跑保护 4-6h API 投入，reject 率 < 20%，全部样本附完整 usage 计费记录
**Depends on**: Phase 1, Phase 2
**Requirements**: TCH-01, TCH-02, TCH-03, TCH-04, TCH-05, TCH-06
**Success Criteria** (what must be TRUE):
  1. `data/labeled.jsonl` ≥ 2700 有效样本（含输入 / 教师完整响应 / 解析 SOLUTION JSON / `usage` 字段），通过 `constraint_lint` 双重校验
  2. 每条响应 `usage.reasoning_tokens > 100`（无静默降档），平均 reasoning_tokens 与总 token 用量、$ 成本写入 `runs/{ts}/teacher_cost.json`
  3. `raw_responses/{prompt_hash}.json` 内容寻址缓存完整（atomic rename 写入），中断续跑时跳过已完成样本
  4. `data/rejected.jsonl` reject 率 < 20%，违反类型分布写入 `runs/{ts}/teacher_reject_stats.json`，违反样本不重试不重新生成
  5. 50-sample smoke test 完成后做 owner 预算外推确认（若超阈值显式 hold）
**Plans**: TBD

### Phase 4: Dataset Build + QLoRA SFT
**Goal**: labeled.jsonl 装配为 80/10/10 split + arrow tokenized 数据集，Qwen3-4B-Thinking-2507 QLoRA r=64 SFT 单次端到端 ≤6h 完成，首 epoch smoke 验证自定义标签学习成功（无原生 `<think>` token 泄漏）
**Depends on**: Phase 1, Phase 3
**Requirements**: DSET-01, DSET-02, DSET-03, DSET-04, DSET-05, TRN-01, TRN-02, TRN-03, TRN-04, TRN-05, TRN-06, TRN-07, TRN-08
**Success Criteria** (what must be TRUE):
  1. `data/tokenized/{train,val_id,val_ood}/` arrow 数据集就绪，sample_id 跨 split 严格不重叠，`tokenizer_check` 全绿，assistant 段以外 `labels=-100`，`max_length` 按 p99 实测设定
  2. `runs/{ts}/train/adapter/` 保存最终 LoRA adapter（r=64, alpha=128, target_modules 覆盖 Q/K/V/O + gate/up/down），训练全程在 `run_safe.sh 100G --` 内运行，端到端 wall time ≤ 6h
  3. 训练入口 boot 时 `tokenizer_check` 通过 + bnb dummy forward 预热 + 100-step dry-run 外推单 epoch ≤2.5h（不达自动收 batch / max_length）
  4. 首 epoch 末 5-prompt smoke test：自定义标签闭合率（`</end_working_out>` + `</SOLUTION>`）≥ 80%，生成 token id 中**不出现** 151667 / 151668（原生 `<think>` / `</think>`）
  5. `runs/{ts}/train/train_log.jsonl` + `data/dataset_card.md`（split 大小、token 长度分布、phase_count 分布、OOD 维度）写出
**Plans**: TBD

### Phase 5: Merge + GGUF Export
**Goal**: LoRA adapter merge 到 bf16 base（**非 4-bit**），转 GGUF bf16 与 Q4_K_M，三精度 parity 验证学生在量化后数值漂移可控
**Depends on**: Phase 4
**Requirements**: EXP-01, EXP-02, EXP-03, EXP-04, EXP-05
**Success Criteria** (what must be TRUE):
  1. `runs/{ts}/merged_bf16/` 存在（bf16 reload base + LoRA merge_and_unload，**不是** 4-bit base merge），vocab_size = 151936（无 embedding resize）
  2. `runs/{ts}/gguf/model.bf16.gguf`（本机 EvoProgTSC/llama.cpp `convert_hf_to_gguf.py`，`Qwen3ForCausalLM` 已注册）+ `runs/{ts}/gguf/model.q4_K_M.gguf`（`llama-quantize` preset 15）写出
  3. GGUF tokenize sanity：`llama-tokenize` 对四个自定义标签输出与 HF tokenizer 一致的多 sub-token 序列
  4. 20-prompt greedy（seed=42, temperature=0.0）parity 测试：HF bf16 vs GGUF bf16 vs GGUF q4_K_M，q4_K_M 对 HF bf16 SOLUTION 数值 MAE ≤ 3s（>3s 触发 imatrix 重量化预案）
**Plans**: 4 plans
- [x] 05-01-PLAN.md — GGUF tokenize sanity check (EXP-04)
- [x] 05-02-PLAN.md — Deterministic 20-prompt parity selector (EXP-05 input)
- [x] 05-03-PLAN.md — Three-precision parity runner with GPU offload (EXP-01/02/03/05)
- [x] 05-04-PLAN.md — Phase 5 report rollup + STATE/ROADMAP closure (EXP-01..05)

### Phase 6: Evaluation Suite
**Goal**: 三 backend（HF bf16 / GGUF bf16 / GGUF q4_K_M）× 四指标（硬约束满足率 / 教师 MAE / OOD gap / Reasoning 关键字）× 两 split（同分布 val / OOD val）矩阵评测，给出部署 go/no-go 决策
**Depends on**: Phase 5
**Requirements**: EVL-01, EVL-02, EVL-03, EVL-04, EVL-05, EVL-06, EVL-07, EVL-08
**Success Criteria** (what must be TRUE):
  1. `gen_cache/{variant}/{sample_id}.json` 缓存所有生成结果（共 600 prompt × 3 variant = 1800 generation），三 variant 共用 prompt_builder + greedy seed=42
  2. `runs/{ts}/eval/per_sample.jsonl` 含四指标逐样本结果：硬约束满足率（按 phase_count 分桶 + trivial 样本排除）、与教师 final MAE / 完全一致率、OOD gap（同分布 vs OOD）、Reasoning 关键字引用质量（规则式打分）
  3. `runs/{ts}/eval/report.md` 输出 4 指标 × 3 variant × 2 split 矩阵 + p99 + 失败案例 top-20 + 量化退化结论
  4. 部署 go/no-go gate 写入 `runs/{ts}/eval/decision.md`：q4_K_M 在 OOD val 硬约束满足率 ≥ HF bf16 的 95% → go；否则启用 imatrix 重量化或回退 fp16 部署
**Plans**: 6 plans
- [x] 06-01-PLAN.md — EVL 数据集选取（300 id + 300 ood, seed=42） (EVL-01)
- [x] 06-02-PLAN.md — hf_bf16 generation runner (EVL-01, EVL-02)
- [x] 06-03-PLAN.md — gguf_bf16 generation runner via llama-server (EVL-01, EVL-02)
- [x] 06-04-PLAN.md — gguf_q4_k_m generation runner (EVL-01, EVL-02)
- [ ] 06-05-PLAN.md — 4 指标计算 + per_sample.jsonl + report.md (EVL-03..07)
- [ ] 06-06-PLAN.md — 部署 go/no-go decision gate + STATE/REQUIREMENTS 闭环 (EVL-07, EVL-08)

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Environment + Foundations | 0/0 | Complete | 2026-05-07 |
| 2. Synthetic Data Generation | 0/0 | Complete | 2026-05-07 |
| 3. Teacher Labeling | 0/0 | Complete | 2026-05-07 |
| 4. Dataset Build + QLoRA SFT | 0/0 | Complete | 2026-05-07 |
| 5. Merge + GGUF Export | 5/4 | Complete    | 2026-05-07 |
| 6. Evaluation Suite | 0/0 | Not started | - |

## Phase Ordering Rationale

- 数据流强依赖：reality.log → dist_prior（P1）→ inputs（P2）→ labeled（P3）→ tokenized + adapter（P4）→ merged + GGUF（P5）→ eval（P6）
- **Phase 1 是 hard fail-fast gate**：verify.py / tokenizer_check / 教师 smoke 任一不通过，后续阶段全部不得启动；P1 烧的成本是分钟级，P3 烧的是 USD + 小时级，P4 烧的是 6h GPU 预算
- **Phase 4 owns BOTH DSET and TRN**：dataset-build 是训练的紧前置且高度耦合（tokenize 用 tokenizer_check、loss-mask 依赖 prompt_builder 模板），合并到一个阶段避免 split 后再调整时跨阶段返工
- **Phase 3 与 P4 工程开发可并行**：教师 4-6h API 后台跑期间，可继续打磨 P4 dataset_builder / trainer 代码（但 P4 训练本身必须等 P3 落盘）
- 失败成本递增 P1 < P2 < P3 < P4 < P5 < P6；Phase 1 的 hard gate 是整个链路的最高 ROI 检查点

## DGX Spark 训练栈权威源声明

- 复用 `/home/samuel/dgx-spark-setup/.venv` 已知良好环境（natolambert 上游）+ `/dgx-spark-training` skill 全部约束（SDPA、swap=0、run_safe.sh、TRITON_PTXAS_PATH）
- **明确不参考** waybarrios/dgx-spark-finetune-llm

---
*Roadmap created: 2026-05-07*
