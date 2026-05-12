# Phase 13: Inventory & Cleanup Boundaries - Context

**Gathered:** 2026-05-12
**Status:** Ready for planning
**Mode:** Auto-generated (discuss skipped via workflow.skip_discuss)

<domain>
## Phase Boundary

This phase delivers a non-destructive cleanup inventory for the current repository before any archive/remove action. It must classify root, data, artifacts, runs, planning, and tests file groups as v4 reproduction source, v4 evidence, archived legacy, temporary, or removable; provide explicit keep/archive/remove rationale for every high-impact file group; and identify canonical v4 assets that must not be deleted.

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion
All implementation choices are at Claude's discretion — discuss phase was skipped per user setting. Use ROADMAP phase goal, INV-01/INV-02, success criteria, and existing project state to guide decisions.

### Scope Constraints
- Phase 13 is inventory-only and must not perform destructive cleanup.
- Preserve canonical v4.0 Qwen3-4B reproduction assets and source imports.
- Treat old/uncommitted `.planning/phases/` content as inventory targets, not already-archived evidence.
- v4.1 does not retrain, add model capabilities, run imatrix/q5_K_M experiments, perform thinking ablations, or integrate EvoProgTSC deployment.

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `.planning/PROJECT.md` names the v4.0 deployment artifact, final replay log, current v4.1 goal, and out-of-scope boundaries.
- `.planning/REQUIREMENTS.md` defines INV-01 and INV-02 as Phase 13 requirements.
- `.planning/STATE.md` records canonical v4.0 assets and cleanup blockers/concerns.

### Established Patterns
- GSD phase artifacts live under `.planning/phases/{phase-number}-{slug}/`.
- Milestone state and decisions are tracked in `.planning/PROJECT.md`, `.planning/REQUIREMENTS.md`, `.planning/ROADMAP.md`, and `.planning/STATE.md`.
- Phase 13 should produce reviewable planning artifacts before any cleanup phase changes files.

### Integration Points
- Phase 14 will consume the inventory to define the canonical v4 reproduction package.
- Phase 15 will consume the keep/archive/remove boundaries to execute safe cleanup.
- Phase 16 will verify the cleaned repository still reproduces the shipped v4 evidence path.

</code_context>

<specifics>
## Specific Ideas

Canonical v4 assets already identified in state include:
- `runs/v4.0-4B-20260509T184844Z/gguf/model.q4_K_M.gguf`
- `reality_test.log`
- `artifacts/v4/phase8/phase8_gate_report.json`
- `runs/v4.0-4B-20260509T184844Z/phase9_sft_report.json`
- `runs/v4.0-4B-20260509T184844Z/phase10_gguf_report.json`
- `artifacts/v4/phase11/phase11_gate_report.json`
- `artifacts/v4/phase12/phase12_report.json`

</specifics>

<deferred>
## Deferred Ideas

- Destructive archive/remove actions are deferred to Phase 15.
- Minimal reproduction guide/package documentation is deferred to Phase 14.
- Post-cleanup verification and handoff are deferred to Phase 16.

</deferred>
