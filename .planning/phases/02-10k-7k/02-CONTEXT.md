# Phase 2: 数据扩量到 10K（教师只标新增 7K） - Context

**Gathered:** 2026-05-08
**Status:** Ready for planning
**Mode:** Auto-generated (discuss skipped via workflow.skip_discuss)

<domain>
## Phase Boundary

在不动 v1.0 `data/labeled.jsonl` 字节的前提下，扩展合成输入分布、用 GPT-5.5 high 并发标注新增 ≥7K 输入，过硬约束 lint 后与 v1.0 合并得到 ≥9000 valid 训练集。

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion
All implementation choices are at Claude's discretion — discuss phase was skipped per user setting. Use ROADMAP phase goal, success criteria, requirements, and codebase conventions to guide decisions.

</decisions>

<code_context>
## Existing Code Insights

Codebase context will be gathered during plan-phase research.

</code_context>

<specifics>
## Specific Ideas

Success criteria from ROADMAP:
1. 合成输入分布扩展到三类（同分布密集填充 / OOD 边界 / v1.0 高 MAE 与 lint reject targeted），生成 ≥7K 新输入且与 v1.0 现有 3K 不重叠（去重后）。
2. GPT-5.5 high + reasoning_effort=high 标注完成；并发 ≤10 worker；JSONL append 进度持久化；中断可断点续跑且不重复调用。
3. 教师输出过硬约束 lint（min_green ≤ final ≤ max_green、整数秒、相位顺序、覆盖全相位），lint 失败样本丢弃不重生成；最终合并集 ≥9000 valid samples。
4. v1.0 `data/labeled.jsonl` git diff clean（read-only mount 引用，字节级不变）；新增样本写入隔离路径。

</specifics>

<deferred>
## Deferred Ideas

None — discuss phase skipped.

</deferred>
