---
phase: 19
slug: 4b-qlora-retrain-export
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-05-18
---

# Phase 19 — Validation Strategy

## Test Infrastructure

| Property | Value |
|---|---|
| **Framework** | pytest 9.0.3 in project venv |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest tests/test_v4_phase19_training_export.py -q` |
| **Regression command** | `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest tests/test_v4_phase19_training_export.py tests/test_v4_phase18_calibrated_dataset_rebuild.py tests/test_v4_phase9_sft_contracts.py tests/test_v4_phase10_gguf_contracts.py -q` |
| **Estimated runtime** | < 90 seconds for contract tests |

## Sampling Rate

- **After every task commit:** Run `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest tests/test_v4_phase19_training_export.py -q`
- **After every plan wave:** Run adjacent regression command above.
- **Before verification:** Run target and adjacent regression; inspect/generated reports if heavy run/export artifacts exist.
- **Max feedback latency:** 90 seconds for non-heavy tests.

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---|---|---|---|---|---|---|---|---|---|
| 19-01-01 | 01 | 1 | TRAIN-01 | T-19-01 | v4.2 constants/defaults require Phase 18 data, Qwen3-4B, existing QLoRA stack, and `v4.2-4B-` run roots | unit | `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest tests/test_v4_phase19_training_export.py::test_v42_training_defaults_lock_phase18_data_and_qwen4b_stack -q` | ❌ W0 | ⬜ pending |
| 19-01-02 | 01 | 1 | TRAIN-01 | T-19-02 | Phase 18 handoff/tokenization writes split Arrow artifacts without protocol/native-think drift | integration | `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest tests/test_v4_phase19_training_export.py::test_phase18_handoff_tokenizes_calibrated_splits_with_protocol_hashes -q` | ❌ W0 | ⬜ pending |
| 19-01-03 | 01 | 1 | TRAIN-01 | T-19-03 | v4.2 training report gate validates adapter, model, run root, data manifest, and Phase 18 hashes | unit/integration | `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest tests/test_v4_phase19_training_export.py::test_phase19_training_report_gate_requires_v42_handoff_evidence -q` | ❌ W0 | ⬜ pending |
| 19-02-01 | 02 | 2 | TRAIN-02 | T-19-04 | v4.2 export plan/report records merged HF, GGUF fp16, GGUF q4_K_M paths and hashes under v4.2 run root | unit/integration | `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest tests/test_v4_phase19_training_export.py::test_v42_export_plan_and_report_require_merged_hf_and_gguf_hashes -q` | ❌ W0 | ⬜ pending |
| 19-02-02 | 02 | 2 | TRAIN-02 | T-19-05 | Wrapper commands use DGX-safe launch/export paths and forbid installs/vLLM/worktrees/frozen roots | unit | `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest tests/test_v4_phase19_training_export.py::test_v42_wrappers_forbid_dependency_installs_unsupported_runtimes_and_frozen_roots -q` | ❌ W0 | ⬜ pending |

## Wave 0 Requirements

- [ ] `tests/test_v4_phase19_training_export.py` — covers TRAIN-01 and TRAIN-02.
- [ ] v4.2 training helper/report implementation.
- [ ] v4.2 export helper/report implementation.

## Manual-Only Verifications

Full training/export runtime may be long. Automated contract tests must verify launchability and report contracts; if actual heavy artifacts are produced during execution, final verification must inspect their hashes/reports.

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 90s for contract tests
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-05-18
