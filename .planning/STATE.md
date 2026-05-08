---
gsd_state_version: 1.0
milestone: v2.0
milestone_name: 强化版
status: executing
last_updated: "2026-05-08T05:20:22.777Z"
last_activity: 2026-05-08
progress:
  total_phases: 4
  completed_phases: 0
  total_plans: 1
  completed_plans: 0
  percent: 0
---

# TSC-CYCLE State

**Last Activity:** 2026-05-08
**Current Milestone:** v2.0 强化版
**Status:** Ready to execute

## Project Reference

See: `.planning/PROJECT.md` (updated 2026-05-08)

**Core value:** 学生模型在 OOD 上仍满足硬约束，并在数值决策上接近 GPT-5.5 high 教师。
**Current focus:** Phase 7 — 标签协议全链路迁移

## Current Position

Phase: 7 — 标签协议全链路迁移
Plan: —
Status: Ready to execute
Last activity: 2026-05-08 -- Phase 07 planning complete

## Phase Status

| Phase | Status | Notes |
|---|---|---|
| 7. 标签协议全链路迁移 | ○ pending | 全链路改用 `<end_working_out>` 并拒绝旧标签 |
| 8. 10K 混合数据扩容与教师标注 | ○ pending | 同分布 + OOD/边界 + v1.0 错误/高 MAE targeted 样本 |
| 9. 扩容数据 QLoRA 重训与 GGUF 导出 | ○ pending | 重训 Qwen3-4B-Thinking，导出 HF fp16 / GGUF fp16 / q4_K_M |
| 10. v2.0 对比评测与部署门禁 | ○ pending | 三项指标严格高于 v1.0 baseline 后 GO |

## Baseline to Beat

- v1.0 q4_K_M OOD hard-constraint lint: 98.7%
- v1.0 HF bf16 OOD hard-constraint lint: 99.3%
- v1.0 teacher MAE delta: +0.18s
- v2.0 must strictly improve q4_K_M OOD hard constraints, teacher MAE, and reasoning format stability.

## Final v1.0 Artifact

**Path:** `runs/20260507T032419Z/gguf/model.q4_K_M.gguf`
