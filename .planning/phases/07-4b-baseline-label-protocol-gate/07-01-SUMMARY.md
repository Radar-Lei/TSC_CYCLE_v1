---
phase: 07-4b-baseline-label-protocol-gate
plan: 01
subsystem: protocol-gate
tags: [protocol, validation, phase7]
requires: []
provides:
  - corrected slash-close protocol
  - protocol fixture gate
  - protocol test coverage
affects:
  - tsc_cycle/prompt_builder.py
  - tsc_cycle/v4_gates/phase7_protocol.py
key-files:
  created:
    - tests/test_v4_phase7_protocol.py
    - tsc_cycle/v4_gates/__init__.py
    - tsc_cycle/v4_gates/phase7_protocol.py
    - artifacts/v4/phase7/protocol_fixture.json
  modified:
    - tsc_cycle/prompt_builder.py
    - tests/test_prompt_builder.py
key-decisions:
  - `</end_working_out>` is the only valid thinking close tag for v4.
  - `<end_working_out>`, `<think>`, and `</think>` fail closed in protocol parsing.
requirements-completed:
  - TAG-01
  - TAG-02
  - TAG-03
duration: 0 min
completed: 2026-05-10
---

# Phase 07 Plan 01: Protocol Gate Summary

Corrected the shared prompt/protocol layer so v4 accepts only the slash-close protocol and rejects malformed or native Qwen thinking tags.

## What Changed

- Updated `tsc_cycle/prompt_builder.py` to use `TAG_THINK_CLOSE = "</end_working_out>"`.
- Added fail-closed rejection for `<end_working_out>`, `<think>`, and `</think>` in `parse_assistant_output`.
- Updated `tests/test_prompt_builder.py` expectations to the corrected protocol.
- Added `tests/test_v4_phase7_protocol.py` for Phase 7 accepted/rejected fixtures.
- Added `tsc_cycle/v4_gates/phase7_protocol.py` and generated `artifacts/v4/phase7/protocol_fixture.json`.

## Verification

- `PYTHONPATH=/home/samuel/TSC_CYCLE /home/samuel/TSC_CYCLE/.venv/bin/python -m pytest -q tests/test_v4_phase7_protocol.py tests/test_prompt_builder.py` — passed, 23 tests.
- `PYTHONPATH=/home/samuel/TSC_CYCLE /home/samuel/TSC_CYCLE/.venv/bin/python -m tsc_cycle.v4_gates.phase7_protocol --out /home/samuel/TSC_CYCLE/artifacts/v4/phase7/protocol_fixture.json` — passed with `ok: true`.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## Self-Check: PASSED

- `TAG_THINK_CLOSE` is exactly `</end_working_out>`.
- The malformed bare close marker and native think markers are rejected.
- `protocol_fixture.json` covers TAG-01, TAG-02, and TAG-03 with `ok: true`.
