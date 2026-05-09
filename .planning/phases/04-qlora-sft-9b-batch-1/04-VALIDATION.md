---
phase: 04
slug: qlora-sft-9b-batch-1
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-05-09
---

# Phase 04 — Validation Strategy

> Per-phase validation contract for Qwen3.5-9B QLoRA SFT execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3 in project `.venv` |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest tests/test_v3_sft_config.py tests/test_v3_sft_frozen.py tests/test_v3_sft_arrow_loader.py -q` |
| **Full suite command** | `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest tests -q` |
| **Estimated runtime** | Quick tests <60s; full suite depends on non-GPU coverage |

---

## Sampling Rate

- **After every task commit:** Run `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest tests/test_v3_sft_*.py -q` after Wave 0 files exist.
- **After every plan wave:** Run `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest tests -q` plus the wave's JSON report assertion command.
- **Before `/gsd-verify-work`:** Phase 4 dry-run and full-run JSON reports must have `ok=true`.
- **Max feedback latency:** <60s for unit/config gates; long GPU dry/full runs are explicit execution gates.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 04-01-01 | 01 | 0 | SFT-01,SFT-02,SFT-03,SFT-05,SFT-07 | T-04-config-drift | Locked config cannot silently fall back to v1.0 defaults | unit | `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest tests/test_v3_sft_config.py -q` | ❌ W0 | ⬜ pending |
| 04-01-02 | 01 | 0 | SFT-08 | T-04-v1-overwrite | v1.0 production artifact is frozen/read-only and not a write target | unit | `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest tests/test_v3_sft_frozen.py -q` | ❌ W0 | ⬜ pending |
| 04-01-03 | 01 | 0 | SFT-04,SFT-06 | T-04-false-green | dry-run and grad gates fail closed before full run | unit | `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest tests/test_v3_sft_dry_run.py tests/test_v3_sft_grad_gate.py -q` | ❌ W0 | ⬜ pending |
| 04-02-01 | 02 | 1 | SFT-01,SFT-02,SFT-03,SFT-05,SFT-07 | T-04-config-drift | trainer builds Qwen3.5-9B QLoRA config exactly from locked values | unit | `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest tests/test_v3_sft_config.py tests/test_v3_sft_arrow_loader.py -q` | ⬜ pending | ⬜ pending |
| 04-03-01 | 03 | 2 | SFT-04,SFT-06 | T-04-false-green | 500-sample dry-run must pass OOD lint and grad gates before full run | integration | `scripts/run_v3_phase4_dry_run.sh` | ⬜ pending | ⬜ pending |
| 04-04-01 | 04 | 3 | SFT-05,SFT-07 | T-04-artifact-drift | full run uses early stopping and isolated v3.0 run root | integration | `scripts/run_v3_phase4_full.sh` | ⬜ pending | ⬜ pending |
| 04-05-01 | 05 | 4 | SFT-01..SFT-08 | T-04-repudiation | aggregate report proves all SFT gates and artifact hashes | integration | `/home/samuel/TSC_CYCLE/.venv/bin/python -m tsc_cycle.v3_gates.sft_report_v3 --run-dir <run-dir>` | ⬜ pending | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_v3_sft_config.py` — stubs for SFT-01, SFT-02, SFT-03, SFT-05, SFT-07.
- [ ] `tests/test_v3_sft_arrow_loader.py` — stubs for direct Phase 3 Arrow IPC consumption.
- [ ] `tests/test_v3_sft_dry_run.py` — stubs for SFT-04 dry-run gate semantics.
- [ ] `tests/test_v3_sft_grad_gate.py` — stubs for SFT-06 grad_norm/NaN fail-closed behavior.
- [ ] `tests/test_v3_sft_frozen.py` — stubs for SFT-08 FROZEN guard and output allowlist.
- [ ] `scripts/run_v3_phase4_dry_run.sh` and `scripts/run_v3_phase4_full.sh` — safe wrapper invocation covered by tests or shell syntax checks.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Full Qwen3.5-9B training convergence | SFT-05 | Long GPU run cannot be simulated by unit tests | Run `scripts/run_v3_phase4_full.sh`; verify `sft_manifest.json` has `ok=true`, early stopping evidence, best adapter path, and isolated run root. |
| 500-sample dry-run GPU gate | SFT-04,SFT-06 | Requires actual model training/generation | Run `scripts/run_v3_phase4_dry_run.sh`; verify dry-run report has `ok=true`, `sample_count=500`, `ood_hard_constraint_pass_rate>=0.95`, `grad_norm_p99<3.0`, and no NaN. |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all missing references
- [x] No watch-mode flags
- [x] Feedback latency <60s for unit/config gates
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
