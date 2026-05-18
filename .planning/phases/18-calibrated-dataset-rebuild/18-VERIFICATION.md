---
phase: 18-calibrated-dataset-rebuild
verified: 2026-05-18T10:47:10Z
status: passed
score: 3/3 must-haves verified
overrides_applied: 0
---

# Phase 18: Calibrated Dataset Rebuild Verification Report

**Phase Goal:** Maintainer can build and review a calibrated v4.2 dataset that removes or repairs saturation-policy violations while preserving protocol format, hard constraints, provenance, hashes, and deterministic splits.
**Verified:** 2026-05-18T10:47:10Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Maintainer can rebuild the v4.2 training dataset from v4 sources with violating examples either rejected or relabelled according to the offline saturation policy gate. | VERIFIED | `build_calibrated_dataset` exists in `tsc_cycle/v4_gates/calibrated_dataset_rebuild.py`; default mode is `filter`; real artifact check found 9501 source rows, 4532 retained rows, 4969 rejected rows, 0 relabelled rows; independent policy scan found no retained `VIOLATION_UNSATURATED_MAX_GREEN` rows; post policy gate `ok: true`. |
| 2 | Maintainer can confirm rebuilt examples preserve the required `<start_working_out>...</end_working_out><SOLUTION>...</SOLUTION>` protocol and all hard constraints. | VERIFIED | Independent full scan of all 4532 retained rows passed `constraint_lint.validate`; rendered prompt/assistant through `build_user_prompt` and `build_full_assistant`; all retained rows had required protocol markers. |
| 3 | Maintainer can review a reconstruction report showing source counts, rejected/relabelled counts, policy-pass rates, hard-constraint pass rates, dataset hashes, and split artifacts. | VERIFIED | `artifacts/v4_2/phase18/reconstruction_report.json` has `ok: true`, `next_phase_allowed: true`, requirements `DATA-01/DATA-02`, counts, policy post gate, hard-constraint pass rate 1.0, source/calibrated/sample hashes, split counts/hashes, paths, and representative rejections. |

**Score:** 3/3 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `tsc_cycle/v4_gates/calibrated_dataset_rebuild.py` | Phase 18 CLI, filtering, splits, path safety, report | VERIFIED | 448 lines; exports `Phase18DatasetConfig` (line 35), `build_calibrated_dataset` (line 305), `build_parser` (line 416); GSD artifact check passed. |
| `tests/test_v4_phase18_calibrated_dataset_rebuild.py` | Regression tests for filter, protocol, split, report, path safety | VERIFIED | 246 lines; Phase 18 suite passed: `5 passed`. |
| `data/v4_2/phase18/labeled_calibrated.jsonl` | Default calibrated v4.2 JSONL | VERIFIED | Exists; 4532 lines; sha256 `f60c263571c938c506db3dc919fdbd1528dba4e271764c8de106b4a626be0d00`; retained rows are canonical-equivalent to source rows, proving filter mode did not rewrite protocol/provenance. |
| `data/v4_2/phase18/splits/manifest.json` | Deterministic split manifest | VERIFIED | Exists; split counts train 3500, val 452, ood_val 580; split id hashes match index file recomputation and report. |
| `data/v4_2/phase18/splits/*.index.jsonl` | Deterministic retained split indexes | VERIFIED | train 3500, val 452, ood_val 580; every retained sample appears exactly once; no rejected sample appears; provenance and hash fields present. |
| `artifacts/v4_2/phase18/reconstruction_report.json` | Maintainer-facing DATA-02 report | VERIFIED | Exists and substantive; includes required counts, pass rates, hashes, splits, paths, rejections, and clean fatal/warning arrays. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `calibrated_dataset_rebuild.py` | `data/v4/phase8/labeled_merged.jsonl` | Source dataset JSONL read and per-row decision | WIRED | GSD key-link check found `_read_jsonl`; defaults point to Phase 8 source; independent artifact scan compared retained IDs to source IDs. |
| `calibrated_dataset_rebuild.py` | `tsc_cycle/v4_gates/saturation_policy.py` | Reuse policy classifiers/audit | WIRED | Imports `classify_violation`, `VIOLATION_UNSATURATED_MAX_GREEN`, `compute_saturation_audit`; retained evidence passes Phase 17 gate. |
| `calibrated_dataset_rebuild.py` | `data/v4/phase8/splits/*.index.jsonl` | Preserve split membership | WIRED | `_load_split_index` reads original indexes; independent scan confirmed output split membership matches original retained membership. |
| `calibrated_dataset_rebuild.py` | `tsc_cycle/constraint_lint.py` | Validate raw solutions before writing | WIRED | Imports `validate`; implementation validates raw solution before projection; full retained dataset scan passed hard constraints. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `labeled_calibrated.jsonl` | `retained_rows` | `source_rows = _read_jsonl(config.source_dataset)` filtered by hard constraints and saturation policy | Yes — 4532 retained source-derived rows, 4969 rejected | FLOWING |
| Split indexes | `split_rows` | Retained rows plus `_load_split_index(config.source_split_dir)` | Yes — train/val/ood_val counts recomputed and membership verified | FLOWING |
| Reconstruction report | `report` | Source rows, retained rows, policy audit/gate, hashes, split manifest | Yes — report hashes/counts independently recomputed | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Phase 18 unit/regression suite | `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest /home/samuel/TSC_CYCLE/tests/test_v4_phase18_calibrated_dataset_rebuild.py -q` | `5 passed` | PASS |
| Adjacent regression suite | `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest /home/samuel/TSC_CYCLE/tests/test_v4_phase18_calibrated_dataset_rebuild.py /home/samuel/TSC_CYCLE/tests/test_v4_phase17_saturation_policy.py /home/samuel/TSC_CYCLE/tests/test_v4_phase8_dataset_rebuild.py -q` | All tests passed (`................................................................... [100%]`) | PASS |
| Real artifact integrity scan | Python verification over source/output/report/splits | All checks true: counts, hard constraints, protocol, no policy violations, split membership, hashes | PASS |

### Probe Execution

| Probe | Command | Result | Status |
|-------|---------|--------|--------|
| Conventional/declared probes | Probe discovery found no `scripts/**/tests/probe-*.sh` and no phase-declared probe paths. | Not applicable | SKIPPED |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| DATA-01 | `18-01-PLAN.md` | Build calibrated v4.2 dataset by filtering or relabeling violating examples while preserving protocol and hard constraints. | SATISFIED | Real output filters 4969 policy violations, retains 4532 rows, has no retained unsaturated max-green violations, and all retained rows pass protocol/hard-constraint scan. |
| DATA-02 | `18-01-PLAN.md` | Review reconstruction report with source counts, rejected/relabelled counts, pass rates, hashes, and splits. | SATISFIED | Report includes counts, policy/hard-constraint pass rates, source/calibrated/sample hashes, split counts/hashes, paths, and representative rejections; hashes/splits recomputed successfully. |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `tsc_cycle/v4_gates/calibrated_dataset_rebuild.py` | 165 | `return {}` in `_record_solution` for non-dict raw solutions | INFO | Not a stub; raw solution validation happens before projection in `build_calibrated_dataset`, and malformed/non-dict cases are rejected. |

No unreferenced `TBD`, `FIXME`, or `XXX` debt markers found in Phase 18 source/tests.

### Human Verification Required

None.

### Gaps Summary

No blocking gaps found. The code, generated dataset, split indexes, reconstruction report, tests, and independent artifact scans support the Phase 18 goal.

---

_Verified: 2026-05-18T10:47:10Z_
_Verifier: Claude (gsd-verifier)_
