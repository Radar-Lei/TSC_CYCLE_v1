---
phase: 15
slug: safe-cleanup-execution
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-05-12
---

# Phase 15 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3 in project venv |
| **Config file** | `/home/samuel/TSC_CYCLE/pyproject.toml` |
| **Quick run command** | `/home/samuel/TSC_CYCLE/.venv/bin/python -m tsc_cycle.reproduction_manifest --check reproduction/v4.0-qwen3-4b-9k-manifest.json` |
| **Full suite command** | `/home/samuel/TSC_CYCLE/.venv/bin/pytest tests/test_v4_reproduction_package.py tests/test_cleanup_inventory.py -q` |
| **Estimated runtime** | Quick: <15s; full phase subset: <60s |

---

## Sampling Rate

- **Before archive execution:** Run the quick manifest check, the full phase subset, and capture baseline `git status --short --untracked-files=normal`.
- **After every archive move batch:** Run the quick manifest check and inspect `git status --short --untracked-files=normal`.
- **After cleanup documentation:** Run the full phase subset and review cleanup notes against archived/deferred paths.
- **Before `/gsd-verify-work`:** Quick manifest check, full phase subset, cleanup-note review, and scoped git status review must pass or be documented.
- **Max feedback latency:** <60 seconds for automated checks.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 15-01-01 | 01 | 0 | CLEAN-01, CLEAN-03 | T-15-01 | Baseline captures existing dirty state before archive actions | git/status | `git -C /home/samuel/TSC_CYCLE status --short --untracked-files=normal` | ❌ W0 | ⬜ pending |
| 15-01-02 | 01 | 0 | CLEAN-01 | T-15-02 | Candidate list is exactly Phase 13 `archive_only` entries and excludes no-delete/manual-review paths | contract/script | `/home/samuel/TSC_CYCLE/.venv/bin/python -m tsc_cycle.reproduction_manifest --check reproduction/v4.0-qwen3-4b-9k-manifest.json` | ✅ | ⬜ pending |
| 15-01-03 | 01 | 0 | CLEAN-01, CLEAN-03 | T-15-03 | Archive moves preserve canonical v4 assets and leave a reviewable git diff/status | integration | `/home/samuel/TSC_CYCLE/.venv/bin/python -m tsc_cycle.reproduction_manifest --check reproduction/v4.0-qwen3-4b-9k-manifest.json` | ✅ | ⬜ pending |
| 15-02-01 | 02 | 1 | DOC-02, CLEAN-03 | T-15-04 | Cleanup note maps archived and deferred legacy paths without serializing local secret/cache payloads | doc/contract | `/home/samuel/TSC_CYCLE/.venv/bin/pytest tests/test_v4_reproduction_package.py tests/test_cleanup_inventory.py -q` | ❌ W0 | ⬜ pending |
| 15-02-02 | 02 | 1 | CLEAN-01, CLEAN-03, DOC-02 | T-15-05 | Final validation proves manifest, inventory contracts, notes, and scoped status remain consistent | integration | `/home/samuel/TSC_CYCLE/.venv/bin/pytest tests/test_v4_reproduction_package.py tests/test_cleanup_inventory.py -q` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `/home/samuel/TSC_CYCLE/.planning/phases/15-safe-cleanup-execution/pre_cleanup_git_status.txt` — baseline status snapshot for CLEAN-03.
- [ ] `/home/samuel/TSC_CYCLE/.planning/phases/15-safe-cleanup-execution/15-CLEANUP-NOTES.md` — covers DOC-02 and maps archived/deferred legacy paths.
- [ ] Guarded archive action list or helper script/command sequence — covers CLEAN-01 by enforcing `phase15_allowed == archive_only`.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Reviewable cleanup scope | CLEAN-03 | Automated tests can validate canonical assets, but maintainers must judge whether the final git status is an intentionally scoped cleanup change set versus unrelated historical clutter | Inspect `pre_cleanup_git_status.txt`, `post_cleanup_git_status.txt`, and `git status --short --untracked-files=normal`; confirm only planned archive/documentation/status snapshot paths changed beyond pre-existing dirty state |
| Legacy handling clarity | DOC-02 | Documentation clarity and rationale for archived/deferred legacy assets require human judgment | Open `15-CLEANUP-NOTES.md` and confirm it explains archived v3/raw paths, deferred manual-review paths such as `reality.log` and the v1 baseline, and why these are outside the main v4 reproduction path |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 60s for Phase 15 automated checks
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-05-12
