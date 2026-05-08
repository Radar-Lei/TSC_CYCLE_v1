# Phase 1: 环境 + Tokenizer + 显存 + llama.cpp 四合一硬门禁 - Context

**Gathered:** 2026-05-08
**Status:** Ready for planning
**Mode:** Auto-generated (discuss skipped via workflow.skip_discuss)

<domain>
## Phase Boundary

在投入任何训练 / 数据扩量成本前，4 项 9B 切换的不可逆假设全部硬验证；任一 fatal gate 失败立即 milestone abort。

## Success Criteria

1. `Qwen/Qwen3.5-9B` 在本机 `/home/samuel/TSC_CYCLE/.venv` 上以 `Qwen3_5ForCausalLM` + bnb 4-bit NF4 + SDPA 完成 1-step forward smoke pass，加载后 `model.named_parameters()` 不含 `vision*` 名空间。
2. 4 个自定义思考标签在 Qwen3.5 tokenizer 下全部拆为 ≥3 sub-tokens；native `<think>`/`</think>` 在 248K vocab 中的 token id 写入 `tokenizer_audit.json`；HF encode ↔ `llama-tokenize` 在 100 prompt 上 100% parity。
3. `memory_budget_v3.py` 在 5 候选 max_seq ∈ {1536, 2048, 2560, 3072, 4096} 上完成实测；选定 peak<85GB 最大值；100-step 训练 dry-run 在 100GB cap 内不 OOM。
4. 本机 `/home/samuel/projects/EvoProgTSC/llama.cpp` micro-convert dry-run 端到端 pass：dummy LoRA → bf16 GGUF → q4_K_M GGUF → `llama-cli` 推理 5 token 无 segfault。
5. 训练运行模板（`systemd-run --scope -p MemoryMax=100G -p MemorySwapMax=0` + swap=0）就位并验证一次空跑。

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion
All implementation choices are at Claude's discretion — discuss phase was skipped per user setting. Use ROADMAP phase goal, success criteria, and codebase conventions to guide decisions.

### Hard Gate Semantics
Any fatal gate failure should stop the milestone rather than silently degrading to a weaker 9B path. Evidence artifacts should be explicit enough for later phases to consume without re-running expensive checks.

</decisions>

<code_context>
## Existing Code Insights

Codebase context has already been gathered in `01-RESEARCH.md` and the six existing Phase 1 plans. Execute those plans as the source of implementation detail.

</code_context>

<specifics>
## Specific Ideas

- Preserve v1.0 artifacts as read-only reference inputs.
- Prefer existing DGX Spark environment constraints: SDPA, no vLLM, no flash-attn, swap-off and `systemd-run` memory cap.
- Treat tokenizer and llama.cpp parity artifacts as shared fixtures for Phase 5.

</specifics>

<deferred>
## Deferred Ideas

None — discuss phase skipped.

</deferred>
