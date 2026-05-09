---
phase: 07
slug: 4b-baseline-label-protocol-gate
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-05-10
---

# Phase 07 — Validation Strategy

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `PYTHONPATH=/home/samuel/TSC_CYCLE /home/samuel/TSC_CYCLE/.venv/bin/python -m pytest -q tests/test_v4_phase7_protocol.py tests/test_v4_phase7_baseline_gate.py tests/test_v4_phase7_tokenizer_audit.py` |
| **Full suite command** | `PYTHONPATH=/home/samuel/TSC_CYCLE /home/samuel/TSC_CYCLE/.venv/bin/python -m pytest -q` |
| **Estimated runtime** | ~60-180 seconds for Phase 7 subset; full suite depends on existing test volume |

## Sampling Rate

- **After every task commit:** Run the Phase 7 quick command.
- **After every plan wave:** Run the Phase 7 quick command plus relevant existing regression tests.
- **Before verification:** `artifacts/v4/phase7/phase7_gate_report.json` must contain `"ok": true` and `"next_phase_allowed": true`.
- **Max feedback latency:** 180 seconds for Phase 7 subset.

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 07-01-01 | 01 | 1 | TAG-01/TAG-02/TAG-03 | T-07-01 | Wrong close tag and native `<think>` are rejected fail-closed | unit | `PYTHONPATH=/home/samuel/TSC_CYCLE /home/samuel/TSC_CYCLE/.venv/bin/python -m pytest -q tests/test_v4_phase7_protocol.py tests/test_prompt_builder.py` | ❌ W0 | ⬜ pending |
| 07-02-01 | 02 | 1 | BASE-01/BASE-02/BASE-03 | T-07-02 | Output paths cannot target the frozen v1 baseline root | unit/smoke | `PYTHONPATH=/home/samuel/TSC_CYCLE /home/samuel/TSC_CYCLE/.venv/bin/python -m pytest -q tests/test_v4_phase7_baseline_gate.py` | ❌ W0 | ⬜ pending |
| 07-03-01 | 03 | 1 | TAG-04 | T-07-03 | Native think token IDs are dynamically recorded and custom tags are multi-token | unit/smoke | `PYTHONPATH=/home/samuel/TSC_CYCLE /home/samuel/TSC_CYCLE/.venv/bin/python -m pytest -q tests/test_v4_phase7_tokenizer_audit.py tests/test_tokenizer_check.py` | ❌ W0 | ⬜ pending |
| 07-04-01 | 04 | 2 | BASE-01..03,TAG-01..04 | T-07-04 | Aggregate gate report blocks Phase 8 unless all sub-gates pass | integration | `PYTHONPATH=/home/samuel/TSC_CYCLE /home/samuel/TSC_CYCLE/.venv/bin/python -m pytest -q tests/test_v4_phase7_gate_report.py` | ❌ W0 | ⬜ pending |

## Wave 0 Requirements

- [ ] `tests/test_v4_phase7_protocol.py` — RED tests for slash-close acceptance, bare-close rejection, native think rejection.
- [ ] `tests/test_v4_phase7_baseline_gate.py` — RED tests for model lock, environment evidence, frozen baseline snapshot, output path guard.
- [ ] `tests/test_v4_phase7_tokenizer_audit.py` — RED tests for tokenizer audit payload contract and dynamic native token ID recording.
- [ ] `tests/test_v4_phase7_gate_report.py` — RED tests for aggregate report shape and `next_phase_allowed` behavior.

## Manual-Only Verifications

All Phase 7 success criteria have automated verification through pytest and JSON artifact inspection.

## Validation Sign-Off

- [x] All tasks have automated verify or Wave 0 dependencies.
- [x] Sampling continuity: no 3 consecutive tasks without automated verify.
- [x] Wave 0 covers all missing references.
- [x] No watch-mode flags.
- [x] Feedback latency target defined.

**Approval:** approved 2026-05-10
