---
gsd_state_version: 1.0
milestone: v4.0
milestone_name: 4B 回退 + 扩展数据重训 + 标签协议修复
status: completed
last_updated: "2026-05-11T14:36:49.152Z"
last_activity: 2026-05-11
progress:
  total_phases: 6
  completed_phases: 6
  total_plans: 23
  completed_plans: 23
  percent: 100
---

# TSC-CYCLE State

**Last Activity:** 2026-05-11
**Current Milestone:** v4.0 4B 回退 + 扩展数据重训 + 标签协议修复
**Status:** v4.0 milestone complete

## Project Reference

See: `.planning/PROJECT.md` (updated 2026-05-11)

**Core value:** 学生模型在 OOD 上仍满足硬约束，并在数值决策上接近 GPT-5.5 high 教师 — 不过拟合到 reality.log。
**Current focus:** v4.0 shipped; awaiting next milestone definition or deployment handoff.

## Current Position

Phase: Milestone v4.0 complete
Plan: —
Status: Awaiting next milestone
Last activity: 2026-05-11 — Milestone v4.0 completed and archived

## Phase Status

| Phase | Status | Notes |
|---|---|---|
| 7. 4B baseline/label protocol gate | ✓ complete | `artifacts/v4/phase7/phase7_gate_report.json` passed with `next_phase_allowed: true` |
| 8. v3 扩展数据 → 4B dataset rebuild | ✓ complete | DATA4B-01..05 covered; `artifacts/v4/phase8/phase8_gate_report.json` passed with `next_phase_allowed: true` |
| 9. 4B QLoRA retrain | ✓ complete | `runs/v4.0-4B-20260509T184844Z/phase9_sft_report.json` passed with `next_phase_allowed: true` |
| 10. merge + GGUF export | ✓ complete | `runs/v4.0-4B-20260509T184844Z/phase10_gguf_report.json` passed with `next_phase_allowed: true` |
| 11. eval matrix + decision | ✓ complete | `artifacts/v4/phase11/phase11_gate_report.json` passed with verdict `GO`, `next_phase_allowed: true`; recommended artifact `runs/v4.0-4B-20260509T184844Z/gguf/model.q4_K_M.gguf` |
| 12. reality.log → reality_test.log replay | ✓ complete | `artifacts/v4/phase12/phase12_report.json` passed with 426/426 parse/lint/protocol counts; human spot-check approved |

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
- DATA4B-05 uses generated Phase 8 JSON artifacts as the source of truth for hashes, counts, truncation evidence, and native-think safety.
- The final Phase 8 wrapper run is the authority for Phase 9 readiness; `phase8_gate_report.json` is green with `next_phase_allowed: true` only after dataset card evidence exists.

### Roadmap Evolution

- Phase 12 added: 需要用最新训练好的模型，以 /home/samuel/TSC_CYCLE/reality.log 的输入为输入（忽略其输出，以我们自己的模型输出为输出，要包括思考过程），构成一个reality_test.log

### Active Todos

- None for v4.0 milestone execution; Phase 12 final `reality_test.log` replay is complete and human-approved.

### Blockers

- None — v4.0 milestone execution complete.

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 260509-x43 | 修复 Phase 4 dry-run TrainingArguments packing 过滤 | 2026-05-09 | 67ae7a7 | [260509-x43-phase-4-dry-run-trainingarguments-init-p](./quick/260509-x43-phase-4-dry-run-trainingarguments-init-p/) |

## Session Continuity

**Next action:** Optional final milestone audit/cleanup or prepare deployment handoff for `/home/samuel/TSC_CYCLE/runs/v4.0-4B-20260509T184844Z/gguf/model.q4_K_M.gguf` and `/home/samuel/TSC_CYCLE/reality_test.log`.

**Key files:**

- `.planning/PROJECT.md`
- `.planning/REQUIREMENTS.md` (current milestone requirements; fresh file should be created by `/gsd-new-milestone`)
- `.planning/ROADMAP.md` (collapsed milestone overview)
- `.planning/milestones/v1.0-ROADMAP.md`
- `.planning/milestones/v4.0-ROADMAP.md`
- `.planning/milestones/v4.0-REQUIREMENTS.md`
- `runs/20260507T032419Z/gguf/model.q4_K_M.gguf` (read-only baseline reference)
- [FLAG] Phase 10 smoke MAE q4_K_M vs HF = 3.09s (>3.0s); Phase 11 should consider imatrix/q5_K_M sensitivity if eval matrix shows regression.
- `reality_test.log` (Phase 12 final replay output, 426/426 parse/lint/protocol green, human-approved)

## Operator Next Steps

- Start the next milestone with /gsd-new-milestone
