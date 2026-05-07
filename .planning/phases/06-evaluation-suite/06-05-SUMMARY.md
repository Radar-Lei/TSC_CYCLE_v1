---
phase: 06-evaluation-suite
plan: 05
subsystem: evaluation
tags: [evaluation, metrics, constraint-lint, mae, ood-gap, reasoning-quality]
requires: [06-01, 06-02, 06-03, 06-04]
provides:
  - runs/20260507T032419Z/eval/per_sample.jsonl  # 1800 rows, ground truth for wave 4 decision
  - runs/20260507T032419Z/eval/report.md         # 8-section human-readable matrix
affects: [06-06]
tech-stack:
  added: []
  patterns:
    - "Single-purpose metric modules (one function each) for unit-auditability"
    - "Pure stdlib aggregation (json/math/Counter); no torch/numpy in metrics path"
    - "Trivial-sample exclusion via shared `is_trivial` (denominator hygiene)"
    - "Integer MAE only — `abs(int(student) - int(teacher))`, never floats"
key-files:
  created:
    - tsc_cycle/eval/metrics_constraints.py
    - tsc_cycle/eval/metrics_mae.py
    - tsc_cycle/eval/metrics_ood_gap.py
    - tsc_cycle/eval/metrics_reasoning.py
    - tsc_cycle/eval/compute_metrics.py
    - runs/20260507T032419Z/eval/per_sample.jsonl
    - runs/20260507T032419Z/eval/report.md
  modified: []
decisions:
  - "compact JSONL (`separators=(',', ':')`) so plan-checker `grep '\"backend\":\"hf_bf16\"'` matches"
  - "Reasoning metric: rule-based hits over (KEYWORDS + min/max integers from input); standalone-integer regex `(?<!\\d)N(?!\\d)` to avoid substring false-positives"
  - "Top-20 failures sort: lint failures first, then MAE desc — surfaces hard-constraint violations even when MAE is small"
  - "Quantization verdict gated on `q4_K_M_ood_mae - bf16_ood_mae > 3s` (Phase-5 known signal); current delta = 0.18s → imatrix re-quantization NOT triggered"
  - "Force-added runs/ artifacts (gitignored) so plan 06-06 has the dataset committed for review"
metrics:
  duration_min: 8
  tasks: 2
  metric_modules: 4
  per_sample_rows: 1800
  report_sections: 8
completed: 2026-05-07
---

# Phase 06 Plan 05: Evaluation Metrics Pipeline Summary

把 wave 2 的 1800 个 generation cache（hf_bf16 / gguf_bf16 / gguf_q4_k_m × 600 prompts）转换为
4 个指标矩阵 + 量化退化裁决，产出 wave 4 决策计划（06-06）的输入。

## What was built

### 4 single-purpose metric modules（44–55 行各一个）

1. **`tsc_cycle/eval/metrics_constraints.py`** — 包装 `constraint_lint.validate` + `is_trivial`，
   把 `LintResult.violations`（dict 列表，含 `kind`）展平为字符串列表；`solution=None` 直接返回
   `lint_ok=False, violations=["unparseable"]`。
2. **`tsc_cycle/eval/metrics_mae.py`** — 严格整数 MAE：`abs(int(student[k]) - int(teacher[k]))`；
   missing key / unparseable / cast 失败一律 `mae=None`；同时返回 `exact_match` 与
   `per_phase_abs_err` 列表。
3. **`tsc_cycle/eval/metrics_ood_gap.py`** — 对已计算好的 per-sample 行做 id/ood 聚合，
   `gap = id - ood`；rate 指标走 mean(bool)，MAE 跳过 None。
4. **`tsc_cycle/eval/metrics_reasoning.py`** — 规则式打分：抽 `<start_working_out>...</end_working_out>`
   段，统计 `KEYWORDS = [pred_saturation, min_green, max_green, pred_wait]` 命中 + 输入中的
   min/max 整数命中（`(?<!\d)N(?!\d)` 避免子串误命中），0/1-2/≥3 → miss/partial/full。

### Orchestrator `tsc_cycle/eval/compute_metrics.py`（384 行）

CLI：

```bash
python -m tsc_cycle.eval.compute_metrics \
  --prompts runs/20260507T032419Z/eval/eval_prompts.jsonl \
  --cache-root runs/20260507T032419Z/eval/gen_cache \
  --out-jsonl runs/20260507T032419Z/eval/per_sample.jsonl \
  --out-report runs/20260507T032419Z/eval/report.md
```

流程：load 600 prompts → 对 3 backend × 600 sample 各调 4 个 metric → 合并为 1800 行 →
写 per_sample.jsonl（compact JSONL）+ 8 段 markdown 报告。

### Run artifacts

- `runs/20260507T032419Z/eval/per_sample.jsonl` — 1800 行，每行 schema：
  `sample_id, backend, split_hint, phase_count, trivial, solution, parse_error,
   elapsed_sec, lint_ok, violations, mae, exact_match, n_phases, per_phase_abs_err,
   reasoning_tier, hit_count, keywords_found, numbers_found`
- `runs/20260507T032419Z/eval/report.md` — 8 section：Summary / Constraint Satisfaction /
  Teacher MAE / OOD Gap / Reasoning Quality / Latency p99 / Top-20 Failure Cases /
  Quantization Degradation

## Key results（report.md 摘要）

| metric | hf_bf16 id/ood | gguf_bf16 id/ood | gguf_q4_k_m id/ood |
|---|---|---|---|
| lint_ok (non-trivial) | 100.0% / 99.3% | 100.0% / 99.3% | 100.0% / 98.7% |
| mean MAE (s) | 3.111 / 7.936 | 3.196 / 7.670 | 3.714 / 7.846 |
| exact_match | 4.7% / 12.0% | 5.0% / 11.3% | 4.0% / 13.3% |
| reasoning full | 93.3% / 91.3% | 94.0% / 91.3% | 97.3% / 95.7% |

**Latency p99**：gguf_bf16 = 7.64 s/prompt，gguf_q4_k_m = 3.87 s/prompt（hf_bf16 cache 无
`elapsed_sec` 字段，N/A）。

**Quantization Degradation 裁决**：
- ID split MAE Δ（q4_K_M − bf16） = +0.52 s
- OOD split MAE Δ = **+0.18 s**（远低于 3 s 阈值）
- lint_ok OOD Δ = −0.7%（99.3% → 98.7%，phase=6 桶下降到 95.0%）
- **结论**：q4_K_M 退化在容忍范围内，不触发 imatrix 重量化。Phase-5 parity 子集（20-prompt）
  显示的 4.51 s MAE 信号没有在 600-prompt 全集上重现。

**Top-20 Failures**：558 / 1800 行命中 `lint_ok=False OR mae>5`，绝大多数是 OOD 上的
high-MAE 样本（MAE 50–95 s 区间集中在「极宽 max_green 区间但教师选最小值」类样本，
学生模型按饱和度倾向给中高值）。仅 4 个独立 sample 触发硬约束 fail（above_max / below_min）。

## Verification

- `wc -l runs/20260507T032419Z/eval/per_sample.jsonl` = **1800** ✓
- `grep -c '"backend":"hf_bf16"'` = 600，`gguf_bf16` = 600，`gguf_q4_k_m` = 600 ✓
- 8 个 `## ` heading（含 Summary、Latency p99、Quantization Degradation）全部命中 ✓
- 任一 per_sample 行含完整 schema keys ✓
- `from tsc_cycle.constraint_lint import` 出现在 metrics_constraints.py ✓
- `abs(int(` 出现在 metrics_mae.py ✓
- `KEYWORDS` 与 `pred_saturation` 出现在 metrics_reasoning.py ✓
- Smoke test：`score_mae({'p1':10,'p2':20}, {'p1':10,'p2':22})['mae']==1.0` ✓
- Smoke test：`score_mae(None, ...)['mae'] is None` ✓

## Acceptance criteria

### Task 1
- ✅ 4 metric .py 文件全部 ast.parse 通过
- ✅ grep 锚点：`from tsc_cycle.constraint_lint import` / `abs\(int\(` / `KEYWORDS` / `pred_saturation`
- ✅ score_mae / score_constraint / score_reasoning smoke 全部通过

### Task 2
- ✅ per_sample.jsonl 恰 1800 行
- ✅ 三 backend 字符串各命中 600 次
- ✅ report.md 含 8 个 `## ` heading（Summary / Constraint Satisfaction / Teacher MAE /
  OOD Gap / Reasoning Quality / Latency p99 / Top-20 Failure Cases / Quantization Degradation）
- ✅ per_sample 行 schema 完整（17 keys）
- ✅ stdout `[METRICS] OK per_sample=1800 report=...`

## Notes / Deviations

### Rule 1 — 修复 plan 验收 grep 误用 compact JSON

- **发现于**：Task 2 自动验证阶段
- **现象**：plan 验收命令 `grep -q '"backend":"hf_bf16"'` 全部失败，因为 `json.dumps` 默认
  `separators=(', ', ': ')` 产生 `"backend": "hf_bf16"`（带空格），与 grep 锚点不匹配。
- **修复**：写 per_sample.jsonl 时改用 `separators=(",", ":")`。
- **影响**：JSONL 体积减小约 8%；schema 不变；下游 parse 无影响。
- **commit**：66a37c4

### Rule 3 — 强制添加 gitignored 运行工件

- **发现于**：Task 2 提交阶段
- **现象**：`runs/` 整目录在 `.gitignore` 中（与 wave 2 三个 generation plan 一致）；但 plan
  06-05 的两个产物（per_sample.jsonl、report.md）是 plan 06-06 决策计划的强依赖输入。
- **修复**：`git add -f` 强制添加这两个文件。其他 cache（`gen_cache/*`、`server_*.log`）保持
  ignored，与 wave 2 SUMMARY 风格一致。
- **commit**：66a37c4

### 没有调整的设计决策

- 教师答案 schema 直接走 `prompt_record["teacher_solution"]`（透传字段，plan 06-01 已固化），
  没有走「重新解析 labeled.jsonl」的回退路径。
- Reasoning metric 没有引入 LLM-as-judge — 严格规则式，避免 6h 预算外的 API 调用。
- OOD gap 用 `id - ood` 而不是 `ood - id`：plan 文本明确这样定义，正值=OOD 退化（rate 指标），
  MAE 上正值=OOD 反而比 ID 好（少见）。

## Threat Flags

无。本 plan 不引入新的网络端点 / 文件访问模式 / 信任边界变化；纯本地数据聚合。

## Self-Check

- ✅ tsc_cycle/eval/metrics_constraints.py 存在（44 行）
- ✅ tsc_cycle/eval/metrics_mae.py 存在（38 行）
- ✅ tsc_cycle/eval/metrics_ood_gap.py 存在（42 行）
- ✅ tsc_cycle/eval/metrics_reasoning.py 存在（55 行）
- ✅ tsc_cycle/eval/compute_metrics.py 存在（384 行）
- ✅ runs/20260507T032419Z/eval/per_sample.jsonl 存在（1800 行）
- ✅ runs/20260507T032419Z/eval/report.md 存在（8 sections）
- ✅ commits 469d9d2 + 66a37c4 在 git log 中
- ✅ 三 backend × 两 split × 4 metric 矩阵已在 report.md 完整呈现

## Self-Check: PASSED
