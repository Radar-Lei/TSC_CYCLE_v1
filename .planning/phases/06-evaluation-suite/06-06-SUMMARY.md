---
phase: 06-evaluation-suite
plan: 06
subsystem: evaluation
tags: [decision-gate, deployment, go-no-go, milestone-closure]
requires: [06-05]
provides:
  - tsc_cycle/eval/decision.py                       # CLI 裁决器（可复用于未来 ts）
  - runs/20260507T032419Z/eval/decision.md           # GO 决议 + 数字依据 + downstream action
affects: []
tech-stack:
  added: []
  patterns:
    - "纯 stdlib 裁决器（argparse + json + math），无新依赖"
    - "trivial 样本（min==max）从分母排除，与 plan 06-05 metric 语义保持一致"
    - "Verdict 阈值 verbatim 写在 decision.md，便于未来回看时无需翻代码"
key-files:
  created:
    - tsc_cycle/eval/decision.py
    - runs/20260507T032419Z/eval/decision.md
  modified:
    - .planning/STATE.md
    - .planning/REQUIREMENTS.md
decisions:
  - "Verdict = GO（ratio = 0.9933 ≥ 0.95）；q4_K_M 直接部署，imatrix 重量化降级为 v2 backlog 非阻塞项"
  - "decision.py 退出码恒为 0：这是裁决器，不是 CI gate；NO-GO 由 decision.md 文本 + 后续人工/自动化触发"
  - "EVL-01..08 全部统一标记为 `Done`（修正之前 EVL-01/02 用了 `Complete` 的不一致）"
metrics:
  duration_min: 5
  tasks: 2
  decision_py_lines: 208
  go_no_go: GO
  ratio: 0.9933
  threshold: 0.95
completed: 2026-05-07
---

# Phase 06 Plan 06: Deployment Decision Gate Summary

把 plan 06-05 产出的 1800 行 per_sample.jsonl 通过 verbatim 阈值
(`q4_K_M_ood_lint_rate / hf_bf16_ood_lint_rate >= 0.95`) 裁决 GO/NO-GO，
落盘 `decision.md`，并把 STATE.md / REQUIREMENTS.md 推进到 milestone v1.0 闭环。

## What was built

### `tsc_cycle/eval/decision.py`（208 行）

CLI：

```bash
python -m tsc_cycle.eval.decision \
  --per-sample runs/20260507T032419Z/eval/per_sample.jsonl \
  --report     runs/20260507T032419Z/eval/report.md \
  --out        runs/20260507T032419Z/eval/decision.md \
  --threshold  0.95
```

核心函数：

- `ood_lint_rate(rows, backend) -> (rate, n)` — 过滤 `backend == X AND split_hint == "ood" AND not trivial`
- `ood_mae(rows, backend) -> float` — 跳过 `mae is None` 的行
- `render_decision_md(...)` — 生成包含 verbatim 阈值行、三 backend 数字表、key findings、downstream action 的 markdown

退出码恒为 0；裁决信号在 stdout 的 `[DECISION] {GO|NO-GO}` 行 + decision.md 文本。

### `runs/20260507T032419Z/eval/decision.md`

Verdict = **GO**，关键数字：

| Backend | OOD lint_ok rate (non-trivial) | n |
|---|---|---|
| hf_bf16 | 0.9933 (99.33%) | 300 |
| gguf_bf16 | 0.9933 | 300 |
| gguf_q4_k_m | 0.9867 | 300 |

- **Computed ratio = 0.9867 / 0.9933 = 0.9933 ≥ 0.95 → GO**
- OOD MAE：hf_bf16=7.936s, gguf_bf16=7.670s, gguf_q4_k_m=7.846s（q4 vs bf16 Δ = +0.18s，远低于 3s 阈值）
- Reasoning full tier：q4_K_M OOD 95.7% 反而高于 bf16 91.3%

### Downstream action（写入 decision.md）

- 部署 `runs/20260507T032419Z/gguf/model.q4_K_M.gguf` (~2.4 GB) 至 EvoProgTSC TSC 决策端点
- 保留 `model.bf16.gguf` 作为 fallback
- imatrix 重量化降级为 v2 `Q-02` backlog（非阻塞）；触发条件 = 生产观测 OOD lint_ok < 95% 或 MAE 漂移 > 3s

## State recoverage

- **STATE.md**:
  - Phase Status 表 `6. Evaluation Suite` 行：`⚙ queued (watchdog)` → `✓ done` (notes 含 ratio + 三个产物文件名)
  - frontmatter `completed_phases: 1 → 6`，`completed_plans: 14 → 20`，`percent: 100`
  - `last_updated`: 2026-05-07T15:00:00.000Z
- **REQUIREMENTS.md**:
  - Traceability 表 EVL-01..EVL-08 全部 `Done`（修正 EVL-01/02 之前的 `Complete` 不一致）

## Verification

- `decision.py` 实测运行 stdout: `[DECISION] GO ratio=0.9933 threshold=0.95` ✓
- `grep -E "^\*\*GO/NO-GO:\*\* (GO|NO-GO)$"` 命中 `**GO/NO-GO:** GO` ✓
- `grep -q "Threshold:.*>= 0.95"` 命中 ✓
- `grep -q "Computed ratio:"` 命中 ✓
- `grep -q "## Downstream Action"` 命中 ✓
- `grep -c "0.95" tsc_cycle/eval/decision.py` = 3 ✓ (verbatim threshold)
- `grep -c 'not r\["trivial"\]' tsc_cycle/eval/decision.py` = 1 ✓ (trivial 排除)
- `wc -l tsc_cycle/eval/decision.py` = 208 ≥ 60 ✓
- STATE.md 行 grep 命中 `| 6. Evaluation Suite | ✓ done` ✓
- REQUIREMENTS.md EVL-01..08 全部 `Done` ✓

## Acceptance criteria

### Task 1
- ✅ `tsc_cycle/eval/decision.py` 存在 208 行
- ✅ decision.md 含 verbatim `**GO/NO-GO:** GO` 行
- ✅ decision.md 含 `Threshold:` 行 + verbatim 数字 `0.95`
- ✅ decision.md 含 `Computed ratio: 0.9933` 行
- ✅ decision.md 含三 backend 数字表（hf_bf16 / gguf_bf16 / gguf_q4_k_m grep 各命中）
- ✅ decision.md 含 `## Downstream Action` heading
- ✅ decision.py grep `0.95` × 3
- ✅ decision.py grep `not r["trivial"]` × 1

### Task 2
- ✅ STATE.md `Phase 6` 行 Status = `✓ done`
- ✅ REQUIREMENTS.md EVL-01..EVL-08 = `Done`
- ✅ STATE.md frontmatter `completed_phases: 6`

## Deviations from Plan

无。Plan 06-06 严格按写就执行：
- 数字 verbatim 来自 plan 06-05 report.md（hf_bf16 ood = 99.33%，q4_K_M ood = 98.67%）
- ratio = 0.9933 ≥ 0.95 自然命中 GO 分支，没有触发 NO-GO 路径
- decision.py 没有引入新依赖（纯 stdlib）
- STATE.md / REQUIREMENTS.md 用 Edit tool 精确替换，未重写整文件

## Threat Flags

无。本 plan 不引入新的网络端点 / 文件访问模式 / 信任边界变化；
- decision.py 是纯本地数据聚合 + 文件写入
- STATE/REQUIREMENTS 是 markdown 元数据更新

## Self-Check

- ✅ tsc_cycle/eval/decision.py 存在（208 行）
- ✅ runs/20260507T032419Z/eval/decision.md 存在（含 GO 决议）
- ✅ .planning/STATE.md Phase 6 = ✓ done
- ✅ .planning/REQUIREMENTS.md EVL-01..08 全部 Done
- ✅ commits 964342f + a6866dd 在 git log 中

## Self-Check: PASSED

## Milestone Status

**v1.0 milestone CLOSED.** 6/6 phases done, 20/20 plans done, 47/47 requirements completed
（45 Done + 1 Done with FLAG=EXP-05 imatrix backlog + EVL-08 Done）。
最终交付物 `runs/20260507T032419Z/gguf/model.q4_K_M.gguf` 可投入 EvoProgTSC 部署。
