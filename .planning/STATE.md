# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-04)

**Core value:** 让模型自己学会"思考"如何优化交通信号周期
**Current focus:** Phase 1 - 相位处理系统

## Current Position

Phase: 1 of 5 (相位处理系统)
Plan: 3 of 3 in current phase
Status: Phase complete
Last activity: 2026-02-04 — Completed 01-03-PLAN.md (主处理流程)

Progress: [███░░░░░░░] 30%

## Performance Metrics

**Velocity:**
- Total plans completed: 3
- Average duration: 5 min
- Total execution time: 0.25 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 1 | 3 | 15 min | 5 min |

**Recent Trend:**
- Last 5 plans: 01-01 (4 min), 01-02 (6 min), 01-03 (5 min)
- Trend: Steady

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- 使用 GRPO 而非监督学习 - 无法获取高质量的 thinking 过程标注,GRPO 可从仿真反馈中自主学习
- 相位冲突用简单策略(保留绿灯多的) - 避免复杂的相位拆分逻辑,优先保证互斥性
- 用 multiprocessing 并行 SUMO - 相比分布式框架更轻量,单机性能足够
- SFT 阶段手工编写示例 - 50-100 条足够让模型学会格式,避免大量标注成本
- 只用 chengdu 场景 - 专注于单场景深度优化,避免多场景泛化复杂性
- 使用 Set[str] 存储 green_lanes (01-01) - 自动去重,支持集合操作,用于冲突检测
- 同时识别 'G' 和 'g' 作为绿灯信号 (01-01) - SUMO 中两者都需要计入冲突检测
- 无绿灯信号即判定为无效相位 (01-02) - 只有黄灯或红灯的相位无法通行,不能用于交通控制
- 任意绿灯车道重叠即判定为冲突 (01-02) - 即使只有 1 条车道重叠也会导致交通冲突
- 冲突解决优先保留绿灯多的相位 (01-02) - 绿灯车道多的相位通行能力更强,贪心算法保证高通行能力
- 绿灯数相等时随机选择 (01-02) - 没有明确的优劣判断标准,随机选择避免固定偏好
- 优先从 SUMO 文件读取 minDur/maxDur (01-03) - 保留原始配置作为基准,缺失时才随机生成
- 缺失值在 5-120 秒范围内随机生成 (01-03) - 太短导致频繁切换,太长影响通行效率
- apply_time_variation 应用 ±2-5 秒随机波动 (01-03) - 生成训练数据多样性,避免过拟合固定时间配置
- CLI 输出同时包含 console 摘要和详细日志 (01-03) - 用户需要快速查看结果,同时保留完整日志用于调试

### Pending Todos

None yet.

### Blockers/Concerns

**部分路口相位不足** (01-02 发现, 01-03 已统计)
- 现象: 28/46 个路口被跳过 (60.9%),冲突解决后相位不足
- 原因: 原始路网配置的相位本身就有严重冲突
- 影响: Phase 2 只能使用 18 个有效路口进行强化学习训练
- 解决方案: 如需更多路口,可考虑放宽验证标准或使用更复杂的冲突解决算法

## Session Continuity

Last session: 2026-02-04
Stopped at: Completed 01-03-PLAN.md (Phase 1 完成)
Resume file: None
Next: Phase 2 - SUMO 环境封装
