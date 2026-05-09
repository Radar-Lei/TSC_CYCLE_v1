---
phase: 07-4b-baseline-label-protocol-gate
plan: 03
subsystem: tokenizer-audit
tags: [tokenizer, qwen3-4b, phase7]
requires:
  - 07-01
provides:
  - Qwen3-4B tokenizer audit
  - dynamic native think token IDs
  - custom tag multi-subtoken evidence
affects:
  - tsc_cycle/tokenizer_check.py
  - tsc_cycle/v4_gates/phase7_tokenizer.py
key-files:
  created:
    - tsc_cycle/v4_gates/phase7_tokenizer.py
    - tests/test_v4_phase7_tokenizer_audit.py
    - artifacts/v4/phase7/tokenizer_audit.json
  modified:
    - tsc_cycle/tokenizer_check.py
key-decisions:
  - Tokenizer audit loads `Qwen/Qwen3-4B-Thinking-2507` by default and rejects Qwen3.5 model IDs.
  - Unit tests use fake tokenizer injection; live tokenizer loading only happens in the CLI smoke.
requirements-completed:
  - TAG-01
  - TAG-03
  - TAG-04
duration: 0 min
completed: 2026-05-10
---

# Phase 07 Plan 03: Tokenizer Audit Summary

Added a Qwen3-4B tokenizer audit gate that proves the corrected custom protocol tags split into multiple sub-tokens and records native `<think>`/`</think>` token IDs dynamically.

## What Changed

- Updated `tsc_cycle/tokenizer_check.py` documentation to reference v4/Qwen3-4B dynamic ID derivation.
- Added `tsc_cycle/v4_gates/phase7_tokenizer.py` with fake-tokenizer injectable evaluation and CLI output.
- Added `tests/test_v4_phase7_tokenizer_audit.py` for payload contract, no hardcoded native IDs, model lock, and frozen-root output guard.
- Generated `artifacts/v4/phase7/tokenizer_audit.json` using the live Qwen3-4B tokenizer.

## Verification

- `PYTHONPATH=/home/samuel/TSC_CYCLE /home/samuel/TSC_CYCLE/.venv/bin/python -m pytest -q tests/test_v4_phase7_tokenizer_audit.py tests/test_tokenizer_check.py` — passed, 11 tests.
- `PYTHONPATH=/home/samuel/TSC_CYCLE /home/samuel/TSC_CYCLE/.venv/bin/python -m tsc_cycle.v4_gates.phase7_tokenizer --out /home/samuel/TSC_CYCLE/artifacts/v4/phase7/tokenizer_audit.json` — passed with `ok: true`.

## Tokenizer Evidence

- `<start_working_out>` → 5 token IDs.
- `</end_working_out>` → 5 token IDs.
- `<SOLUTION>` → 3 token IDs.
- `</SOLUTION>` → 4 token IDs.
- Native `<think>` / `</think>` token IDs were dynamically recorded as 151667 / 151668.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- HF Hub emitted an unauthenticated request warning while loading the tokenizer; this did not affect the audit result.

## Self-Check: PASSED

- All custom tags satisfy the `min_custom_subtokens >= 3` gate.
- Native think IDs are recorded dynamically and `chat_template_used` is false.
- `tokenizer_audit.json` is outside the frozen v1 baseline root.
