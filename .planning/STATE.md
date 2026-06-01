---
gsd_state_version: 1.0
milestone: v4.2
milestone_name: 饱和度-绿灯策略校准 / 教师标签重建
status: Complete
stopped_at: Phase 20.1 complete
last_updated: "2026-05-19T14:30:00.000Z"
last_activity: 2026-05-19 -- Phase 20.1 generated reality_test_v2.log and comparison report
progress:
  total_phases: 5
  completed_phases: 5
  total_plans: 10
  completed_plans: 10
  percent: 100
---

# TSC-CYCLE State

## Project Reference

See: `.planning/PROJECT.md` (updated 2026-05-18)

**Core value:** 学生模型在 OOD 上仍满足硬约束，并在数值决策上接近正确的饱和度-绿灯策略，不是过拟合旧教师标签或 reality.log。
**Current focus:** Phase 20.1 — 以新训练好的模型 replay reality.log 并对比 reality_test.log

## Current Position

Phase: 20.1
Plan: 20.1-PLAN.md
Status: Complete
Last activity: 2026-05-19 -- Phase 20.1 generated reality_test_v2.log and comparison report

Progress: [██████████] 100%

## Performance Metrics

**Velocity:**

- v4.2 plans completed: 10
- Average duration: 10 min
- Total execution time: 50 min

**By Phase:**

| Phase | Plans | Status | Completed |
|-------|-------|--------|-----------|
| 17. Audit & Saturation Policy Gate | 3/3 | Complete | 2026-05-18 |
| 18. Calibrated Dataset Rebuild | 1/1 | Complete | 2026-05-18 |
| 19. 4B QLoRA Retrain & Export | 2/2 | Complete | 2026-05-18 |
| 20. Evaluation & Reality Replay Handoff | 3/3 | Complete | 2026-05-19 |
| 20.1. reality_test_v2 replay comparison | 1/1 | Complete | 2026-05-19 |

## Accumulated Context

### Roadmap Evolution

- Phase 20.1 inserted after Phase 20: 以新训练好的模型，以/home/samuel/TSC_CYCLE/reality.log为输入，以模型输出为输出，得到reality_test_v2.log好与之前reality_test.log做对比 (URGENT)

### Decisions

Decisions are logged in PROJECT.md Key Decisions table. Recent decisions affecting current work:

- v4.2 is not related to EvoProgTSC; no Evo integration belongs in active phases.
- Final deployment system prompt / inference prompt must remain unchanged from the v4 inference protocol and must not explicitly include the saturation band rule.
- Saturation band rule is offline-only: audit, data filtering/relabeling, training validation, and evaluation gates.
- v4.2 stays on `Qwen/Qwen3-4B-Thinking-2507` and the existing DGX Spark-safe QLoRA/export stack.
- Phase 17 policy gate defaults intentionally fail current v4 dataset/replay evidence on low-saturation max-green excess, while prompt protocol evidence remains green.
- `sat_ge_1.0_allowed_max` has no max-green failure threshold; saturated max-green is allowed by the offline policy.
- [Phase 17-audit-saturation-policy-gate]: Store POLICY-03 expected prompt bytes in an independent JSON fixture instead of recomputing them from build_user_prompt at import time. — This makes byte-for-byte prompt drift detection independent of the implementation under test.
- [Phase 17-audit-saturation-policy-gate]: Accept only artifact roots whose resolved path is explicitly an artifacts/v4/phase17 subtree. — This prevents broad maintainer-supplied trust roots from authorizing writes to data or source files.
- [Phase 17-audit-saturation-policy-gate]: Select representative audit examples by deterministic per-origin coverage before filling remaining slots globally. — This keeps maintainer-facing audit output from hiding replay evidence behind dataset ordering.
- [Phase 18-calibrated-dataset-rebuild]: Use filter mode for v4.2 calibration; relabelled rows remain 0 to avoid reasoning/solution contradictions while satisfying DATA-01.
- [Phase 18-calibrated-dataset-rebuild]: Preserve Phase 8 split membership for retained rows; do not re-randomize train/val/OOD splits for v4.2.

### Pending Todos

- None.

### Blockers/Concerns

- None.

## Deferred Items

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| Deployment | External TSC endpoint integration | Out of scope for v4.2 | v4.2 start |
| Experiment | thinking on/off ablation | Deferred to later milestone | v4.2 start |
| Experiment | imatrix/q5_K_M fallback evaluation | Deferred to later milestone | v4.2 start |

## Session Continuity

Last session: 2026-05-19T00:05:00.000Z
Stopped at: Phase 19 executed
Resume file: None
Next action: Milestone audit / ship decision
