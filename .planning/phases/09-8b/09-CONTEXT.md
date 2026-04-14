# Phase 9: 8B 训练与导出 - Context

**Gathered:** 2026-04-11
**Status:** Ready for planning
**Mode:** Auto-generated (infrastructure phase — discuss skipped)

<domain>
## Phase Boundary

开发者完成 Qwen3-8B 的 SFT -> GRPO -> GGUF 完整训练链路，产出可用模型文件

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion
All implementation choices are at Claude's discretion — pure infrastructure phase. Use ROADMAP phase goal, success criteria, and codebase conventions to guide decisions.

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `config/config_8b.json` — Qwen3-8B 训练配置（Phase 8 产出）
- `docker/sft_train.sh` — SFT 训练入口脚本，支持 `--config` 参数
- `docker/grpo_simple_train.sh` — GRPO 训练入口脚本，支持 `--config` 参数
- `docker/convert_gguf.sh` — GGUF 转换脚本，支持 `--model-path` 参数
- `src/sft/train.py` — SFT 训练 Python 脚本
- `src/grpo_simple/train.py` — GRPO 训练 Python 脚本

### Established Patterns
- 训练流程：`docker/sft_train.sh --config config/config_8b.json` → SFT 模型
- GRPO 流程：`docker/grpo_simple_train.sh --config config/config_8b.json` → GRPO 模型
- GGUF 导出：`docker/convert_gguf.sh --model-path outputs/sft/qwen3-8b/model`
- 量化格式：Q4_K_M、Q8_0、F16

### Integration Points
- SFT 产出路径 `outputs/sft/qwen3-8b/model` 作为 GRPO 输入
- GGUF 导出依赖训练完成的模型目录

</code_context>

<specifics>
## Specific Ideas

No specific requirements — infrastructure phase. Follow existing training and export patterns.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>
