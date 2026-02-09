# Phase 3: GRPO 训练 - Context

**Gathered:** 2026-02-10
**Status:** Ready for planning

<domain>
## Phase Boundary

通过实时 SUMO 仿真 reward 优化模型配时方案质量。从 SFT 合并模型开始，使用 GRPO 强化学习结合 SUMO 仿真反馈，让模型学会输出更优的信号配时方案。

</domain>

<decisions>
## Implementation Decisions

### Reward 函数设计
- **三层分层结构**：L1 格式 → L2 约束 → L3 SUMO 仿真
- **L1 格式层**：参考 qwen3_(4b)_grpo.py 的精确匹配 + 近似匹配两个函数
  - `match_format_exactly`: 标签完整且内容可解析时给高分
  - `match_format_approximately`: 按标签出现次数给渐进分
  - 标签格式为 `<think>...</think><CyclePlan>...</CyclePlan>`（与 SFT 一致）
- **L2 约束层**：渐进式约束评分
  - 相位顺序正确性：按正确比例给分
  - 绿灯时长约束 (min_green ≤ final ≤ max_green)：按满足比例给分
  - 不是二元制，部分满足也给部分分
- **L3 SUMO 仿真层**：仅当 L1 格式正确 + L2 所有约束全部满足时才执行仿真
  - 仿真指标：车辆通过量 + 排队车辆数（加权组合）
  - 归一化方式：相对于原始方案的基准值
  - 基准值预计算：训练前对每个 state file 用原始配时方案跑一次 SUMO 仿真，结果存入 `outputs/grpo/baseline.json`（按 state_file 索引）
  - 约束不满足时仿真 reward 为 0
- **think 长度惩罚**：长度范围惩罚（过短或过长都扣分）
- **Reward 函数数量**：参考脚本模式，多个 reward 函数并行叠加分数

### SUMO 仿真集成
- **集成方式**：TraCI + loadState
  - 通过 TraCI 接口连接 SUMO，用 loadState 加载状态文件
  - 设置模型输出的配时方案，仿真一个信号周期
  - 统计周期内的车辆通过量和排队数
- **仿真时长**：一个信号周期（每条数据对应下一个周期的配时优化）
- **并行策略**：预加载进程池
  - 进程池大小 = num_generations（每个候选方案一个 worker）
  - 每个 worker 维护一个 TraCI 连接
  - 一批候选方案全部并行完成后才计算 reward
- **部署环境**：Docker 容器内直接调用 SUMO（无头模式 sumo，非 sumo-gui）
- **文件访问**：项目根目录挂载到容器内
  - state file：`outputs/states/` 下 21 个子目录（20 个 arterial4x4 + 1 个 chengdu）
  - sumocfg 映射：
    - arterial4x4_* → `sumo_simulation/arterial4x4/arterial4x4_*/arterial4x4.sumocfg`
    - chengdu → `sumo_simulation/environments/chengdu/chengdu.sumocfg`
- **参考代码**：`sumo_simulation/sumo_simulator.py` 可参考，更多信息参考 `sumo_simulation/sumo_docs/` 中的 SUMO 文档
- **基准预计算**：Phase 3 新建 `docker/grpo_baseline.sh` 脚本，结果存到 `outputs/grpo/baseline.json`

### GRPO 训练超参数
- **所有超参数写在 config.json 中**，便于随时调整
- **num_generations**：暂定 4（可调整）
- **训练规模**：max_steps 控制（可调整）
- **不使用 vLLM**：环境不支持 vLLM，使用 `use_vllm=False`，回退到 Hugging Face 推理模式
  - 对应：`fast_inference=False`（加载模型时）
  - 去掉 `vllm_sampling_params` 相关配置
- **起始模型**：加载 SFT 训练后的合并模型 (outputs/sft/model)
- **保存方式**：合并 LoRA 保存 merged_16bit 到 outputs/grpo/model
- **其他超参数**：参考 qwen3_(4b)_grpo.py，写入 config.json

### 容错与异常处理
- **SUMO 仿真崩溃/异常**：直接终止程序报错（loadState 失败、TraCI 断开等系统级异常不容忍）
- **单次仿真超时**：60 秒现实时间超时限制，超时终止报错

### Claude's Discretion
- Reward 分数的具体数值设计（各层分值大小）
- 分层门槛式 vs 并行叠加式的具体实现（倾向参考脚本的并行叠加模式）
- think 长度惩罚的具体 token 范围阈值
- 通过量与排队数的加权比例
- 学习率、KL 系数、warmup 等具体超参数默认值
- 进程池的具体实现方式（multiprocessing Pool / concurrent.futures）
- Docker 脚本的具体结构

</decisions>

<specifics>
## Specific Ideas

- 参考 `qwen3_(4b)_grpo.py` 的整体训练框架和 reward 函数设计模式
- 标签格式已从参考脚本的 `<start_working_out>/<SOLUTION>` 更新为 `<think>/<CyclePlan>`
- 基准值用单独文件存储（baseline.json），避免修改 Phase 2 的数据
- 用户提供了不使用 vLLM 的代码示例，明确了 `use_vllm=False` 的配置方式

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 03-grpo-training*
*Context gathered: 2026-02-10*
