---
phase: 03
slug: dataset-rebuild-qwen3-5-retokenize-split
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-09
---

# Phase 03 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3 |
| **Config file** | `pyproject.toml` (`testpaths=["tests"]`, `addopts="-q"`) |
| **Quick run command** | `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest tests/test_v3_dataset_rebuild.py -q` |
| **Full suite command** | `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest -q` |
| **Estimated runtime** | ~1-5 minutes depending on tokenizer load |

---

## Sampling Rate

- **After every task commit:** Run `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest tests/test_v3_dataset_rebuild.py -q`.
- **After every plan wave:** Run `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest tests/test_v3_dataset_rebuild.py tests/test_hashing.py tests/test_prompt_builder.py -q`.
- **Before `/gsd-verify-work`:** Run full focused dataset rebuild command on `data/v3/phase2/labeled_merged.jsonl`, then focused tests and baseline diff checks.
- **Max feedback latency:** <5 minutes for tests; full tokenization may take longer but must emit deterministic reports.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 03-W0-01 | Wave 0 tests | 0 | DATA-01 | T-03-duplicate-split | Split IDs are disjoint and deterministic | unit/integration | `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest tests/test_v3_dataset_rebuild.py::test_split_exact_sizes_and_v1_ood_alignment -q` | ❌ W0 | ⬜ pending |
| 03-W0-02 | Wave 0 tests | 0 | DATA-02 | T-03-path-drift | Writes only `data/tokenized/v3/*.arrow` | unit/integration | `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest tests/test_v3_dataset_rebuild.py::test_writes_arrow_ipc_files -q` | ❌ W0 | ⬜ pending |
| 03-W0-03 | Wave 0 tests | 0 | DATA-03 | T-03-truncation | Truncation rate is measured before truncation and fails above 5% | unit | `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest tests/test_v3_dataset_rebuild.py::test_truncation_rate_gate_fails_closed -q` | ❌ W0 | ⬜ pending |
| 03-W0-04 | Wave 0 tests | 0 | DATA-04 | T-03-reproducibility | Split indices persist sample IDs and hashes | unit | `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest tests/test_v3_dataset_rebuild.py::test_split_indices_persist_hashes_and_manifest -q` | ❌ W0 | ⬜ pending |

---

## Wave 0 Requirements

- [ ] `tests/test_v3_dataset_rebuild.py` — covers DATA-01..04.
- [ ] `tsc_cycle/v3_gates/dataset_rebuild_v3.py` — implementation target for the tests.
- [ ] PyArrow IPC reader smoke for generated `.arrow` files.

---

## Manual-Only Verifications

All phase behaviors should have automated verification. If tokenizer download/cache is missing, the executor should stop with an environment checkpoint rather than mark the phase complete.

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency <5 minutes for focused tests
- [ ] `nyquist_compliant: true` set in frontmatter after Wave 0 tests are implemented and mapped

**Approval:** pending
