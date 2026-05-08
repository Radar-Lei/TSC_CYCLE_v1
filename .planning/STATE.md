---
gsd_state_version: 1.0
milestone: v3.0
milestone_name: 9B 基座切换
status: executing
last_updated: "2026-05-08T15:16:07.327Z"
last_activity: 2026-05-08
progress:
  total_phases: 6
  completed_phases: 1
  total_plans: 11
  completed_plans: 8
  percent: 73
---

# TSC-CYCLE State

**Last Activity:** 2026-05-08
**Current Milestone:** v3.0 9B 基座切换
**Status:** Ready to execute

## Project Reference

See: `.planning/PROJECT.md` (updated 2026-05-08)

**Core value:** 学生模型在 OOD 上仍满足硬约束，并在数值决策上接近 GPT-5.5 high 教师 — 不过拟合到 reality.log。
**Current focus:** Phase 02 — 数据扩量到 10K（教师只标新增 7K）

## Current Position

Phase: 02 (数据扩量到 10K（教师只标新增 7K）) — EXECUTING
Plan: 3 of 5

- Phase: 1 (not started)
- Plan: — (run `/gsd-plan-phase 1` next)
- Status: Roadmap created, ready for Phase 1 planning
- Last activity: 2026-05-08 — Milestone v3.0 ROADMAP created (6 phases, 39/39 REQ coverage)

**Progress:**

[███████░░░] 73%
[░░░░░░] 0/6 phases complete

```

## Phase Status

| Phase | Status | Notes |
|---|---|---|
| 1. 环境 + Tokenizer + 显存 + llama.cpp 四合一硬门禁 | ○ pending | Hard gates；任一 fatal fail → milestone abort |
| 2. 数据扩量到 10K（教师只标新增 7K） | ○ pending | v1.0 labeled.jsonl read-only；新增 ≥7K 经 lint |
| 3. Dataset Rebuild（Qwen3.5 retokenize + split） | ○ pending | 80/10/10 seed=42；OOD val 含 v1.0 OOD 全集 |
| 4. QLoRA SFT (9B, batch=1, 跑到收敛) | ○ pending | 500-sample dry-run gate + early-stopping，不设 6h 上限 |
| 5. Merge + GGUF Export + imatrix | ○ pending | imatrix 必跑；三精度 SOLUTION smoke |
| 6. Eval Matrix + 三阈值决策门 | ○ pending | v1.0 baseline read-only mount；GO/NO-GO/用户决策三态 |

## Baseline to Beat (v1.0)

- v1.0 q4_K_M OOD hard-constraint lint: **98.7%**
- v1.0 HF bf16 OOD hard-constraint lint: **99.3%**
- v1.0 q4_K_M vs HF bf16 ratio: **0.9933**
- v1.0 teacher MAE delta: **+0.18s**
- v3.0 决策门：`q4_v3 vs fp16_v3 ≥ 0.95` ∧ `q4_v3 vs q4_v1 ≥ 1.00` ∧ `q4_v3 hard_constraint_pass ≥ 98%`

## Frozen v1.0 Artifact (read-only mount in v3.0)

**Path:** `runs/20260507T032419Z/gguf/model.q4_K_M.gguf` (2.4 GB)
**Eval gen_cache:** `runs/20260507T032419Z/eval/gen_cache/gguf_q4km/`
**Constraint:** v3.0 全 phase 零写入；Phase 4 SFT-08 强制标记 FROZEN.md + chmod -w。

## Accumulated Context

### Key Decisions

- v2.0 abandoned (2026-05-08)；v3.0 phase numbering reset to 1（v2.0 phases 7-8 归档到 `milestones/v2.0-abandoned/`）
- v3.0 训练不设 6h 上限（用户决定）；靠 early-stopping callback 收敛（val loss patience=3，max epoch 5）
- 数据扩量到 10K = v1.0 3K read-only ∪ 教师标 7K 新增（lint pass 后 ≥9000 valid）
- 训练栈完全沿用 `/dgx-spark-training` v1.0 已验证环境；不引入新 PyTorch/Unsloth/Axolotl

### Active Todos

- Run `/gsd-plan-phase 1` — 把 Phase 1 的 10 项硬门禁 requirements 拆解为 plans

### Blockers

- None — Phase 1 无外部依赖

## Session Continuity

**Next action:** `/gsd-plan-phase 1`

**Key files:**

- `.planning/PROJECT.md`
- `.planning/REQUIREMENTS.md` (39 v3.0 REQs + traceability)
- `.planning/ROADMAP.md` (6 phases)
- `.planning/research/{SUMMARY,ARCHITECTURE,PITFALLS,STACK,FEATURES}.md`
- `.planning/milestones/v1.0-ROADMAP.md`
