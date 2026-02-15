# Project State: TSC-CYCLE

**Last Updated:** 2026-02-11

---

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-10)

**Core value:** 给定交叉口实时交通状态,大模型输出的信号配时方案能最大化车辆通过量、最小化排队车辆数
**Current focus:** v1.1 Phase 6 - Integration (In Progress)

---

## Current Position

**Active Milestone:** v1.1 Improve Reward & GRPO Data Filter
**Active Phase:** Phase 6 of 6 (Integration) — In Progress
**Active Plan:** Plan 01 of 03
**Current Status:** Phase 6-01 complete (GRPO Pipeline Integration)

**Last activity:** 2026-02-15 — Completed quick task 2: 合并最新GRPO checkpoint到model目录

Progress: [█████████████████░░░] 87% (10 of 12 plans complete across milestone v1.1)

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

| 06    | 01   | 379s     | 2     | 4     | 2026-02-11T18:37:38Z |

**Total:** 10 plans, average 656 seconds/plan

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
| 2 | 合并最新GRPO checkpoint到model目录 | 2026-02-15 | f0b914c | [2-grpo-checkpoint-model](./quick/2-grpo-checkpoint-model/) |

---

## Session Continuity

### Last Session Summary

**What:** Phase 06-01 — GRPO Pipeline Integration 执行

**Outcome:**
- 创建端到端流水线脚本 `docker/grpo_pipeline.sh`（385 行，5 步串联）
- 创建训练分析脚本 `src/scripts/analyze_grpo_training.py`（260 行）
- 更新 `config.json` 添加压缩函数配置和最少样本数阈值
- 更新 `src/grpo/rewards.py` 压缩函数可配置化

**Key Decisions:**
- 压缩函数字符串枚举设计（预留扩展其他函数）
- 训练前检查在 shell 层实现（汇总所有问题）
- 过滤后数据覆盖原始路径（带首次备份）
- 分析脚本独立于 pipeline（可单独调用）

**Next:** Phase 06-02 (UAT) 或 Phase 06-03

**Stopped At:** 完成 06-01-PLAN.md

### Context for Next Session

Phase 06-01 完成了 GRPO 端到端流水线集成：
1. pipeline 脚本串联 5 个步骤（数据生成→过滤→baseline→训练→分析）
2. 训练前检查（文件、样本数、baseline、reward 配置）
3. 训练分析工具（zero-std、reward 分布、趋势）
4. 压缩函数可配置化（从 config 读取，替代硬编码）

核心文件：
- `docker/grpo_pipeline.sh` — 端到端流水线入口脚本
- `src/scripts/analyze_grpo_training.py` — 训练分析脚本
- `config/config.json` — 压缩函数和阈值配置
- `src/grpo/rewards.py` — 可配置压缩函数

下一步：执行 Phase 06 后续计划（UAT 或文档完善）

---

*State initialized: 2026-02-09*
