# Phase 4: Reward Enhancement - Context

**Gathered:** 2026-02-10
**Status:** Ready for planning

<domain>
## Phase Boundary

改进 SUMO reward 公式和 baseline 基准策略，使不同质量的配时方案获得有区分度的连续分数，消除二值化问题。涵盖 RWD-01~04：非线性压缩、饱和度启发式 baseline、delay 指标、验证分布。

</domain>

<decisions>
## Implementation Decisions

### Reward 压缩函数
- 去掉 `min(combined, 1.0)` 的 cap，改用**改善率**计算：`improvement = (model - baseline) / baseline`
- 正值部分用 **log(1+x)** 非线性压缩，消除大值区间的二值化
- **允许负分**：比 baseline 差时得负分，为 GRPO 提供更强的对比信号
- 负分下界用比例控制：`-sumo_max_score * negative_ratio`，`negative_ratio` 默认 0.5，放在 config 中
- 当 baseline 某维度=0 时，该维度贡献 0 分（跳过），避免极端值

### Baseline 策略
- 从"默认信号周期仿真"改为**饱和度启发式基准**
- 分配逻辑：**线性插值** `green = min_green + min(pred_saturation, 1.0) * (max_green - min_green)`
- 数据来源：从 grpo_train.jsonl 的 prompt 中解析 phase_waits，获取 pred_saturation / min_green / max_green
- 输出：**覆盖旧的 baseline.json**，不新建文件
- 仿真方式：和之前一样跑 SUMO，只是绿灯时长换成饱和度启发式计算的值

### Delay 指标
- 采集方式：逐步遍历 controlled_lanes 上的车辆，累加 `traci.vehicle.getWaitingTime()`
- 只统计**目标交叉口**的车辆延误，不是全网
- 融入公式：**三维加权求和** `throughput_w * t_imp + queue_w * q_imp + delay_w * d_imp`
- delay 改善率方向：`(baseline_delay - model_delay) / max(baseline_delay, 1)`，延误越小越好
- 三个权重都放 config.json，**不预设默认值**，由用户配置
- baseline 也需要采集 delay 指标

### 验证与可视化
- 扩展现有 `test_rewards.py`，加入 SUMO reward 分布验证功能
- 小样本验证（50-100 条），覆盖不同场景
- 输出统计摘要到控制台（均值、标准差、分布分位数）
- 设定**自动检查规则**判断分布是否连续（如 reward 标准差阈值、唯一值数量等），不通过则报警
- 集成到 `grpo_train.sh` 中，训练前在 Docker 容器中自动运行验证，检查不通过则中止训练

### Claude's Discretion
- log(1+x) 压缩后的具体缩放系数（映射到 sumo_max_score 范围内的方式）
- 自动检查规则的具体阈值（标准差下界、唯一值数量下界）
- delay 采集时的车辆遍历优化细节
- test_rewards.py 中验证样本的选取策略（随机 vs 分层抽样）

</decisions>

<specifics>
## Specific Ideas

- queue_ratio 旧公式 `baseline_queue / max(model_queue, 1)` 存在设计缺陷（baseline_queue=0 时该维度永远为 0），改善率方案同时修复了这个问题
- 现有 test_rewards.py 只测试 L1/L2/think 的格式验证，不涉及 SUMO 仿真，需要扩展
- 所有代码都必须在 Docker 中执行，验证脚本集成时需要注意 Docker 环境

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 04-reward-enhancement*
*Context gathered: 2026-02-10*
