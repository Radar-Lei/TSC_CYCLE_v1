# Project State: TSC-CYCLE

**Last Updated:** 2026-02-10

---

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-10)

**Core value:** 给定交叉口实时交通状态,大模型输出的信号配时方案能最大化车辆通过量、最小化排队车辆数
**Current focus:** v1.1 Phase 4 - Reward Enhancement

---

## Current Position

**Active Milestone:** v1.1 Improve Reward & GRPO Data Filter
**Active Phase:** Phase 4 of 6 (Reward Enhancement)
**Active Plan:** Ready to plan
**Current Status:** Roadmap created, ready to plan Phase 4

**Last activity:** 2026-02-10 — v1.1 roadmap created

Progress: [████████████░░░░░░░░] 50% (3 of 6 phases complete across all milestones)

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

**Total:** 6 plans, average 317 seconds/plan

---

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

**What:** v1.1 Roadmap 创建

**Outcome:**
- 从 v1.1 的 8 个 requirements 中识别出 3 个自然阶段
- Phase 4: Reward Enhancement (RWD-01/02/03) — 改进公式 + baseline 策略
- Phase 5: Data Filtering (DAT-01/02) — 过滤空交叉口 + 统计输出
- Phase 6: Integration (INT-01/02/03) — 配置 + 训练脚本 + Docker 流程集成
- 100% requirement coverage 验证完成（8/8 mapped）

**Next:** `/gsd:plan-phase 4` — 规划 Reward Enhancement 阶段

**Stopped At:** Roadmap creation complete

### Context for Next Session

Phase 4 将改进三个紧密耦合的部分：
1. SUMO reward 公式（去掉 cap，用非线性压缩）
2. Baseline 策略（从默认周期改为饱和度启发式）
3. Baseline 预计算脚本（重新生成 baseline.json）

核心文件：
- `src/grpo/rewards.py` — SUMO reward 计算逻辑
- `src/grpo/baseline.py` — Baseline 预计算脚本
- `config/config.json` — 配置驱动

---

*State initialized: 2026-02-09*
