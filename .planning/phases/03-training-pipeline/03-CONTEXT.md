# Phase 3: Training Pipeline - Context

**Gathered:** 2026-02-08
**Status:** Ready for planning

<domain>
## Phase Boundary

SFT 和 GRPO 训练流程能够正常执行并产出模型。从已生成的 JSONL 训练数据出发，完成有监督微调（SFT）和群体相对策略优化（GRPO）两阶段训练，输出可用的交通信号控制模型。不包含统一执行入口和端到端验证（属于 Phase 4）。

</domain>

<decisions>
## Implementation Decisions

### 训练数据准备
- SFT 数据需要 train/val 划分（如 90/10），用验证集监控过拟合
- GRPO 是在线 RL，不需要传统 train/val 划分
- 不做额外数据过滤/校验 — 信任数据生成流程的输出质量；异常输出由 GRPO 奖励函数给低分引导纠正
- SFT 数据预处理生成已应用 chat template 的格式，训练时直接加载（不在 trainer 中动态转换）

### SFT 训练配置
- 小规模优先（100-300 steps），先跑通流程再调优
- 去掉 4-bit 量化，使用 bf16 全精度 LoRA 微调
- LoRA 参数保持现有（rank=32, alpha=64），仅去掉量化
- Checkpoint 定期保存 + 滚动删除（每 N 步保存，保留最近 K 个）

### GRPO 奖励设计
- 格式奖励与仿真奖励权重保持 0.2/0.8
- 格式奖励采用分级评分（<think> 标签正确得部分分，JSON 可解析得部分分，字段完整得满分）
- 仿真失败时（SUMO 崩溃或超时）跳过该样本，不纳入梯度计算
- 仿真奖励的交通指标保持现有（平均等待时间、排队长度等）

### 训练流程串联
- SFT 和 GRPO 分步执行，不自动串联
- SFT 模型通过固定路径约定传递给 GRPO（如 outputs/sft_model/）
- 支持从 checkpoint 恢复训练
- 训练监控使用终端打印 + 日志文件，不集成可视化工具

### Claude's Discretion
- SFT train/val 的具体划分比例
- Checkpoint 保存频率和保留数量
- 格式奖励各级别的具体分值
- 日志文件的格式和内容详细程度
- 具体的学习率和优化器参数调整

</decisions>

<specifics>
## Specific Ideas

- 基础模型为 unsloth/Qwen3-4B-Base，使用 LoRA 微调
- 训练框架使用 TRL（SFTTrainer + GRPOTrainer）
- GRPO 阶段使用 vLLM 进行高效采样
- 仿真奖励通过 SUMO/TraCI 接口评估信号配时方案
- SFT 输出格式为 `<think>\n\n</think>[{...}]`（CoT 空占位策略）

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 03-training-pipeline*
*Context gathered: 2026-02-08*
