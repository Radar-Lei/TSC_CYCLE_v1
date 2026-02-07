# TSC_CYCLE - 交通信号控制训练流水线

## What This Is

基于 SUMO 交通仿真的信号控制优化训练流水线。通过数据生成 → SFT → GRPO 三阶段训练，让大语言模型学会输出优化的交通信号周期控制策略。流水线从 SUMO 仿真采集原始数据，转换为带 Chain-of-Thought 推理格式的训练数据，经过监督微调学习格式，最终通过 GRPO 强化学习优化信号控制策略。

## Core Value

能够一键执行完整的训练流水线（数据生成 → SFT → GRPO），稳定地从 SUMO 仿真数据生成到强化学习微调，输出可用的交通信号控制模型。

## Requirements

### Validated

<!-- 从现有代码库推断出的已实现功能 -->

- ✓ SUMO 交通仿真集成 — existing
- ✓ 相位配置自动解析（phase_processor）— existing
- ✓ 多阶段训练流程（SFT + GRPO）— existing
- ✓ Unsloth + LoRA 加速训练框架 — existing
- ✓ Docker 容器化部署 — existing
- ✓ 训练数据 JSONL 格式 — existing
- ✓ 状态快照保存和恢复 — existing
- ✓ 周期边界检测机制 — existing

### Active

<!-- 当前需要修复和实现的功能 -->

- [ ] 交叉口级并行数据生成（修复嵌套并行问题）
- [ ] 分阶段执行入口（run.sh 支持 --stage=data/sft/grpo）
- [ ] 清理冗余配置（移除时段配置等不需要的参数）
- [ ] 简化并行逻辑（单层并行，以交叉口为单位）
- [ ] 场景自动发现（扫描 sumo_simulation/environments/ 子文件夹）
- [ ] 数据生成到训练的完整流程验证
- [ ] 小规模快速验证模式（1-2 场景 × 1-2 交叉口）

### Out of Scope

- 多时段仿真 — 所有仿真固定 3600 秒，不需要时段配置
- 非 Docker 执行 — 所有代码必须在 Docker 环境中运行
- 实时在线控制 — 当前专注于离线训练流水线
- 模型性能优化 — 当前专注于流程稳定性，模型效果后续优化

## Context

**现有系统状态：**
- 代码库已实现基础的数据生成和训练流程
- 数据生成并行逻辑存在问题（嵌套并行导致失败）
- 配置文件包含冗余参数（如时段配置，实际不需要）
- 训练流程需要手动分步执行，缺少统一入口

**技术环境：**
- Python 3.14.2
- SUMO 交通仿真引擎
- Unsloth 训练加速框架
- Qwen3-4B-Base 基础模型
- CUDA GPU 加速
- Docker 容器部署

**数据流：**
1. SUMO 仿真生成原始交通数据（3600 秒场景）
2. 周期边界检测并采样状态快照
3. 转换为 CoT 格式训练数据（二度生成）
4. SFT 训练学习输出格式（包括隐式推理格式）
5. GRPO 强化学习优化信号控制策略

**已知问题：**
- 数据生成阶段并行执行失败
- 配置参数混乱（有不需要的时段配置）
- 代码可能存在冗余
- 流程依赖关系不清晰

## Constraints

- **执行环境**: 所有代码必须在 Docker 容器中运行（run.sh 入口）
- **仿真时长**: 固定 3600 仿真秒，不支持可变时段
- **场景来源**: `sumo_simulation/environments/` 下的子文件夹，每个子文件夹一个场景
- **并行单元**: 交叉口级别并行，不嵌套多层并行
- **GPU 要求**: NVIDIA GPU + CUDA 支持
- **共享内存**: Docker 需要至少 32GB shm-size

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| 使用 Unsloth 加速训练 | 相比原生 Transformers，训练速度提升 2-5 倍，内存占用降低 | ✓ Good |
| 选择 GRPO 而非 PPO | GRPO 更适合生成任务的奖励建模，收敛更稳定 | — Pending |
| 交叉口级并行而非场景级 | 交叉口间独立，粒度更细，利用率更高 | ⚠️ Revisit — 当前并行逻辑有问题 |
| 固定 3600 秒仿真时长 | 简化配置，所有场景统一处理，避免时段复杂度 | ✓ Good |
| Docker 容器化部署 | 统一依赖环境（SUMO + Python + CUDA），避免环境问题 | ✓ Good |
| 二度数据生成策略 | 原始仿真数据 → CoT 格式数据，分离关注点 | — Pending |

---
*Last updated: 2026-02-07 after initialization*
