---
phase: 13
slug: inventory-cleanup-boundaries
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-05-12
---

# Phase 13 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3 in `/home/samuel/TSC_CYCLE/.venv` |
| **Config file** | `/home/samuel/TSC_CYCLE/pyproject.toml` |
| **Quick run command** | `/home/samuel/TSC_CYCLE/.venv/bin/pytest tests/test_cleanup_inventory.py -q` |
| **Full suite command** | `/home/samuel/TSC_CYCLE/.venv/bin/pytest -q` |
| **Estimated runtime** | Quick: <10s after Wave 0; full suite depends on existing tests |

---

## Sampling Rate

- **After every task commit:** Run `/home/samuel/TSC_CYCLE/.venv/bin/pytest tests/test_cleanup_inventory.py -q` once `tests/test_cleanup_inventory.py` exists.
- **After every plan wave:** Run `/home/samuel/TSC_CYCLE/.venv/bin/pytest -q`.
- **Before `/gsd-verify-work`:** Full suite must be green or failures must be documented as pre-existing/unrelated.
- **Max feedback latency:** <60 seconds for Phase 13-specific tests.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 13-01-01 | 01 | 0 | INV-01 | T-13-01 | Inventory generation is read-only and does not delete/move/archive files | unit/schema | `/home/samuel/TSC_CYCLE/.venv/bin/pytest tests/test_cleanup_inventory.py::test_inventory_covers_required_groups -q` | ❌ W0 | ⬜ pending |
| 13-01-02 | 01 | 0 | INV-02 | T-13-02 | High-impact groups include action, rationale, risk, and evidence fields | unit/schema | `/home/samuel/TSC_CYCLE/.venv/bin/pytest tests/test_cleanup_inventory.py::test_high_impact_groups_have_rationale -q` | ❌ W0 | ⬜ pending |
| 13-01-03 | 01 | 0 | INV-02 | T-13-03 | Canonical v4 no-delete assets are present and marked keep/no_delete | unit/schema | `/home/samuel/TSC_CYCLE/.venv/bin/pytest tests/test_cleanup_inventory.py::test_canonical_v4_assets_are_no_delete -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_cleanup_inventory.py` — stubs for INV-01/INV-02 inventory schema, required group coverage, high-impact rationale, canonical no-delete assets, and read-only behavior.
- [ ] Inventory artifact path decision — recommended `.planning/phases/13-inventory-cleanup-boundaries/inventory/inventory.json` plus a human-readable Markdown report.
- [ ] Optional source module decision — recommended `tsc_cycle/cleanup_inventory.py` if the executor chooses reusable code instead of a phase-local script.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Maintainer review of keep/archive/remove rationale quality | INV-02 | Automated tests can verify required fields but not whether rationale is sufficiently useful for maintainer judgment | Open the generated Markdown inventory and confirm each high-impact group has clear classification, action, rationale, risk, and evidence |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 60s for Phase 13-specific tests
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-05-12
