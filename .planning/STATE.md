# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-04)

**Core value:** 让模型自己学会"思考"如何优化交通信号周期
**Current focus:** Phase 3 - SFT 预训练

## Current Position

Phase: 3 of 5 (SFT 预训练)
Plan: 0 of ? in current phase
Status: Ready for planning
Last activity: 2026-02-05 — Completed Phase 2 (训练数据生成)

Progress: [██████░░░░] 60%

## Performance Metrics

**Velocity:**
- Total plans completed: 6
- Average duration: 6 min
- Total execution time: 0.57 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 1 | 3 | 15 min | 5 min |
| 2 | 3 | 20 min | 6.7 min |

**Recent Trend:**
- Last 5 plans: 01-03 (5 min), 02-01 (5 min), 02-02 (6 min), 02-03 (9 min)
- Trend: Slight increase (complex integration tasks)

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
- 使用 dataclass 实现数据模型 (02-01) - 自动生成 __init__ 和 __repr__,支持 to_dict/from_dict 序列化
- 自适应采样采用三级策略 (02-01) - 高变化(>50%)立即采样,中等变化(>30%)缩短间隔,低变化使用基础间隔
- prev_queue_state 在 record_sample 更新 (02-01) - 使用 .copy() 避免外部修改,用于 should_sample 计算变化率
- 状态文件名包含日期、时间、信号灯ID (02-01) - 避免冲突,默认使用 .xml.gz 压缩节省空间
- 高斯噪声标准差默认为真实值的 10% (02-02) - 平衡数据多样性和真实性,10% 是合理的测量误差范围
- 时间波动范围 ±2-5 秒,边界约束 5-120s (02-02) - 2-5 秒波动增加多样性且不偏离原始配置,min_green 5-60s 避免频繁切换,max_green 30-120s 确保足够时间
- 容量估算每条车道 15 辆车 (02-02) - 简单线性估算,总容量 15-60 避免极端值
- traci 调用失败时返回默认值 0 (02-02) - 避免异常中断数据收集,在无 SUMO 连接时也能测试
- 时段定义: 早高峰 07:00-09:00, 晚高峰 17:00-19:00 (02-03) - 基于典型城市交通模式
- 端口分配策略: 10000 + day_index (02-03) - 避免并行 SUMO 实例的 TraCI 端口冲突
- 增量模式默认开启 (02-03) - 跳过已存在输出文件,支持中断后继续运行
- 每天数据保存为独立 JSONL 文件 (02-03) - 便于按日期管理,支持流式读取

### Pending Todos

None yet.

### Blockers/Concerns

**部分路口相位不足** (01-02 发现, 01-03 已统计)
- 现象: 28/46 个路口被跳过 (60.9%),冲突解决后相位不足
- 原因: 原始路网配置的相位本身就有严重冲突
- 影响: Phase 2 只能使用 18 个有效路口进行强化学习训练
- 解决方案: 如需更多路口,可考虑放宽验证标准或使用更复杂的冲突解决算法

## Session Continuity

Last session: 2026-02-05
Stopped at: Completed 02-03-PLAN.md (并行仿真与 CLI) - Phase 2 complete
Resume file: None
Next: Phase 03 - 强化学习训练
