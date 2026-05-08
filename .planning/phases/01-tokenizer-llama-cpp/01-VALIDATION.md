---
phase: 01
slug: tokenizer-llama-cpp
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-05-08
---

# Phase 01 — Validation Strategy

> Per-phase validation contract for Phase 1 hard gates.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + Python CLI artifact checks |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `.venv/bin/python -m pytest tests/test_prompt_builder.py tests/test_hashing.py` |
| **Full suite command** | `.venv/bin/python -m pytest` |
| **Estimated runtime** | ~30 seconds for unit suite; GPU gates are manual/long-running commands |

---

## Sampling Rate

- **After every task commit:** Run the quick pytest command when the task changes importable Python modules.
- **After every plan wave:** Run `.venv/bin/python -m pytest` plus any CLI smoke command introduced in that wave.
- **Before verification:** All artifact JSON files listed below must exist and report pass/fatal=false.
- **Max feedback latency:** Unit checks <60s; GPU gates are explicitly long-running manual/autonomous commands under `run_safe.sh`.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 01-01-01 | 01 | 1 | ENV-01/MEM-03 | T-01 | No unsafe model class; no vision params | CLI smoke | `scripts/dgx_spark/run_safe.sh 100G -- python -m tsc_cycle.v3_gates.env_smoke_v3 --model Qwen/Qwen3.5-9B --out artifacts/v3/phase1/env_smoke.json` | ❌ W0 | ⬜ pending |
| 01-02-01 | 02 | 1 | TOK-01/TOK-02/TOK-04 | T-02 | No native think leakage; dynamic IDs | CLI + unit | `python -m tsc_cycle.v3_gates.tokenizer_audit_v3 --model Qwen/Qwen3.5-9B --out artifacts/v3/phase1/tokenizer_audit.json` | ❌ W0 | ⬜ pending |
| 01-03-01 | 03 | 2 | TOK-03 | T-03 | Tokenizer parity exact match | CLI artifact | `python -m tsc_cycle.v3_gates.tokenizer_parity_v3 --model Qwen/Qwen3.5-9B --out artifacts/v3/phase1/tokenizer_parity.json` | ❌ W0 | ⬜ pending |
| 01-04-01 | 04 | 2 | MEM-01/MEM-02/ENV-03 | T-04 | Memory cap prevents unified-memory runaway | GPU profile | `scripts/dgx_spark/run_safe.sh 100G -- python -m tsc_cycle.v3_gates.memory_budget_v3 --model Qwen/Qwen3.5-9B --seqs 1536 2048 2560 3072 4096 --out artifacts/v3/phase1/memory_budget.json` | ❌ W0 | ⬜ pending |
| 01-05-01 | 05 | 3 | ENV-02 | T-05 | llama.cpp chain fails closed | CLI artifact | `scripts/dgx_spark/run_safe.sh 100G -- python -m tsc_cycle.v3_gates.gguf_microconvert_v3 --model Qwen/Qwen3.5-9B --out runs/v3.0-gates/gguf_microconvert` | ❌ W0 | ⬜ pending |

---

## Wave 0 Requirements

- [ ] `tsc_cycle/v3_gates/` package exists with importable CLI modules.
- [ ] `artifacts/v3/phase1/` output directory is created by scripts, not committed unless artifact policy permits.
- [ ] Existing `pytest` suite remains green after tokenizer/check refactors.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Swap disabled before long GPU gates | ENV-03/MEM-02 | May require sudo/system policy and should not be silently changed | Run `swapon --show`; if non-empty, user must approve `sudo swapoff -a` before long training dry-runs. |
| 100-step Qwen3.5-9B dry-run | MEM-02 | Long GPU job; may run for many minutes and consume local GPU exclusively | Use selected max_seq from `memory_budget.json` and run the documented `run_safe.sh 100G` command. |

---

## Validation Sign-Off

- [x] All tasks have automated CLI or explicit manual GPU verification.
- [x] Sampling continuity: no 3 consecutive implementation tasks without an automated verify command.
- [x] Wave 0 covers missing validation infrastructure.
- [x] No watch-mode flags.
- [x] Unit feedback latency <60s; GPU gates explicitly classified as long-running.
- [x] `nyquist_compliant: true` set in frontmatter.

**Approval:** approved 2026-05-08
