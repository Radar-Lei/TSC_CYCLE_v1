# TSC-CYCLE

## What This Is

交通信号控制 AI 训练系统。使用 Qwen3-4B 模型通过 SFT 和 GRPO 强化学习训练，让模型能够根据交通状态输出最优信号配时方案。包含完整的数据生成、模型训练和评估流程。

## Core Value

训练出能通过思维链推理优化交通信号配时的 AI 模型，提升交通效率，减少拥墙。

## Requirements

### Validated

- ✓ 数据生成流程 — 从 SUMO 仿真生成训练样本
- ✓ SFT 训练流程 — Qwen3-4B-Base + LoRA 微调
- ✓ GRPO 训练流程 — 多层奖励函数强化学习
- ✓ Benchmark 评估框架 — 模型对比评估系统
- ✓ 加权平均统计 — v1.0 (按周期时长加权)
- ✓ Throughput 指标 — v1.0 (通过车辆数/秒)

### Active

- [ ] SFT 训练流程迁移到 GLM-4.7-Flash-FP8-Dynamic
- [ ] 验证 GLM tokenizer 自定义标签兼容性

### Out of Scope

- API 服务部署 — 仅本地运行
- 实时控制系统 — 当前仅离线评估
- 移动端支持 — 桌面优先

## Context

**当前状态 (v1.0 shipped):**
- Benchmark 评估系统支持加权平均统计
- Comparison CSV 包含 throughput 列
- 21 个单元测试覆盖统计逻辑

**技术栈：**
- 模型：Qwen3-4B-Base + LoRA (rank 32)
- 训练：Unsloth, TRL (SFTTrainer/GRPOTrainer)
- 仿真：SUMO/TraCI
- 自定义标签：`<start_working_out>`/`<end_working_out>`/`<SOLUTION>`/`</SOLUTION>`

**已知问题：**
- Qwen3 tokenizer 中 ` comienza`/` termina` 是 added tokens，不能用于 SFT 自定义标签（已改用不在词表中的标签）

**数据流：**
1. SUMO 仿真 → 训练样本 (train.jsonl)
2. SFT 训练 → 基础模型
3. GRPO 训练 → 强化模型
4. Benchmark 评估 → 性能对比

## Constraints

- **环境**：本地/服务器运行，Docker 容器化
- **模型**：Qwen3-4B 系列固定
- **仿真**：依赖 SUMO 交通仿真器

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| 使用 `<start_working_out>` 替代 ` comienza` | 避免 tokenizer 语义冲突 | ✓ Good |
| SFT 训练 2 epochs | 1 epoch 不够充分 | ✓ Good |
| LoRA rank 32 | 平衡效果和资源 | ✓ Good |
| 加权平均使用 samples length 作为权重 | 周期时长直接影响统计意义 | ✓ Good |
| Throughput 计算方式：先按周期再加权 | 避免 total/total 的偏差 | ✓ Good |
| `weighted_summary` 参数可选 | 向后兼容现有调用 | ✓ Good |

## Current Milestone: v1.1 模型迁移

**Goal:** 将 SFT 训练流程迁移到 GLM-4.7-Flash-FP8-Dynamic，提升模型质量

**Target features:**
- SFT 训练流程适配 GLM-4.7-Flash
- GLM tokenizer 自定义标签兼容性验证

**Out of scope for this milestone:**
- GRPO 训练流程
- Benchmark 评估更新
- Docker 脚本更新

---
*Last updated: 2026-02-18 after starting v1.1 milestone*
