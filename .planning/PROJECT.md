# TSC_CYCLE LLM Fine-tuning Pipeline

## What This Is

基于 SUMO 交通仿真生成的信号周期数据，通过 SFT + GRPO 两阶段微调 Qwen3-4B-Base 模型，使其学会根据各相位的预测饱和度、容量、绿灯时间约束等信息，输出下一个信号周期的最优绿灯配时方案。模型在 GRPO 阶段通过调用 SUMO 仿真执行方案并获取真实交通指标作为 reward 来进行强化学习优化。

## Core Value

模型能正确输出符合格式约束和硬约束的信号配时方案，并通过 GRPO 强化学习不断提升配时质量（车辆通量最大化、排队最小化）。

## Requirements

### Validated

- ✓ 基础数据生成（train.jsonl，1588 条样本，多路口多相位数） — existing
- ✓ SUMO 仿真器封装（状态保存/恢复、指标采集、相位控制） — existing
- ✓ 相位配置提取（phase_config_*.json） — existing
- ✓ 月度流量数据生成 — existing

### Active

- [ ] SFT 数据生成：从 train.jsonl 抽取 100 条，添加中文 `<think>` 思考链和 `<Solution>` 答案标签
- [ ] SFT 训练脚本：使用 Unsloth + LoRA 微调 Qwen3-4B-Base 学习输出格式
- [ ] GRPO 训练数据准备：prompt + answer 格式（不含思考链），与 state_file 关联
- [ ] GRPO reward 函数：格式奖励 + SUMO 仿真综合指标（通量、排队、等待时间加权）
- [ ] GRPO 训练脚本：使用 GRPOTrainer 进行强化学习微调
- [ ] 支持不同相位数（2-4 个）的动态输出格式

### Out of Scope

- 多路口联合优化 — 当前为单路口独立决策
- 实时部署/在线推理 — 当前聚焦训练流水线
- 移动端或 Web UI — 纯脚本训练流程

## Context

- **已有代码库**：基于 Python 的 SUMO 交通仿真框架，支持 TraCI 控制、状态保存/恢复
- **参考实现**：`qwen3_(4b)_grpo.py`（Unsloth 官方数学推理 GRPO 示例）
- **数据格式**：JSONL，每条包含 prompt（配时输入）、prediction（结构化数据）、state_file（SUMO 状态快照路径）、metadata
- **模型输出格式**：JSON 数组 `[{"phase_id": <int>, "final": <int>}, ...]`
- **相位数差异**：不同路口有 2、3、4 个相位不等
- **SFT 思考链格式**：`<think>中文推理过程</think><Solution>JSON答案</Solution>`
- **GRPO 数据格式**：仅 prompt + answer，不含思考链

## Constraints

- **Tech stack**: Unsloth + trl (SFTTrainer, GRPOTrainer) + vLLM 推理加速 — 与参考代码一致
- **Base model**: unsloth/Qwen3-4B-Base — 用户指定
- **Hardware**: 需要 GPU 支持，状态恢复需要 SUMO 环境可用
- **Data**: SFT 仅用 100 条数据（少量高质量样本足够学格式）
- **SUMO**: GRPO reward 需要能从 state_file 恢复仿真并执行方案

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| 用 `<think>` / `<Solution>` 而非 `<start_working_out>` | 用户偏好，类似 DeepSeek 风格 | — Pending |
| SFT 思考链用中文 | 与 prompt 语言保持一致，降低模型学习难度 | — Pending |
| GRPO reward 使用综合指标 | 通量、排队、等待时间加权比单一指标更全面 | — Pending |
| SFT 数据 100 条 | 参考代码仅用约 59 条即可学会格式，100 条足够 | — Pending |

---
*Last updated: 2026-02-09 after initialization*
