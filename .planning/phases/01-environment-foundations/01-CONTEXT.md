# Phase 1: Environment + Foundations - Context

**Gathered:** 2026-05-07
**Status:** Ready for planning
**Mode:** Auto-generated (autonomous workflow with workflow.skip_discuss=true)

<domain>
## Phase Boundary

训练环境通过 fail-fast 体检，跨阶段共享模块（prompt_builder / constraint_lint / tokenizer_check / hashing / manifest）单元测试全绿，分布先验落盘，5-prompt 教师 smoke test 端到端通。

</domain>

<decisions>
## Implementation Decisions

### Locked from CLAUDE.md / REQUIREMENTS.md
- 复用 `/home/samuel/dgx-spark-setup/.venv` 已知良好环境（natolambert 上游 + dgx-spark-training skill）
- attn_implementation **强制 SDPA**；`flash_attn` 必须 ImportError
- 自定义思考标签（多 sub-token）：`<start_working_out>` / `</end_working_out>` / `<SOLUTION>` / `</SOLUTION>`
- 教师 = `gpt-5.5`，`reasoning_effort="high"`
- 学生 = `Qwen/Qwen3-4B-Thinking-2507`
- 教师 client 直接复用 EvoProgTSC 模式（指数退避 + 结构化输出降级）

### Claude's Discretion
- TRL 版本：实测得 1.3.0（与 transformers 5.8.0 配套），CLAUDE.md 的 0.22.x 锚点已过时。Phase 4 用 TRL 1.x SFTConfig API
- transformers 实测 5.8.0（CLAUDE.md 锚 4.56.2，<5.0）— 已升级到 5.x，仍能加载 Qwen3 系列；P4 训练时按 5.x API 写
- 教师 JSON Schema：`{"reasoning": str, "solution": dict[str, int]}`（structured strict）+ 明文 fallback 解析 `<SOLUTION>...</SOLUTION>`
- prompt_builder 模板逐字复刻 reality.log 输出（中文系统词 + 全套硬约束 + 5 条输出要求）

</decisions>

<canonical_refs>
## Canonical References

- `CLAUDE.md` — 整套技术栈决策（增量包、forbid list、tokenizer 注意事项）
- `.planning/REQUIREMENTS.md` — ENV/FND v1 requirement IDs
- `.planning/ROADMAP.md` — Phase 1 success criteria
- `reality.log` — 教师 prompt 真实样本来源 + dist_prior 数据源
- `/home/samuel/.claude/skills/dgx-spark-training/SKILL.md` — 训练环境准则
- `/home/samuel/projects/EvoProgTSC/evoprog/llm/client.py` — 教师 client 派生原型

</canonical_refs>

<specifics>
## Specific Ideas

- `tsc_cycle/prompt_builder.py` 的模板与 reality.log 100% 字面对齐，便于 GPT-5.5 high 复用其训练时见过的中文 TSC 提示分布
- `tsc_cycle/teacher/client.py` 的 `require_reasoning_tokens_min=100` 实现 TCH-02（静默降档检测）
- `data/dist_prior.json` schema：`phase_count_distribution` + `per_position[i]{min/max/cap/wait/sat}` + `range_modes_top` 用于 Phase 2 加权采样

</specifics>

<deferred>
## Deferred Ideas

- WandB tracking（Phase 4 训练时启用）
- imatrix 重量化（Phase 5 EXP-05 触发条件下）
</deferred>
