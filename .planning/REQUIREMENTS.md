# Requirements: TSC-CYCLE v2

**Defined:** 2026-04-11
**Core Value:** 让模型在严格输出格式和绿灯约束下，稳定学会按输入饱和度分配合理的相位绿灯时间

## v1.3 Requirements

### 脚本适配 (ENV)

- [ ] **ENV-01**: 训练脚本支持通过参数指定模型名，输出目录自动按模型名隔离（如 `outputs/sft/qwen3-8b/`、`outputs/grpo_simple/qwen3-8b/`）
- [ ] **ENV-02**: SFT 训练脚本适配 Qwen3-8B 全精度加载（移除 BnB 量化相关逻辑）

### 训练与导出 (TRAIN)

- [ ] **TRAIN-01**: 用现有 SFT 数据对 unsloth/Qwen3-8B 完成 SFT 微调，产出可加载的完整模型
- [ ] **TRAIN-02**: 用 SFT 产出的 Qwen3-8B 模型完成简化版 GRPO 训练，产出可加载的完整 GRPO 模型
- [ ] **TRAIN-03**: SFT 和 GRPO 模型分别导出 GGUF 格式（Q4_K_M、Q8_0、F16）

### 验证 (VAL)

- [ ] **VAL-01**: 用 validate.py 对 GRPO 产出的 8B 模型跑 4000 条数据自动验证（格式/约束/饱和度通过率）

## Future Requirements

### Evaluation

- **EVAL-02**: 开发者可以比较简化版 GRPO 与 SUMO reward GRPO 的训练结果差异

### Advanced Reward

- **ARWD-01**: 开发者可以在饱和度比例 reward 之外，再叠加 queue、delay 或 throughput 等多目标 reward
- **ARWD-02**: 开发者可以探索不同的 target 归一化或全周期预算分配策略

### Model Comparison

- **COMP-01**: 开发者可以对比 Qwen3-4B 和 Qwen3-8B 在同一评测集上的效果差异

## Out of Scope

| Feature | Reason |
|---------|--------|
| 旧版 `src/grpo/` 重构或与 `src/grpo_simple/` 合并 | 保留现有完整版流水线 |
| BnB 量化加载 | 8B 模型全精度即可，无需量化 |
| 多目标 reward 调参 | 先验证 8B 基座效果 |
| 大规模超参数搜索 | 先跑通单次训练 |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| ENV-01 | Phase 8 | Pending |
| ENV-02 | Phase 8 | Pending |
| TRAIN-01 | Phase 9 | Pending |
| TRAIN-02 | Phase 9 | Pending |
| TRAIN-03 | Phase 9 | Pending |
| VAL-01 | Phase 10 | Pending |

**Coverage:**
- v1.3 requirements: 6 total
- Mapped to phases: 6
- Unmapped: 0

---
*Requirements defined: 2026-04-11*
*Last updated: 2026-04-11 — roadmap phase mappings added*
