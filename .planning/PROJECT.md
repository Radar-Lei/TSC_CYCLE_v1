# TSC-CYCLE: 交通信号配时优化大模型微调

## What This Is

基于 SUMO 仿真的交通信号配时优化大模型微调流水线。通过 SFT + GRPO 两阶段训练 Qwen3-4B-Base，使其能够根据交叉口当前交通状态（饱和度、排队等），输出下一个信号周期各相位的最优绿灯时长。SFT 阶段让模型学会输出格式，GRPO 阶段通过实时 SUMO 仿真 reward 优化配时方案质量。

## Core Value

给定交叉口实时交通状态，大模型输出的信号配时方案能最大化车辆通过量、最小化排队车辆数。

## Requirements

### Validated

- ✓ 基础训练数据生成（train.jsonl + SUMO state 文件） — data.sh 已完成
- ✓ SUMO 仿真环境搭建（Docker 镜像 qwen3-tsc-grpo:latest） — 已完成
- ✓ 多场景支持（arterial4x4_10、chengdu 等） — 已完成
- ✓ 相位配置处理（phase_config 生成） — 已完成
- ✓ SFT 数据：100 条分层抽样样本 + AI 手写 think 内容 — v1.0
- ✓ SFT 训练脚本：unsloth + LoRA 微调 Qwen3-4B-Base — v1.0
- ✓ GRPO 数据准备：1588 条 prompt + state_file — v1.0
- ✓ GRPO reward 函数：三层体系（格式 + 约束 + SUMO 仿真） — v1.0
- ✓ GRPO 训练流水线：Docker 容器化完整流程 — v1.0

### Active

(待 v1.1 milestone 定义)

### Out of Scope

- 基础数据生成程序修改 — 已完成，无需改动
- Docker 镜像修改 — 现有镜像已包含所有依赖
- 模型推理/部署服务 — 当前只做训练
- 在线学习/持续训练 — 当前为离线训练

## Context

### Current State

v1.0 MVP 已交付。代码库约 42,800 LOC Python。
Tech stack: Python, unsloth, trl (SFTTrainer + GRPOTrainer), SUMO/TraCI, Docker。
全部代码在 Docker 容器中运行（qwen3-tsc-grpo:latest）。

### 代码结构

- `src/sft/train.py` — SFT 训练脚本（253 LOC）
- `src/grpo/rewards.py` — 5 个 reward 函数（572 LOC）
- `src/grpo/train.py` — GRPO 训练流水线（326 LOC）
- `src/grpo/baseline.py` — Baseline 预计算
- `src/scripts/` — 数据生成脚本
- `src/data_generator/` — 数据生成模块
- `docker/` — Docker 入口脚本（sft_train.sh, grpo_train.sh, grpo_baseline.sh）
- `config/config.json` — 统一配置文件

### 已知问题 / 技术债务

- 标签格式需要从 `<think>/<solution>` 替换为自定义标签（`<start_working_out>` 等），避免与 Qwen3 tokenizer 的 added tokens 冲突
- SFT 训练 epochs 应为 2（1 epoch 不够充分）
- REQUIREMENTS.md 中的 traceability 状态未及时更新（已在归档中修正）

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| 基础模型选 Qwen3-4B-Base | 从 Base 开始训练可完全控制输出格式 | ✓ Good |
| SFT 数据手工构造而非程序生成 | 只需 100 条学格式，AI 推算 final 值 | ✓ Good |
| GRPO 用实时 SUMO 仿真算 reward | 方案空间太大无法预计算 | ✓ Good |
| 多进程并行 reward | 每个 prompt 生成多候选，并行计算加速 | ✓ Good |
| 所有程序在 Docker 中运行 | 环境一致性 | ✓ Good |
| 分层抽样策略 | 确保覆盖所有交叉口和饱和度区间 | ✓ Good |
| 三层 reward 体系 (L1/L2/L3) | 格式→约束→仿真渐进评估，L3 门控节省计算 | ✓ Good |
| Baseline 归一化 | 相对改进评分，避免不同场景间 reward 偏差 | ✓ Good |
| 渐进式 L2 约束评分 | 部分满足给部分分，引导学习过程 | ✓ Good |
| 自定义标签替换 think/solution | 避免 Qwen3 tokenizer added tokens 语义冲突 | ⚠️ Revisit — 已发现问题但需在训练执行时验证 |

## Constraints

- **运行环境**: 所有训练和数据处理必须在 Docker 容器内运行（qwen3-tsc-grpo:latest）
- **基础模型**: Qwen3-4B-Base（通过 unsloth 加载）
- **格式标签**: `<start_working_out>...<end_working_out><SOLUTION>...</SOLUTION>`（替换后）
- **GRPO reward**: 实时 SUMO 仿真，多进程并行计算

---
*Last updated: 2026-02-10 after v1.0 milestone*
