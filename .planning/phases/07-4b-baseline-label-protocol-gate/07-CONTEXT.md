# Phase 7: 4B baseline/label protocol gate - Context

**Gathered:** 2026-05-10
**Status:** Ready for planning
**Mode:** Auto-generated (discuss skipped via workflow.skip_discuss and user requested autonomous execution)

<domain>
## Phase Boundary

This phase implements a hard preflight gate before any v4.0 dataset rebuild or training. It must prove the milestone is back on the validated Qwen3-4B route, that v1.0 baseline artifacts are referenced read-only, and that only the corrected custom protocol `<start_working_out>...</end_working_out><SOLUTION>...</SOLUTION>` is accepted.

</domain>

<decisions>
## Implementation Decisions

### Baseline and Environment Gate
- The student model is locked to `Qwen/Qwen3-4B-Thinking-2507`; Qwen3.5-9B must not be selected by any Phase 7 gate.
- Training environment checks must reference `/dgx-spark-training` expectations and `/home/samuel/dgx-spark-setup/.venv`; do not upgrade PyTorch, Transformers, CUDA, or the training framework.
- v1.0 baseline paths under `runs/20260507T032419Z/` are read-only references; Phase 7 must detect and report whether the gate writes there.

### Label Protocol Gate
- The only accepted thought/output protocol is `<start_working_out>...</end_working_out><SOLUTION>...</SOLUTION>`.
- The incorrect closing marker `<end_working_out>` must be rejected as a malformed ending tag.
- Native Qwen `<think>` and `</think>` must be rejected anywhere in fixture inputs or outputs.
- Tokenizer audit must dynamically record the native `<think>`/`</think>` token IDs and prove the four custom tags split into multiple sub-tokens.

### Claude's Discretion
- Implementation details are at Claude's discretion as long as the gate is scriptable, testable, and produces auditable artifacts for downstream Phase 8-11 execution.

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- Existing v3 gate code and tests are likely reusable for environment/tokenizer/protocol smoke checks.
- `.planning/PROJECT.md`, `.planning/REQUIREMENTS.md`, and `.planning/ROADMAP.md` are the source of truth for Phase 7 requirements.
- v1.0 artifact reference: `runs/20260507T032419Z/gguf/model.q4_K_M.gguf`; v1.0 eval cache reference: `runs/20260507T032419Z/eval/gen_cache/gguf_q4km/`.

### Established Patterns
- Gate outputs should be explicit JSON/Markdown artifacts under versioned artifact paths, not implicit console-only checks.
- Tests should verify both accepted fixtures and rejected malformed/native-thinking fixtures.
- Project constraints prohibit vLLM and flash-attn paths on this DGX Spark machine.

### Integration Points
- Phase 8 will consume the tokenizer audit outputs, recorded native think token IDs, and final protocol strings from this phase.
- Phase 11 will consume read-only baseline references and v1 baseline metrics.

</code_context>

<specifics>
## Specific Ideas

- Prefer a small Phase 7 gate module/script plus tests rather than changing training code prematurely.
- The gate report should include model id, environment path, baseline path/write check, custom tag tokenization lengths, native think token IDs, accepted fixture result, and rejected fixture results.

</specifics>

<deferred>
## Deferred Ideas

- Dataset cleaning and `<end_working_out>` normalization counts belong to Phase 8.
- Full training smoke and adapter generation belong to Phase 9.
- GGUF conversion and q4_K_M smoke belong to Phase 10.
- Final eval matrix and GO/NO-GO decision belong to Phase 11.

</deferred>
