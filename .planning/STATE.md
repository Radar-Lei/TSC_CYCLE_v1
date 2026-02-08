# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-07)

**Core value:** 能够一键执行完整的训练流水线（数据生成 → SFT → GRPO），稳定地从 SUMO 仿真数据生成到强化学习微调，输出可用的交通信号控制模型。
**Current focus:** Phase 3 - Training Pipeline

## Current Position

Phase: 3 of 4 (Training Pipeline)
Plan: 2 of 3
Status: In progress
Last activity: 2026-02-08 — Completed 03-02-PLAN.md

Progress: [███████░░░] 70%

## Performance Metrics

**Velocity:**
- Total plans completed: 8
- Average duration: 4.1 minutes
- Total execution time: 0.55 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01 | 3 | 14 min | 4.7 min |
| 02 | 3 | 11 min | 3.7 min |
| 03 | 2 | 11 min | 5.5 min |

**Recent Trend:**
- Last 5 plans: 02-02 (4 min), 02-03 (4 min), 03-01 (4 min), 03-02 (7 min)
- Trend: Consistent high velocity (~4-7 min/plan)

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- 删除时段配置 — 固定 3600s 仿真时长使时段配置不必要（01-01）
- 删除 schema 验证 — config.json 作为唯一配置源（01-01）
- 扁平任务池模式 — 所有场景×交叉口展开为统一任务列表（01-02）
- Shell 脚本简化为 4 个独立脚本（01-03）
- 统一输出路径到 outputs/（01-03）
- CoT 空占位策略 — <think>\n\n</think> 不预生成推理文本，让模型自主学习（02-02）
- 智能饱和度插值 — final 基于 pred_saturation 线性插值 min_green 到 max_green（02-02）
- 动态首绿相位检测 — CycleDetector 从 phase_config 提取首绿相位 index，支持任意相位序列（02-03）
- 分级格式奖励 — 统一 graded_format_reward 替代二元精确/近似匹配（03-02）
- NaN 跳过策略 — 仿真失败返回 NaN 而非固定负奖励，TRL 自动排除梯度计算（03-02）

### Pending Todos

None yet.

### Blockers/Concerns

**Phase 1 (complete):**
- ✓ 时段配置相关代码已全部移除
- ✓ 嵌套并行逻辑已重构为扁平任务池
- ✓ Shell 脚本已简化为 4 个独立脚本
- ✓ 验证通过（10/10 must-haves）

**Phase 2 (complete):**
- ✓ 数据生成核心流程参数已修复（02-01 完成）
- ✓ 交叉口级并行执行支持完整（metadata 字段已添加）
- ✓ CoT 格式 SFT 训练数据转换完成（02-02 完成）
- ✓ 周期边界全量采样验证通过（02-02 验证）
- ✓ 动态绿相检测完成（02-03 完成）

**Phase 3 readiness:**
- ✓ SFT 训练流程修复完成（03-01 完成）
- ✓ GRPO 奖励函数重构完成（03-02 完成）
- 格式奖励采用三级分级评分（think 标签 / JSON 可解析 / 字段完整）
- 仿真失败时返回 NaN，不参与梯度计算
- 数据加载路径与 Phase 2 输出一致（outputs/training/）

## Session Continuity

Last session: 2026-02-08
Stopped at: Phase 3 Plan 2 complete
Resume file: .planning/phases/03-training-pipeline/03-03-PLAN.md
