# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-04)

**Core value:** 让模型自己学会"思考"如何优化交通信号周期
**Current focus:** Phase 3 - SFT 预训练

## Current Position

Phase: 5 of 5 (Docker 部署环境)
Plan: 5 of 5 in current phase
Status: All phases complete
Last activity: 2026-02-05 — Completed 05-05-PLAN.md (Gap Closure: --config 参数 + Docker 入口脚本)

Progress: [██████████] 100%

## Performance Metrics

**Velocity:**
- Total plans completed: 17
- Average duration: 6.0 min
- Total execution time: 1.7 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 1 | 3 | 15 min | 5 min |
| 2 | 3 | 20 min | 6.7 min |
| 3 | 3 | 18 min | 6 min |
| 4 | 3 | 19 min | 6.3 min |
| 5 | 5 | 33 min | 6.6 min |

**Recent Trend:**
- Last 5 plans: 05-01 (5 min), 05-02 (5 min), 05-03 (3 min), 05-04 (8 min), 05-05 (12 min)
- Trend: 全部 5 个 Phase 完成,Gap Closure 完成,Docker 部署环境完全就绪,可一键运行完整训练流程

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
- THINKING_START/END 使用 <think></think> (03-02) - 与 DeepSeek R1 格式一致,清晰标记思考过程
- LoRA rank=32, alpha=64 (03-02) - 参考 Qwen3 GRPO notebook,中等配置平衡性能和训练速度
- SFT 使用 16bit 而非 4bit (03-02) - 16bit 精度更高,SFT 阶段需要准确学习格式
- 集成 chat_template 到 load_model_for_sft (03-02) - 确保模型加载后 tokenizer 已配置好,避免遗忘
- device_map=None 避免与 Trainer 冲突 (03-03) - Unsloth 默认 device_map='auto',与 Transformers Trainer 不兼容
- Docker 使用 --user 和 --entrypoint (03-03) - 绕过容器入口脚本权限问题,直接执行 python3
- SFT 训练 300 steps (03-03) - 对 80 个手工示例足够学习格式,生成 253MB LoRA adapter
- 格式奖励参考 Qwen3 GRPO notebook (04-01) - 完全匹配 +3.0, 部分匹配按符号计分
- 无效相位配置返回 -2.0 (04-01) - 引导模型学习有效配置
- 奖励权重默认格式 20%, 仿真 80% (04-01) - 优先关注交通效果,保留格式引导
- 使用 signal.alarm 实现 120 秒超时机制 (04-02) - 防止 SUMO 仿真卡死
- 评估失败返回 -1.0,JSON 解析失败返回 0.0 (04-02) - 引导模型避免无效方案,避免过度惩罚格式错误
- 三个指标等权分配 (04-02) - 排队 33%、通行 33%、等待 34%,平衡三个维度
- 参考值选择排队 50 辆、通行 100 辆、等待 60 秒 (04-02) - 基于典型路口规模
- 数据加载支持 limit 参数 (04-03) - 调试时可以快速验证流程,例: --data-limit 100
- 支持 --disable-simulation 参数 (04-03) - 仿真需要 SUMO 环境,调试时可以只用格式奖励
- GRPO 使用 4bit 量化 (04-03) - GRPO 显存占用高,4bit 节省内存,可在 16GB GPU 上训练
- 复用 SFT 的 chat_template (04-03) - 保持 SFT 和 GRPO 的输入格式一致,训练更稳定
- 使用 JSON 而非 YAML (05-01) - 单一 config.json 文件简化配置管理
- jsonschema 作为可选依赖 (05-01) - fallback 机制确保在缺少 jsonschema 时也能工作
- 点号路径访问嵌套配置 (05-01) - get_config_value 支持 "training.sft.max_steps" 格式
- 检查点双重验证 (05-02) - 状态文件 + 输出文件存在性双重检查,防止不一致
- 日志按阶段分离 (05-02) - logs/${DATE}-${stage_name}.log 模式,便于调试
- PIPESTATUS[0] 保留退出码 (05-02) - tee 管道中获取真实命令退出码
- 使用 JSON 配置替代 YAML (05-03) - jq 读取 config.json,简化配置管理
- 阶段函数返回值表示成功/失败 (05-03) - 主流程用 || exit 1 快速失败
- entrypoint.sh 启动 Xvfb (05-03) - 提供虚拟 X server 给 SUMO 使用
- 在第一个 apt-get 步骤添加 jq (05-04) - 避免额外的镜像层,减少镜像大小
- COPY entrypoint.sh 在 USER 切换前 (05-04) - 确保 entrypoint.sh 具有正确权限
- 预创建工作目录 (05-04) - 避免运行时权限问题

### Pending Todos

None yet.

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 001 | 更换数据生成源为 sumo_simulation/environments 子文件夹 | 2026-02-07 | 8cc9560 | [001-sumo-simulation-environments](.planning/quick/001-sumo-simulation-environments/) |

### Blockers/Concerns

**部分路口相位不足** (01-02 发现, 01-03 已统计)
- 现象: 28/46 个路口被跳过 (60.9%),冲突解决后相位不足
- 原因: 原始路网配置的相位本身就有严重冲突
- 影响: Phase 2 只能使用 18 个有效路口进行强化学习训练
- 解决方案: 如需更多路口,可考虑放宽验证标准或使用更复杂的冲突解决算法

## Session Continuity

Last activity: 2026-02-07 - Completed quick task 001: 更换数据生成源为 sumo_simulation/environments 子文件夹
Last session: 2026-02-07
Stopped at: Quick task 001 完成 - 多场景数据生成支持
Resume file: None
Next: 执行 ./docker/publish.sh 启动 51 个场景的完整数据生成
