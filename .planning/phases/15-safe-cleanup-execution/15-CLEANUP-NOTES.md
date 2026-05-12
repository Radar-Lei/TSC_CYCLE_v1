# Phase 15 Cleanup Notes

## Scope and Safety Boundary

Phase 15 started as an inventory-driven archive-only cleanup, then was tightened after maintainer clarification: the desired handoff is a clean v4.0 Qwen3-4B 9k reproduction package, not an in-project legacy archive. Non-v4 required legacy/cache paths may be deleted directly when they are outside the canonical reproduction manifest required assets.

Safety guarantees:

- Canonical v4 paths from `reproduction/v4.0-qwen3-4b-9k-manifest.json` were preserved in place.
- No parent root was moved wholesale: `artifacts`, `data`, and `runs` remain present.
- Local secret, virtualenv, and agent/worktree payloads are not serialized here and were not deleted.
- Legacy archive payloads under `runs/_legacy_archive/` were removed from the project after the maintainer clarified that in-project archival was unnecessary.
- Optional tokenized Arrow caches and the old v1 baseline were removed because they are not required for the v4.0 Qwen3-4B 9k reproduction package.

## Research Resolution

`15-RESEARCH.md` contains `## Open Questions (RESOLVED)`. The resolved cleanup policy is:

- In-project archive payloads are not retained after maintainer clarification; the legacy archive root `runs/_legacy_archive/` was removed.
- `runs/20260507T032419Z` and optional v4 tokenized caches were deleted because they are not required by the canonical v4 reproduction manifest.
- `reality.log`, `.env`, `.venv`, `.claude`, `.planning`, and root policy files remain deferred/preserved.
- Phase 15 does not create tarballs, duplicate large archives, retrain models, regenerate datasets, or run inference.

## Legacy v1/v2/v3 Handling

- `v2.0 Label Migration` is already abandoned/archived under `.planning/milestones/v2.0-abandoned/`.
- `.planning/milestones/v2.0-abandoned/` is outside the main v4 reproduction path and must not be treated as a canonical v4 asset.
- The v1 baseline under `runs/20260507T032419Z` was deleted after maintainer clarification because it is not the v4 target and is not required by the reproduction manifest.
- The v3/raw legacy paths approved for automatic handling were first moved to an ignored local archive and then deleted when the maintainer clarified that archive retention was unnecessary.

## Removed Non-v4 Paths

These non-required paths were removed from the project working tree:

| Path | Basis | Rationale |
|---|---|---|
| `artifacts/v3` | Phase 13 `archive_only` / `archive_candidate` | v3 reports are historical audit evidence outside the v4.0 Qwen3-4B reproduction target. |
| `data/v3` | Phase 13 `archive_only` / `archive_candidate` | v3 expanded data is lineage, but not required source for the v4.1 minimal reproduction package. |
| `raw_responses` | Phase 13 `archive_only` / `archive_candidate` | Legacy teacher/API raw responses are not reproducer-facing v4 source. |
| `runs/v3.0-gates` | Phase 13 `archive_only` / `archive_candidate` | Bulky v3 gate outputs are outside the v4.0 Qwen3-4B target. |
| `runs/_legacy_archive/` | Maintainer clarification | In-project archive retention did not satisfy the cleanup goal. |
| `runs/20260507T032419Z` | Obsolete legacy / not required | v1 q4_K_M baseline is not the v4 target. |
| `data/v4/phase8/tokenized/` | Optional rebuild cache / not required | Tokenized Arrow caches are reproducible from retained source JSONL and split indexes. |
| `.pytest_cache`, `tsc_cycle/__pycache__`, `tests/__pycache__` | Local temporary cache | Cache directories are rebuildable and not part of reproduction source. |

No raw response body, prompt text, local secret, virtualenv payload, or agent/worktree payload is included in this note.

## Deferred Manual-Review Paths

The following paths were deliberately preserved/deferred and were not moved or deleted:

| Path | Decision | Reason |
|---|---|---|
| `.env` | Deferred | Local secret/config file; metadata only, no values serialized. |
| `.venv` | Deferred | Local Python environment needed for validation; package list not serialized. |
| `.claude` | Deferred | Local agent/worktree state; payloads not serialized. |
| `.planning` | Deferred/preserved | Planning state is needed for v4.1 cleanup provenance and orchestration. |
| `reality.log` | Deferred | Original input distribution log; not final v4 replay output, but manual review is required. |
| `.gitignore` | Deferred | Root-level repo policy file; role-based review required before cleanup. |
| `data/v4/phase8` | Preserved | Contains required v4 source inputs; optional `tokenized/` cache was removed. |
| `artifacts` | Preserved parent root | Contains preserved canonical v4 evidence; legacy v3 child was removed. |
| `data` | Preserved parent root | Contains preserved v4 data; legacy v3 child and optional tokenized cache were removed. |
| `runs` | Preserved parent root | Contains canonical v4 model/report paths; v1 baseline and legacy archive root were removed. |

## Preserved Canonical v4 Paths

The canonical v4.0 Qwen3-4B 9k reproduction package remains in place. Key preserved examples include:

### Final model and reports

- `runs/v4.0-4B-20260509T184844Z/gguf/model.q4_K_M.gguf`
- `runs/v4.0-4B-20260509T184844Z/phase9_sft_report.json`
- `runs/v4.0-4B-20260509T184844Z/phase10_gguf_report.json`
- `reality_test.log`

### Required v4 evidence artifacts

- `artifacts/v4/phase8/phase8_gate_report.json`
- `artifacts/v4/phase11/phase11_gate_report.json`
- `artifacts/v4/phase12/manifest.json`
- `artifacts/v4/phase12/per_sample.jsonl`
- `artifacts/v4/phase12/phase12_report.json`

### Required v4 source/data inputs from the reproduction manifest

- `data/v4/phase8/labeled_merged.jsonl`
- `data/v4/phase8/splits/manifest.json`
- `data/v4/phase8/splits/ood_val.index.jsonl`
- `data/v4/phase8/splits/train.index.jsonl`
- `data/v4/phase8/splits/val.index.jsonl`

Optional rebuild caches under `data/v4/phase8/tokenized/` were removed; the retained source JSONL and split index files are sufficient for the v4.0 Qwen3-4B 9k reproduction package.

## Validation Evidence

Plan 15-01 verified the reproduction package before and after archive moves. Plan 15-02 reruns final validation after this cleanup note:

- `/home/samuel/TSC_CYCLE/.venv/bin/python -m tsc_cycle.reproduction_manifest --check /home/samuel/TSC_CYCLE/reproduction/v4.0-qwen3-4b-9k-manifest.json`
- `/home/samuel/TSC_CYCLE/.venv/bin/pytest /home/samuel/TSC_CYCLE/tests/test_v4_reproduction_package.py /home/samuel/TSC_CYCLE/tests/test_cleanup_inventory.py -q`

Final Plan 15-02 validation results:

- Manifest check: PASS (`OK: /home/samuel/TSC_CYCLE/reproduction/v4.0-qwen3-4b-9k-manifest.json`).
- Pytest subset: PASS (`21 passed`).
- Status snapshot: captured in `post_cleanup_git_status.txt` for maintainer comparison.

The expected review outcome is that the manifest check passes, the pytest subset passes, and the cleanup scope remains limited to non-v4 legacy/cache removal plus Phase 15 notes/status snapshots.

## Git Status Snapshots

Tracked review snapshots:

- `pre_cleanup_git_status.txt` — baseline status before archive moves.
- `post_archive_git_status.txt` — status after the four archive-only moves.
- `post_cleanup_git_status.txt` — final status after cleanup notes and validation.

Maintainer review should compare these snapshots with the current `git -C /home/samuel/TSC_CYCLE status --short --untracked-files=normal`. The final cleanup scope is limited to:

- Removed legacy sources: `artifacts/v3`, `data/v3`, `raw_responses`, `runs/v3.0-gates`.
- Removed in-project archive root: `runs/_legacy_archive/`.
- Removed non-v4 baseline/cache paths: `runs/20260507T032419Z`, `data/v4/phase8/tokenized/`, `.pytest_cache`, `tsc_cycle/__pycache__`, and `tests/__pycache__`.
- Phase 15 documentation/status artifacts under `.planning/phases/15-safe-cleanup-execution/`.

All other dirty paths visible in the snapshots are pre-existing unrelated repository state or deferred/manual-review paths, not opportunistic cleanup targets for this plan.
