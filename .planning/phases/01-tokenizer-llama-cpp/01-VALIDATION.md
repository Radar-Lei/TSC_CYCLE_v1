---
phase: 1
slug: tokenizer-llama-cpp
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-05-08
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3 + GPU smoke/integration scripts |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest -q tests/test_prompt_builder.py tests/test_hashing.py` |
| **Full suite command** | `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest -q` |
| **Estimated runtime** | quick: <30s; GPU gates: minutes to hours depending on model load and memory sweep |

---

## Sampling Rate

- **After every task commit:** Run the relevant unit test or dry-run command for the modified gate module.
- **After every plan wave:** Run `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest -q` plus any completed gate smoke command.
- **Before `/gsd-verify-work`:** Run `scripts/run_v3_phase1_gates.sh` and require `artifacts/v3/phase1/phase1_gate_report.json` to contain `"ok": true`.
- **Max feedback latency:** non-GPU tasks <60s; GPU hard gates may exceed 60s but must write JSON artifacts for each completed sub-gate.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 1-01-01 | 01 | 1 | ENV-01, MEM-03 | T-01-paths | Records model class/config and rejects any `vision`/`visual` parameters | GPU smoke | `scripts/dgx_spark/run_safe.sh 100G -- /home/samuel/TSC_CYCLE/.venv/bin/python -m tsc_cycle.v3_gates.env_smoke_v3 --model Qwen/Qwen3.5-9B` | ❌ W0 | ⬜ pending |
| 1-02-01 | 02 | 1 | TOK-01, TOK-02, TOK-04 | T-02-tokenizer | Uses dynamic tokenizer IDs and raw protocol text; no chat_template | unit/smoke | `/home/samuel/TSC_CYCLE/.venv/bin/python -m tsc_cycle.v3_gates.tokenizer_audit_v3 --model Qwen/Qwen3.5-9B` | ❌ W0 | ⬜ pending |
| 1-03-01 | 03 | 1 | TOK-03 | T-03-subprocess | Invokes llama-tokenize with argv list and records binary provenance | integration | `/home/samuel/TSC_CYCLE/.venv/bin/python -m tsc_cycle.v3_gates.tokenizer_parity_v3 --n 100 --gguf runs/v3.0-gates/gguf_microconvert/tokenizer.gguf --require-gguf` | ❌ W0 | ⬜ pending |
| 1-04-01 | 04 | 2 | MEM-01, MEM-02 | T-04-memory | Runs all five sequence lengths under 100G cap and selects max peak<85GB | GPU integration | `scripts/dgx_spark/run_safe.sh 100G -- /home/samuel/TSC_CYCLE/.venv/bin/python -m tsc_cycle.v3_gates.memory_budget_v3 --seqs 1536 2048 2560 3072 4096 --steps 100` | ❌ W0 | ⬜ pending |
| 1-05-01 | 05 | 2 | ENV-02 | T-05-artifacts | Writes only to v3 artifacts/runs paths and fails before overwriting existing outputs | integration | `scripts/dgx_spark/run_safe.sh 100G -- /home/samuel/TSC_CYCLE/.venv/bin/python -m tsc_cycle.v3_gates.gguf_microconvert_v3` | ❌ W0 | ⬜ pending |
| 1-06-01 | 06 | 3 | ENV-01, ENV-02, ENV-03, TOK-01, TOK-02, TOK-03, TOK-04, MEM-01, MEM-02, MEM-03 | T-06-report | Aggregates all gate JSON files and aborts on first fatal failure | integration | `scripts/run_v3_phase1_gates.sh` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tsc_cycle/v3_gates/env_smoke_v3.py` — Qwen3.5 CausalLM NF4 SDPA smoke and no-vision assertion.
- [ ] `tsc_cycle/v3_gates/tokenizer_audit_v3.py` — custom tag split, native think ID JSON, no chat_template raw protocol check.
- [ ] `tsc_cycle/v3_gates/tokenizer_parity_v3.py` — 100-prompt HF encode ↔ llama-tokenize parity.
- [ ] `tsc_cycle/v3_gates/memory_budget_v3.py` — five-candidate memory sweep and 100-step dry-run.
- [ ] `tsc_cycle/v3_gates/gguf_microconvert_v3.py` — dummy LoRA → GGUF → Q4_K_M → llama-cli 5-token smoke.
- [ ] `tsc_cycle/v3_gates/phase1_report.py` — pass/fail aggregation into `phase1_gate_report.json`.
- [ ] `scripts/run_v3_phase1_gates.sh` — ordered fail-fast orchestrator.
- [ ] Tests for dynamic think IDs, no v1.0 hardcoded native IDs in v3 path, and raw-text/no-chat-template assembly.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| If swap is enabled, disabling it may require sudo confirmation | ENV-03 | `sudo swapoff -a` affects machine state and may require user approval | Check `swapon --show`; if non-empty, ask user before running swapoff; rerun `scripts/dgx_spark/run_safe.sh 100G -- /home/samuel/TSC_CYCLE/.venv/bin/python -c 'print("scope ok")'` |
| If EvoProgTSC llama.cpp lacks `llama-tokenize`, building that target may require local toolchain repair | TOK-03 | Build failures can depend on local CMake state | First try the EvoProgTSC tree; if unavailable, record fallback `/home/samuel/llama.cpp/build/bin/llama-tokenize` provenance in parity JSON |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency bounded for non-GPU checks; GPU gates write incremental artifacts
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-05-08
