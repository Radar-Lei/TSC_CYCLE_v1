# Roadmap: TSC-CYCLE

## Shipped Milestones

- **v1.0** ✅ 2026-05-07 — Thinking 4B Student Distillation (Phases 1–6, deployment GO) — see `milestones/v1.0-ROADMAP.md`

## Current Milestone: v2.0 强化版

**Goal:** 在 v1.0 已可部署模型基础上，通过 10K 教师标注数据扩容、混合分布增强和重训，产出在 OOD 硬约束、教师 MAE、思考格式稳定性三方面都严格优于 v1.0 的更强 GGUF 模型。

**Baseline to beat:** v1.0 q4_K_M OOD lint=98.7%，HF bf16=99.3%，教师 MAE Δ +0.18s。

| Phase | Name | Goal | Requirements |
|-------|------|------|--------------|
| 7 | 1/1 | Complete    | 2026-05-08 |
| 8 | 10K 混合数据扩容与教师标注 | 构建 10K 同分布/OOD/targeted 混合数据集，并完成 GPT-5.5 high 标注与 split。 | DATA-01, DATA-02, DATA-03 |
| 9 | 扩容数据 QLoRA 重训与 GGUF 导出 | 用 10K 数据重训 Qwen3-4B-Thinking，并导出 HF fp16、GGUF fp16、q4_K_M。 | TRAIN-01, TRAIN-02 |
| 10 | v2.0 对比评测与部署门禁 | 对比 v1.0/v2.0 的 HF 与 q4 指标，验证三项严格提升并给出 go/no-go。 | EVAL-01, EVAL-02, EVAL-03, EVAL-04 |

## Phase Details

### Phase 7: 标签协议全链路迁移

**Goal:** 全链路 prompt、数据、训练、推理与评测统一新思考结束标签 `<end_working_out>`。

**Requirements:** TAG-01, TAG-02

**Success Criteria:**
1. 所有生成/解析/训练/评测路径输出协议为 `<start_working_out>...<end_working_out><SOLUTION>...</SOLUTION>`。
2. 解析器和 lint 对 `</end_working_out>` 旧标签样本给出失败结果。
3. tokenizer 检查确认新标签仍按普通 sub-token 拆分，不注册 added token。
4. 单元测试覆盖新标签正例、旧标签反例、缺失标签反例。

**Plans:** 1/1 plans complete

Plans:
- [x] 07-01-PLAN.md — 协议常量迁移 + parser 拒绝旧标签 + 测试覆盖扩展（单 plan，3 task）

### Phase 8: 10K 混合数据扩容与教师标注

**Goal:** 生成并标注 10K 规模混合分布训练数据，覆盖同分布、OOD/边界和 v1.0 错误/高 MAE targeted 样本。

**Requirements:** DATA-01, DATA-02, DATA-03

**Success Criteria:**
1. 数据生成器能产生 10K 候选输入，并记录三类样本来源与比例。
2. 数据集报告展示字段分布、边界覆盖、OOD 覆盖和相对 v1.0 的差异。
3. GPT-5.5 high 标注流程在 ≤10 worker 下可断点续跑，并只保留通过硬约束 lint 的样本。
4. 产出可复现 train/val/OOD split，且 split metadata 记录随机种子、输入版本和标注版本。

**Plans:** 4 plans

Plans:
**Wave 1**
- [ ] 08-01-PLAN.md — sample_targeted + manifest 模块 + Wave 0 测试脚手架（DATA-01/03）
- [ ] 08-02-PLAN.md — dataset.py 输出 dataset_report + split_manifest + dist_check targeted（DATA-02/03）

**Wave 2** *(blocked on Wave 1 completion)*
- [ ] 08-03-PLAN.md — cache 协议审计 + smoke probe + 10K 全量教师标注（DATA-01/03）

**Wave 3** *(blocked on Wave 2 completion)*
- [ ] 08-04-PLAN.md — run_pipeline.sh 端到端 + 用户 checkpoint 验证（DATA-01/02/03）

### Phase 9: 扩容数据 QLoRA 重训与 GGUF 导出

**Goal:** 使用扩容数据完成学生重训，并导出可部署 GGUF 产物。

**Requirements:** TRAIN-01, TRAIN-02

**Success Criteria:**
1. DGX Spark 训练命令遵循 SDPA、swap/OOM 防护和已知良好 venv 约束。
2. 训练日志、配置、adapter、dataset fingerprint 全部落盘，可复现实验。
3. adapter 成功 merge 为 HF fp16，并通过基础推理 smoke test。
4. llama.cpp 导出 GGUF fp16 与 q4_K_M，且 q4_K_M 可被本地推理命令加载。

### Phase 10: v2.0 对比评测与部署门禁

**Goal:** 用可比评测证明 v2.0 q4_K_M 在 OOD 硬约束、教师 MAE、思考格式稳定性三方面严格优于 v1.0 baseline。

**Requirements:** EVAL-01, EVAL-02, EVAL-03, EVAL-04

**Success Criteria:**
1. v2.0 q4_K_M OOD 硬约束满足率严格高于 v1.0 q4_K_M 98.7%。
2. v2.0 q4_K_M 教师 MAE 严格优于 v1.0 baseline。
3. v2.0 q4_K_M 思考格式完整率严格优于 v1.0 baseline，并且无旧结束标签输出。
4. 最终报告并列展示 v1.0/v2.0、HF bf16/q4_K_M 指标与差值。
5. 部署裁决给出 GO / NO-GO，并明确若失败应回退到哪个产物或下一步补救。

## Coverage

| Requirement | Phase |
|-------------|-------|
| TAG-01 | Phase 7 |
| TAG-02 | Phase 7 |
| DATA-01 | Phase 8 |
| DATA-02 | Phase 8 |
| DATA-03 | Phase 8 |
| TRAIN-01 | Phase 9 |
| TRAIN-02 | Phase 9 |
| EVAL-01 | Phase 10 |
| EVAL-02 | Phase 10 |
| EVAL-03 | Phase 10 |
| EVAL-04 | Phase 10 |

**Coverage:** 11/11 requirements mapped (100%).

---
*Roadmap updated: 2026-05-08 after milestone v2.0 roadmap creation.*
