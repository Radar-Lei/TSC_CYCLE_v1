# Phase 15: Safe Cleanup Execution - Research

**Researched:** 2026-05-12 [VERIFIED: /home/samuel/TSC_CYCLE/.planning/STATE.md]  
**Domain:** inventory-driven repository cleanup, archival safety, reproduction-manifest validation [VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/15-safe-cleanup-execution/15-CONTEXT.md]  
**Confidence:** HIGH for cleanup boundaries and validation commands; MEDIUM for archive destination because maintainer has not explicitly approved a physical archive root [VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/13-inventory-cleanup-boundaries/inventory/inventory.json] [ASSUMED]

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
## Phase Boundary

This phase performs a safe, reviewable cleanup of repository clutter that is unrelated to the canonical v4.0 Qwen3-4B 9k reproduction package. It must consume the Phase 13 cleanup inventory and the Phase 14 reproduction manifest/guide, preserve every canonical v4 asset in its expected path, and produce maintainer-readable archive/removal notes explaining what changed and why.

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

### Claude's Discretion
All implementation choices are at Claude's discretion — discuss phase was skipped per user setting. Use ROADMAP Phase 15 goal, CLEAN-01, CLEAN-03, DOC-02, Phase 13 inventory artifacts, Phase 14 reproduction package artifacts, and current repository state to guide decisions.

### Deferred Ideas (OUT OF SCOPE)
## Deferred Ideas

- Full post-cleanup reproduction verification is deferred to Phase 16.
- Any cleanup requiring human manual review is deferred unless explicitly approved by the maintainer.
- Deployment integration, imatrix/q5_K_M fallback, and thinking ablations remain out of scope for v4.1.
</user_constraints>

## Project Constraints (from CLAUDE.md)

- Respond in Simplified Chinese for user-facing output. [VERIFIED: /home/samuel/TSC_CYCLE/CLAUDE.md]
- Do not include `Co-Authored-By` lines in git commit messages. [VERIFIED: /home/samuel/TSC_CYCLE/CLAUDE.md]
- The machine is DGX Spark and vLLM is currently unavailable. [VERIFIED: /home/samuel/TSC_CYCLE/CLAUDE.md]
- Do not read or upload entire PDFs; split by page if PDFs are involved. [VERIFIED: /home/samuel/TSC_CYCLE/CLAUDE.md]
- Repository edits should stay inside the GSD workflow unless the user explicitly bypasses it. [VERIFIED: /home/samuel/TSC_CYCLE/CLAUDE.md]
- Phase 15 is cleanup/reproduction packaging only; no retraining, new model capability, imatrix/q5_K_M evaluation, thinking ablation, or EvoProgTSC deployment belongs in this phase. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/STATE.md]

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CLEAN-01 | Maintainer can safely archive or remove files unrelated to v4.0 Qwen3-4B reproduction without deleting canonical v4 assets or breaking source code imports. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/REQUIREMENTS.md] | Use Phase 13 `phase15_allowed` as the allowlist, archive only `archive_only` entries, and run manifest/source tests after cleanup. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/13-inventory-cleanup-boundaries/inventory/inventory.json] |
| CLEAN-03 | Maintainer can inspect git status after cleanup and see a reviewable, intentionally scoped change set rather than mixed historical clutter. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/REQUIREMENTS.md] | Capture pre-cleanup status, avoid manual-review entries, and compare post-cleanup `git status --short --untracked-files=normal` against the archive/removal note. [VERIFIED: git status in session] |
| DOC-02 | Maintainer can understand where legacy v1/v2/v3 artifacts went and why they are no longer part of the main v4 reproduction path. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/REQUIREMENTS.md] | Write a cleanup note that maps each legacy path to action, destination/deferred state, rationale, and Phase 13/14 source evidence. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/15-safe-cleanup-execution/15-CONTEXT.md] |
</phase_requirements>

## Summary

Phase 15 should be planned as an allowlist-driven archive operation, not as a broad deletion pass. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/15-safe-cleanup-execution/15-CONTEXT.md] The only Phase 13 entries currently safe for automatic action are `artifacts/v3`, `data/v3`, `raw_responses`, and `runs/v3.0-gates`, because they are `phase15_allowed=archive_only` and `recommended_action=archive_candidate`. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/13-inventory-cleanup-boundaries/inventory/inventory.json]

No Phase 13 entry is currently a `remove_candidate`, so hard deletion should not be planned for Phase 15. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/13-inventory-cleanup-boundaries/inventory/inventory.json] Manual-review entries such as `.env`, `.venv`, `.claude`, `.pytest_cache`, `reality.log`, `.planning`, `data/v4/phase8`, `runs/20260507T032419Z`, and group roots must be documented as deferred unless the maintainer explicitly approves them. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/13-inventory-cleanup-boundaries/inventory/inventory.json]

The repository already has validation hooks for the cleanup boundary and reproduction package: `tsc_cycle.cleanup_inventory`, `tsc_cycle.reproduction_manifest`, `tests/test_cleanup_inventory.py`, and `tests/test_v4_reproduction_package.py`. [VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/cleanup_inventory.py] [VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/reproduction_manifest.py] [VERIFIED: /home/samuel/TSC_CYCLE/tests/test_cleanup_inventory.py] [VERIFIED: /home/samuel/TSC_CYCLE/tests/test_v4_reproduction_package.py]

**Primary recommendation:** Implement Phase 15 as a reversible archive-only change for the four `archive_only` candidates, plus a maintainer cleanup note and manifest/test/git-status validation; remove nothing automatically. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/13-inventory-cleanup-boundaries/inventory/inventory.json]

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|--------------|----------------|-----------|
| Candidate selection | Repository metadata layer | Python CLI/tooling | Phase 13 JSON is the machine-readable cleanup boundary. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/13-inventory-cleanup-boundaries/inventory/inventory.json] |
| Archive execution | Filesystem | Git working tree | Files move on disk, while git status provides reviewability for tracked changes. [VERIFIED: git status in session] |
| Canonical v4 preservation | Reproduction manifest | Filesystem | The repo-level manifest names required evidence/source assets and validates hashes/counts against disk. [VERIFIED: /home/samuel/TSC_CYCLE/reproduction/v4.0-qwen3-4b-9k-manifest.json] [VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/reproduction_manifest.py] |
| Cleanup documentation | Planning docs | Reproduction guide | Phase 15 must explain legacy handling, while the Phase 14 guide remains the reproducer-facing package boundary. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/15-safe-cleanup-execution/15-CONTEXT.md] |
| Validation gate | Existing pytest + manifest CLI | Git status inspection | The manifest check and two pytest files are already listed as verification commands. [VERIFIED: /home/samuel/TSC_CYCLE/reproduction/v4.0-qwen3-4b-9k-guide.md] |

## Standard Stack

### Core

| Library/Tool | Version | Purpose | Why Standard |
|--------------|---------|---------|--------------|
| Project Python venv | Python 3.12.3 | Run project validation commands | `pyproject.toml` requires `>=3.12,<3.13`, and the project venv reports Python 3.12.3. [VERIFIED: /home/samuel/TSC_CYCLE/pyproject.toml] [VERIFIED: environment probe] |
| pytest | 9.0.3 in project venv | Run cleanup and reproduction package tests | Existing tests protect Phase 13/14 contracts. [VERIFIED: environment probe] [VERIFIED: /home/samuel/TSC_CYCLE/tests/test_cleanup_inventory.py] |
| Git | 2.43.0 | Review scoped cleanup changes | Phase 15 success criteria require inspectable git status. [VERIFIED: environment probe] [VERIFIED: /home/samuel/TSC_CYCLE/.planning/ROADMAP.md] |
| Python stdlib `pathlib`, `json`, `hashlib` | bundled | Path guards, manifest parsing, checksum validation | Existing project modules already use these stdlib APIs for safe repo-relative paths and SHA-256 checks. [VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/cleanup_inventory.py] [VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/reproduction_manifest.py] |

### Supporting

| Tool | Version | Purpose | When to Use |
|------|---------|---------|-------------|
| GNU tar | 1.35 | Optional external archival packaging | Use only if maintainer requests a tarball; directory moves are safer for large ignored model/run trees because tar copies may duplicate tens of GB. [VERIFIED: environment probe] [VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/13-inventory-cleanup-boundaries/inventory/inventory.json] |
| rsync | 3.2.7 | Optional copy-with-attributes fallback | Use only if cross-filesystem move is required and disk space is confirmed. [VERIFIED: environment probe] [ASSUMED] |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Inventory-driven archive allowlist | Ad-hoc shell `rm -rf` or broad glob cleanup | Ad-hoc deletion can cross the no-delete/manual-review boundary and is not reviewable against Phase 13. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/13-inventory-cleanup-boundaries/inventory/inventory.md] |
| Existing manifest/test validation | New cleanup framework | Existing modules already validate canonical assets and cleanup inventory contracts, so new framework adds risk without need. [VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/reproduction_manifest.py] [VERIFIED: /home/samuel/TSC_CYCLE/tests/test_v4_reproduction_package.py] |
| Reversible archive move | Hard delete | Phase 13 has zero `remove_candidate` entries and four `archive_only` entries. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/13-inventory-cleanup-boundaries/inventory/inventory.json] |

**Installation:** No new packages should be installed for Phase 15. [VERIFIED: /home/samuel/TSC_CYCLE/pyproject.toml]

**Version verification:** npm registry checks are not applicable because Phase 15 uses existing Python project tooling and standard filesystem/git utilities. [VERIFIED: /home/samuel/TSC_CYCLE/pyproject.toml]

## Architecture Patterns

### System Architecture Diagram

```text
Phase 13 inventory.json
        |
        v
Candidate filter: phase15_allowed == archive_only
        |
        +--> archive candidates: artifacts/v3, data/v3, raw_responses, runs/v3.0-gates
        |
        +--> deferred/manual-review: .env, .venv, .claude, reality.log, runs/20260507T032419Z, group roots
        |
        v
Preflight guards
  - assert every reproduction manifest required asset exists
  - assert no no_delete/manual_review path is in the action set
  - capture baseline git status
        |
        v
Reversible archive moves only
        |
        v
Cleanup note: source -> destination/deferred reason -> Phase 13 rationale
        |
        v
Validation
  - reproduction manifest --check
  - cleanup/reproduction pytest subset
  - git status scoped review
```

### Recommended Project Structure

```text
.planning/phases/15-safe-cleanup-execution/
├── 15-RESEARCH.md                  # this research artifact [VERIFIED]
├── 15-CLEANUP-NOTES.md             # recommended maintainer-facing archive/removal note [ASSUMED]
├── pre_cleanup_git_status.txt      # recommended baseline status snapshot, no secrets/payloads [ASSUMED]
└── post_cleanup_git_status.txt     # recommended scoped status snapshot, no secrets/payloads [ASSUMED]

runs/_legacy_archive/phase15-safe-cleanup/
├── artifacts-v3/                   # recommended local archive destination for artifacts/v3 [ASSUMED]
├── data-v3/                        # recommended local archive destination for data/v3 [ASSUMED]
├── raw_responses/                  # recommended local archive destination for raw_responses [ASSUMED]
└── runs-v3.0-gates/                # recommended local archive destination for runs/v3.0-gates [ASSUMED]
```

**Archive root rationale:** `runs/` is already ignored by `.gitignore`, so `runs/_legacy_archive/phase15-safe-cleanup/` avoids introducing a new ignored-root rule and avoids making tens of GB of legacy payloads appear as untracked files. [VERIFIED: /home/samuel/TSC_CYCLE/.gitignore] [ASSUMED]

### Pattern 1: Allowlist candidate extraction

**What:** Select actions only from Phase 13 entries where `phase15_allowed == "archive_only"`. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/13-inventory-cleanup-boundaries/inventory/inventory.json]  
**When to use:** Use before any archive move. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/15-safe-cleanup-execution/15-CONTEXT.md]

```python
# Source: /home/samuel/TSC_CYCLE/.planning/phases/13-inventory-cleanup-boundaries/inventory/inventory.json
import json
from pathlib import Path

inventory = json.loads(Path(".planning/phases/13-inventory-cleanup-boundaries/inventory/inventory.json").read_text())
candidates = [
    entry for entry in inventory["entries"]
    if entry.get("phase15_allowed") == "archive_only"
]
assert {entry["path"] for entry in candidates} == {
    "artifacts/v3",
    "data/v3",
    "raw_responses",
    "runs/v3.0-gates",
}
```

### Pattern 2: No-delete manifest guard

**What:** Validate the reproduction manifest before and after cleanup. [VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/reproduction_manifest.py]  
**When to use:** Run before archive execution and after archive execution. [VERIFIED: /home/samuel/TSC_CYCLE/reproduction/v4.0-qwen3-4b-9k-guide.md]

```bash
/home/samuel/TSC_CYCLE/.venv/bin/python -m tsc_cycle.reproduction_manifest --check reproduction/v4.0-qwen3-4b-9k-manifest.json
```

### Pattern 3: Document deferred manual-review paths

**What:** Manual-review paths should be recorded as deferred, not moved or deleted. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/15-safe-cleanup-execution/15-CONTEXT.md]  
**When to use:** Use for `.env`, `.venv`, `.claude`, `.pytest_cache`, `.planning`, `reality.log`, `runs/20260507T032419Z`, `data/v4/phase8`, and group roots. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/13-inventory-cleanup-boundaries/inventory/inventory.json]

### Anti-Patterns to Avoid

- **Acting on parent directories:** Do not move `artifacts`, `data`, or `runs` wholesale; each parent contains canonical or manual-review children. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/13-inventory-cleanup-boundaries/inventory/inventory.json]
- **Treating optional v4 cache as removable:** `data/v4/phase8/tokenized/*.arrow` are optional rebuild caches in the Phase 14 manifest, but Phase 13 did not mark them `archive_only` or `remove_candidate`. [VERIFIED: /home/samuel/TSC_CYCLE/reproduction/v4.0-qwen3-4b-9k-manifest.json] [VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/13-inventory-cleanup-boundaries/inventory/inventory.json]
- **Deleting ignored local state automatically:** `.env`, `.venv`, `.claude`, `.pytest_cache`, and `tsc_cycle/__pycache__` are manual-review entries, not automatic cleanup targets. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/13-inventory-cleanup-boundaries/inventory/inventory.json]
- **Using system Python by default:** The system `python3` reports 3.14.4, while the project requires Python `<3.13`; use `/home/samuel/TSC_CYCLE/.venv/bin/python` for validation. [VERIFIED: environment probe] [VERIFIED: /home/samuel/TSC_CYCLE/pyproject.toml]

## Phase 15 Action Classification

| Path | Phase 13 status | Phase 15 recommendation | Reason |
|------|-----------------|-------------------------|--------|
| `artifacts/v3` | `archive_only`, `archive_candidate` | Archive, do not delete | Historical v3 reports are audit evidence outside v4 target. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/13-inventory-cleanup-boundaries/inventory/inventory.json] |
| `data/v3` | `archive_only`, `archive_candidate` | Archive, do not delete | v3 expanded data is lineage but not final v4.1 reproduction target. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/13-inventory-cleanup-boundaries/inventory/inventory.json] |
| `raw_responses` | `archive_only`, `archive_candidate` | Archive, do not delete | Legacy teacher/API raw responses are not reproducer-facing v4 source. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/13-inventory-cleanup-boundaries/inventory/inventory.json] |
| `runs/v3.0-gates` | `archive_only`, `archive_candidate` | Archive, do not delete | Bulky v3 gate outputs are outside the v4.0 Qwen3-4B target. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/13-inventory-cleanup-boundaries/inventory/inventory.json] |
| `runs/20260507T032419Z` | `manual_review_required`, `keep_or_archive` | Defer | v1 q4_K_M baseline is manual-review, not automatic. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/13-inventory-cleanup-boundaries/inventory/inventory.json] |
| `reality.log` | `manual_review_required`, `keep_or_archive` | Defer | Original input distribution log is not the final replay output but requires review. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/13-inventory-cleanup-boundaries/inventory/inventory.json] |
| `data/v4/phase8` | `manual_review_required`, `keep_or_archive` | Defer and preserve required subpaths | Phase 14 manifest requires `labeled_merged.jsonl` and split manifest/index files. [VERIFIED: /home/samuel/TSC_CYCLE/reproduction/v4.0-qwen3-4b-9k-manifest.json] |
| `runs/v4.0-4B-20260509T184844Z` | `no_delete`, `keep` | Preserve in place | This run root contains canonical v4 q4 model and required reports. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/13-inventory-cleanup-boundaries/inventory/inventory.json] |
| `.env`, `.venv`, `.claude`, `.pytest_cache`, `tsc_cycle/__pycache__` | `manual_review_required` | Defer; never serialize payloads | Local temporary/secret/cache/agent state requires maintainer review. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/13-inventory-cleanup-boundaries/inventory/inventory.json] |
| Any `remove_candidate` | none found | No removal action | Phase 13 inventory contains zero `remove_candidate` entries. [VERIFIED: inventory action bucket probe] |

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Cleanup eligibility | Ad-hoc glob rules | Phase 13 `inventory.json` `phase15_allowed` field | The inventory already encodes no-delete/manual-review/archive-only boundaries. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/13-inventory-cleanup-boundaries/inventory/inventory.json] |
| Canonical asset validation | Custom hash script from scratch | `python -m tsc_cycle.reproduction_manifest --check ...` | Existing CLI validates required assets, sizes, hashes, line counts, and semantic counts. [VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/reproduction_manifest.py] |
| Source/import safety | Manual eyeballing only | `pytest tests/test_v4_reproduction_package.py tests/test_cleanup_inventory.py -q` | Existing tests cover inventory contracts and reproduction package consistency. [VERIFIED: /home/samuel/TSC_CYCLE/tests/test_cleanup_inventory.py] [VERIFIED: /home/samuel/TSC_CYCLE/tests/test_v4_reproduction_package.py] |
| Secret-safe docs | Directory payload dumps | Metadata-only cleanup notes | Phase 13/14 explicitly avoid serializing secret/local payloads. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/15-safe-cleanup-execution/15-CONTEXT.md] |

**Key insight:** The hard part is not moving files; the hard part is proving the moved files were exactly the Phase 13-safe candidates and that no canonical v4 manifest path changed. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/15-safe-cleanup-execution/15-CONTEXT.md]

## Common Pitfalls

### Pitfall 1: Pre-existing dirty git status hides cleanup scope

**What goes wrong:** Cleanup changes are mixed with older modified/untracked files. [VERIFIED: git status in session]  
**Why it happens:** The current repository already has many modified and untracked files before Phase 15 starts. [VERIFIED: git status in session]  
**How to avoid:** Capture `pre_cleanup_git_status.txt`, limit actions to the four archive-only paths plus Phase 15 docs, then capture `post_cleanup_git_status.txt`. [VERIFIED: git status in session]  
**Warning signs:** `git status --short --untracked-files=normal` shows changes outside the planned archive-only paths and Phase 15 documentation. [VERIFIED: git status in session]

### Pitfall 2: Parent-directory cleanup deletes canonical v4 assets

**What goes wrong:** Moving/deleting `runs`, `artifacts`, or `data` removes required v4 evidence/source assets. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/13-inventory-cleanup-boundaries/inventory/inventory.json]  
**Why it happens:** Parent directories are manual-review or mixed classification while child paths have stricter no-delete/archive-only rules. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/13-inventory-cleanup-boundaries/inventory/inventory.json]  
**How to avoid:** Only act on exact archive-only paths. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/13-inventory-cleanup-boundaries/inventory/inventory.json]  
**Warning signs:** An action list contains `runs`, `artifacts`, `data`, `data/v4/phase8`, or `runs/v4.0-4B-20260509T184844Z`. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/13-inventory-cleanup-boundaries/inventory/inventory.json]

### Pitfall 3: Moving optional v4 caches breaks guide/manifest expectations

**What goes wrong:** The Phase 14 guide says optional cache/audit files exist, but cleanup moves them without regenerating/updating the manifest. [VERIFIED: /home/samuel/TSC_CYCLE/reproduction/v4.0-qwen3-4b-9k-guide.md]  
**Why it happens:** Optional does not mean Phase 15-approved for archive/removal. [VERIFIED: /home/samuel/TSC_CYCLE/reproduction/v4.0-qwen3-4b-9k-manifest.json]  
**How to avoid:** Preserve optional v4 cache/audit files unless a later approved plan updates the reproduction manifest/guide. [VERIFIED: /home/samuel/TSC_CYCLE/reproduction/v4.0-qwen3-4b-9k-manifest.json]  
**Warning signs:** Action list includes `data/v4/phase8/tokenized/*` or `runs/v4.0-4B-20260509T184844Z/eval_phase11/*`. [VERIFIED: /home/samuel/TSC_CYCLE/reproduction/v4.0-qwen3-4b-9k-manifest.json]

### Pitfall 4: Duplicating huge archives exhausts disk

**What goes wrong:** Tar/copy archives duplicate tens of GB before deleting originals. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/13-inventory-cleanup-boundaries/inventory/inventory.json]  
**Why it happens:** `runs/v3.0-gates` is recorded as 59,440,485,774 bytes and `runs/20260507T032419Z` is recorded as 20,236,301,670 bytes. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/13-inventory-cleanup-boundaries/inventory/inventory.json]  
**How to avoid:** Prefer same-filesystem directory moves for archive-only candidates and defer the v1 baseline. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/13-inventory-cleanup-boundaries/inventory/inventory.json] [ASSUMED]  
**Warning signs:** A plan proposes tar/copy of `runs/v3.0-gates` or `runs/20260507T032419Z` without disk-space verification. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/13-inventory-cleanup-boundaries/inventory/inventory.json]

### Pitfall 5: Removing `.venv` breaks validation on this machine

**What goes wrong:** The validation command accidentally uses system Python 3.14.4, which is outside the project Python upper bound. [VERIFIED: environment probe] [VERIFIED: /home/samuel/TSC_CYCLE/pyproject.toml]  
**Why it happens:** `.venv` looks like temporary clutter but is manual-review and provides Python 3.12.3. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/13-inventory-cleanup-boundaries/inventory/inventory.json] [VERIFIED: environment probe]  
**How to avoid:** Do not auto-remove `.venv`; run validation through `/home/samuel/TSC_CYCLE/.venv/bin/python` and `/home/samuel/TSC_CYCLE/.venv/bin/pytest`. [VERIFIED: environment probe]  
**Warning signs:** A plan runs `python3` or deletes `.venv`. [VERIFIED: environment probe]

## Code Examples

### Exact candidate extraction command

```bash
python3 - <<'PY'
import json
from pathlib import Path
root = Path('/home/samuel/TSC_CYCLE')
inv = json.loads((root/'.planning/phases/13-inventory-cleanup-boundaries/inventory/inventory.json').read_text())
for entry in inv['entries']:
    if entry.get('phase15_allowed') == 'archive_only':
        print(entry['path'], entry['recommended_action'])
PY
```

### Required no-delete validation command

```bash
/home/samuel/TSC_CYCLE/.venv/bin/python -m tsc_cycle.reproduction_manifest --check reproduction/v4.0-qwen3-4b-9k-manifest.json
```

### Required pytest subset

```bash
/home/samuel/TSC_CYCLE/.venv/bin/pytest tests/test_v4_reproduction_package.py tests/test_cleanup_inventory.py -q
```

### Git status review command

```bash
git -C /home/samuel/TSC_CYCLE status --short --untracked-files=normal
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Manual historical cleanup by inspection | Phase 13 inventory plus Phase 14 reproduction manifest | v4.1 Phase 13/14 on 2026-05-12 [VERIFIED: /home/samuel/TSC_CYCLE/.planning/STATE.md] | Cleanup can be planned from explicit no-delete/archive/manual-review fields. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/13-inventory-cleanup-boundaries/inventory/inventory.json] |
| Using `.planning/phases/` as reproducer source of truth | Repo-level `reproduction/` manifest and guide | Phase 14 on 2026-05-12 [VERIFIED: /home/samuel/TSC_CYCLE/.planning/STATE.md] | Phase 15 must preserve manifest paths rather than historical planning paths. [VERIFIED: /home/samuel/TSC_CYCLE/reproduction/v4.0-qwen3-4b-9k-guide.md] |

**Deprecated/outdated:**
- Treating v1/v3/raw outputs as the v4 target is outdated; Phase 14 explicitly classifies them as obsolete legacy/not the v4 target. [VERIFIED: /home/samuel/TSC_CYCLE/reproduction/v4.0-qwen3-4b-9k-manifest.json]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `runs/_legacy_archive/phase15-safe-cleanup/` is an acceptable local archive root for Phase 15 payload moves. [ASSUMED] | Recommended Project Structure | Maintainer may prefer a different archive location or may want tracked archival payloads instead of ignored local archive moves. |
| A2 | Same-filesystem directory moves are preferred over tar/copy for huge archive-only directories. [ASSUMED] | Common Pitfalls | If cross-filesystem archival is required, planner must add disk-space checks and rsync/tar fallback steps. |

## Open Questions (RESOLVED)

1. **Should the archive payloads be tracked or intentionally local/ignored?**
   - What we know: `runs/` is ignored and the biggest archive-only candidate is under `runs/v3.0-gates`. [VERIFIED: /home/samuel/TSC_CYCLE/.gitignore] [VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/13-inventory-cleanup-boundaries/inventory/inventory.json]
   - RESOLVED decision: Use ignored local archive payloads under `runs/_legacy_archive/phase15-safe-cleanup/` plus tracked cleanup notes/status snapshots. This follows Phase 15 CONTEXT's Claude-discretion decision authority and avoids making tens of GB of legacy payloads part of the reviewable tracked change set. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/15-safe-cleanup-execution/15-CONTEXT.md] [ASSUMED]

2. **Should `reality.log` and the v1 baseline be archived in Phase 15?**
   - What we know: Both are obsolete/not-v4-target in Phase 14, but Phase 13 marks them manual-review rather than archive-only. [VERIFIED: /home/samuel/TSC_CYCLE/reproduction/v4.0-qwen3-4b-9k-manifest.json] [VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/13-inventory-cleanup-boundaries/inventory/inventory.json]
   - RESOLVED decision: Defer both and list them in cleanup notes as manual-review items. Phase 15 automatic actions remain restricted to Phase 13 `archive_only` entries. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/15-safe-cleanup-execution/15-CONTEXT.md]

3. **Should optional v4 tokenized caches be removed later?**
   - What we know: They are optional rebuild cache in the Phase 14 manifest but not Phase 13 archive-only/remove candidates. [VERIFIED: /home/samuel/TSC_CYCLE/reproduction/v4.0-qwen3-4b-9k-manifest.json]
   - RESOLVED decision: Preserve them in Phase 15. Any later cache removal would require a separate approved plan that updates the reproduction manifest/guide expectations. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/15-safe-cleanup-execution/15-CONTEXT.md]

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| `/home/samuel/TSC_CYCLE/.venv/bin/python` | Manifest validation | ✓ | Python 3.12.3 [VERIFIED: environment probe] | None needed |
| `/home/samuel/TSC_CYCLE/.venv/bin/pytest` | Test subset | ✓ | pytest 9.0.3 [VERIFIED: environment probe] | None needed |
| `git` | Status review | ✓ | 2.43.0 [VERIFIED: environment probe] | None needed |
| `tar` | Optional archive packaging | ✓ | GNU tar 1.35 [VERIFIED: environment probe] | Prefer directory moves unless tarball requested [ASSUMED] |
| `rsync` | Optional copy fallback | ✓ | 3.2.7 [VERIFIED: environment probe] | Use only for cross-filesystem fallback [ASSUMED] |
| system `python3` | Not recommended for project validation | ✓ | Python 3.14.4 [VERIFIED: environment probe] | Use project venv because `pyproject.toml` requires `<3.13`. [VERIFIED: /home/samuel/TSC_CYCLE/pyproject.toml] |

**Missing dependencies with no fallback:** None found for Phase 15 validation. [VERIFIED: environment probe]

**Missing dependencies with fallback:** None found. [VERIFIED: environment probe]

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 in `/home/samuel/TSC_CYCLE/.venv` [VERIFIED: environment probe] |
| Config file | `/home/samuel/TSC_CYCLE/pyproject.toml` with `testpaths = ["tests"]` and `addopts = "-q"` [VERIFIED: /home/samuel/TSC_CYCLE/pyproject.toml] |
| Quick run command | `/home/samuel/TSC_CYCLE/.venv/bin/python -m tsc_cycle.reproduction_manifest --check reproduction/v4.0-qwen3-4b-9k-manifest.json` [VERIFIED: /home/samuel/TSC_CYCLE/reproduction/v4.0-qwen3-4b-9k-guide.md] |
| Full phase subset command | `/home/samuel/TSC_CYCLE/.venv/bin/pytest tests/test_v4_reproduction_package.py tests/test_cleanup_inventory.py -q` [VERIFIED: /home/samuel/TSC_CYCLE/reproduction/v4.0-qwen3-4b-9k-guide.md] |
| Status review command | `git -C /home/samuel/TSC_CYCLE status --short --untracked-files=normal` [VERIFIED: git status in session] |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| CLEAN-01 | Canonical v4 assets remain present with expected hashes/counts after cleanup. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/REQUIREMENTS.md] | manifest/integration | `/home/samuel/TSC_CYCLE/.venv/bin/python -m tsc_cycle.reproduction_manifest --check reproduction/v4.0-qwen3-4b-9k-manifest.json` | ✅ [VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/reproduction_manifest.py] |
| CLEAN-01 | Cleanup boundary still marks canonical v4 assets as keep/no_delete. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/REQUIREMENTS.md] | unit/contract | `/home/samuel/TSC_CYCLE/.venv/bin/pytest tests/test_cleanup_inventory.py -q` | ✅ [VERIFIED: /home/samuel/TSC_CYCLE/tests/test_cleanup_inventory.py] |
| CLEAN-03 | Change set is inspectable and scoped. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/REQUIREMENTS.md] | manual + command output | `git -C /home/samuel/TSC_CYCLE status --short --untracked-files=normal` plus compare to cleanup note | ✅ git available [VERIFIED: environment probe] |
| DOC-02 | Legacy v1/v2/v3/raw handling is documented. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/REQUIREMENTS.md] | documentation review | Check Phase 15 cleanup note contains action/deferred rows for `artifacts/v3`, `data/v3`, `raw_responses`, `runs/v3.0-gates`, `runs/20260507T032419Z`, and `reality.log`. | ❌ Wave 0 gap: cleanup note does not exist yet [VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/15-safe-cleanup-execution directory listing] |

### Sampling Rate

- **Before archive execution:** run manifest check, pytest subset, and baseline git status. [VERIFIED: /home/samuel/TSC_CYCLE/reproduction/v4.0-qwen3-4b-9k-guide.md]
- **After each archive move batch:** run manifest check and inspect git status. [ASSUMED]
- **Phase gate:** manifest check + pytest subset + cleanup note review + post-cleanup git status review. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/ROADMAP.md]

### Wave 0 Gaps

- [ ] `/home/samuel/TSC_CYCLE/.planning/phases/15-safe-cleanup-execution/15-CLEANUP-NOTES.md` — covers DOC-02 and maps archived/deferred legacy paths. [ASSUMED]
- [ ] A small guarded cleanup executor or scripted command sequence — covers CLEAN-01 by enforcing `phase15_allowed == archive_only`. [ASSUMED]
- [ ] Pre/post git status snapshots — covers CLEAN-03 reviewability without mixing pre-existing dirty state. [VERIFIED: git status in session]

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|------------------|
| V2 Authentication | no | Phase 15 does not implement authentication. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/15-safe-cleanup-execution/15-CONTEXT.md] |
| V3 Session Management | no | Phase 15 does not implement sessions. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/15-safe-cleanup-execution/15-CONTEXT.md] |
| V4 Access Control | yes, local filesystem boundary | Restrict actions to Phase 13 allowlist and repo-relative paths. [VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/cleanup_inventory.py] |
| V5 Input Validation | yes | Use `resolve_repo_path` / `_resolve_repo_path` guards that reject paths outside repo root. [VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/cleanup_inventory.py] [VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/reproduction_manifest.py] |
| V6 Cryptography | limited | Use existing SHA-256 checks for integrity; do not invent new crypto. [VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/reproduction_manifest.py] |

### Known Threat Patterns for cleanup tooling

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Path traversal archive target/source | Tampering | Resolve and require paths to stay under repo root before action. [VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/cleanup_inventory.py] |
| Secret leakage in cleanup notes | Information Disclosure | Do not serialize `.env`, `.claude`, `.venv`, cache payloads, or file contents. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/15-safe-cleanup-execution/15-CONTEXT.md] |
| Accidental deletion of canonical v4 assets | Tampering/Denial of Service | Manifest pre/post check and `phase15_allowed=no_delete` guard. [VERIFIED: /home/samuel/TSC_CYCLE/reproduction/v4.0-qwen3-4b-9k-manifest.json] |
| Unreviewable destructive cleanup | Repudiation | Pre/post git status snapshots and cleanup note mapping each action. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/ROADMAP.md] |

## Sources

### Primary (HIGH confidence)

- `/home/samuel/TSC_CYCLE/.planning/phases/15-safe-cleanup-execution/15-CONTEXT.md` — Phase 15 boundary, constraints, inputs, outputs, deferred scope.
- `/home/samuel/TSC_CYCLE/.planning/REQUIREMENTS.md` — CLEAN-01, CLEAN-03, DOC-02 definitions.
- `/home/samuel/TSC_CYCLE/.planning/STATE.md` — v4.1 decisions and Phase 14 completion state.
- `/home/samuel/TSC_CYCLE/.planning/ROADMAP.md` — Phase 15 goal and success criteria.
- `/home/samuel/TSC_CYCLE/.planning/phases/13-inventory-cleanup-boundaries/inventory/inventory.json` — machine-readable cleanup boundary.
- `/home/samuel/TSC_CYCLE/.planning/phases/13-inventory-cleanup-boundaries/inventory/inventory.md` — maintainer-facing cleanup rationale.
- `/home/samuel/TSC_CYCLE/reproduction/v4.0-qwen3-4b-9k-manifest.json` — canonical v4 package boundary.
- `/home/samuel/TSC_CYCLE/reproduction/v4.0-qwen3-4b-9k-guide.md` — reproducer-facing guide and verification commands.
- `/home/samuel/TSC_CYCLE/tsc_cycle/cleanup_inventory.py` — inventory generator and repo path guard.
- `/home/samuel/TSC_CYCLE/tsc_cycle/reproduction_manifest.py` — manifest validator and hash/count checks.
- `/home/samuel/TSC_CYCLE/tests/test_cleanup_inventory.py` — cleanup inventory contract tests.
- `/home/samuel/TSC_CYCLE/tests/test_v4_reproduction_package.py` — reproduction manifest/guide contract tests.
- `/home/samuel/TSC_CYCLE/pyproject.toml` — Python/test configuration.
- `/home/samuel/TSC_CYCLE/.gitignore` — ignored directories and local artifact patterns.

### Secondary (MEDIUM confidence)

- Environment probes run during research — Python/pytest/git/tar/rsync availability and versions.
- Current git status probe — confirms substantial pre-existing modified/untracked state.

### Tertiary (LOW confidence)

- Archive root recommendation under `runs/_legacy_archive/phase15-safe-cleanup/` — marked as an assumption because maintainer has not approved a physical archive destination.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — existing Python/pytest/git tools and versions were probed locally. [VERIFIED: environment probe]
- Cleanup candidate set: HIGH — directly derived from Phase 13 `phase15_allowed` values. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/13-inventory-cleanup-boundaries/inventory/inventory.json]
- Architecture: HIGH — existing manifest/inventory/test modules define the validation path. [VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/reproduction_manifest.py]
- Archive destination: MEDIUM — recommended for practical ignored/local archival but needs maintainer confirmation. [ASSUMED]
- Pitfalls: HIGH — based on inventory classifications, manifest categories, `.gitignore`, and current git status. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/13-inventory-cleanup-boundaries/inventory/inventory.json] [VERIFIED: git status in session]

**Research date:** 2026-05-12 [VERIFIED: /home/samuel/TSC_CYCLE/.planning/STATE.md]  
**Valid until:** 2026-06-11 if Phase 13/14 artifacts remain unchanged; re-run research if inventory or reproduction manifest changes. [ASSUMED]
