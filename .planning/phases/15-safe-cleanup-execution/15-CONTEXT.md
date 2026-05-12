# Phase 15: Safe Cleanup Execution - Context

**Gathered:** 2026-05-12
**Status:** Ready for planning
**Mode:** Auto-generated (discuss skipped via workflow.skip_discuss)

<domain>
## Phase Boundary

This phase performs a safe, reviewable cleanup of repository clutter that is unrelated to the canonical v4.0 Qwen3-4B 9k reproduction package. It must consume the Phase 13 cleanup inventory and the Phase 14 reproduction manifest/guide, preserve every canonical v4 asset in its expected path, and produce maintainer-readable archive/removal notes explaining what changed and why.

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion
All implementation choices are at Claude's discretion — discuss phase was skipped per user setting. Use ROADMAP Phase 15 goal, CLEAN-01, CLEAN-03, DOC-02, Phase 13 inventory artifacts, Phase 14 reproduction package artifacts, and current repository state to guide decisions.

### Safety Constraints
- Canonical v4 assets from `reproduction/v4.0-qwen3-4b-9k-manifest.json` must not be deleted, moved, archived, or rewritten.
- Phase 13 entries with `phase15_allowed=no_delete` must remain in place.
- Phase 13 entries with `phase15_allowed=manual_review_required` must not be deleted automatically; if they need cleanup, document them as deferred/manual-review items.
- Cleanup should prefer reversible archive moves for legacy evidence over hard deletion when the file may have audit value.
- Local secret, virtualenv, cache, and agent/worktree paths remain local temporary state; avoid serializing secret contents or payload metadata in docs.
- The final git status should be intentionally scoped to cleanup and documentation changes, not mixed with unrelated historical work.

### Required Inputs
- `.planning/phases/13-inventory-cleanup-boundaries/inventory/inventory.json` is the machine-readable cleanup boundary.
- `.planning/phases/13-inventory-cleanup-boundaries/inventory/inventory.md` is the maintainer-facing rationale input.
- `reproduction/v4.0-qwen3-4b-9k-manifest.json` is the canonical v4 package boundary to preserve.
- `reproduction/v4.0-qwen3-4b-9k-guide.md` is the reproducer-facing guide that must remain accurate after cleanup.

### Required Output Shape
- A reviewable cleanup change set that archives or removes only Phase 13-safe non-v4 clutter.
- A maintainer-facing cleanup note explaining legacy v1/v2/v3 artifact handling and why those paths are outside the main v4 reproduction path.
- Verification that the Phase 14 manifest check and Phase 13/14 pytest contracts still pass after cleanup.

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `tsc_cycle/cleanup_inventory.py` can regenerate the Phase 13 inventory and identifies canonical v4 no-delete assets.
- `tsc_cycle/reproduction_manifest.py` can validate the Phase 14 reproduction manifest against disk.
- `tests/test_cleanup_inventory.py` and `tests/test_v4_reproduction_package.py` protect cleanup boundaries and reproduction package consistency.

### Established Patterns
- Phase artifacts live under `.planning/phases/{phase-number}-{slug}/`.
- Repo-level reproduction source-of-truth lives under `reproduction/`.
- Legacy milestone roadmaps already live under `milestones/`; cleanup notes should follow simple Markdown documentation patterns rather than introducing a new toolchain.

### Integration Points
- Phase 16 will verify the cleaned repository still reproduces shipped v4 evidence.
- Phase 15 must leave enough notes and machine-readable state for Phase 16 to know what was intentionally archived/removed.

</code_context>

<specifics>
## Specific Ideas

Canonical v4 assets seeded by Phase 14 include:
- `runs/v4.0-4B-20260509T184844Z/gguf/model.q4_K_M.gguf`
- `reality_test.log`
- `artifacts/v4/phase8/phase8_gate_report.json`
- `runs/v4.0-4B-20260509T184844Z/phase9_sft_report.json`
- `runs/v4.0-4B-20260509T184844Z/phase10_gguf_report.json`
- `artifacts/v4/phase11/phase11_gate_report.json`
- `artifacts/v4/phase12/phase12_report.json`
- `artifacts/v4/phase12/manifest.json`
- `artifacts/v4/phase12/per_sample.jsonl`
- required v4 source data and split metadata listed in the manifest.

Potential cleanup should be derived from Phase 13 `recommended_action` and `phase15_allowed`, not from ad-hoc guesses.

</specifics>

<deferred>
## Deferred Ideas

- Full post-cleanup reproduction verification is deferred to Phase 16.
- Any cleanup requiring human manual review is deferred unless explicitly approved by the maintainer.
- Deployment integration, imatrix/q5_K_M fallback, and thinking ablations remain out of scope for v4.1.

</deferred>
