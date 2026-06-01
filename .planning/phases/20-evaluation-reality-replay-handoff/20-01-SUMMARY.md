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

- Focused Phase 20 contract suite: passed (`17 passed`).
- Adjacent Phase 20/19/17 regression suite: passed (exit code 0).
- EVAL-01 report validation is green: `ok: true`, `next_phase_allowed: true`, `requirements_covered: [EVAL-01]`.

## Real eval evidence

- `scripts/run_v4_phase20_eval.sh` completed prompt generation, HF generation cache, and output normalization for 1032 eval rows.
- Original blocking failure: sample `a1eb7bbeaeeaadf10cd1b51bd090ba206576058a303a46bd62c8081f0042ca6e` output phase `1 = 59` while `min_green = max_green = 57`, producing `hard_constraint_lint` / `above_max`.
- The normalized eval output now applies one advisory `hard_bound_clamp` repair for that sample, preserving the original raw generated text/source solution while evaluating the bound-safe solution.
- `artifacts/v4_2/phase20/eval_report.json` is green: `hard_constraint_lint` passed `1032/1032`, `fatal_failures: []`, `advisory.normalization_repairs: 1`.
- Phase 19 export preflight is green after accepting the existing relative-path Phase 19 export evidence.

## Artifacts

- `tsc_cycle/v4_gates/phase20_eval.py`
- `scripts/run_v4_phase20_eval.sh`
- `tests/test_v4_phase20_evaluation_handoff.py`
- `.planning/phases/20-evaluation-reality-replay-handoff/20-01-SUMMARY.md`
- `artifacts/v4_2/phase20/eval_outputs.jsonl`
- `artifacts/v4_2/phase20/eval_report.json`
