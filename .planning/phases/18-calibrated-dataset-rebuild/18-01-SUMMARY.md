---
phase: 18-calibrated-dataset-rebuild
plan: "01"
subsystem: calibrated-dataset-rebuild
tags: [python, pytest, jsonl, saturation-policy, v4.2]

requires:
  - phase: 17-audit-saturation-policy-gate
    provides: offline saturation policy classifier, projectors, and gate
provides:
  - Filter-mode v4.2 calibrated dataset rebuild CLI
  - v4.2 calibrated JSONL and deterministic split indexes
  - Reconstruction report with counts, pass rates, hashes, and representative rejections
affects: [phase-19-4b-qlora-retrain-export, phase-20-evaluation-reality-replay]

tech-stack:
  added: []
  patterns: [stdlib JSONL transform, Phase 17 policy reuse, Phase 8 split/hash preservation]

key-files:
  created:
    - tsc_cycle/v4_gates/calibrated_dataset_rebuild.py
    - tests/test_v4_phase18_calibrated_dataset_rebuild.py
    - data/v4_2/phase18/labeled_calibrated.jsonl
    - data/v4_2/phase18/splits/manifest.json
    - data/v4_2/phase18/splits/train.index.jsonl
    - data/v4_2/phase18/splits/val.index.jsonl
    - data/v4_2/phase18/splits/ood_val.index.jsonl
    - artifacts/v4_2/phase18/reconstruction_report.json

key-decisions:
  - "Use filter mode as the Phase 18 default; relabelled_rows remains 0 to avoid reasoning/solution contradictions."
  - "Reuse Phase 17 saturation policy helpers as the only policy source of truth."
  - "Preserve retained sample split membership from Phase 8 indexes instead of re-randomizing splits."

patterns-established:
  - "Phase 18 outputs are isolated under data/v4_2/phase18 and artifacts/v4_2/phase18."
  - "Reconstruction report exposes source/retained/rejected/relabelled counts plus post-policy gate evidence."

requirements-completed: [DATA-01, DATA-02]

completed: 2026-05-18
---

# Phase 18 Plan 01: Calibrated Dataset Rebuild Summary

**Filter-mode calibrated v4.2 dataset rebuild with deterministic splits and maintainer-facing reconstruction report**

## Accomplishments

- Added `tsc_cycle/v4_gates/calibrated_dataset_rebuild.py` with `Phase18DatasetConfig`, `build_calibrated_dataset`, CLI defaults, output path guards, filter-mode calibration, split reconstruction, and report writing.
- Added `tests/test_v4_phase18_calibrated_dataset_rebuild.py` covering policy filtering, hard-constraint/protocol preservation, split hash artifacts, report fields, CLI defaults, and path safety.
- Generated real Phase 18 artifacts under `data/v4_2/phase18/` and `artifacts/v4_2/phase18/`.

## Generated Dataset Summary

- Source rows: 9501
- Retained rows: 4532
- Rejected rows: 4969
- Policy rejected rows: 4969
- Hard-constraint rejected rows: 0
- Malformed rejected rows: 0
- Relabelled rows: 0
- Split counts: train 3500, val 452, ood_val 580
- Calibrated JSONL sha256: `f60c263571c938c506db3dc919fdbd1528dba4e271764c8de106b4a626be0d00`
- Post-calibration policy gate: pass

## Files Created/Modified

- `tsc_cycle/v4_gates/calibrated_dataset_rebuild.py`
- `tests/test_v4_phase18_calibrated_dataset_rebuild.py`
- `data/v4_2/phase18/labeled_calibrated.jsonl`
- `data/v4_2/phase18/splits/*.index.jsonl`
- `data/v4_2/phase18/splits/manifest.json`
- `artifacts/v4_2/phase18/reconstruction_report.json`

## Verification

- `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest tests/test_v4_phase18_calibrated_dataset_rebuild.py -q` — PASS
- `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest tests/test_v4_phase18_calibrated_dataset_rebuild.py tests/test_v4_phase17_saturation_policy.py tests/test_v4_phase8_dataset_rebuild.py -q` — PASS
- `/home/samuel/TSC_CYCLE/.venv/bin/python -m tsc_cycle.v4_gates.calibrated_dataset_rebuild` — PASS; wrote Phase 18 artifacts and report

## Deviations from Plan

None. Phase 18 uses the planned filter-mode default and leaves relabeling out of scope.

## User Setup Required

None.

## Known Stubs

None.

## Next Phase Readiness

Phase 19 can consume `data/v4_2/phase18/labeled_calibrated.jsonl` and split indexes for calibrated QLoRA training.
