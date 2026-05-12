---
phase: 14-canonical-v4-reproduction-package
plan: "01"
subsystem: reproduction-package
tags: [pytest, manifest, sha256, documentation, v4.0]

requires:
  - phase: 13-inventory-cleanup-boundaries
    provides: Phase 13 inventory JSON/Markdown and canonical v4 no-delete boundary
provides:
  - Repo-level v4.0 Qwen3-4B 9k reproduction manifest
  - Repo-level human guide for canonical v4 assets and verification commands
  - Deterministic stdlib builder/validator CLI with pytest contracts
affects: [phase-15-cleanup, phase-16-verification, reproduction]

tech-stack:
  added: []
  patterns:
    - Deterministic stdlib JSON manifest generation
    - Chunked SHA-256 disk validation
    - Repo-root guarded filesystem paths

key-files:
  created:
    - tests/test_v4_reproduction_package.py
    - tsc_cycle/reproduction_manifest.py
    - reproduction/v4.0-qwen3-4b-9k-manifest.json
    - reproduction/v4.0-qwen3-4b-9k-guide.md
  modified:
    - tests/test_v4_reproduction_package.py

key-decisions:
  - "Use repo-level reproduction/ manifest and guide as the reproducer-facing source of truth; .planning/phases remains provenance input only."
  - "Classify tokenized Arrow files as optional rebuild cache, not required v4 source."
  - "Serialize local paths as metadata only and omit local payloads/secrets from manifest and guide."

patterns-established:
  - "Manifest assets are grouped into required_evidence, required_source, optional_rebuild_cache, optional_audit, obsolete_legacy, and local_temporary."
  - "--check validates required disk facts by recomputing size, SHA-256, and text line counts."

requirements-completed: [REPRO-01, REPRO-03, DOC-01]

duration: 6min23s
completed: 2026-05-12
---

# Phase 14 Plan 01: Canonical v4 Reproduction Package Summary

**Repo-level v4.0 Qwen3-4B 9k reproduction manifest and guide with disk-recomputed hashes, counts, and required/optional asset boundaries**

## Performance

- **Duration:** 6min23s
- **Started:** 2026-05-12T04:07:11Z
- **Completed:** 2026-05-12T04:13:34Z
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments

- Added fail-closed pytest contracts for canonical v4 required evidence/source assets, hash/count freshness, category boundaries, non-destructive behavior, secret safety, and repo-root path guards.
- Implemented `tsc_cycle.reproduction_manifest` with deterministic manifest/guide generation, `--check` validation, and stdlib-only disk metadata extraction.
- Published `reproduction/v4.0-qwen3-4b-9k-manifest.json` and `reproduction/v4.0-qwen3-4b-9k-guide.md` outside `.planning/phases/` as the reproducer-facing source of truth.

## Task Commits

Each task was committed atomically:

1. **Task 1: Write RED reproduction package contract tests** - `71ca4c3` (test)
2. **Task 2: Implement deterministic reproduction manifest builder and validator CLI** - `e895fff` (feat)
3. **Task 3: Generate repo-level manifest and guide, then pass Phase 14 contracts** - `22fa578` (docs)

**Plan metadata:** pending final docs commit

## Files Created/Modified

- `tests/test_v4_reproduction_package.py` - Phase 14 contract tests for required assets, category boundaries, hashes/counts, guide content, path guards, and secret-safe non-destructive behavior.
- `tsc_cycle/reproduction_manifest.py` - Deterministic builder/validator CLI exposing `build_package_manifest`, JSON/Markdown writers, validation, and `main`.
- `reproduction/v4.0-qwen3-4b-9k-manifest.json` - Machine-readable canonical v4.0 reproduction package boundary.
- `reproduction/v4.0-qwen3-4b-9k-guide.md` - Human-facing entry point for external reproducers.

## Decisions Made

- The repo-level `reproduction/` manifest and guide are the source of truth; `.planning/phases/` paths are retained only as provenance inputs in the manifest.
- Tokenized Arrow outputs are optional rebuild cache, while labeled JSONL and split manifest/index JSONL files are required source inputs.
- Local environment/agent/cache paths are listed as local temporary metadata only and do not serialize file payloads or local secret contents.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Reconciled secret-safe serialization with verification command content**
- **Found during:** Task 2 (manifest builder verification)
- **Issue:** Phase 14 contract tests detected `.venv/` in serialized verification commands and `.claude/` via nested local temporary paths, conflicting with the plan's secret-safe serialization requirement.
- **Fix:** Switched manifest verification commands to generic `python`/`pytest` command text and kept local temporary categorization metadata-only without serializing nested `.claude/worktrees` paths.
- **Files modified:** `tsc_cycle/reproduction_manifest.py`, `tests/test_v4_reproduction_package.py`
- **Verification:** `/home/samuel/TSC_CYCLE/.venv/bin/pytest /home/samuel/TSC_CYCLE/tests/test_v4_reproduction_package.py -q`
- **Committed in:** `e895fff`

**2. [Rule 1 - Bug] Matched guide source-of-truth wording required by contracts**
- **Found during:** Task 2 (manifest builder verification)
- **Issue:** The first guide rendering used capitalized wording while the contract checked the exact lower-case source-of-truth phrase.
- **Fix:** Updated guide text to include the exact `do not use .planning/phases/ as the source of truth` wording while preserving the reproducer-facing direction.
- **Files modified:** `tsc_cycle/reproduction_manifest.py`
- **Verification:** `/home/samuel/TSC_CYCLE/.venv/bin/pytest /home/samuel/TSC_CYCLE/tests/test_v4_reproduction_package.py -q`
- **Committed in:** `e895fff`

---

**Total deviations:** 2 auto-fixed (2 bug fixes)
**Impact on plan:** Both fixes strengthened the planned security/source-of-truth contracts. No destructive action, retraining, regeneration, or inference was introduced.

## Issues Encountered

- The generated guide was manually inspected and confirmed to start from `reproduction/`, name the final q4_K_M artifact, expose hashes/counts/commands, and avoid treating `.planning/phases/` as the reproducer source of truth.
- Pre-existing unrelated modified/untracked files remain in the working tree; Phase 14 commits staged only task-relevant files.

## User Setup Required

None - no external service configuration required.

## Known Stubs

None found in files created/modified for this plan.

## Threat Flags

None - Phase 14 added local filesystem manifest tooling only; the plan threat model already covered CLI path handling, hash/count validation, metadata serialization, and non-destructive scope.

## Verification

- `/home/samuel/TSC_CYCLE/.venv/bin/python -m tsc_cycle.reproduction_manifest --repo-root /home/samuel/TSC_CYCLE --check /home/samuel/TSC_CYCLE/reproduction/v4.0-qwen3-4b-9k-manifest.json`
- `/home/samuel/TSC_CYCLE/.venv/bin/pytest /home/samuel/TSC_CYCLE/tests/test_v4_reproduction_package.py /home/samuel/TSC_CYCLE/tests/test_cleanup_inventory.py -q`

## Next Phase Readiness

- Phase 15 can consume the repo-level reproduction manifest to preserve canonical v4 assets before cleanup.
- Phase 16 can use the `--check` command and pytest contracts as the baseline for post-cleanup verification.

## Self-Check: PASSED

- Found created/modified files: `tests/test_v4_reproduction_package.py`, `tsc_cycle/reproduction_manifest.py`, `reproduction/v4.0-qwen3-4b-9k-manifest.json`, `reproduction/v4.0-qwen3-4b-9k-guide.md`, and this summary.
- Found task commits: `71ca4c3`, `e895fff`, `22fa578`.

---
*Phase: 14-canonical-v4-reproduction-package*
*Completed: 2026-05-12*
