---
phase: 14
slug: canonical-v4-reproduction-package
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-05-12
---

# Phase 14 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3 in project venv |
| **Config file** | `/home/samuel/TSC_CYCLE/pyproject.toml` |
| **Quick run command** | `/home/samuel/TSC_CYCLE/.venv/bin/pytest /home/samuel/TSC_CYCLE/tests/test_v4_reproduction_package.py -q` |
| **Full suite command** | `/home/samuel/TSC_CYCLE/.venv/bin/pytest -q` |
| **Estimated runtime** | Quick: <15s after Wave 0; full suite depends on existing tests |

---

## Sampling Rate

- **After every task commit:** Run `/home/samuel/TSC_CYCLE/.venv/bin/pytest /home/samuel/TSC_CYCLE/tests/test_v4_reproduction_package.py -q` once the test file exists.
- **After every plan wave:** Run `/home/samuel/TSC_CYCLE/.venv/bin/pytest /home/samuel/TSC_CYCLE/tests/test_cleanup_inventory.py /home/samuel/TSC_CYCLE/tests/test_v4_reproduction_package.py -q`.
- **Before `/gsd-verify-work`:** Full suite must be green or failures must be documented as pre-existing/unrelated.
- **Max feedback latency:** <60 seconds for Phase 14-specific tests.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 14-01-01 | 01 | 0 | REPRO-01 | T-14-01 | Manifest names canonical v4 assets without `.planning/phases/` as source-of-truth | unit/contract | `/home/samuel/TSC_CYCLE/.venv/bin/pytest /home/samuel/TSC_CYCLE/tests/test_v4_reproduction_package.py::test_manifest_lists_required_v4_assets -q` | ❌ W0 | ⬜ pending |
| 14-01-02 | 01 | 0 | REPRO-03 | T-14-02 | Manifest distinguishes required, optional audit, rebuild cache, obsolete legacy, local temporary | unit/contract | `/home/samuel/TSC_CYCLE/.venv/bin/pytest /home/samuel/TSC_CYCLE/tests/test_v4_reproduction_package.py::test_manifest_classifies_required_optional_and_obsolete_assets -q` | ❌ W0 | ⬜ pending |
| 14-01-03 | 01 | 0 | DOC-01 | T-14-03 | Guide exposes hashes, counts, final artifact names, and minimal verification commands | unit/contract | `/home/samuel/TSC_CYCLE/.venv/bin/pytest /home/samuel/TSC_CYCLE/tests/test_v4_reproduction_package.py::test_guide_exposes_hashes_counts_and_commands -q` | ❌ W0 | ⬜ pending |

---

## Wave 0 Requirements

- [ ] `/home/samuel/TSC_CYCLE/tests/test_v4_reproduction_package.py` — covers REPRO-01, REPRO-03, DOC-01.
- [ ] `/home/samuel/TSC_CYCLE/tsc_cycle/reproduction_manifest.py` — deterministic builder/validator module and CLI.
- [ ] `/home/samuel/TSC_CYCLE/reproduction/v4.0-qwen3-4b-9k-manifest.json` — repo-level machine-readable package boundary.
- [ ] `/home/samuel/TSC_CYCLE/reproduction/v4.0-qwen3-4b-9k-guide.md` — repo-level human entry point.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Reproducer-facing guide clarity | DOC-01 | Automated tests can verify presence of paths/hashes/commands but not whether a new reproducer finds the guide clear | Open `reproduction/v4.0-qwen3-4b-9k-guide.md` and confirm it identifies required vs optional assets and minimal verification steps without relying on `.planning/phases/` |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 60s for Phase 14-specific tests
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-05-12
