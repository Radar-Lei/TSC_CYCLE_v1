---
phase: 08-v3-4b-dataset-rebuild
plan: 02
subsystem: data
tags: [dataset-rebuild, qwen3-4b, tokenization, jsonl, pyarrow, v4]

requires:
  - phase: 08-v3-4b-dataset-rebuild
    provides: Phase 8 RED contracts for v4 source rebuild and split/tokenize behavior
  - phase: 07-4b-baseline-label-protocol-gate
    provides: Phase 7 tokenizer/native-think gate and next-phase handoff report
provides:
  - v4 Phase 8 source merge, malformed tag normalization, canonical dedupe, and manifest gates
  - deterministic seed=42 v4 split indexes and dry-run rebuild evidence for Qwen3-4B raw-text tokenization
  - v4-isolated source, cleaning, split, and rebuild artifacts under data/v4/phase8 and artifacts/v4/phase8
affects: [phase9-4b-qlora-retrain, DATA4B, qwen3-4b-tokenization]

tech-stack:
  added: []
  patterns:
    - Frozen v1 output guard before all Phase 8 filesystem writes
    - Injected tokenizer path for CPU-fast tests and live AutoTokenizer loading only when needed
    - Native think token ID checks on untruncated raw-text IDs before max_seq_length truncation

key-files:
  created:
    - tsc_cycle/v4_gates/dataset_rebuild.py
    - data/v4/phase8/labeled_merged.jsonl
    - data/v4/phase8/splits/manifest.json
    - artifacts/v4/phase8/source_manifest.json
    - artifacts/v4/phase8/cleaning_report.json
    - artifacts/v4/phase8/rebuild_report.json
  modified: []

key-decisions:
  - "Phase 8 source dedupe uses canonical normalized records with lineage removed for the dedupe key, while manifest sample hashes preserve full normalized records for reproducibility evidence."
  - "Dry-run CLI writes JSONL/index/report artifacts but intentionally skips Arrow IPC tokenized files to avoid heavy writes during smoke verification."

patterns-established:
  - "All v4 rebuild outputs call the frozen-root guard before writing to prevent accidental mutation of runs/20260507T032419Z."
  - "Split selection keeps all v1 OOD rows in ood_val, fills the remaining OOD target from deterministic sampled v3 extended OOD rows, then samples val from the remaining sorted pool."

requirements-completed: [DATA4B-01, DATA4B-02, DATA4B-03, DATA4B-04]

duration: 6min
completed: 2026-05-09
---

# Phase 08 Plan 02: v4 Dataset Rebuild Engine Summary

**v4 Qwen3-4B dataset rebuild engine with source normalization, deterministic split indexes, native-think token gates, and dry-run rebuild evidence**

## Performance

- **Duration:** 6 min
- **Started:** 2026-05-09T17:42:55Z
- **Completed:** 2026-05-09T17:49:11Z
- **Tasks:** 2
- **Files modified:** 10

## Accomplishments

- Implemented `Phase8DatasetConfig`, `build_v4_source_dataset`, `build_v4_splits_and_tokenized`, `build_parser`, and `main` in `tsc_cycle/v4_gates/dataset_rebuild.py`.
- Generated v4 source artifacts from explicit v1 valid and v3 new lint-pass JSONL sources, including normalized merged JSONL, source manifest, and cleaning report.
- Produced deterministic seed=42 train/val/ood_val split index artifacts and dry-run rebuild report with Qwen3-4B defaults, native think token IDs, and truncation-rate evidence.

## Task Commits

1. **Task 1/2: Implement v4 source merge, deterministic split, tokenization, and CLI** - `9f3ba84` (feat)
2. **Task 2 artifacts: Generate v4 dataset rebuild artifacts** - `115c7b3` (chore)

**Plan metadata:** pending final docs commit

## Files Created/Modified

- `tsc_cycle/v4_gates/dataset_rebuild.py` - Phase 8 v4 source merge, cleaning, split, tokenization, report, and CLI implementation.
- `data/v4/phase8/labeled_merged.jsonl` - normalized deduped v4 source JSONL generated from explicit v1/v3 sources.
- `data/v4/phase8/splits/train.index.jsonl` - deterministic train split index.
- `data/v4/phase8/splits/val.index.jsonl` - deterministic validation split index.
- `data/v4/phase8/splits/ood_val.index.jsonl` - deterministic OOD validation split index containing v1 OOD alignment rows.
- `data/v4/phase8/splits/v1_ood_alignment.json` - v1 OOD alignment evidence.
- `data/v4/phase8/splits/manifest.json` - split hashes, counts, and v4 path manifest.
- `artifacts/v4/phase8/source_manifest.json` - source counts, SHA-256s, dedupe evidence, and DATA4B-01 gates.
- `artifacts/v4/phase8/cleaning_report.json` - malformed close-tag replacement count and native think absence evidence.
- `artifacts/v4/phase8/rebuild_report.json` - dry-run split/tokenization gate evidence and DATA4B-02..05 coverage.

## Verification

- `PYTHONPATH=/home/samuel/TSC_CYCLE /home/samuel/TSC_CYCLE/.venv/bin/python -m pytest -q /home/samuel/TSC_CYCLE/tests/test_v4_phase8_dataset_rebuild.py -k 'not aggregate'`
  - Result: 7 passed.
- Full Phase 8 test file with `--maxfail=1`
  - Result: expected failure on `ModuleNotFoundError: No module named 'tsc_cycle.v4_gates.phase8_report'`, which belongs to later aggregate/card work outside Plan 08-02.
- CLI dry run:
  - `PYTHONPATH=/home/samuel/TSC_CYCLE /home/samuel/TSC_CYCLE/.venv/bin/python -m tsc_cycle.v4_gates.dataset_rebuild --dry-run ...`
  - Result: `ok: true`, split counts `train=7601`, `val=950`, `ood_val=950`, truncation over-length rate `0.0`, native think token IDs `[151667, 151668]`.
- Grep acceptance checks:
  - `data/v4/phase8` occurrences in non-comment implementation lines: 3
  - `Qwen/Qwen3-4B-Thinking-2507` occurrences in non-comment implementation lines: 1
  - `Qwen3.5` occurrences in non-comment implementation lines: 0

## Decisions Made

- Used full normalized record hashes for manifest reproducibility and a lineage-stripped canonical hash for dedupe so v1/v3 duplicate fixture rows correctly prefer the v1 row.
- Kept tokenization raw-text only: `build_user_prompt(input) + build_full_assistant(reasoning, solution)`, `add_special_tokens=False`, and no chat template calls.
- Kept Arrow IPC writes behind `write_tokenized` / `--dry-run`; dry-run still emits reports and split indexes but no tokenized Arrow files.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Dedupe fixture equivalence required lineage-insensitive canonical key**
- **Found during:** Task 1/2 verification against RED contracts
- **Issue:** The v1/v3 duplicate fixture differs by lineage after close-tag normalization, so hashing the full record would not dedupe the intended duplicate.
- **Fix:** Added a lineage-stripped canonical dedupe key while preserving full normalized sample hashes in the source manifest.
- **Files modified:** `tsc_cycle/v4_gates/dataset_rebuild.py`
- **Verification:** Non-aggregate Phase 8 tests passed and manifest reports `v3_duplicate_rows == 1` on fixture contracts.
- **Committed in:** `9f3ba84`

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** The auto-fix was required to satisfy deterministic dedupe semantics and did not expand scope.

## Issues Encountered

- Full `tests/test_v4_phase8_dataset_rebuild.py` still fails at aggregate report tests because `tsc_cycle.v4_gates.phase8_report` is not part of Plan 08-02 and is reserved for a later plan.

## User Setup Required

None - no external service configuration required.

## Known Stubs

None detected in files created/modified by this plan.

## Threat Flags

None - the implementation addresses the planned filesystem, JSONL, tokenization, and native-think trust boundaries without adding new network endpoints, auth paths, or schema trust boundaries.

## Next Phase Readiness

- Phase 8 aggregate report and dataset card plans can consume `artifacts/v4/phase8/source_manifest.json`, `cleaning_report.json`, and `rebuild_report.json`.
- Phase 9 can use the v4 source and split artifacts after the later aggregate Phase 8 handoff gate is implemented.

## Self-Check: PASSED

- Found `tsc_cycle/v4_gates/dataset_rebuild.py`.
- Found `data/v4/phase8/labeled_merged.jsonl`.
- Found `data/v4/phase8/splits/manifest.json`.
- Found `artifacts/v4/phase8/source_manifest.json`.
- Found `artifacts/v4/phase8/cleaning_report.json`.
- Found `artifacts/v4/phase8/rebuild_report.json`.
- Found task commit `9f3ba84` in git history.
- Found artifact commit `115c7b3` in git history.

---
*Phase: 08-v3-4b-dataset-rebuild*
*Completed: 2026-05-09*
