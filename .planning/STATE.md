# Project State: TSC-CYCLE

**Last Updated:** 2026-02-10

---

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-10)

**Core value:** 给定交叉口实时交通状态,大模型输出的信号配时方案能最大化车辆通过量、最小化排队车辆数
**Current focus:** v1.1 Improve Reward & GRPO Data Filter

---

## Current Position

**Active Phase:** Not started (defining requirements)
**Active Plan:** —
**Current Status:** Defining requirements

**Last activity:** 2026-02-10 — Milestone v1.1 started

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

---

## Accumulated Context

### Blockers

无

### Key Findings from v1.0 Training

- SUMO reward 二值化严重：几乎只有 0 或 5.0，baseline 太弱导致 combined 轻松到 1.0
- ~20% 训练步 frac_reward_zero_std=1.0（4 个 generation reward 完全一样），GRPO 学不到东西
- 空交叉口样本（passed=0, queue=0）浪费计算资源
- 数据量从 1588 → 16788 条（大幅扩充）
- 保存模型时出现 397 次 retrying（unsloth 已知问题，不影响训练）

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 1 | 给 grpo_baseline.sh 添加类似 data.sh 的进度打印功能 | 2026-02-10 | c9ca8de | [1-grpo-baseline-sh-data-sh](./quick/1-grpo-baseline-sh-data-sh/) |

---

## Session Continuity

### Last Session Summary

**What:** v1.1 Milestone 初始化

**Outcome:**
- 分析了 100 步 GRPO 训练日志，发现 reward 二值化、zero-std、空交叉口等关键问题
- 确定了 v1.1 三大改进方向

**Next:** 完成 requirements 定义和 roadmap

**Stopped At:** Defining requirements for v1.1

### Context for Next Session

v1.1 聚焦三个方向：
1. Reward 改进 — 去掉 min(1.0) cap + 非线性压缩 + 改进 baseline（饱和度启发式基准）
2. 数据过滤 — 过滤空交叉口、低区分度样本、场景均衡抽样
3. Zero-std 问题 — 确保 4 个 generation 能产生差异化 reward

---

*State initialized: 2026-02-09*
