# Phase 1: 环境 + Tokenizer + 显存 + llama.cpp 四合一硬门禁 - Context

**Gathered:** 2026-05-08
**Status:** Ready for planning
**Mode:** Auto-generated (discuss skipped via workflow.skip_discuss)

<domain>
## Phase Boundary

本阶段在投入任何训练或数据扩量成本前，硬验证 9B 基座切换的四类不可逆假设：DGX Spark 环境/模型加载、Qwen3.5 tokenizer 标签兼容、9B QLoRA 显存预算、llama.cpp GGUF 导出链路。任一 fatal gate 失败时，本里程碑应 abort 或回到用户决策。

本阶段覆盖 ENV-01/02/03、TOK-01/02/03/04、MEM-01/02/03，不执行真实数据扩量、不启动全量教师标注、不进行全量 SFT。

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion
All implementation choices are at Claude's discretion — discuss phase was skipped per user setting. Use ROADMAP phase goal, success criteria, REQUIREMENTS.md, and codebase conventions to guide decisions.

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- v1.0/v2.0 既有标签协议与数据管线可作为兼容性参考，但 Phase 1 应以 Qwen3.5 实测结果为准。
- `/home/samuel/dgx-spark-setup/.venv` 与 `/dgx-spark-training` 约束是训练环境权威来源。
- `/home/samuel/projects/EvoProgTSC/llama.cpp` 是 GGUF convert/quantize 权威链路。

### Established Patterns
- 自定义思考标签必须保持为普通文本 sub-token，不注册 added tokens，不使用 native `<think>` / `</think>` 作为训练标签。
- 训练和 smoke test 必须强制 SDPA，避免 flash-attn/vLLM 路径。
- DGX Spark 训练命令必须使用 swap-off + `systemd-run --scope -p MemoryMax=100G -p MemorySwapMax=0` 防护。

### Integration Points
- Phase 1 产出的 tokenizer audit、memory budget、run template、llama.cpp micro-convert smoke 结果将作为 Phase 3/4/5 的硬依赖。

</code_context>

<specifics>
## Specific Ideas

No specific requirements — discuss phase skipped. Refer to ROADMAP phase description and success criteria.

</specifics>

<deferred>
## Deferred Ideas

None — discuss phase skipped.

</deferred>
