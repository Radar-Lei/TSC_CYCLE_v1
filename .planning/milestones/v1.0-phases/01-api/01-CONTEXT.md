# Phase 1: API 客户端与数据采样 - Context

**Gathered:** 2026-03-25
**Status:** Ready for planning
**Mode:** Auto-generated (infrastructure phase — discuss skipped)

<domain>
## Phase Boundary

用户可以通过一个可靠的客户端调用 GLM-5 API，并获得从 train.jsonl 中均匀抽取的 5000 条样本。

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion
All implementation choices are at Claude's discretion — pure infrastructure phase. Use ROADMAP phase goal, success criteria, and codebase conventions to guide decisions.

Key references:
- GLM-5 API endpoint: `https://open.bigmodel.cn/api/coding/paas/v4`, model: `glm-5`
- 参考实现: `/home/samuel/projects/signalclaw` 中的 LLM 客户端
- 现有 LLM 客户端模式: `benchmark/llm_client.py` (OpenAI SDK + 指数退避)
- 并发限制: 4 个并发请求
- 数据源: `outputs/data/train.jsonl` (16,788 条)
- 目标: 均匀抽取 5000 条，覆盖高/中/低饱和度

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `benchmark/llm_client.py`: LLMClient 类，OpenAI SDK + 指数退避重试，可作为 GLM-5 客户端参考
- `src/data_generator/prompt_builder.py`: PromptBuilder，含 SYSTEM_PROMPT 和 TASK_TEMPLATE
- `src/data_generator/models.py`: PhaseWait, Prediction, TrainingSample 数据模型

### Established Patterns
- OpenAI SDK 兼容接口调用 (`openai.OpenAI(base_url=..., api_key=...)`)
- 指数退避重试 (base_delay * 2^attempt)
- 数据类 + to_dict()/from_dict() 序列化模式
- argparse CLI with `--config` 参数

### Integration Points
- 输入: `outputs/data/train.jsonl` (prompt + prediction + state_file + metadata)
- 输出: 抽样后的数据供 Phase 2 使用
- 配置: `config/config.json` 或新的 GLM-5 配置节

</code_context>

<specifics>
## Specific Ideas

No specific requirements — infrastructure phase. Refer to ROADMAP phase description and success criteria.

</specifics>

<deferred>
## Deferred Ideas

None — infrastructure phase.

</deferred>
