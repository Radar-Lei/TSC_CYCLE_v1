# Phase 1: Benchmark 统计优化 - Context

**Gathered:** 2026-02-18
**Status:** Ready for planning

<domain>
## Phase Boundary

优化 Benchmark 评估系统，实现加权平均统计和 throughput 指标，确保不同模型在相同交叉口的评估结果公平可比较。加权平均按周期数加权，throughput 反映周期平均通行能力。

</domain>

<decisions>
## Implementation Decisions

### 加权平均计算方式

- **适用范围**：所有统计指标都使用加权平均（如等待时间、队列长度、延误等）
- **权重选择**：按周期数 (cycles) 加权 — 运行周期越多，该场景的统计数据权重越大
- **零值处理**：如果某场景周期数为 0，跳过该场景不参与计算

### Throughput 定义与计算

- **定义**：周期平均通过车辆数，反映单位时间的通行效率
- **计算公式**：
  1. 每周期 throughput = 该周期通过车辆数 / 周期时长
  2. 汇总 throughput = 各周期 throughput 按周期时长加权平均
- **车辆范围**：仅计算完全通过交叉口的车辆
- **细分粒度**：交叉口级
- **输出位置**：
  - Comparison CSV（新增列）
  - Summary 报告
  - 单独的 throughput 文件

### 输出格式与报告

- **CSV 结构**：保持现有长格式（每行一个 model-scenario 组合）
- **加权对比**：仅显示加权后结果，替换原有的简单平均
- **Summary 报告内容**：
  - 模型汇总（各模型在所有场景上的统计）
  - 模型对比（不同模型在同一场景上的横向对比）
- **文件命名**：参考现有格式 `comparison_YYYY-MM-DD_HH-MM-SS.csv`

### 测试覆盖范围

- **测试重点**：验证加权平均公式的数学正确性
- **测试数据**：使用真实的 benchmark 运行数据
- **测试位置**：`benchmark/tests/` 目录

### Claude's Discretion

- 不同长度 episode 的聚合方式（先内后外 vs 完全展开）
- Throughput 单独文件的具体格式
- Summary 报告的详细布局
- 测试用例的具体设计

</decisions>

<specifics>
## Specific Ideas

- 参考现有 `comparison_2026-02-18_06-21-16.csv` 的格式
- Throughput 应该是周期平均并按周期时长加权，而非简单累计总数

</specifics>

<deferred>
## Deferred Ideas

None — 讨论保持在 phase 范围内

</deferred>

---

*Phase: 01-benchmark*
*Context gathered: 2026-02-18*
