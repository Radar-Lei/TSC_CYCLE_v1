---
phase: 20-evaluation-reality-replay-handoff
plan: "03"
status: code-complete-blocked-by-eval-red
completed: 2026-05-19
requirements: [EVAL-03]
---

# Plan 20-03 Summary — EVAL-03 Comparison and Final Handoff

## Completed

- Added `tsc_cycle/v4_gates/phase20_comparison.py` with a fail-closed v4.0 vs v4.2 comparison gate.
- Added `tsc_cycle/v4_gates/phase20_handoff.py` with final handoff manifest writing and validation.
- Added tests for hard-constraint non-regression, low-saturation max-green reduction, upstream EVAL-01/EVAL-02 preflight failure, advisory-only teacher-MAE, lightweight imports, recomputed handoff hashes, missing artifact failure, and v4.0 path rejection.
- Comparison acceptance covers `EVAL-03` only when upstream eval/replay gates are green, hard constraints do not regress, and v4.2 low-saturation max-green failures are reduced and threshold-compliant.
- Handoff acceptance covers exactly `EVAL-01`, `EVAL-02`, and `EVAL-03` only when eval, replay, comparison, and all required artifact records validate with recomputed on-disk size/hash evidence.

## Validation

- Focused Phase 20 contract suite: passed (`16 passed`).
- Python compile and diff whitespace checks: passed.
- Adjacent Phase 20/19/17/12 regression suite: passed (exit code 0; 87 tests, warnings only).

## Pending live evidence

- Final green comparison and handoff manifest still depend on accepted full non-dry-run `EVAL-02` replay evidence under `artifacts/v4_2/phase20`.
- Comparison and handoff are currently blocked because `artifacts/v4_2/phase20/eval_report.json` is red on one EVAL-01 hard-constraint violation.
- Once eval and live replay are green, run:
  `/home/samuel/TSC_CYCLE/.venv/bin/python -m tsc_cycle.v4_gates.phase20_comparison --report /home/samuel/TSC_CYCLE/artifacts/v4_2/phase20/comparison_report.json`
- Then run:
  `/home/samuel/TSC_CYCLE/.venv/bin/python -m tsc_cycle.v4_gates.phase20_handoff --manifest /home/samuel/TSC_CYCLE/artifacts/v4_2/phase20/handoff_manifest.json`

## Artifacts

- `tsc_cycle/v4_gates/phase20_comparison.py`
- `tsc_cycle/v4_gates/phase20_handoff.py`
- `tests/test_v4_phase20_evaluation_handoff.py`
- `.planning/phases/20-evaluation-reality-replay-handoff/20-03-SUMMARY.md`
