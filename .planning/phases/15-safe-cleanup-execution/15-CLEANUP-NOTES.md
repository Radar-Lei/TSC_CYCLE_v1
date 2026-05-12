# Phase 15 Cleanup Notes

## Scope and Safety Boundary

Phase 15 is an inventory-driven, archive-only cleanup for legacy paths outside the canonical v4.0 Qwen3-4B 9k reproduction package. The cleanup boundary is the Phase 13 inventory plus the Phase 14 reproduction manifest and guide.

Safety guarantees:

- No hard deletion occurred in Phase 15.
- No parent root was moved wholesale: `artifacts`, `data`, and `runs` remain mixed/manual-review roots.
- Automatic actions were limited to the four Phase 13 `archive_only` paths listed below.
- Canonical v4 paths from `reproduction/v4.0-qwen3-4b-9k-manifest.json` were preserved in place.
- Local secret, virtualenv, cache, and agent/worktree payloads are not serialized here.
- Archive payloads intentionally live under the ignored local archive root `runs/_legacy_archive/phase15-safe-cleanup/`.

## Research Resolution

`15-RESEARCH.md` contains `## Open Questions (RESOLVED)`. The resolved cleanup policy is:

- Archive payloads intentionally use the ignored local root `runs/_legacy_archive/phase15-safe-cleanup/` plus tracked notes/status snapshots.
- `reality.log`, `runs/20260507T032419Z`, optional v4 tokenized caches, and all Phase 13 `manual_review_required` entries remain deferred.
- Phase 15 does not create tarballs, duplicate large archives, retrain models, regenerate datasets, run inference, or broaden cleanup beyond the Phase 13 allowlist.

## Legacy v1/v2/v3 Handling

- `v2.0 Label Migration` is already abandoned/archived under `milestones/v2.0-abandoned/`.
- `milestones/v2.0-abandoned/` is outside the main v4 reproduction path and must not be treated as a canonical v4 asset.
- The v1 baseline under `runs/20260507T032419Z` is a historical reference and remains deferred/manual-review.
- The v3/raw legacy paths approved for automatic handling were archived locally, not deleted.

## Archived Automatic Actions

Exactly four automatic archive actions were performed by Plan 15-01:

| Source | Destination | Phase 13 allowance | Rationale |
|---|---|---|---|
| `artifacts/v3` | `runs/_legacy_archive/phase15-safe-cleanup/artifacts-v3` | `archive_only` / `archive_candidate` | v3 reports are historical audit evidence outside the v4.0 Qwen3-4B reproduction target. |
| `data/v3` | `runs/_legacy_archive/phase15-safe-cleanup/data-v3` | `archive_only` / `archive_candidate` | v3 expanded data is lineage, but not required source for the v4.1 minimal reproduction package. |
| `raw_responses` | `runs/_legacy_archive/phase15-safe-cleanup/raw_responses` | `archive_only` / `archive_candidate` | Legacy teacher/API raw responses are not reproducer-facing v4 source and should not expose payload bodies in tracked docs. |
| `runs/v3.0-gates` | `runs/_legacy_archive/phase15-safe-cleanup/runs-v3.0-gates` | `archive_only` / `archive_candidate` | Bulky v3 gate outputs are outside the v4.0 Qwen3-4B target and were moved by same-filesystem archive rather than duplicated. |

No archive payload directory listing, raw response body, prompt text, or local secret/cache payload is included in this note.

## Deferred Manual-Review Paths

The following paths were deliberately preserved/deferred and were not moved or deleted:

| Path | Decision | Reason |
|---|---|---|
| `.env` | Deferred | Local secret/config file; metadata only, no values serialized. |
| `.venv` | Deferred | Local Python environment needed for validation; package list not serialized. |
| `.claude` | Deferred | Local agent/worktree state; payloads not serialized. |
| `.pytest_cache` | Deferred | Local test cache; no cache content listings. |
| `tsc_cycle/__pycache__` | Deferred | Local bytecode cache; no cache content listings. |
| `.planning` | Deferred/preserved | Planning state is needed for v4.1 cleanup provenance and orchestration. |
| `reality.log` | Deferred | Original input distribution log; not final v4 replay output, but manual review is required. |
| `.gitignore` | Deferred | Root-level repo policy file; role-based review required before cleanup. |
| `data/v4/phase8` | Deferred/preserved | Contains required v4 source inputs plus optional caches; no Phase 15 automatic movement. |
| `runs/20260507T032419Z` | Deferred | v1 q4_K_M historical baseline; manual-review only. |
| `artifacts` | Deferred mixed parent root | Contains preserved canonical v4 evidence and archived legacy children; never move parent wholesale. |
| `data` | Deferred mixed parent root | Contains preserved v4 data and legacy lineage; never move parent wholesale. |
| `runs` | Deferred mixed parent root | Contains canonical v4 model/report paths, v1 baseline, and ignored archive root; never move parent wholesale. |

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

Optional rebuild caches under `data/v4/phase8/tokenized/` were also preserved because Phase 15 did not have approval to archive/remove them.

## Validation Evidence

Plan 15-01 verified the reproduction package before and after archive moves. Plan 15-02 reruns final validation after this cleanup note:

- `/home/samuel/TSC_CYCLE/.venv/bin/python -m tsc_cycle.reproduction_manifest --check /home/samuel/TSC_CYCLE/reproduction/v4.0-qwen3-4b-9k-manifest.json`
- `/home/samuel/TSC_CYCLE/.venv/bin/pytest /home/samuel/TSC_CYCLE/tests/test_v4_reproduction_package.py /home/samuel/TSC_CYCLE/tests/test_cleanup_inventory.py -q`

The expected review outcome is that the manifest check passes, the pytest subset passes, and the cleanup scope remains limited to archive-only legacy paths plus Phase 15 notes/status snapshots.

## Git Status Snapshots

Tracked review snapshots:

- `pre_cleanup_git_status.txt` — baseline status before archive moves.
- `post_archive_git_status.txt` — status after the four archive-only moves.
- `post_cleanup_git_status.txt` — final status after cleanup notes and validation.

Maintainer review should compare these snapshots with the current `git -C /home/samuel/TSC_CYCLE status --short --untracked-files=normal`. The intended new cleanup scope is limited to:

- Archived automatic sources: `artifacts/v3`, `data/v3`, `raw_responses`, `runs/v3.0-gates`.
- Ignored local archive root: `runs/_legacy_archive/phase15-safe-cleanup/`.
- Phase 15 documentation/status artifacts under `.planning/phases/15-safe-cleanup-execution/`.

All other dirty paths visible in the snapshots are pre-existing unrelated repository state or deferred/manual-review paths, not opportunistic cleanup targets for this plan.
