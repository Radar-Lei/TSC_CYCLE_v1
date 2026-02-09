# TSC-CYCLE: 交通信号配时优化大模型微调

## What This Is

基于 SUMO 仿真的交通信号配时优化大模型微调流水线。通过 SFT + GRPO 两阶段训练 Qwen3-4B-Base，使其能够根据交叉口当前交通状态（饱和度、排队等），输出下一个信号周期各相位的最优绿灯时长。GRPO 阶段通过实时拉起 SUMO 仿真执行大模型方案来计算 reward。

## Core Value

给定交叉口实时交通状态，大模型输出的信号配时方案能最大化车辆通过量、最小化排队车辆数。

## Requirements

### Validated

- ✓ 基础训练数据生成（train.jsonl + SUMO state 文件） — data.sh 已完成
- ✓ SUMO 仿真环境搭建（Docker 镜像 qwen3-tsc-grpo:latest） — 已完成
- ✓ 多场景支持（arterial4x4_10、chengdu 等） — 已完成
- ✓ 相位配置处理（phase_config 生成） — 已完成

### Active

- [ ] SFT 数据：从 train.jsonl 中取 100 条，直接构造带 `<think>...</think><solution>...</solution>` 格式的中文短思考链数据
- [ ] SFT 训练脚本：Docker 中运行，让 Qwen3-4B-Base 学会输出格式
- [ ] GRPO 训练脚本：Docker 中运行，reward 通过实时 SUMO 仿真计算（车辆通过量 + 排队车辆数 + 格式正确性 + think 长度惩罚）
- [ ] GRPO reward 函数：多进程并行调 SUMO（loadState → 执行方案 → 统计指标）

### Out of Scope

- 基础数据生成程序修改 — 已完成，无需改动
- Docker 镜像修改 — 现有镜像已包含所有依赖
- 模型推理/部署服务 — 当前只做训练
- 在线学习/持续训练 — 当前为离线训练

## Context

### 现有代码基础
- `data.sh`：基础数据生成入口，在 Docker 中运行 `src.scripts.generate_training_data`
- `sumo_simulation/sumo_simulator.py`：SUMO 仿真器封装，支持 saveState/loadState 反事实仿真
- `src/data_generator/`：数据生成模块（prompt 构建、采样、状态管理等）
- `qwen3_(4b)_grpo.py`：参考脚本（数学推理任务的 SFT+GRPO），需适配为交通信号任务
- `config/config.json`：统一配置文件

### 数据格式
- **train.jsonl**（1588 条）：每条包含 `prompt`（交通状态+任务说明）、`prediction`（各相位饱和度/min_green/max_green/capacity）、`state_file`（SUMO 状态文件路径）、`metadata`
- **输出格式**：`[{"phase_id": <int>, "final": <int>}, ...]` JSON 数组

### 参考脚本标签对比
- 参考脚本用 `<start_working_out>...<end_working_out><SOLUTION>...</SOLUTION>`
- 本项目用 `<think>...</think><solution>...</solution>`

### Docker 运行模式
- 所有脚本必须像 data.sh 一样通过宿主机 shell 脚本调用 `docker run` 执行
- 镜像：`qwen3-tsc-grpo:latest`
- 容器内工作目录：`/home/samuel/SCU_TSC`
- 项目目录挂载：宿主机项目根目录 → 容器内 `/home/samuel/SCU_TSC`
- 环境变量：`SUMO_HOME=/usr/share/sumo`

## Constraints

- **运行环境**: 所有训练和数据处理必须在 Docker 容器内运行（qwen3-tsc-grpo:latest）
- **基础模型**: Qwen3-4B-Base（通过 unsloth 加载）
- **SFT 数据**: 100 条，由 AI 直接从 train.jsonl 构造（非程序生成），中文短思考（50-200 token）
- **格式标签**: `<think>...</think><solution>...</solution>`
- **GRPO reward**: 实时 SUMO 仿真，多进程并行计算
- **reward 指标**: 车辆通过量（越多越好）、排队车辆数（越少越好）、格式正确性、think 长度惩罚

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| 基础模型选 Qwen3-4B-Base | 与参考脚本一致，从 Base 开始训练可完全控制输出格式 | — Pending |
| SFT 数据手工构造而非程序生成 | 只需 100 条学格式，AI 根据 prediction 推算合理 final 值即可 | — Pending |
| GRPO 用实时 SUMO 仿真算 reward | 方案空间太大无法预计算，实时仿真虽慢但准确 | — Pending |
| 多进程并行 reward | GRPO 每个 prompt 生成多个候选，并行计算加速 | — Pending |
| 所有程序在 Docker 中运行 | 环境一致性，Docker 已包含所有依赖 | — Pending |

---
*Last updated: 2026-02-09 after initialization*
