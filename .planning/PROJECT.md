# TSC-CYCLE

## What This Is

交通信号控制 AI 训练系统。使用 Qwen3-4B 模型通过 SFT 和 GRPO 强化学习训练，让模型能够根据交通状态输出最优信号配时方案。包含完整的数据生成、模型训练、GGUF 导出和评估流程。

## Core Value

训练出能通过思维链推理优化交通信号配时的 AI 模型，提升交通效率，减少拥堵。

## Requirements

### Validated

- ✓ 数据生成流程 — 从 SUMO 仿真生成训练样本
- ✓ SFT 训练流程 — Qwen3-4B-Base + LoRA 微调
- ✓ GRPO 训练流程 — 多层奖励函数强化学习
- ✓ Benchmark 评估框架 — 模型对比评估系统
- ✓ 加权平均统计 — v1.0 (按周期时长加权)
- ✓ Throughput 指标 — v1.0 (通过车辆数/秒)
- ✓ 增强训练数据 — v1.1 (思考链 300-400 token)
- ✓ Tokenizer 兼容性验证 — v1.1 (Qwen3 无 added token 冲突)
- ✓ SFT 代码迁移与训练 — v1.1 (Qwen3-4B LoRA r=16/alpha=16)
- ✓ F16 GGUF 导出 — v1.1 (7.5GB, 398 tensors)
- ✓ Q4_K_M GGUF 量化 — v1.1 (2.4GB)
- ✓ GGUF 测试脚本 — v1.1 (sft_test.sh --gguf)
- ✓ LM Studio 部署 — v1.1 (符号链接就绪)

### Active

(None — planning next milestone)

### Out of Scope

- API 服务部署 — 仅本地运行
- 实时控制系统 — 当前仅离线评估
- 移动端支持 — 桌面优先
- GLM-4.7-Flash 迁移 — FP8 兼容性问题，Qwen3 已满足需求

## Context

**当前状态 (v1.1 shipped):**
- Qwen3-4B SFT 训练完成，产出可用模型
- F16 和 Q4_K_M 两种 GGUF 格式均已导出
- LM Studio 可直接加载推理
- 增强训练数据覆盖交通分析和配时推理（300-400 token 思考链）
- Benchmark 评估系统支持加权平均统计和 throughput 指标

**技术栈：**
- 模型：Qwen3-4B-Base + LoRA (rank 16, alpha 16)
- 训练：Unsloth, TRL (SFTTrainer/GRPOTrainer)
- 仿真：SUMO/TraCI
- 导出：llama.cpp (convert_hf_to_gguf.py + llama-quantize)
- 自定义标签：`<start_working_out>`/`<end_working_out>`/`<SOLUTION>`/`</SOLUTION>`

**已知问题：**
- Qwen3 tokenizer 中 `<think>`/`</think>` 是 added tokens，不能用于 SFT 自定义标签（已改用不在词表中的标签）
- GLM-4.7-Flash FP8 模型与 Unsloth 兼容性问题（已放弃，改用 Qwen3）

**代码库：**
- src: ~7,796 LOC Python
- docker: ~1,762 LOC Shell

**数据流：**
1. SUMO 仿真 → 训练样本 (train.jsonl)
2. 增强数据生成 → 扩展思考链 (sft_train.jsonl)
3. SFT 训练 → 基础模型 (outputs/sft/model)
4. GGUF 导出 → F16 + Q4_K_M (outputs/sft/model/*.gguf)
5. GRPO 训练 → 强化模型
6. Benchmark 评估 → 性能对比

## Constraints

- **环境**：本地/服务器运行，Docker 容器化
- **模型**：Qwen3-4B 系列固定
- **仿真**：依赖 SUMO 交通仿真器

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| 使用 `<start_working_out>` 替代 `<think>` | 避免 tokenizer 语义冲突 | ✓ Good |
| SFT 训练 2 epochs | 1 epoch 不够充分 | ✓ Good |
| LoRA rank 16, alpha 16 | v1.1 优化，平衡效果和资源 | ✓ Good |
| 加权平均使用 samples length 作为权重 | 周期时长直接影响统计意义 | ✓ Good |
| Throughput 计算方式：先按周期再加权 | 避免 total/total 的偏差 | ✓ Good |
| `weighted_summary` 参数可选 | 向后兼容现有调用 | ✓ Good |
| 放弃 GLM-4.7-Flash 改用 Qwen3-4B | FP8 兼容性问题，Qwen3 更稳定 | ✓ Good |
| SFT 保存合并后完整权重 | 确保 GGUF 导出包含真实张量 | ✓ Good |
| GGUF outtype 标准化为大写 | 修复 llama-quantize 大小写敏感问题 | ✓ Good |
| Qwen3 响应掩码使用 `<\|im_start\|>` 边界 | 匹配 Qwen3 chat template 格式 | ✓ Good |

---
*Last updated: 2026-02-21 after v1.1 milestone*
