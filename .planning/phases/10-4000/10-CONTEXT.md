# Phase 10: 4000 条数据自动验证 - Context

**Gathered:** 2026-04-12
**Status:** Ready for planning
**Mode:** Auto-generated (infrastructure phase — discuss skipped)

<domain>
## Phase Boundary

用 validate.py 对 GRPO 产出的 8B 模型跑 4000 条数据验证，确认格式/约束/饱和度通过率达标

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion
All implementation choices are at Claude's discretion — pure infrastructure phase. Use ROADMAP phase goal, success criteria, and codebase conventions to guide decisions.

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/validate.py` — 验证脚本，支持 `--model-path` 和 `--num-samples` 参数
- `outputs/grpo_simple/qwen3-8b/model` — Phase 9 产出的 GRPO 模型
- `config/config_8b.json` — 8B 模型配置

### Established Patterns
- v1.2 验证标准：格式通过率 >= 80%，约束通过率 >= 80%
- 验证结果输出为 JSON 格式
- Docker 容器执行验证推理

### Integration Points
- validate.py 读取 GRPO 模型进行推理
- 验证结果保存到模型目录下

</code_context>

<specifics>
## Specific Ideas

No specific requirements — infrastructure phase. Follow existing validation patterns from v1.2.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>
