# Phase 8: 脚本参数化与全精度适配 - Context

**Gathered:** 2026-04-11
**Status:** Ready for planning
**Mode:** Auto-generated (infrastructure phase — discuss skipped)

<domain>
## Phase Boundary

开发者可以通过参数指定模型名，训练脚本自动将产物输出到按模型名隔离的目录，且 8B 模型以全精度加载无需量化

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion
All implementation choices are at Claude's discretion — pure infrastructure phase. Use ROADMAP phase goal, success criteria, and codebase conventions to guide decisions.

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `config/config.json` — 4B 模型配置（load_in_4bit: false）
- `config/config_32b.json` — 32B 模型配置（load_in_4bit: true, 路径已按模型名隔离）
- `src/sft/train.py` — SFT 训练脚本，支持 `--config` 参数，已支持 HuggingFace repo ID（`/` 判断）
- `src/grpo_simple/train.py` — GRPO 训练脚本，支持 `--config` 参数
- `docker/sft_train.sh` — Docker SFT 训练入口，支持 `--config` 参数
- `docker/grpo_simple_train.sh` — Docker GRPO 训练入口，支持 `--config` 参数
- `docker/convert_gguf.sh` — GGUF 转换脚本，支持 `--model-path` 参数

### Established Patterns
- 配置隔离模式：`config_32b.json` 已展示按模型名隔离路径的模式（`outputs/sft/qwen3-32b/model`）
- 全部路径由 `config.paths` 驱动，Python 脚本不硬编码路径
- Docker shell 脚本解析 config JSON 获取路径
- SFT 脚本 `setup_model()` 已有 `load_in_4bit` 开关

### Integration Points
- `docker/sft_train.sh --config config/config_8b.json` → `src/sft/train.py`
- `docker/grpo_simple_train.sh --config config/config_8b.json` → `src/grpo_simple/train.py`
- GRPO 依赖 SFT 产出模型路径（`grpo_simple.model.model_name` 指向 SFT output）

</code_context>

<specifics>
## Specific Ideas

No specific requirements — infrastructure phase. Follow config_32b.json pattern.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>
