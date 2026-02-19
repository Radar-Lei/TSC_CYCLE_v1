# Roadmap: TSC-CYCLE

## Milestones

- **v1.0 Benchmark 统计优化** - Phase 1 (shipped 2026-02-18)
- **v1.1 模型迁移** - Phases 2-4 (in progress)

## Overview

v1.1 里程碑将 SFT 训练流程从 Qwen3-4B 迁移到 GLM-4.7-Flash (BF16)。首先验证 tokenizer 兼容性并生成增强数据，然后完成训练迁移，最后导出 GGUF 模型。

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

- [x] **Phase 1: Benchmark 统计优化** - 加权平均统计与 throughput 指标 (v1.0 shipped)
- [x] **Phase 2: Tokenizer 验证与数据准备** - 验证 GLM tokenizer 兼容性，生成增强训练数据 (completed 2026-02-18)
- [ ] **Phase 3: SFT 训练迁移** - 更新训练代码适配 GLM-4.7-Flash (BF16)，跑通端到端训练
- [ ] **Phase 4: 模型导出与量化** - 导出 GGUF 格式 (F16 + Q4_K_M)

## Phase Details

<details>
<summary>v1.0 Benchmark 统计优化 (Phase 1) - SHIPPED 2026-02-18</summary>

### Phase 1: Benchmark 统计优化
**Goal**: 实现加权平均统计确保模型比较公平
**Depends on**: Nothing (first phase)
**Requirements**: BENCH-01, BENCH-02, BENCH-03 (v1.0 requirements - completed)
**Success Criteria**:
  1. Comparison CSV 包含加权平均统计列
  2. Throughput 指标正确计算并输出
  3. 21 个单元测试全部通过
**Plans**: 1 plan (completed)

Plans:
- [x] 01-01: 实现加权平均统计和 throughput 指标

</details>

### Phase 2: Tokenizer 验证与数据准备
**Goal**: 确认 GLM tokenizer 与自定义标签兼容，生成增强版训练数据
**Depends on**: Phase 1 (v1.0 shipped)
**Requirements**: TOK-01, TOK-02, DATA-01, DATA-02
**Success Criteria** (what must be TRUE):
  1. GLM tokenizer 正确处理自定义标签（`<start_working_out>`, `<end_working_out>`, `<SOLUTION>`, `</SOLUTION>`），无 added token 语义冲突
  2. 增强版训练数据生成完成，思考链长度达到 300-400 token
  3. 新数据覆盖原有 train.jsonl，格式与 GLM 模型兼容
  4. TOK-01/TOK-02 将在 Phase 3 SFT 训练中验证（跳过专门验证）
**Plans**: 2 plans

Plans:
- [x] 02-01: 生成增强版 SFT 训练数据 — 扩展思考链至 300-400 token
- [x] 02-02: 部署增强版数据 — 备份原数据，部署新数据，生成统计报告

### Phase 3: SFT 训练迁移
**Goal**: 完成 GLM-4.7-Flash (BF16) 的 SFT 训练流程，产出微调模型
**Depends on**: Phase 2
**Requirements**: SFT-01, SFT-02, SFT-03, SFT-04, SFT-05, SFT-06
**Success Criteria** (what must be TRUE):
  1. 模型加载代码成功加载 unsloth/GLM-4.7-Flash
  2. LoRA 适配器正确应用于 GLM 模型 (r=16, alpha=16, dropout=0)
  3. 端到端训练流程跑通，无错误完成训练
  4. 训练产出模型保存到 `/home/samuel/TSC_CYCLE/outputs/sft/model`
  5. 模型能正确推理，输出符合预期的信号配时方案格式
**Plans**: 2 plans

Plans:
- [ ] 03-01: 更新模型和 LoRA 配置 — 切换到 unsloth/GLM-4.7-Flash，配置 r=16/alpha=16/dropout=0
- [ ] 03-02: 跑通端到端 SFT 训练 — 更新代码引用，执行训练并人工验证推理结果

### Phase 4: 模型导出与量化
**Goal**: 将 SFT 训练产出的模型导出为 GGUF 格式，支持 F16 和 Q4_K_M 量化
**Depends on**: Phase 3
**Requirements**: EXPR-01, EXPR-02, EXPR-03
**Success Criteria** (what must be TRUE):
  1. 训练完成后自动触发 GGUF 导出流程
  2. F16 GGUF 模型存在于 `/home/samuel/TSC_CYCLE/outputs/sft/model`
  3. Q4_K_M 量化 GGUF 模型存在于 `/home/samuel/TSC_CYCLE/outputs/sft/model`
  4. GGUF 模型可用 llama.cpp 正确加载和推理
**Plans**: TBD

Plans:
- [ ] 04-01: 实现 GGUF 导出和量化流程

## Progress

**Execution Order:**
Phases execute in numeric order: 2 → 3 → 4

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Benchmark 统计优化 | v1.0 | 1/1 | Complete | 2026-02-18 |
| 2. Tokenizer 验证与数据准备 | v1.1 | 2/2 | Complete | 2026-02-18 |
| 3. SFT 训练迁移 | v1.1 | 0/2 | In Progress | - |
| 4. 模型导出与量化 | v1.1 | 0/1 | Not started | - |

---

*Roadmap created: 2026-02-18*
*Last updated: 2026-02-19*
