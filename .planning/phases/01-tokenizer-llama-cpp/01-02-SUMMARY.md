---
phase: 01-tokenizer-llama-cpp
plan: "02"
subsystem: tokenizer-dataset-gates
tags: [qwen3.5, tokenizer, dataset, raw-text, tdd, pytest]

requires:
  - phase: 01-tokenizer-llama-cpp
    provides: Phase 1 planning context and Qwen3.5 tokenizer gate requirements
provides:
  - Dynamic tokenizer helpers for Qwen3.5 native think ID discovery
  - Raw-text SFT dataset assembly metadata and native-ID leakage rejection
  - Qwen3.5 tokenizer audit CLI plus runtime tokenizer_audit.json evidence
affects: [phase-1-tokenizer-parity, phase-3-dataset-rebuild, phase-4-sft]

tech-stack:
  added: []
  patterns:
    - tokenizer-derived native think IDs instead of hardcoded v1.0 constants
    - prompt_builder raw text assembly instead of tokenizer chat_template
    - fail-closed JSON gate artifacts under artifacts/v3/phase1

key-files:
  created:
    - tests/test_tokenizer_check.py
    - tests/test_v3_dataset_raw_text.py
    - tsc_cycle/v3_gates/__init__.py
    - tsc_cycle/v3_gates/tokenizer_audit_v3.py
    - artifacts/v3/phase1/tokenizer_audit.json
  modified:
    - tsc_cycle/tokenizer_check.py
    - tsc_cycle/student/dataset.py

key-decisions:
  - "Native <think> and </think> IDs are discovered from the active tokenizer and no longer validated against Qwen3-4B constants."
  - "V3 SFT dataset assembly exposes raw-text metadata and keeps chat_template_used=false as real wiring evidence for the audit gate."

patterns-established:
  - "Tokenizer gates call check_tokenizer(..., min_custom_subtokens=3) and record native_think encodings verbatim."
  - "Dataset tokenization calls native_think_token_ids(tokenizer) and passes the resulting set into assert_no_native_think_in_ids."

requirements-completed: [TOK-01, TOK-02, TOK-04]

duration: 4min
completed: 2026-05-08
---

# Phase 01 Plan 02: Dynamic Tokenizer Audit + Raw-Text Dataset Wiring Summary

**Qwen3.5 tokenizer safety gate with dynamic native think IDs, raw-text SFT assembly proof, and committed audit evidence**

## Performance

- **Duration:** 4 min
- **Started:** 2026-05-08T10:42:07Z
- **Completed:** 2026-05-08T10:46:05Z
- **Tasks:** 3 completed
- **Files modified:** 7

## Accomplishments

- Refactored tokenizer safety checks to require custom tags to tokenize into at least 3 IDs and to derive native `<think>` / `</think>` IDs dynamically.
- Wired dataset tokenization to raw `build_user_prompt` / `build_full_assistant` strings and dynamic native-ID leakage rejection.
- Added `tsc_cycle.v3_gates.tokenizer_audit_v3` and committed `artifacts/v3/phase1/tokenizer_audit.json` showing Qwen3.5 native IDs `[248068]` and `[248069]`, all custom tag lengths ≥3, and `chat_template_used=false`.

## Task Commits

Each task was committed atomically:

1. **Task 02-01 RED: Dynamic tokenizer check tests** - `ad6e059` (test)
2. **Task 02-01 GREEN: Dynamic tokenizer helpers** - `325d9d1` (feat)
3. **Task 02-02 RED: Raw-text dataset tests** - `8bed99a` (test)
4. **Task 02-02 GREEN: Dataset raw-text/native-ID wiring** - `241d261` (feat)
5. **Task 02-03 GREEN: Qwen3.5 tokenizer audit CLI** - `e0f8549` (feat)
6. **Plan artifact: Qwen3.5 tokenizer audit JSON** - `bede31c` (test)

**Plan metadata:** committed separately after this summary.

_Note: TDD tasks produced RED then GREEN commits. Task 02-03 was a CLI glue/gate task; py_compile and acceptance checks passed._

## Files Created/Modified

- `tsc_cycle/tokenizer_check.py` - Dynamic tokenizer invariants, native think lookup helpers, and required caller-provided native-ID rejection.
- `tsc_cycle/student/dataset.py` - Raw-text dataset wiring metadata and dynamic native think ID leakage check.
- `tsc_cycle/v3_gates/tokenizer_audit_v3.py` - Qwen3.5 tokenizer audit CLI writing the required JSON schema and failing closed.
- `tsc_cycle/v3_gates/__init__.py` - v3 gates package marker.
- `tests/test_tokenizer_check.py` - Fake-tokenizer coverage for ≥3 custom tag minimum and dynamic native IDs.
- `tests/test_v3_dataset_raw_text.py` - Fake-tokenizer coverage proving no `apply_chat_template` call and native `<think>` rejection.
- `artifacts/v3/phase1/tokenizer_audit.json` - Runtime evidence for TOK-01/TOK-02/TOK-04.

## Verification

- `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest tests/test_tokenizer_check.py` — passed, 5 tests.
- `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest tests/test_v3_dataset_raw_text.py` — passed, 3 tests.
- `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest tests/test_tokenizer_check.py tests/test_v3_dataset_raw_text.py` — passed, 8 tests.
- `/home/samuel/TSC_CYCLE/.venv/bin/python -m py_compile tsc_cycle/tokenizer_check.py tsc_cycle/student/dataset.py tsc_cycle/v3_gates/tokenizer_audit_v3.py` — passed.
- `/home/samuel/TSC_CYCLE/.venv/bin/python -m tsc_cycle.v3_gates.tokenizer_audit_v3 --model Qwen/Qwen3.5-9B --out artifacts/v3/phase1/tokenizer_audit.json` — passed.

## Decisions Made

- Dynamic native think IDs are the only validation truth for v3.0; v1.0 constants are not exported or used by dataset checks.
- Dataset audit evidence comes from `dataset_wiring_metadata()` rather than a bare unsupported constant in the CLI.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## Known Stubs

None - stub scan only found local empty-list accumulators used as implementation details, not UI/data placeholders.

## Threat Flags

None - changes stay within planned tokenizer output and dataset assembly trust boundaries; no new network endpoint, auth path, file access trust boundary, or schema trust boundary was introduced.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Ready for Phase 1 tokenizer parity work: `tokenizer_audit.json` now records Qwen3.5-derived token IDs and custom tag encodings.
- Ready for later dataset rebuild: SFT tokenization now has a raw-text path and dynamic native-ID rejection that can be reused with Qwen3.5 tokenizer.

## Self-Check: PASSED

- Found files: `tsc_cycle/tokenizer_check.py`, `tsc_cycle/student/dataset.py`, `tsc_cycle/v3_gates/tokenizer_audit_v3.py`, `tests/test_tokenizer_check.py`, `tests/test_v3_dataset_raw_text.py`, `artifacts/v3/phase1/tokenizer_audit.json`.
- Found commits: `ad6e059`, `325d9d1`, `8bed99a`, `241d261`, `e0f8549`, `bede31c`.
- Audit artifact assertion passed: all custom tag lengths are ≥3, dynamic native IDs are present, and `chat_template_used` is false.

---
*Phase: 01-tokenizer-llama-cpp*
*Completed: 2026-05-08*
