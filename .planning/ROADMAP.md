# Roadmap: TSC-CYCLE 评估优化

## Overview

本里程碑聚焦于优化 Benchmark 评估系统，通过改进统计计算方式和添加新指标，确保不同模型在相同交叉口的评估结果公平可比较。完成后，评估系统能够准确反映各模型的实际交通优化能力。

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Benchmark 统计优化** - 实现加权平均统计和 throughput 指标

## Phase Details

### Phase 1: Benchmark 统计优化
**Goal**: Benchmark 评估结果公平可比较，提供准确的吞吐量指标
**Depends on**: Nothing (first phase)
**Requirements**: BENCH-01, BENCH-02, BENCH-03
**Success Criteria** (what must be TRUE):
  1. Benchmark 输出的统计数据使用加权平均（按周期数加权），不同模型在相同交叉口的评估结果可直接对比
  2. Comparison CSV 文件中包含 throughput（通过车辆数）列，反映各模型在每个场景的车辆通行能力
  3. 加权平均计算逻辑经过单元测试验证，确保数学正确性
**Plans:** 1 plan

Plans:
- [ ] 01-01-PLAN.md — 实现加权平均统计和 throughput 指标 (TDD)

## Progress

**Execution Order:**
Phases execute in numeric order: 1

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Benchmark 统计优化 | 0/1 | Not started | - |
