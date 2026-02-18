# Milestones

## v1.0 Benchmark 统计优化 (Shipped: 2026-02-18)

**Phases completed:** 1 phase, 1 plan, 5 tasks

**Key accomplishments:**
- 实现加权平均统计 `calculate_weighted_average()` 和 `calculate_weighted_metrics()`，按周期时长加权确保模型比较公平
- 添加 throughput（吞吐量）指标到 comparison CSV 和终端输出
- TDD 完整覆盖：21 个单元测试全部通过，覆盖边界条件和端到端流程
- 向后兼容设计：`weighted_summary` 参数可选

**Git range:** d2a4a89 → 1be90f2
**Duration:** 14 days

---

