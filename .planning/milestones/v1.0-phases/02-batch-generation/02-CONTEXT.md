# Phase 2: 批量推理链生成 - Context

**Gathered:** 2026-03-25
**Status:** Ready for planning

<domain>
## Phase Boundary

用户运行一个命令即可批量生成 5000 条含 think 链和 solution 的数据，过程可中断恢复。输入为 Phase 1 抽样的 5000 条样本，输出为每条附带 GLM-5 生成的 think 链和 solution 的完整记录。

</domain>

<decisions>
## Implementation Decisions

### Prompt 设计
- 复用现有 `src/data_generator/prompt_builder.py` 中的 SYSTEM_PROMPT + TASK_TEMPLATE
- 在 system prompt 中额外约束 think 链目标长度 ~500 token
- GLM-5 输出使用 `<start_working_out>...<end_working_out><SOLUTION>...</SOLUTION>` 标签——与 SFT 训练标签一致

### 约束校验
- 提取 `src/grpo/rewards.py` 中 check_constraints 的核心校验逻辑到独立函数
- 校验项：相位顺序一致 + min_green ≤ final ≤ max_green + final 为整数
- 约束违反时丢弃该条重试，单条最多 3 次

### 存储与断点续传
- 中间结果存储：`outputs/glm5/results.jsonl`，每条一行 JSON
- 断点续传：启动时读已有结果的 ID 集合，跳过已完成条目
- 3 次均失败的样本记录日志并跳过

### 进度显示
- 单行刷新格式：`[生成] 1234/5000 (24.7%) | 成功率: 96.3% | 平均think: 487 tok`
- 遵循项目 `print("[TAG] ...")` 风格

### Claude's Discretion
- 具体的并发编排方式（asyncio vs ThreadPoolExecutor 已在 Phase 1 client 中使用 ThreadPool）
- 错误日志的具体格式和位置

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/glm5/client.py`: GLM5Client (Phase 1 产出)，call_single() 和 call_batch()
- `src/glm5/sampler.py`: StratifiedSampler (Phase 1 产出)，sample_training_data()
- `src/data_generator/prompt_builder.py`: SYSTEM_PROMPT, TASK_TEMPLATE, PromptBuilder
- `src/grpo/rewards.py`: check_constraints() 中的约束校验逻辑 (phase order + green range)

### Established Patterns
- 批量任务使用 ThreadPoolExecutor (data_generator, grpo/baseline.py)
- JSONL 格式存储数据 (train.jsonl, sft_train.jsonl)
- CLI 使用 argparse + --config/--input/--output 参数
- 中文 print("[TAG] ...") 日志模式

### Integration Points
- 输入: Phase 1 抽样结果 (outputs/glm5/sampled_5000.jsonl)
- 输出: outputs/glm5/results.jsonl (含 think + solution)
- 配置: GLM_API_KEY 环境变量

</code_context>

<specifics>
## Specific Ideas

No specific requirements — standard approaches accepted.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>
