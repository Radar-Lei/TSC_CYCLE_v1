---
phase: 01-tokenizer-llama-cpp
plan: "04"
subsystem: v3-memory-budget-gate
status: complete
tags: [v3, memory, qlora, dgx-spark, qwen3.5-9b]
key-files:
  created:
    - artifacts/v3/phase1/memory_budget.json
    - artifacts/v3/phase1/train_100step.json
  modified:
    - tsc_cycle/v3_gates/memory_budget_v3.py
    - tests/test_v3_memory_budget.py
    - scripts/dgx_spark/run_safe.sh
    - tests/test_run_safe_script.py
metrics:
  selected_max_seq: 2048
  train_100step_peak_reserved_gb: 37.518
  train_100step_steps: 100
---

# Plan 01-04 Summary: Qwen3.5-9B Memory Budget Gate

## Outcome

Implemented and verified the Qwen3.5-9B QLoRA memory budget gate under `scripts/dgx_spark/run_safe.sh 100G`.

Final selected `max_seq_length`: **2048**.

## Evidence

| Candidate | Step-1 status | Peak reserved GB | 100-step status |
|---:|---|---:|---|
| 1536 | ok | 29.275 | not needed after 2048 passed |
| 2048 | ok | 38.410 | ok |
| 2560 | ok | 78.205 | oom_kill |
| 3072 | oom_kill | n/a | n/a |
| 4096 | oom_kill | n/a | n/a |

Artifacts:

- `artifacts/v3/phase1/memory_budget.json`
- `artifacts/v3/phase1/train_100step.json`
- diagnostic probes retained under `artifacts/v3/phase1/*seq*_step1.json` and `artifacts/v3/phase1/train_steps_seq2048_diag.jsonl`

## Implementation Notes

- `memory_budget_v3.py` loads Qwen3.5-9B in 4-bit NF4 with SDPA, `use_reentrant=False`, LoRA `r=64`, `lora_alpha=64`, `lora_dropout=0.0`, and `target_modules="all-linear"`.
- The dry-run optimizer now receives only `requires_grad=True` LoRA parameters. This avoids optimizer state allocation for frozen base weights.
- The training probe runs CUDA cleanup after each step to avoid accumulating reserved-memory pressure during long dry-runs.
- `run_safe.sh` now fails fast when non-interactive sudo for `/usr/bin/systemd-run` is unavailable and explicitly refuses password passing via stdin/env/arguments.

## Verification

Commands run:

```bash
bash -n scripts/dgx_spark/run_safe.sh
/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest tests/test_run_safe_script.py tests/test_v3_memory_budget.py -q
/home/samuel/TSC_CYCLE/.venv/bin/python -m py_compile tsc_cycle/v3_gates/memory_budget_v3.py
scripts/dgx_spark/run_safe.sh 100G -- /home/samuel/TSC_CYCLE/.venv/bin/python -m tsc_cycle.v3_gates.memory_budget_v3 --model Qwen/Qwen3.5-9B --seq 2048 --steps 100 --out artifacts/v3/phase1/train_100step.json
```

Latest automated verification: 7 tests passed.

## Deviations

- The original in-process all-candidate sweep was killed by systemd OOM before Python could write JSON. The final `memory_budget.json` therefore aggregates isolated per-sequence `run_safe` probes plus journal evidence for OOM-killed candidates.
- Step-1 memory alone selected 2560, but 2560 failed the required 100-step dry-run. The final Phase 1 training candidate is 2048 because it is the largest candidate that satisfies both the step-1 memory criterion and the 100-step dry-run gate.

## Self-Check: PASSED

- All five required sequence candidates were physically attempted.
- The selected max sequence is backed by a successful 100-step dry-run under `run_safe 100G`.
- OOM candidates are recorded as measured failures, not extrapolated omissions.
