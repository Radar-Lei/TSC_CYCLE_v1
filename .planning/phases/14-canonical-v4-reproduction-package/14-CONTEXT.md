# Phase 14: Canonical v4 Reproduction Package - Context

**Gathered:** 2026-05-12
**Status:** Ready for planning
**Mode:** Auto-generated (discuss skipped via workflow.skip_discuss)

<domain>
## Phase Boundary

This phase delivers a repo-level canonical v4.0 reproduction package manifest or guide so a reproducer can locate and understand the minimal Qwen3-4B 9k reproduction assets without inspecting historical `.planning/phases/` directories. It must identify canonical inputs, manifests, reports, the final q4_K_M GGUF artifact, and `reality_test.log`; distinguish required reproduction assets from optional audit artifacts and obsolete intermediate outputs; include expected hashes/counts/final artifact names/minimal verification commands; and keep `.planning/phases/` history out of the source-of-truth path.

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion
All implementation choices are at Claude's discretion — discuss phase was skipped per user setting. Use ROADMAP Phase 14 goal, REPRO-01, REPRO-03, DOC-01, Phase 13 inventory artifacts, and existing project state to guide decisions.

### Phase 13 Inputs
- Use `.planning/phases/13-inventory-cleanup-boundaries/inventory/inventory.json` as the machine-readable cleanup-boundary input.
- Use `.planning/phases/13-inventory-cleanup-boundaries/inventory/inventory.md` as the maintainer-facing rationale input.
- Preserve the Phase 13 decision that canonical v4.0 evidence paths are `keep`/`no_delete` and local/legacy/temporary paths require conservative handling.

### Scope Constraints
- Phase 14 documents and packages the reproduction boundary; it does not delete, archive, move, retrain, regenerate datasets, or create new model capabilities.
- Phase 14 must not rely on `.planning/phases/` history as the reproducer-facing source of truth, though it may read phase artifacts as inputs while generating the repo-level manifest.
- Cleanup execution remains deferred to Phase 15.
- Post-cleanup verification remains deferred to Phase 16.

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- Phase 13 inventory JSON/Markdown classify canonical v4 assets, optional audit evidence, legacy outputs, temporary paths, and removable candidates.
- `.planning/PROJECT.md`, `.planning/REQUIREMENTS.md`, and `.planning/STATE.md` name v4.0 shipped artifacts and package goals.
- `tsc_cycle/cleanup_inventory.py` can regenerate inventory artifacts if needed, but Phase 14 should primarily consume the committed inventory.

### Established Patterns
- GSD phase artifacts live under `.planning/phases/{phase-number}-{slug}/`.
- Reproduction evidence paths and counts are tracked in JSON reports under `artifacts/v4/` and `runs/v4.0-4B-20260509T184844Z/`.
- Tests should validate manifest consistency and asset existence rather than trusting prose.

### Integration Points
- Phase 15 will consume the canonical package boundary to archive/remove non-v4 clutter safely.
- Phase 16 will consume the manifest/guide to verify the cleaned repository still reproduces the shipped evidence path.

</code_context>

<specifics>
## Specific Ideas

Canonical v4 assets seeded by Phase 13 include:
- `runs/v4.0-4B-20260509T184844Z/gguf/model.q4_K_M.gguf`
- `reality_test.log`
- `artifacts/v4/phase8/phase8_gate_report.json`
- `runs/v4.0-4B-20260509T184844Z/phase9_sft_report.json`
- `runs/v4.0-4B-20260509T184844Z/phase10_gguf_report.json`
- `artifacts/v4/phase11/phase11_gate_report.json`
- `artifacts/v4/phase12/phase12_report.json`
- `artifacts/v4/phase12/manifest.json`
- `artifacts/v4/phase12/per_sample.jsonl`

Recommended repo-level source-of-truth artifact should be outside `.planning/phases/` so external reproducers do not need historical phase context.

</specifics>

<deferred>
## Deferred Ideas

- Destructive archive/remove actions are deferred to Phase 15.
- Full post-cleanup verification and handoff are deferred to Phase 16.
- Deployment integration, imatrix/q5_K_M fallback, and thinking ablations remain out of scope for v4.1.

</deferred>
