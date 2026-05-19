---
phase: 20-evaluation-reality-replay-handoff
plan: "02"
status: code-complete-pending-live-replay
completed: 2026-05-19
requirements: [EVAL-02]
---

# Plan 20-02 Summary — EVAL-02 Reality Replay Gate

## Completed

- Added `tsc_cycle/v4_gates/phase20_log_render.py` with v4.2 replay rendering and fail-closed per-output validation.
- Added `tsc_cycle/v4_gates/phase20_reality_test.py` with reality input extraction, live llama-server replay orchestration, manifest/per-sample/report writing, and report validation.
- Added `scripts/run_v4_phase20_reality_test.sh` for the canonical q4_K_M replay path against `runs/v4.2-4B-20260518T111519Z/gguf/model.q4_K_M.gguf`.
- Enforced Phase 19 export and Phase 20 eval report preflights before replay evidence can be accepted.
- Enforced that dry-run, limited replay, count mismatch, parse/protocol/lint/saturation failure, missing final log, or model hash mismatch cannot cover `EVAL-02`.
- Kept GGUF live replay helpers imported lazily inside `_run_live`.

## Validation

- Focused Phase 20 contract suite: passed (`13 passed`).
- Adjacent Phase 20/19/17/12 regression suite: passed (exit code 0; 84 tests, warnings only).

## Pending live evidence

- Full non-dry-run q4_K_M replay is hardware-dependent and remains pending.
- Acceptance command after `artifacts/v4_2/phase20/eval_report.json` exists:
  `/home/samuel/TSC_CYCLE/scripts/run_v4_phase20_reality_test.sh`
- Validation command:
  `/home/samuel/TSC_CYCLE/.venv/bin/python -m tsc_cycle.v4_gates.phase20_reality_test --validate-report --report /home/samuel/TSC_CYCLE/artifacts/v4_2/phase20/reality_replay_report.json`

## Artifacts

- `tsc_cycle/v4_gates/phase20_log_render.py`
- `tsc_cycle/v4_gates/phase20_reality_test.py`
- `scripts/run_v4_phase20_reality_test.sh`
- `tests/test_v4_phase20_evaluation_handoff.py`
- `.planning/phases/20-evaluation-reality-replay-handoff/20-02-SUMMARY.md`
