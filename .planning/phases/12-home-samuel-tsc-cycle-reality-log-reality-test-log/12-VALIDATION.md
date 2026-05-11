---
phase: 12
slug: home-samuel-tsc-cycle-reality-log-reality-test-log
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-05-11
---

# Phase 12 — Validation Strategy

> Per-phase validation contract for generating `reality_test.log` from the latest v4 model.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `pytest tests/test_phase12_reality_log_generation.py -q` |
| **Full suite command** | `pytest tests/test_phase12_reality_log_generation.py -q && python -m tsc_cycle.v4_gates.phase12_reality_test --dry-run --limit 3` |
| **Estimated runtime** | ~60 seconds for tests/dry-run; full generation depends on llama inference |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_phase12_reality_log_generation.py -q`
- **After every plan wave:** Run `pytest tests/test_phase12_reality_log_generation.py -q && python -m tsc_cycle.v4_gates.phase12_reality_test --dry-run --limit 3`
- **Before `/gsd-verify-work`:** Full suite plus actual `reality_test.log` generation/report must be green
- **Max feedback latency:** 60 seconds for automated checks before full generation

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 12-01-01 | 01 | 1 | Phase 12 goal | T-12-01 | Ignore existing outputs in `reality.log`; parse only prompt input JSON | unit | `pytest tests/test_phase12_reality_log_generation.py -q` | ❌ W0 | ⬜ pending |
| 12-01-02 | 01 | 1 | Phase 12 goal | T-12-02 | Fail closed on malformed model outputs instead of silently repairing them | unit/integration | `python -m tsc_cycle.v4_gates.phase12_reality_test --dry-run --limit 3` | ❌ W0 | ⬜ pending |
| 12-02-01 | 02 | 2 | Phase 12 goal | T-12-03 | Write `reality_test.log` atomically only after all required samples succeed | integration | `python -m tsc_cycle.v4_gates.phase12_reality_test --limit 3 --output /tmp/reality_test.log` | ❌ W0 | ⬜ pending |
| 12-03-01 | 03 | 3 | Phase 12 goal | T-12-04 | Verify final log contains full custom reasoning protocol and no native think tags | artifact gate | `python -m tsc_cycle.v4_gates.phase12_report --input reality_test.log` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_phase12_reality_log_generation.py` — RED tests for input-only parsing, protocol validation, atomic write behavior, and report checks.
- [ ] `tsc_cycle/v4_gates/phase12_reality_test.py` — implementation target for CLI/dry-run/generation.
- [ ] `tsc_cycle/v4_gates/phase12_report.py` — implementation target for final artifact verification.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Full 426-sample generation with q4_K_M model | Phase 12 goal | Runtime can be long and depends on llama-server/model availability | Run the final Phase 12 wrapper and inspect `artifacts/v4/phase12/phase12_report.json` plus first/last entries in `reality_test.log` |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 60s for automated checks before full generation
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-05-11
