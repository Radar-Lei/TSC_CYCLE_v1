# Requirements: TSC-CYCLE 评估优化

**Defined:** 2026-02-18
**Core Value:** 训练能优化交通信号配时的 AI 模型，提升交通效率

## v1 Requirements

### Benchmark 统计优化

- [x] **BENCH-01**: 统计方式改为加权平均（按周期数加权），确保不同模型在相同交叉口的评估结果公平可比较
- [x] **BENCH-02**: comparison CSV 输出中添加通过车辆数（throughput）指标
- [x] **BENCH-03**: 验证加权平均计算逻辑正确

## Out of Scope

| Feature | Reason |
|---------|--------|
| 实时 API 服务 | 当前仅本地评估 |
| 新场景添加 | 仅修改现有 benchmark 统计逻辑 |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| BENCH-01 | Phase 1 | Complete |
| BENCH-02 | Phase 1 | Complete |
| BENCH-03 | Phase 1 | Complete |

**Coverage:**
- v1 requirements: 3 total
- Mapped to phases: 3
- Unmapped: 0 ✓

---
*Requirements defined: 2026-02-18*
*Last updated: 2026-02-18 after initial definition*
