# Requirements: TSC-CYCLE v1.1 模型迁移

**Defined:** 2026-02-18
**Core Value:** 训练能优化交通信号配时的 AI 模型，提升交通效率

## v1.1 Requirements

### Tokenizer 兼容性

- [x] **TOK-01**: 验证 GLM-4.7 tokenizer 对自定义标签（`<start_working_out>`、`<end_working_out>`、`<SOLUTION>`、`</SOLUTION>`）的处理方式（推迟到 Phase 3 SFT 训练中验证）
- [x] **TOK-02**: 确认 GLM tokenizer 没有 added token 语义冲突（避免重蹈 Qwen3 覆辙）（推迟到 Phase 3 SFT 训练中验证）

### SFT 数据增强

- [x] **DATA-01**: 扩展思考链长度至 300-400 token（当前太短）
- [x] **DATA-02**: 基于现有数据生成增强版训练数据，覆盖原数据

### SFT 训练迁移

- [x] **SFT-01**: 更新模型加载代码适配 GLM-4.7-Flash-FP8-Dynamic
- [x] **SFT-02**: 更新训练配置（学习率、batch size 等基础参数）
- [x] **SFT-03**: 验证 LoRA 适配 GLM 模型
- [x] **SFT-04**: 确保训练数据格式与 GLM 兼容
- [ ] **SFT-05**: 跑通端到端 SFT 训练流程
- [ ] **SFT-06**: SFT 模型输出到 `/home/samuel/TSC_CYCLE/outputs/sft/model`

### 模型导出与量化

- [ ] **EXPR-01**: SFT 训练完成后自动导出 GGUF 格式
- [ ] **EXPR-02**: 生成 F16 GGUF 模型到 `/home/samuel/TSC_CYCLE/outputs/sft/model`
- [ ] **EXPR-03**: 生成 Q4_K_M 量化 GGUF 模型到 `/home/samuel/TSC_CYCLE/outputs/sft/model`

## v2 Requirements

(Deferred to future release)

## Out of Scope

| Feature | Reason |
|---------|--------|
| GRPO 训练流程迁移 | 本里程碑仅聚焦 SFT |
| Benchmark 评估更新 | 暂不评估模型质量提升 |
| Docker 脚本更新 | 非核心功能 |
| 实时控制系统 | 当前仅离线评估 |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| TOK-01 | Phase 2 | Deferred to Phase 3 |
| TOK-02 | Phase 2 | Deferred to Phase 3 |
| DATA-01 | Phase 2 | Complete |
| DATA-02 | Phase 2 | Complete |
| SFT-01 | Phase 3 | Complete |
| SFT-02 | Phase 3 | Complete |
| SFT-03 | Phase 3 | Complete |
| SFT-04 | Phase 3 | Complete |
| SFT-05 | Phase 3 | Pending |
| SFT-06 | Phase 3 | Pending |
| EXPR-01 | Phase 4 | Pending |
| EXPR-02 | Phase 4 | Pending |
| EXPR-03 | Phase 4 | Pending |

**Coverage:**
- v1.1 requirements: 13 total
- Mapped to phases: 13
- Unmapped: 0

---
*Requirements defined: 2026-02-18*
*Last updated: 2026-02-18 after roadmap creation*
