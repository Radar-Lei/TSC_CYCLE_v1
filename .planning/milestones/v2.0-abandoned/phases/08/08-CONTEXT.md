# Phase 8: 10K 混合数据扩容与教师标注 - Context

**Gathered:** 2026-05-08
**Status:** Ready for planning
**Mode:** Auto-generated (discuss skipped via workflow.skip_discuss)

<domain>
## Phase Boundary

生成并标注 10K 规模混合分布训练数据，覆盖同分布、OOD/边界和 v1.0 错误/高 MAE targeted 样本。

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion
所有实现选择由 Planner/Executor 决定，约束遵循：
- 使用 GPT-5.5 high 教师，`reasoning_effort="high"`，并发 ≤ 10 worker
- 教师输出必须通过硬约束 lint（min/max/整数/相位覆盖）才能进入训练集
- 标注流程必须支持断点续跑（JSONL append）
- train/val/OOD split metadata 需记录随机种子、输入版本和标注版本
- 协议格式遵循 Phase 7 已锁定的 `<start_working_out>...<end_working_out><SOLUTION>...</SOLUTION>`

</decisions>

<code_context>
## Existing Code Insights

`tsc_cycle/teacher/` 与教师 client 调用现有 EvoProgTSC 风格的 OpenAI 客户端封装，需在 plan-phase 研究中确认实际位置与接口。

</code_context>

<specifics>
## Specific Ideas

参考 PROJECT.md / CLAUDE.md 中 OpenAI 教师 API 模式（结构化输出 + JSON Schema strict + BadRequestError 降级 + RateLimitError 退避 + 进度持久化）。

</specifics>

<deferred>
## Deferred Ideas

None — discuss phase skipped.

</deferred>
