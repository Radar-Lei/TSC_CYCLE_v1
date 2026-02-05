# Phase 4: GRPO 强化学习 - Context

**Gathered:** 2026-02-05
**Status:** Ready for planning

<domain>
## Phase Boundary

让模型从 SUMO 仿真反馈中学会推理最优信号周期。实现 GRPO 训练循环:模型根据 Phase 2 保存的状态快照生成周期方案 → SUMO 仿真评估效果 → 奖励信号反馈 → 模型参数更新。不包括新场景扩展、可视化工具等其他能力。

</domain>

<decisions>
## Implementation Decisions

### 奖励函数设计

#### 格式奖励
- **Claude 决定具体实现**
- 参考 notebook 风格:格式完全正确 +3.0,部分正确按符号计分(每个符号 ±0.5)

#### 仿真指标
- **使用三个指标综合评估:**
  - 排队长度 (`traci.getLastStepHaltingNumber`)
  - 通行量 (departed vehicles)
  - 等待时间 (`traci.getWaitingTime`)

#### 奖励组合
- **格式 20% + 仿真 80%** - 优先关注交通效果,但保留格式引导

#### 指标权重
- **Claude 决定** - 在等待时间、通行量、排队长度之间平衡分配权重

### 仿真评估策略

#### 评估时长
- **1 个周期 (60-90s)** - 从状态快照恢复后,应用方案仿真 1 个信号周期评估效果

#### 并行策略
- **并行评估 (multiprocessing)** - 每个 batch 的多个方案并行启动 SUMO 实例,加速评估

#### 失败处理
- **Claude 决定** - 处理仿真超时、崩溃、无法加载状态等异常情况

#### SUMO 进程管理
- **复用 SUMO 进程** - 避免频繁重启,通过 `traci.simulation.loadState()` 加载不同状态快照

### 训练循环配置

**参考 `Qwen3_(4B)_GRPO.ipynb` 配置:**

#### 训练规模
- **max_steps = 100** - 快速验证,适合初期调试

#### Batch 配置
- **更平滑训练:**
  - `per_device_train_batch_size = 1`
  - `num_generations = 4`
  - `gradient_accumulation_steps = 4` - 提升训练稳定性

#### 学习率
- **learning_rate = 5e-6** - notebook 推荐的 GRPO 学习率

#### 其他超参数
- `warmup_ratio = 0.1`
- `lr_scheduler_type = "linear"`
- `optim = "adamw_8bit"`
- `weight_decay = 0.001`
- `temperature = 1.0`

### 输出处理与容错

#### 格式错误
- **notebook 风格(完全+部分奖励)**
  - 格式完全匹配:`<think>...</think>[{phase_id, final}...]` → +3.0
  - 部分匹配:按符号数量计分(每个 `</think>`, `[`, `]` 等 ±0.5)
  - 完全错误:负奖励

#### 思考过程
- **Claude 决定** - `<think>` 部分是否计入训练 loss

#### 无效相位配置
- **给负奖励 (-2.0)** - 相位 ID 不存在或时间超出范围时惩罚,引导模型学习有效配置

</decisions>

<specifics>
## Specific Ideas

**关键澄清:**
- Phase 2 已保存每条数据对应的 SUMO 状态快照(`.xml.gz` 文件)
- GRPO 训练时从 `state_file` 路径恢复状态,应用模型生成的方案,仿真 1 个周期评估效果
- **不是**反复运行同一个方案,而是每条数据恢复到采样时的状态快照

**Notebook 参考:**
- 使用 `Qwen3_(4B)_GRPO.ipynb` 作为实现参考
- 奖励函数设计借鉴 notebook 的多级奖励策略(格式+答案+近似匹配)
- 训练配置复用 notebook 的超参数设置

</specifics>

<deferred>
## Deferred Ideas

无 — 讨论始终围绕 GRPO 训练循环实现,未涉及范围外功能。

</deferred>

---

*Phase: 04-grpo-强化学习*
*Context gathered: 2026-02-05*
