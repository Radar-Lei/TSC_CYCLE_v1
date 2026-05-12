---
phase: 13-inventory-cleanup-boundaries
plan: "01"
subsystem: tooling
tags: [inventory, cleanup-boundaries, pytest, json, read-only]

requires:
  - phase: 12-reality-log-replay
    provides: shipped v4.0 q4_K_M model, final replay log, and Phase 8-12 evidence paths
provides:
  - Read-only cleanup inventory generator with repository path containment guard
  - Pytest inventory contract for INV-01 and INV-02
  - Machine-readable Phase 13 inventory JSON with canonical v4 no-delete assets
affects: [phase-13, phase-14, phase-15, phase-16, v4.1-cleanup]

tech-stack:
  added: []
  patterns:
    - Python stdlib-only inventory generation via pathlib, json, argparse, subprocess
    - Conservative cleanup classification separate from recommended action and Phase 15 allowance

key-files:
  created:
    - tests/test_cleanup_inventory.py
    - tsc_cycle/cleanup_inventory.py
    - .planning/phases/13-inventory-cleanup-boundaries/inventory/inventory.json
  modified: []

key-decisions:
  - "Phase 13 inventory is read-only and writes only the explicit inventory JSON artifact."
  - "Canonical v4.0 evidence paths are classified as v4 evidence with keep/no_delete."
  - "Local secret, virtualenv, cache, and agent/worktree paths are recorded as metadata-only entries requiring manual review."

patterns-established:
  - "Inventory entries separate classification, recommended_action, and phase15_allowed so Phase 15 can act conservatively."
  - "Path resolution rejects traversal or absolute paths outside /home/samuel/TSC_CYCLE."

requirements-completed: [INV-01, INV-02]

duration: 4min 3s
completed: 2026-05-12
---

# Phase 13 Plan 01: Read-Only Inventory Contract and Generator Summary

**Read-only cleanup boundary inventory with pytest contracts, canonical v4 no-delete evidence, and metadata-only handling for local secret/cache paths**

## Performance

- **Duration:** 4min 3s
- **Started:** 2026-05-12T03:02:27Z
- **Completed:** 2026-05-12T03:06:30Z
- **Tasks:** 3
- **Files modified:** 3

## Accomplishments

- Added RED pytest contracts for required inventory groups, schema fields, canonical v4 no-delete assets, read-only behavior, metadata-only local handling, and repository path containment.
- Implemented `tsc_cycle.cleanup_inventory` with stdlib-only `build_inventory`, `write_inventory_json`, `main`, and path guard support.
- Generated `.planning/phases/13-inventory-cleanup-boundaries/inventory/inventory.json` covering root, data, artifacts, runs, planning, tests, source, scripts, and local groups.

## Task Commits

1. **Task 1: Write RED inventory schema and preservation contracts** - `93613a8` (test)
2. **Task 2: Implement read-only inventory generator** - `d105d9b` (feat)
3. **Task 3: Generate machine-readable Phase 13 inventory JSON** - `950e931` (feat)

Additional stabilization commit: `b4aa6a1` (fix) made generated inventory metadata stable across verification reruns.

## Files Created/Modified

- `tests/test_cleanup_inventory.py` - Pytest contracts for INV-01/INV-02, canonical no-delete assets, read-only source inspection, metadata-only local entries, and outside-root rejection.
- `tsc_cycle/cleanup_inventory.py` - Read-only repository inventory generator and CLI.
- `.planning/phases/13-inventory-cleanup-boundaries/inventory/inventory.json` - Machine-readable cleanup boundary inventory.

## Decisions Made

- Used Python stdlib only; no new dependencies or training/runtime stack changes.
- Kept local ignored/secret/cache paths in the inventory as metadata-only high-impact entries with `manual_review_before_remove` rather than content inspection.
- Added a date-only `generated_at` marker so routine verification does not dirty the generated JSON with second-level timestamp churn.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Stabilized generated inventory timestamp**
- **Found during:** Overall verification after Task 3
- **Issue:** Re-running the generator changed `generated_at` every time, making verification produce an unstaged diff after the Task 3 commit.
- **Fix:** Changed `generated_at` to a date-only marker and regenerated the JSON.
- **Files modified:** `tsc_cycle/cleanup_inventory.py`, `.planning/phases/13-inventory-cleanup-boundaries/inventory/inventory.json`
- **Verification:** `/home/samuel/TSC_CYCLE/.venv/bin/pytest /home/samuel/TSC_CYCLE/tests/test_cleanup_inventory.py -q`
- **Committed in:** `b4aa6a1`

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Necessary for deterministic review and repeatable verification; no destructive cleanup or scope expansion.

## Issues Encountered

- Source inspection correctly rejected the string `replace(` when timestamp formatting used `datetime.replace`; changed to `strftime`.
- Metadata-only tests rejected the literal word `content` in local-entry rationale; changed wording to `file payloads` to keep the serialized inventory free of content-like fields or text.

## Verification

- `/home/samuel/TSC_CYCLE/.venv/bin/pytest /home/samuel/TSC_CYCLE/tests/test_cleanup_inventory.py -q` passed.
- `/home/samuel/TSC_CYCLE/.venv/bin/python -m tsc_cycle.cleanup_inventory --repo-root /home/samuel/TSC_CYCLE --output-json /home/samuel/TSC_CYCLE/.planning/phases/13-inventory-cleanup-boundaries/inventory/inventory.json` completed.
- Stub scan over created/modified plan files found no TODO/FIXME/placeholder patterns.

## Known Stubs

None.

## Self-Check: PASSED

- Found created files: `tests/test_cleanup_inventory.py`, `tsc_cycle/cleanup_inventory.py`, `.planning/phases/13-inventory-cleanup-boundaries/inventory/inventory.json`, `.planning/phases/13-inventory-cleanup-boundaries/13-01-SUMMARY.md`.
- Found task commits: `93613a8`, `d105d9b`, `950e931`, `b4aa6a1`.

## Threat Flags

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 13 Plan 02 can consume the committed JSON inventory to produce the maintainer-facing Markdown cleanup boundary report.
- Canonical v4.0 assets are already marked `keep` and `no_delete`; local/cache/secret paths require manual review before any Phase 15 removal.

---
*Phase: 13-inventory-cleanup-boundaries*
*Completed: 2026-05-12*
