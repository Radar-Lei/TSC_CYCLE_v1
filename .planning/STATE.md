---
gsd_state_version: 1.0
milestone: v4.0
milestone_name: 4B 回退 + 扩展数据重训 + 标签协议修复
status: executing
last_updated: "2026-05-09T17:50:34.393Z"
last_activity: 2026-05-09
progress:
  total_phases: 5
  completed_phases: 1
  total_plans: 8
  completed_plans: 6
  percent: 75
---

# TSC-CYCLE State

**Last Activity:** 2026-05-09
**Current Milestone:** v4.0 4B 回退 + 扩展数据重训 + 标签协议修复
**Status:** Ready to execute

## Project Reference

See: `.planning/PROJECT.md` (updated 2026-05-10)

**Core value:** 学生模型在 OOD 上仍满足硬约束，并在数值决策上接近 GPT-5.5 high 教师 — 不过拟合到 reality.log。
**Current focus:** Phase 08 — v3 扩展数据 → 4B dataset rebuild

## Current Position

Phase: 08 (v3 扩展数据 → 4B dataset rebuild) — EXECUTING
Plan: 3 of 4
Status: Ready to execute
Progress: [████████░░] 75%
Last activity: 2026-05-09

## Phase Status

| Phase | Status | Notes |
|---|---|---|
| 7. 4B baseline/label protocol gate | ✓ complete | `artifacts/v4/phase7/phase7_gate_report.json` passed with `next_phase_allowed: true` |
| 8. v3 扩展数据 → 4B dataset rebuild | ○ next | Reuse v1 valid + v3 lint-pass data; rebuild split/tokenized artifacts with Qwen3-4B tokenizer |
| 9. 4B QLoRA retrain | ○ pending | v1 verified 4B QLoRA path; raw-text protocol; isolated v4 run root |
| 10. merge + GGUF export | ○ pending | Merge adapter; export GGUF fp16 + q4_K_M; verify three-precision protocol smoke |
| 11. eval matrix + decision | ○ pending | Compare v4 HF/q4 against v1 q4 baseline; produce GO/NO-GO/user decision |

## Baseline to Beat (v1.0)

- v1.0 q4_K_M OOD hard-constraint lint: **98.7%**
- v1.0 HF bf16 OOD hard-constraint lint: **99.3%**
- v1.0 q4_K_M vs HF bf16 ratio: **0.9933**
- v1.0 teacher MAE delta: **+0.18s**
- v4.0 decision gate: `v4 q4_K_M hard_constraint_pass ≥ 98%` ∧ `v4 q4_K_M vs v4 HF ≥ 0.95` ∧ `v4 q4_K_M vs v1 q4_K_M not significantly worse`

## Frozen v1.0 Artifact (read-only reference in v4.0)

**Path:** `runs/20260507T032419Z/gguf/model.q4_K_M.gguf` (2.4 GB)
**Eval gen_cache:** `runs/20260507T032419Z/eval/gen_cache/gguf_q4km/`
**Constraint:** v4.0 全 phase 零写入；Phase 7 必须证明只读引用有效。

## Accumulated Context

### Key Decisions

- v1.0 shipped (2026-05-07): 4B QLoRA → GGUF q4_K_M 端到端闭环，OOD hard-constraint lint 98.7%，部署裁决 GO。
- v2.0 abandoned (2026-05-08): 标签迁移方向需要纠正；本项目思考结束标签必须是 `</end_working_out>`，不是 `<end_working_out>`。
- v3.0 stopped (2026-05-10): Phase 1-3 完成并产出扩展数据与 Qwen3.5 split/tokenized artifacts，但 Qwen3.5-9B 本机训练太慢，用户决定停止 9B 路线。
- v4.0 route: 回到 v1 已验证 `Qwen/Qwen3-4B-Thinking-2507`，复用 v3 新增 lint-pass 数据，但必须用 Qwen3-4B tokenizer 重新 rebuild dataset/split/tokenized artifacts。
- 训练栈继续沿用 `/dgx-spark-training` 与 `/home/samuel/dgx-spark-setup/.venv`；不引入新 PyTorch、Unsloth、Axolotl 或 vLLM。
- 全链路协议固定为 `<start_working_out>...</end_working_out><SOLUTION>...</SOLUTION>`；禁止原生 `<think>`/`</think>`。
- Phase 8 RED contracts require explicit v1 valid + v3 new lint-pass sources, v4-isolated outputs, Qwen3-4B raw-text tokenization, and aggregate report gating before Phase 9.

### Active Todos

- Execute Phase 8 Plan 02 — implement v4 source merge, deterministic split/tokenization, and rebuild report against RED contracts.

### Blockers

- None — v4.0 roadmap 已创建；下一步是 Phase 7 planning。

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 260509-x43 | 修复 Phase 4 dry-run TrainingArguments packing 过滤 | 2026-05-09 | 67ae7a7 | [260509-x43-phase-4-dry-run-trainingarguments-init-p](./quick/260509-x43-phase-4-dry-run-trainingarguments-init-p/) |

## Session Continuity

**Next action:** `/gsd-execute-phase 8` (continue with 08-02-PLAN.md)

**Key files:**

- `.planning/PROJECT.md`
- `.planning/REQUIREMENTS.md` (24 v4.0 REQs + traceability)
- `.planning/ROADMAP.md` (v4.0 phases 7-11)
- `.planning/milestones/v1.0-ROADMAP.md`
- `runs/20260507T032419Z/gguf/model.q4_K_M.gguf` (read-only baseline reference)
