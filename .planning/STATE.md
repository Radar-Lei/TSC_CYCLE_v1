# Project State: TSC-CYCLE

**Last Updated:** 2026-02-11

---

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-10)

**Core value:** 给定交叉口实时交通状态,大模型输出的信号配时方案能最大化车辆通过量、最小化排队车辆数
**Current focus:** v1.1 Phase 4 - Reward Enhancement

---

## Current Position

**Active Milestone:** v1.1 Improve Reward & GRPO Data Filter
**Active Phase:** Phase 5 of 6 (Data Filtering)
**Active Plan:** 05-01 (Data Filter Script)
**Current Status:** Phase 05-01 executed successfully

**Last activity:** 2026-02-11 — Completed Phase 05-01 (Data Filter Script)

Progress: [███████████████░░░░░] 75% (5 of 6 phases complete across all milestones)

---

## Performance Metrics

**Velocity:** 1 plan/session (稳定进行)

| Phase | Plan | Duration | Tasks | Files | Completed |
|-------|------|----------|-------|-------|-----------|
| 01    | 01   | 259s     | 1     | 2     | 2026-02-09T12:24:12Z |
| 01    | 02   | 497s     | 2     | 3     | 2026-02-09T12:36:00Z |
| 01    | 03   | 217s     | 2     | 3     | 2026-02-09T12:44:44Z |
| 02    | 01   | 282s     | 2     | 3     | 2026-02-09T16:38:44Z |
| 03    | 01   | 246s     | 2     | 4     | 2026-02-09T19:54:45Z |
| 03    | 02   | 402s     | 3     | 3     | 2026-02-10T04:12:47Z |
| 04    | 01   | 4895s    | 3     | 4     | 2026-02-11T03:29:48Z |
| 04    | 02   | 1800s    | 2     | 2     | 2026-02-11T04:00:00Z |
| 05    | 01   | 331s     | 2     | 3     | 2026-02-11T08:18:40Z |

**Total:** 9 plans, average 732 seconds/plan

## Accumulated Context

### Blockers

无

### Key Findings from v1.0 Training

- SUMO reward 二值化严重：几乎只有 0 或 5.0，baseline 太弱导致 combined 轻松到 1.0
- ~20% 训练步 frac_reward_zero_std=1.0（4 个 generation reward 完全一样），GRPO 学不到东西
- 空交叉口样本（passed=0, queue=0）浪费计算资源
- 数据量从 1588 → 16788 条（大幅扩充）

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 1 | 给 grpo_baseline.sh 添加类似 data.sh 的进度打印功能 | 2026-02-10 | c9ca8de | [1-grpo-baseline-sh-data-sh](./quick/1-grpo-baseline-sh-data-sh/) |

---

## Session Continuity

### Last Session Summary

**What:** Phase 05-01 — Data Filter Script 执行

**Outcome:**
- 创建过滤脚本 `src/scripts/filter_grpo_data.py`（260 行）
- 创建 Docker 入口脚本 `docker/filter_data.sh`（135 行）
- 更新 `config.json` 添加 `data_filter` 配置块
- 实际过滤结果: 16788 → 13781 条（剔除 17.9% 空/极低流量样本）

**Key Decisions:**
- 过滤阈值: saturation_sum < 0.1（基于数据分析 14% 样本 total_sat=0, 18% < 0.1）
- 双输出文件: filtered + rejected（保留原始数据不变）
- 统计报告: 终端 + 文本文件（样本数、剔除比例、流量分布）
- Docker 串联: filter_data.sh 自动执行 过滤 → baseline 重算，支持 --skip-baseline

**Next:** Phase 05 后续计划或 Phase 06

**Stopped At:** 完成 Phase 05-01

### Context for Next Session

Phase 05-01 完成了数据过滤工具链：
1. 过滤脚本能从 prompt 提取 phase_waits 并计算 saturation_sum
2. Docker 入口脚本串联 filter → baseline 重算流程
3. 实际过滤剔除 17.9% 低质量样本（与预期 18% 接近）

核心文件：
- `src/scripts/filter_grpo_data.py` — 数据过滤脚本
- `docker/filter_data.sh` — Docker 入口脚本
- `config/config.json` — 过滤配置（data_filter 块）

下一步：检查 Phase 05 是否有其他计划，或进入 Phase 06

---

*State initialized: 2026-02-09*
