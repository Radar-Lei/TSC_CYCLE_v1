# Phase 4: 简化版 Reward 与解析核心 - Context

**Gathered:** 2026-04-02
**Status:** Ready for planning

<domain>
## Phase Boundary

实现一套不依赖 SUMO 仿真的简化版 GRPO reward 核心。该阶段只处理 completion 解析、格式/约束校验，以及基于 `pred_saturation` 比例目标绿灯时长的 reward，不负责完整训练闭环和结果验证。

</domain>

<decisions>
## Implementation Decisions

### 数据来源
- 简化版 GRPO prompt 数据直接来自 `outputs/data/train.jsonl`
- 不使用 GLM-5 生成的 SFT 样本作为 reward 监督数据来源
- 仍然保留 `outputs/sft/model` 作为可选初始化模型路径，后续是否继续沿用由训练阶段决定

### Reward 规则
- 保持输出标签协议：`<start_working_out>/<end_working_out>/<SOLUTION>`
- `solution` 必须是按相位顺序排列的 `{"phase_id": int, "final": int}` 列表
- 每个 phase 的目标绿灯时间按 `round(max_green * pred_saturation)` 计算
- 目标值再裁剪到 `[min_green, max_green]`
- 对格式错误、JSON 解析失败、phase 顺序错误、越界输出进行降分

### Docker 约束
- GRPO 相关流程必须通过 `unsloth/unsloth:dgxspark-latest` Docker 执行
- 不新增宿主机直跑的主流程作为默认路径

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `docker/Dockerfile`: 当前训练镜像已基于 `unsloth/unsloth:dgxspark-latest`
- `src/grpo/rewards.py`: 旧版 reward 的格式和约束检查逻辑可参考
- `outputs/data/train.jsonl`: 原始样本已包含 `prediction.phase_waits[*].pred_saturation/min_green/max_green`

### Integration Points
- 新目录：`src/grpo_simple/`
- 数据脚本：`src/scripts/generate_grpo_simple_data.py`
- Docker 入口：`docker/grpo_simple_data.sh`、`docker/grpo_simple_train.sh`

</code_context>

<specifics>
## Specific Ideas

- reward 层和训练入口隔离，避免污染 `src/grpo/`
- 先验证 reward 排序能力，再串训练

</specifics>

<deferred>
## Deferred Ideas

- 是否完全放弃 `outputs/sft/model` 初始化，推迟到 Phase 5 决定
- Benchmark 接回与 SUMO 离线评估

</deferred>
