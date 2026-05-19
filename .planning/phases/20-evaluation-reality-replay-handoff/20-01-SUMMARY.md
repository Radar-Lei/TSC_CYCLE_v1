---
phase: 20-evaluation-reality-replay-handoff
plan: "01"
status: complete
completed: 2026-05-19
requirements: [EVAL-01]
---

# Plan 20-01 Summary — EVAL-01 Calibrated Evaluation Gate

## Completed

- Added `tsc_cycle/v4_gates/phase20_eval.py` with the Phase 20 EVAL-01 public API:
  - `build_phase20_eval_prompts`
  - `load_phase20_generated_outputs`
  - `evaluate_phase20_outputs`
  - `write_phase20_eval_report`
  - `validate_phase20_eval_report`
  - `main`
- Built prompt construction from calibrated Phase 18 `val` and `ood_val` split rows under `data/v4_2/phase18`, preserving `split_hint`/`slice_hint` provenance.
- Added generated-output normalization from `artifacts/v4_2/phase20/gen_cache/v4_2_hf/*.json` into `eval_outputs.jsonl`, failing closed when any cache row is missing.
- Added fail-closed evaluation report logic that validates Phase 19 export handoff first, then blocks on parse/protocol, hard-constraint lint, and saturation-policy gates.
- Kept teacher-MAE advisory-only under `advisory.teacher_mae`; it is not included in blocking gate criteria or decision inputs.
- Added `scripts/run_v4_phase20_eval.sh` for the deterministic DGX-safe chain: build prompts → HF generation cache → normalize outputs → evaluate report.

## Validation

- Focused Phase 20 contract suite: passed (`9 passed`).
- Adjacent Phase 20/19/17 regression suite: passed (exit code 0).

## Artifacts

- `tsc_cycle/v4_gates/phase20_eval.py`
- `scripts/run_v4_phase20_eval.sh`
- `tests/test_v4_phase20_evaluation_handoff.py`
- `.planning/phases/20-evaluation-reality-replay-handoff/20-01-SUMMARY.md`
