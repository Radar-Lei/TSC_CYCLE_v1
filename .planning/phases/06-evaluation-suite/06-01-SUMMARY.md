---
phase: 06-evaluation-suite
plan: 01
subsystem: eval/dataset-selector
tags: [evaluation, deterministic-sampling, phase-06]
requires:
  - data/labeled.jsonl (Phase 3 output, 2700 id + 300 ood, all trivial=False)
provides:
  - tsc_cycle.eval.eval_prompts (CLI module)
  - runs/20260507T032419Z/eval/eval_prompts.jsonl (frozen 600-sample EVL set)
affects:
  - Plan 06-02 / 06-03 / 06-04 (wave 2 generation runners) — all three backends
    must consume this exact file via --prompts to avoid split drift
tech-stack:
  added: []
  patterns:
    - "Single random.Random(seed=42) for the whole pick (per Plan 06-01 literal spec)"
    - "Bucket sorted by sample_id before random.sample → FS-iteration-order independence"
    - "Output written with sort_keys=False + fixed key order for byte-stable md5"
    - "phase_count fallback chain: input.phases → input.phase_min_green → input.prediction.phase_waits"
key-files:
  created:
    - tsc_cycle/eval/eval_prompts.py
    - runs/20260507T032419Z/eval/eval_prompts.jsonl  # gitignored (runs/)
  modified: []
decisions:
  - "Use single Random(42) (Plan 06-01) rather than the dual Random(seed)/Random(seed+1) pattern from 05-02; bucket pool 远大于需求 (id 2700→300, ood 300→300), 单 RNG 即可"
  - "phase_count 实际从 input.prediction.phase_waits 读取（plan 列出的 input.phases / input.phase_min_green 在当前 Phase 3 schema 中不存在），保留 fallback 链以防未来 schema 演进"
  - "id 在前 ood 在后顺序写出，不打乱 — 让下游 runner 可按 split_hint 流式 partition"
metrics:
  duration: ~5min
  tasks_completed: 1/1
  files_created: 2
  completed_date: 2026-05-07
requirements: [EVL-01]
---

# Phase 06 Plan 01: EVL Dataset Selector Summary

固化了 600 个 (300 id + 300 ood) 评测样本到 `runs/20260507T032419Z/eval/eval_prompts.jsonl`，作为 wave 2 三 backend (HF / GGUF bf16 / GGUF q4_K_M) generation runner 的共享输入，消除 split 漂移。

## What Was Built

### `tsc_cycle/eval/eval_prompts.py` (172 行)

CLI 工具，参数：
- `--labeled` (default `data/labeled.jsonl`)
- `--out` (default `runs/20260507T032419Z/eval/eval_prompts.jsonl`)
- `--n-id` / `--n-ood` (default 300 / 300)
- `--seed` (default 42)

流程：流式扫 labeled.jsonl → 按 `split_hint` 分桶 → assert 池大小 ≥ 需求 → 排序后 `random.Random(42).sample` 各抽 300 → projection 成 EVL 行 schema (固定 key 顺序) → id+ood 顺序拼接 → 落盘 → stdout 打印 `[EVAL-PROMPTS] OK n_id=300 n_ood=300 out=...`

输出每行 schema：
```json
{
  "sample_id": "...",
  "split_hint": "id" | "ood",
  "input": { "prediction": {...}, "sample_id": "...", "split_hint": "...", "trivial": false },
  "teacher_solution": { "1": 23, "2": 45, ... },
  "phase_count": 4,
  "trivial": false
}
```

### `runs/20260507T032419Z/eval/eval_prompts.jsonl` (600 行)

300 id + 300 ood 评测样本。`runs/` 被 .gitignore 排除，重新生成命令：
```bash
/home/samuel/dgx-spark-setup/.venv/bin/python -m tsc_cycle.eval.eval_prompts
```
md5 跨次运行 byte-stable。

## Acceptance Criteria — All Passed

| 条件 | 期望 | 实际 | 状态 |
|------|------|------|------|
| File exists | eval_prompts.jsonl | 存在 | ✓ |
| Line count | 600 | 600 | ✓ |
| `split_hint": "id"` 数量 | 300 | 300 | ✓ |
| `split_hint": "ood"` 数量 | 300 | 300 | ✓ |
| 第 1 行含 6 个字段 | sample_id/split_hint/input/teacher_solution/phase_count/trivial | 全齐 | ✓ |
| Determinism (md5 二次重跑) | identical | `3d98fb49a5dbbc0b9549e8bab6f4eb2d` × 2 | ✓ |
| 脚本行数 | ≥ 60 | 172 | ✓ |

## Pool Sizes (实际 vs 需求)

| Bucket | Have | Need | Status |
|--------|------|------|--------|
| id (split_hint=="id") | 2700 | 300 | OK |
| ood (split_hint=="ood") | 300 | 300 | exact match |
| trivial (id+ood) | 0 / 0 | — | exclude_trivial 无意义；plan 未要求过滤 |

## Schema Notes (实测 vs Plan)

Plan 第 6 步 phase_count 的 fallback 链假设 `input["phases"]` 或 `input["phase_min_green"]`，实测当前 Phase 3 schema 是：
```
input.keys = ['prediction', 'sample_id', 'split_hint', 'trivial']
input.prediction.keys = ['as_of', 'phase_waits', '_crossing_id']
```
phase 列表实际位置是 `input.prediction.phase_waits`（list of `{phase_id, pred_wait, min_green, max_green, capacity, ...}`）。脚本保留三段 fallback：先查 `phases` → `phase_min_green` → `prediction.phase_waits`，确保未来 schema 演进时无需改代码。

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] phase_count 从 input.prediction.phase_waits 读取（plan 写的 input.phases / input.phase_min_green 不存在）**
- **Found during:** Task 1 schema 检查
- **Issue:** Plan 第 6 步指定 `len(r["input"]["phases"])` fallback `len(r["input"]["phase_min_green"])`，但实际 Phase 3 输出两个 key 都没有，会导致 phase_count 始终为 0
- **Fix:** 添加第三层 fallback `len(input["prediction"]["phase_waits"])`，前两层保留以兼容未来 schema
- **Files modified:** tsc_cycle/eval/eval_prompts.py (`_phase_count` helper)
- **Commit:** 7284b82

无其他偏差。

## Auth Gates

无 — 纯本地脚本。

## Out-of-Scope Discoveries

无（所有处理都在 plan 明确范围内）。

## Known Stubs

无。

## Self-Check: PASSED

- ✓ FOUND: tsc_cycle/eval/eval_prompts.py
- ✓ FOUND: runs/20260507T032419Z/eval/eval_prompts.jsonl (600 行, gitignored)
- ✓ FOUND commit: 7284b82 (feat(06-01): deterministic EVL prompt selector)
