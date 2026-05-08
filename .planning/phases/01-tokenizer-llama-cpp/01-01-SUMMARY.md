---
phase: 01-tokenizer-llama-cpp
plan: "01"
subsystem: infra
tags: [dgx-spark, qwen3.5, bitsandbytes, systemd-run, pytest]

requires: []
provides:
  - Qwen3.5 causal-LM NF4+SDPA environment smoke gate
  - run_safe 100G MemoryMax/MemorySwapMax=0 scope evidence gate
  - vLLM-optional DGX environment verifier and no-download unit coverage
affects: [phase-1-tokenizer-llama-cpp, env-gates, memory-gates]

tech-stack:
  added: []
  patterns:
    - Fail-fast Python gate modules write JSON evidence before nonzero exit
    - Qwen3.5 model identity is verified via class/config and vision namespace scan

key-files:
  created:
    - tsc_cycle/v3_gates/__init__.py
    - tsc_cycle/v3_gates/env_smoke_v3.py
    - tsc_cycle/v3_gates/run_safe_scope_check_v3.py
    - tests/test_v3_env_gate.py
  modified:
    - scripts/dgx_spark/verify.py

key-decisions:
  - "Missing vLLM remains warning-only because project constraints say vLLM is unavailable on this host."
  - "run_safe scope gate records sudo/systemd evidence but never changes host swap state."

patterns-established:
  - "Gate CLIs expose build_parser() so parser defaults can be tested without GPU/model downloads."
  - "Runtime gates emit failure artifacts as well as success artifacts."

requirements-completed: [ENV-01, ENV-03, MEM-03]

duration: 3 min 51 sec
completed: 2026-05-08
---

# Phase 01 Plan 01: Qwen3.5 Environment Gate Summary

**Qwen3.5 causal-LM NF4+SDPA smoke gates with run_safe 100G scope evidence and vLLM-optional DGX verifier.**

## Performance

- **Duration:** 3 min 51 sec
- **Started:** 2026-05-08T10:42:12Z
- **Completed:** 2026-05-08T10:46:03Z
- **Tasks:** 3
- **Files modified:** 5

## Accomplishments

- Added `env_smoke_v3.py` to load `Qwen/Qwen3.5-9B` via `AutoModelForCausalLM` with NF4, bf16, SDPA, strict Qwen3.5 causal-LM assertions, no-vision parameter scan, and JSON artifact output.
- Added `run_safe_scope_check_v3.py` to prove swap-disabled state and `MemoryMax=100G` / `MemorySwapMax=0` systemd scope evidence without silently running `swapoff`.
- Updated DGX environment verification so required packages stay hard failures while `deepspeed` and `vllm` are optional warnings.
- Added no-download pytest coverage for parser defaults, Qwen3.5 causal-LM acceptance/rejection, vision namespace counting, and memory scope helper parsing.

## Task Commits

Each task was committed atomically:

1. **Task 01-01: Implement Qwen3.5 causal-LM environment smoke gate** - `f1cf058` (feat)
2. **Task 01-02: Implement run_safe scope and swap artifact gate** - `8708987` (feat)
3. **Task 01-03: Update environment verifier and unit coverage** - `833d65c` (test)

## Files Created/Modified

- `tsc_cycle/v3_gates/__init__.py` - Declares the v3 gate package.
- `tsc_cycle/v3_gates/env_smoke_v3.py` - Qwen3.5 causal-LM model load and forward-pass evidence gate.
- `tsc_cycle/v3_gates/run_safe_scope_check_v3.py` - swap/systemd memory-scope evidence gate.
- `scripts/dgx_spark/verify.py` - Separates required package checks from optional `deepspeed`/`vllm` checks.
- `tests/test_v3_env_gate.py` - No-download unit coverage for Phase 1 env gate helpers.

## Decisions Made

- Missing `vllm` is not a hard failure because project instructions explicitly say this host cannot currently use vLLM.
- The swap gate is read-only with respect to host swap state; it fails with a user-approval message instead of invoking `sudo swapoff -a`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Full run_safe artifact command hit sudo password gate**
- **Found during:** Plan-level verification
- **Issue:** `scripts/dgx_spark/run_safe.sh 100G -- ...run_safe_scope_check_v3...` requires sudo and the non-interactive executor cannot provide a password.
- **Fix:** Treated this as an execution-environment gate, not a code failure; verified the module with py_compile and unit tests, and left the replayable command intact for an environment where sudo credentials are available.
- **Files modified:** None
- **Verification:** `/home/samuel/TSC_CYCLE/.venv/bin/python -m py_compile ...` and pytest passed.
- **Committed in:** N/A (no code change)

---

**Total deviations:** 1 blocking environment gate documented
**Impact on plan:** Source gates and tests are complete; runtime JSON artifacts require sudo-capable execution by the orchestrator or host session.

## Issues Encountered

- The planned `run_safe.sh` empty-run evidence command failed before Python execution because sudo needed a terminal/password. No artifact file was produced in this worktree.
- The heavy `env_smoke_v3.py --model Qwen/Qwen3.5-9B` GPU/download command was not run after the sudo gate failed; the module is implemented and syntax-checked for later sudo-capable Phase 1 gate execution.

## Verification

- PASS: `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest tests/test_v3_env_gate.py` — 9 passed, 2 warnings.
- PASS: `/home/samuel/TSC_CYCLE/.venv/bin/python -m py_compile tsc_cycle/v3_gates/env_smoke_v3.py tsc_cycle/v3_gates/run_safe_scope_check_v3.py scripts/dgx_spark/verify.py`.
- BLOCKED: `scripts/dgx_spark/run_safe.sh 100G -- /home/samuel/TSC_CYCLE/.venv/bin/python -m tsc_cycle.v3_gates.run_safe_scope_check_v3 --out artifacts/v3/phase1/run_safe_scope.json` — sudo password required in non-interactive worktree.
- NOT RUN: `scripts/dgx_spark/run_safe.sh 100G -- /home/samuel/TSC_CYCLE/.venv/bin/python -m tsc_cycle.v3_gates.env_smoke_v3 --model Qwen/Qwen3.5-9B --out artifacts/v3/phase1/env_smoke.json` — deferred behind sudo-capable gate execution.

## User Setup Required

None - no external service configuration required. Runtime gate execution needs a sudo-capable session for `systemd-run`.

## Known Stubs

None. Empty lists/dicts in gate code are initialized accumulators or JSON defaults, not UI/data-source stubs.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: model-loader | `tsc_cycle/v3_gates/env_smoke_v3.py` | New CLI loads a user-supplied model id; mitigated by Qwen3.5 causal-LM identity assertion and vision/visual namespace rejection. |
| threat_flag: host-memory-state | `tsc_cycle/v3_gates/run_safe_scope_check_v3.py` | New CLI inspects host swap/systemd state; mitigated by read-only swap check and required run_safe memory-scope evidence. |

## Next Phase Readiness

- Ready for the remaining Phase 1 wave-1 plans to build tokenizer and llama.cpp gates.
- Orchestrator or host session should rerun the two plan-level `run_safe.sh` commands with sudo privileges to produce `artifacts/v3/phase1/run_safe_scope.json` and `artifacts/v3/phase1/env_smoke.json`.

## Self-Check: PASSED

- Created files exist: `tsc_cycle/v3_gates/__init__.py`, `tsc_cycle/v3_gates/env_smoke_v3.py`, `tsc_cycle/v3_gates/run_safe_scope_check_v3.py`, `tests/test_v3_env_gate.py`.
- Modified verifier exists: `scripts/dgx_spark/verify.py`.
- Task commits exist: `f1cf058`, `8708987`, `833d65c`.

---
*Phase: 01-tokenizer-llama-cpp*
*Completed: 2026-05-08*
