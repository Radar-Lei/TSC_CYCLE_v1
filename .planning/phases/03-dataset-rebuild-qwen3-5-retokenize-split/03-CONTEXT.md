# Phase 3: Dataset Rebuild（Qwen3.5 retokenize + split） - Context

**Gathered:** 2026-05-09
**Status:** Ready for planning
**Mode:** Auto-generated (discuss skipped via workflow.skip_discuss)

<domain>
## Phase Boundary

用 Qwen3.5 tokenizer 重新 tokenize 合并后的 ≥9000 valid 数据集，做 80/10/10 split (seed=42)，OOD val 包含 v1.0 OOD val 全集以保跨里程碑可比。

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion
All implementation choices are at Claude's discretion — discuss phase was skipped per user setting. Use ROADMAP phase goal, success criteria, requirements, Phase 1 gate outputs, Phase 2 merged dataset, and codebase conventions to guide decisions.

</decisions>

<code_context>
## Existing Code Insights

Codebase context will be gathered during plan-phase research. Phase 3 depends on Phase 2 artifacts under `data/v3/phase2/` and Phase 1 selected tokenizer/memory constraints.

</code_context>

<specifics>
## Specific Ideas

Success criteria from ROADMAP:
1. 80/10/10 split (train/val/ood_val) 落盘到 `data/splits/v3/`，seed=42；OOD val 包含 v1.0 OOD val 全集 + v3.0 新增 OOD subset。
2. Qwen3.5 tokenizer 重 tokenize 输出到 `data/tokenized/v3/{train,val,ood_val}.arrow`。
3. 截断率 ≤5%（max_seq_length 用 Phase 1 MEM-01 选定值）。
4. split 索引文件 + 样本哈希持久化，便于评测复现并校验 v1.0 OOD val 子集对齐。

</specifics>

<deferred>
## Deferred Ideas

None — discuss phase skipped.

</deferred>
