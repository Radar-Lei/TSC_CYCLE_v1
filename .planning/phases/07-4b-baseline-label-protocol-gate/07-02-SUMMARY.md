---
phase: 07-4b-baseline-label-protocol-gate
plan: 02
subsystem: baseline-gate
tags: [baseline, environment, readonly, phase7]
requires: []
provides:
  - Qwen3-4B model lock gate
  - environment evidence report
  - frozen v1 baseline read-only snapshot
affects:
  - tsc_cycle/v4_gates/phase7_baseline.py
key-files:
  created:
    - tsc_cycle/v4_gates/phase7_baseline.py
    - tests/test_v4_phase7_baseline_gate.py
    - artifacts/v4/phase7/environment.json
    - artifacts/v4/phase7/baseline_readonly.json
  modified:
    - tsc_cycle/v4_gates/__init__.py
key-decisions:
  - `Qwen/Qwen3-4B-Thinking-2507` is the only accepted Phase 7 model id.
  - Missing bnb/trl in `/home/samuel/dgx-spark-setup/.venv` is a warning only; Phase 7 does not mutate environments.
  - The actual discovered v1 q4 cache path is recorded because the documented `gguf_q4km` path is absent.
requirements-completed:
  - BASE-01
  - BASE-02
  - BASE-03
duration: 0 min
completed: 2026-05-10
---

# Phase 07 Plan 02: Baseline Gate Summary

Implemented a v4 Phase 7 baseline/environment/read-only gate that locks the route to Qwen3-4B and proves the frozen v1 baseline root is unchanged.

## What Changed

- Added `tsc_cycle/v4_gates/phase7_baseline.py` with model id validation, environment probes, output path guard, baseline snapshots, and CLI entry point.
- Added `tests/test_v4_phase7_baseline_gate.py` for model lock, frozen-root path guard, snapshot contract, and aggregate-compatible artifact payloads.
- Generated `artifacts/v4/phase7/environment.json` and `artifacts/v4/phase7/baseline_readonly.json`.

## Verification

- `PYTHONPATH=/home/samuel/TSC_CYCLE /home/samuel/TSC_CYCLE/.venv/bin/python -m pytest -q tests/test_v4_phase7_baseline_gate.py` — passed, 6 tests.
- `PYTHONPATH=/home/samuel/TSC_CYCLE /home/samuel/TSC_CYCLE/.venv/bin/python -m tsc_cycle.v4_gates.phase7_baseline --environment-out /home/samuel/TSC_CYCLE/artifacts/v4/phase7/environment.json --baseline-out /home/samuel/TSC_CYCLE/artifacts/v4/phase7/baseline_readonly.json` — passed with `ok: true`.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- Non-blocking warning: documented v1 cache path `runs/20260507T032419Z/eval/gen_cache/gguf_q4km` is absent; actual discovered q4 cache includes `eval/gen_cache/gguf_q4_k_m`.
- Non-blocking warning: `/home/samuel/dgx-spark-setup/.venv` lacks `bitsandbytes` and `trl`; Phase 7 reports this without installation.

## Self-Check: PASSED

- BASE-01 model lock accepts only `Qwen/Qwen3-4B-Thinking-2507`.
- BASE-02 environment evidence has `mutation_actions: []`.
- BASE-03 frozen baseline before/after snapshots are unchanged and no Phase 7 artifact was written under `runs/20260507T032419Z/`.
