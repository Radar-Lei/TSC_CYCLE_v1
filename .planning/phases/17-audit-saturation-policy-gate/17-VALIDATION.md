---
phase: 17
slug: audit-saturation-policy-gate
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-05-18
---

# Phase 17 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3 in project venv |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest tests/test_v4_phase17_saturation_policy.py -q` |
| **Full suite command** | `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest -q` |
| **Estimated runtime** | ~60 seconds |

---

## Sampling Rate

- **After every task commit:** Run `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest tests/test_v4_phase17_saturation_policy.py -q`
- **After every plan wave:** Run `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest tests/test_v4_phase17_saturation_policy.py tests/test_phase12_reality_log_generation.py tests/test_v4_phase8_dataset_rebuild.py -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 17-01-01 | 01 | 1 | POLICY-01 | T-17-01 | Finite saturation inputs classify into exact half-open bands | unit | `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest tests/test_v4_phase17_saturation_policy.py::test_saturation_band_boundaries -q` | ❌ W0 | ⬜ pending |
| 17-01-02 | 01 | 1 | AUDIT-01 | T-17-02 | Dataset rows project to per-phase denominators by band/split/source without hiding malformed rows | unit/integration | `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest tests/test_v4_phase17_saturation_policy.py::test_dataset_audit_bands_by_split_and_source -q` | ❌ W0 | ⬜ pending |
| 17-01-03 | 01 | 1 | AUDIT-02 | T-17-03 | Dataset and replay representative failures expose required fields and categories | unit/integration | `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest tests/test_v4_phase17_saturation_policy.py::test_representative_failures_include_dataset_and_replay_fields -q` | ❌ W0 | ⬜ pending |
| 17-02-01 | 02 | 2 | POLICY-02 | T-17-04 | Threshold gate fails closed with fatal_failures and nonzero CLI exit when configured limits are exceeded | unit/integration | `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest tests/test_v4_phase17_saturation_policy.py::test_policy_gate_fails_closed_on_threshold_excess -q` | ❌ W0 | ⬜ pending |
| 17-02-02 | 02 | 2 | POLICY-03 | T-17-05 | Prompt builder output remains byte-for-byte v4 protocol and contains no explicit saturation band rule | unit | `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest tests/test_v4_phase17_saturation_policy.py::test_prompt_protocol_unchanged_and_no_band_rule -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_v4_phase17_saturation_policy.py` — covers AUDIT-01, AUDIT-02, POLICY-01, POLICY-02, POLICY-03.
- [ ] `tsc_cycle/v4_gates/saturation_policy.py` — canonical classifier/projector/gate logic.
- [ ] `tsc_cycle/v4_gates/phase17_audit.py` — CLI/report orchestration.

---

## Manual-Only Verifications

All phase behaviors have automated verification.

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 60s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-05-18
