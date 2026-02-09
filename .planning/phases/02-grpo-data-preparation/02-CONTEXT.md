# Phase 2: GRPO 数据准备 - Context

**Gathered:** 2026-02-09
**Status:** Ready for planning

<domain>
## Phase Boundary

准备好用于 GRPO 训练的 prompt 和状态文件对。从 train.jsonl 中提取全部样本，构造符合 GRPO 训练框架要求的数据格式。同时修改 data.sh 涉及的数据生成程序，使其生成的 prompt 与 SFT 阶段保持一致。

</domain>

<decisions>
## Implementation Decisions

### Prompt 构造
- 格式参考 qwen3_(4b)_grpo.py：拆分为 `[{role: "system", ...}, {role: "user", ...}]` 两条 messages 放在 `prompt` 字段中
- system prompt 基于 SFT 版本微调措辞，强调"优化"而非"学习格式"，但保持标签格式一致（`<think>...</think><CyclePlan>...</CyclePlan>`）
- user 消息复用 SFT 数据格式：prediction JSON（用 `【cycle_predict_input_json】` 包裹）+ 任务说明 + 硬约束 + 输出格式要求
- 不需要 answer 字段（reward 由 SUMO 仿真计算，不做标准答案比对）
- 需要修改 data.sh 涉及的数据生成程序，使 train.jsonl 中的 prompt（特别是 system prompt）与 SFT 保持一致

### 样本选取策略
- 全部使用 outputs/data/train.jsonl（当前 1588 条，后续可能增加场景后用 data.sh 重新生成）
- 不做抽样或过滤，简单提取转换格式即可
- SFT 样本重叠不在意
- 数据源：直接读取 outputs/data/train.jsonl

### State file 关联
- state_file 使用相对路径（相对于项目根目录），如 `outputs/states/arterial4x4_10/state_xxx.xml`
- state_file 放在 metadata 字段中（不作为独立顶层字段）
- 保留 train.jsonl 中的原始 metadata 字段（tl_id, sim_time, date, cycle_count）

### 输出数据格式
- 存储格式：JSONL
- 输出位置：outputs/grpo/grpo_train.jsonl
- 创建新的独立脚本：src/scripts/generate_grpo_data.py

### Claude's Discretion
- GRPO 数据的具体字段结构（在 prompt + metadata 的框架下自行决定）
- system prompt 的具体微调措辞
- 脚本内部实现细节

</decisions>

<specifics>
## Specific Ideas

- 参考 qwen3_(4b)_grpo.py 的数据格式（第 233-239 行）：`{"prompt": [messages], "answer": ...}` 结构，但去掉 answer 字段
- data.sh 需要修改其调用的程序，使 prompt 格式（特别是 system prompt 和标签格式）与 SFT 阶段的 `<think>...</think><CyclePlan>...</CyclePlan>` 保持一致
- state_file 路径需要从原始的绝对路径（`/home/samuel/SCU_TSC/outputs/states/...`）转换为相对路径（`outputs/states/...`）

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 02-grpo-data-preparation*
*Context gathered: 2026-02-09*
