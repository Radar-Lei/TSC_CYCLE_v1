# Phase 5: 简化版训练入口与验证 - Context

**Gathered:** 2026-04-02
**Status:** Ready for planning

<domain>
## Phase Boundary

在 Unsloth Docker 中串起简化版 GRPO 数据生成、训练入口和基础验证，确保输出目录与旧版 `outputs/grpo/` 隔离。

</domain>

<decisions>
## Implementation Decisions

### 训练环境
- 训练必须通过 Unsloth Docker 执行
- 默认镜像沿用仓库现有 `docker/Dockerfile` 构建出的 `qwen3-tsc-grpo:latest`

### 数据与输出
- 输入 prompt 数据放在 `outputs/grpo_simple/grpo_train.jsonl`
- checkpoints 输出到 `outputs/grpo_simple/checkpoints`
- 合并后的模型输出到 `outputs/grpo_simple/model`

### 风险点
- 如果 `outputs/sft/model` 与新 reward 目标偏差过大，可能需要改为从 base model 或其他 checkpoint 启动
- 该决定应在真正开跑训练前明确

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/grpo_simple/train.py`: 新增的简化版训练入口
- `docker/grpo_simple_train.sh`: Docker 中执行简化版训练
- `tests/test_grpo_simple_rewards.py`: reward 基础测试

### Integration Points
- 配置：`config/config.json` 中 `training.grpo_simple` 与 `paths.grpo_simple_*`
- 数据脚本：`src/scripts/generate_grpo_simple_data.py`

</code_context>

<specifics>
## Specific Ideas

- 训练入口与数据生成都通过 Docker 包装，减少环境漂移
- 先把数据路径从 `outputs/grpo/` 切到 `outputs/grpo_simple/`

</specifics>

<deferred>
## Deferred Ideas

- 起始模型是否改用 `model/Qwen3-4B-Base`
- reward 权重和 KL 系数的调参

</deferred>
