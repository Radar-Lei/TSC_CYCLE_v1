---
phase: 20
slug: evaluation-reality-replay-handoff
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-05-19
---

# Phase 20 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | `pyproject.toml` / existing pytest discovery |
| **Quick run command** | `.venv/bin/python -m pytest tests/test_v4_phase20_evaluation_handoff.py -q` |
| **Full suite command** | `.venv/bin/python -m pytest tests/test_v4_phase20_evaluation_handoff.py tests/test_v4_phase19_training_export.py tests/test_v4_phase17_saturation_policy.py tests/test_v4_phase12_reality.py -q` |
| **Estimated runtime** | ~60-180 seconds, excluding live GGUF replay |

---

## Sampling Rate

- **After every task commit:** Run the Phase 20 focused pytest file.
- **After every plan wave:** Run the full adjacent v4 regression suite listed above.
- **Before `/gsd:verify-work`:** Full suite plus Phase 20 real report validators must be green.
- **Max feedback latency:** 180 seconds for automated unit/contract checks; live replay may run as an explicit long-running task.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 20-01-01 | 01 | 1 | EVAL-01 | T-20-01 | Teacher-MAE cannot be a blocking success gate | unit/contract | `.venv/bin/python -m pytest tests/test_v4_phase20_evaluation_handoff.py -q` | ✅ W0 | ⬜ pending |
| 20-01-02 | 01 | 1 | EVAL-01 | T-20-02 | Parse/lint/protocol/saturation failures fail closed | unit/contract | `.venv/bin/python -m pytest tests/test_v4_phase20_evaluation_handoff.py -q` | ✅ W0 | ⬜ pending |
| 20-02-01 | 02 | 2 | EVAL-02 | T-20-03 | Replay uses validated q4_K_M GGUF from Phase 19 export report | unit/contract | `.venv/bin/python -m pytest tests/test_v4_phase20_evaluation_handoff.py -q` | ✅ W0 | ⬜ pending |
| 20-02-02 | 02 | 2 | EVAL-02 | T-20-04 | Generated replay log must pass parse/lint/protocol/saturation gates | unit/contract + optional live | `.venv/bin/python -m pytest tests/test_v4_phase20_evaluation_handoff.py -q` | ✅ W0 | ⬜ pending |
| 20-03-01 | 03 | 3 | EVAL-03 | T-20-05 | v4.0 vs v4.2 comparison must reject hard-constraint regression | unit/contract | `.venv/bin/python -m pytest tests/test_v4_phase20_evaluation_handoff.py -q` | ✅ W0 | ⬜ pending |
| 20-03-02 | 03 | 3 | EVAL-03 | T-20-06 | Handoff manifest recomputes on-disk hashes and records accepted evidence only | unit/contract | `.venv/bin/python -m pytest tests/test_v4_phase20_evaluation_handoff.py -q` | ✅ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing pytest infrastructure covers the phase. The first implementation task should create `tests/test_v4_phase20_evaluation_handoff.py` with failing contract tests before adding new gates.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live q4_K_M replay runtime on DGX Spark | EVAL-02 | Full llama.cpp replay can be long-running and hardware-dependent | Run the Phase 20 replay wrapper against `runs/v4.2-4B-20260518T111519Z/gguf/model.q4_K_M.gguf`, then validate the generated report/log with the Phase 20 replay validator. |

---

## Validation Sign-Off

- [x] All tasks have automated verify or explicit live-replay verification.
- [x] Sampling continuity: no 3 consecutive tasks without automated verify.
- [x] Wave 0 covers all missing references.
- [x] No watch-mode flags.
- [x] Feedback latency target documented.
- [x] `nyquist_compliant: true` set in frontmatter.

**Approval:** approved 2026-05-19
