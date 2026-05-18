---
phase: 18
slug: calibrated-dataset-rebuild
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-05-18
---

# Phase 18 — Validation Strategy

## Test Infrastructure

| Property | Value |
|---|---|
| **Framework** | pytest 9.0.3 in project venv |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest tests/test_v4_phase18_calibrated_dataset_rebuild.py -q` |
| **Regression command** | `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest tests/test_v4_phase18_calibrated_dataset_rebuild.py tests/test_v4_phase17_saturation_policy.py tests/test_v4_phase8_dataset_rebuild.py -q` |
| **Estimated runtime** | < 60 seconds for targeted tests |

## Sampling Rate

- **After every task commit:** Run `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest tests/test_v4_phase18_calibrated_dataset_rebuild.py -q`
- **After every plan wave:** Run `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest tests/test_v4_phase18_calibrated_dataset_rebuild.py tests/test_v4_phase17_saturation_policy.py tests/test_v4_phase8_dataset_rebuild.py -q`
- **Before verification:** Run the full suite if targeted and adjacent regressions are green.
- **Max feedback latency:** 60 seconds

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---|---|---|---|---|---|---|---|---|---|
| 18-01-01 | 01 | 1 | DATA-01 | T-18-01 | Filter mode removes unsaturated max-green violations while retaining allowed saturated/trivial rows | unit | `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest tests/test_v4_phase18_calibrated_dataset_rebuild.py::test_filter_mode_removes_unsaturated_max_green_violations -q` | ❌ W0 | ⬜ pending |
| 18-01-02 | 01 | 1 | DATA-01 | T-18-02 | Retained rows preserve hard constraints and prompt/assistant protocol | unit/integration | `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest tests/test_v4_phase18_calibrated_dataset_rebuild.py::test_retained_rows_preserve_hard_constraints_and_protocol -q` | ❌ W0 | ⬜ pending |
| 18-01-03 | 01 | 1 | DATA-02 | T-18-03 | Rebuilt split indexes preserve retained sample split membership and deterministic hashes | integration | `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest tests/test_v4_phase18_calibrated_dataset_rebuild.py::test_split_indexes_preserve_retained_membership_and_hashes -q` | ❌ W0 | ⬜ pending |
| 18-01-04 | 01 | 1 | DATA-02 | T-18-04 | Reconstruction report exposes counts, pass rates, hashes, split artifacts, and rejection examples | integration | `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest tests/test_v4_phase18_calibrated_dataset_rebuild.py::test_reconstruction_report_contains_counts_hashes_and_policy_pass_rates -q` | ❌ W0 | ⬜ pending |
| 18-01-05 | 01 | 1 | DATA-01/DATA-02 | T-18-05 | CLI defaults isolate v4.2 outputs and reject frozen/Phase 8/broad output paths | unit | `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest tests/test_v4_phase18_calibrated_dataset_rebuild.py::test_cli_defaults_and_path_guards_keep_phase18_outputs_isolated -q` | ❌ W0 | ⬜ pending |

## Wave 0 Requirements

- [ ] `tests/test_v4_phase18_calibrated_dataset_rebuild.py` — covers DATA-01 and DATA-02.
- [ ] `tsc_cycle/v4_gates/calibrated_dataset_rebuild.py` — calibrated rebuild implementation and CLI.

## Manual-Only Verifications

None. Phase behaviors are covered by automated tests and generated reports.

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 60s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-05-18
