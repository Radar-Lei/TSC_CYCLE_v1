# Phase 7: 标签协议全链路迁移 - Context

**Gathered:** 2026-05-08
**Status:** Ready for planning

<domain>
## Phase Boundary

本阶段只交付标签协议迁移：把 prompt、训练样本组装、推理解析、reasoning/constraint 评测、tokenizer 检查和单元测试中的思考结束标签统一为 `<end_working_out>`，并让解析/lint 明确拒绝旧标签 `</end_working_out>`。不改变数据生成策略、教师标注规模、训练配置、GGUF 导出或评测门槛。

</domain>

<decisions>
## Implementation Decisions

### 协议源头
- **D-01:** `tsc_cycle/prompt_builder.py` 必须作为标签协议 single source of truth；下游训练、评测和测试应导入其常量，而不是重复硬编码旧/新标签。
- **D-02:** 目标格式锁定为 `<start_working_out>...<end_working_out><SOLUTION>...</SOLUTION>`。旧结束标签 `</end_working_out>` 是反例，不能兼容解析。

### 解析与失败语义
- **D-03:** `parse_assistant_output` 对旧结束标签必须返回解析失败语义：不能从旧标签样本提取有效 reasoning/solution。
- **D-04:** 保留 assistant prefill 场景：模型输出可能省略开标签，但必须使用新结束标签 `<end_working_out>` 后接 `<SOLUTION>`。

### Tokenizer 安全
- **D-05:** 新标签仍必须验证为 Qwen3 tokenizer 的普通 multi-token 序列，不注册 added token，不触发 `resize_token_embeddings`。
- **D-06:** 原生 `<think>` / `</think>` 单 token 只用于泄漏检测；不能出现在训练样本 tokenized `input_ids` 中。

### 测试覆盖
- **D-07:** 单元测试必须覆盖新标签正例、旧标签反例、缺失标签反例、prefill-only 新结束标签场景和 tokenizer 多 token 检查。
- **D-08:** 搜索替换后必须验证没有源代码路径仍把 `</end_working_out>` 当作正例或目标协议；只允许在负例测试/拒绝逻辑/历史文档中出现。

### Claude's Discretion
本阶段无需用户交互决策；实现细节由 planner/executor 选择，但必须保持范围最小：优先修改现有文件，不引入新协议抽象层，除非现有重复硬编码导致测试无法清晰表达。

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Milestone scope
- `.planning/ROADMAP.md` — Phase 7 goal and success criteria: new ending tag, old-tag rejection, tokenizer check, tests.
- `.planning/REQUIREMENTS.md` — TAG-01 and TAG-02 locked requirements; old `</end_working_out>` explicitly out of scope.
- `.planning/PROJECT.md` — v2.0 target features, tokenizer safety constraints, and project-level decisions around custom thinking tags.

### Existing implementation
- `tsc_cycle/prompt_builder.py` — current protocol constants, prompt text, assistant assembly, and parser.
- `tsc_cycle/student/dataset.py` — SFT assistant text construction, loss mask boundary, native think token leakage check.
- `tsc_cycle/eval/metrics_reasoning.py` — reasoning segment scoring through `parse_assistant_output`.
- `tsc_cycle/eval/metrics_constraints.py` — constraint metric integration point that consumes parsed solution output.
- `tsc_cycle/student/tokenize_sanity.py` — HF/GGUF tokenizer parity check for custom tags.
- `tsc_cycle/tokenizer_check.py` — tokenizer safety checks used by dataset tokenization.
- `tests/test_prompt_builder.py` — current prompt/parser unit tests that must be updated/expanded.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `tsc_cycle.prompt_builder` constants and helpers already centralize most protocol handling and should remain the canonical import target.
- `tsc_cycle.tokenizer_check.check_tokenizer` already enforces custom tag multi-token safety before tokenized dataset creation.
- `tests/test_prompt_builder.py` already has roundtrip and prefill parser tests; extend these rather than creating a parallel test suite.

### Established Patterns
- Training data text is assembled via `build_full_assistant(reasoning, solution)` and appended after the user prompt in `tsc_cycle/student/dataset.py`.
- Evaluation code should score/validate by calling parser utilities, not by duplicating tag regexes.
- Native Qwen3 `<think>` token IDs are treated as forbidden leakage in tokenized samples.

### Integration Points
- Update prompt requirements in `USER_TEMPLATE` so future teacher/student generations are instructed to emit `<end_working_out>`.
- Update parser boundaries and prefill handling in `parse_assistant_output`.
- Update tokenizer parity tag lists in `student/tokenize_sanity.py` and tokenizer safety checks to reflect the new closing tag.
- Update tests to assert old `</end_working_out>` is rejected and new `<end_working_out>` roundtrips.

</code_context>

<specifics>
## Specific Ideas

Use a small negative-test fixture containing `x</end_working_out><SOLUTION>{"1":60}</SOLUTION>` and assert it does not parse as a valid sample. Use a corresponding positive fixture `x<end_working_out><SOLUTION>{"1":60}</SOLUTION>` for prefill-only output.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 7-标签协议全链路迁移*
*Context gathered: 2026-05-08*
