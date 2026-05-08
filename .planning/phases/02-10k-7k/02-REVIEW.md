---
phase: 02-10k-7k
reviewed: 2026-05-08T16:07:08Z
depth: standard
files_reviewed: 18
files_reviewed_list:
  - data/v3/phase2/README.phase2.txt
  - data/v3/phase2/datagen_manifest.json
  - data/v3/phase2/inputs_all.jsonl
  - data/v3/phase2/inputs_ood.jsonl
  - data/v3/phase2/inputs_same_dist.jsonl
  - data/v3/phase2/inputs_targeted.jsonl
  - scripts/generate_v3_phase2_inputs.sh
  - scripts/run_v3_phase2_all.sh
  - scripts/run_v3_phase2_label_full.sh
  - scripts/run_v3_phase2_label_smoke.sh
  - scripts/run_v3_phase2_merge.sh
  - tests/conftest.py
  - tests/test_v3_datagen_inputs.py
  - tests/test_v3_datagen_merge.py
  - tests/test_v3_labeler.py
  - tsc_cycle/sample_inputs.py
  - tsc_cycle/teacher/labeler.py
  - tsc_cycle/v3_gates/phase2_datagen_report.py
findings:
  critical: 1
  warning: 1
  info: 0
  total: 2
status: issues_found
---

# Phase 02: Code Review Report

**Reviewed:** 2026-05-08T16:07:08Z
**Depth:** standard
**Files Reviewed:** 18
**Status:** issues_found

## Summary

审查了 Phase 2 输入产物、labeler/merge gate、运行脚本与测试。主要问题集中在付费标注编排：全量 wrapper 的 500-attempt checkpoint 逻辑会永久跳过 targeted 分层，且 labeler 在同一次运行内不去重输入样本，可能导致重复 GPT API 调用与重复输出记录。

## Critical Issues

### CR-01: 全量标注在 7000 attempted 时停止，永远不覆盖 targeted reservoir

**File:** `scripts/run_v3_phase2_all.sh:182-184`; `data/v3/phase2/inputs_all.jsonl:6751`

**Issue:** `run_full_chunks` 只要求 `attempted >= 7000 && accepted >= 6000` 就停止，但 `inputs_all.jsonl` 的顺序是 5250 same_dist、1500 ood、750 targeted；targeted 从第 6751 行才开始。若前 7000 个样本达到 6000 accepted，循环会在只尝试 250/750 个 targeted 后退出并立即 merge。这违反 Phase 2 的三源数据治理目标，且会让 500 个 targeted（高-MAE/lint-reject 邻域）完全不进入教师标注，训练集偏离设计分布。

**Fix:** gate 不应只看总 attempted/accepted；必须要求所有目标分层都已尝试或 accepted/rejected 覆盖完整 reservoir（至少覆盖 targeted 750）。一种直接修复是把最小尝试数提升到完整 reservoir，或更严格地按 source 统计 done IDs：

```bash
MIN_ATTEMPTED=7500
# 或在 phase2_counts 中统计 accepted/rejected 的 source，停止条件加入：
# targeted_attempted >= 750 && same_dist_attempted >= 5250 && ood_attempted >= 1500
```

同时在 merge gate 报告中加入 source-level attempted/accepted 下限，避免 wrapper 之外直接 merge 时绕过该约束。

## Warnings

### WR-01: 同一批输入内部重复 sample_id 不会在提交前去重，可能产生重复 API 调用和重复输出

**File:** `tsc_cycle/teacher/labeler.py:137-140`, `tsc_cycle/teacher/labeler.py:182-186`

**Issue:** `pending = [s for s in all_inputs if s["sample_id"] not in done]` 只排除历史 done ID，没有在 `all_inputs` 当前批次内去重；随后所有 pending 都一次性提交到 ThreadPoolExecutor。只要输入文件或多个 `--input-files` 之间出现重复 `sample_id`，同一个样本会被并发提交多次，浪费 GPT-5.5 预算，并向 labeled/rejected append 重复记录。后续 merge gate 虽然会发现 duplicate_done_ids，但重复费用和重复 API 调用已经发生。

**Fix:** 构造 pending 时维护本轮 seen 集合，并在提交前 fail-fast 或跳过重复项。建议 fail-fast，避免静默掩盖数据生成问题：

```python
seen_pending: set[str] = set()
pending: list[dict] = []
for sample in all_inputs:
    sid = sample.get("sample_id")
    if not sid:
        raise ValueError("input row missing sample_id")
    if sid in done:
        continue
    if sid in seen_pending:
        raise ValueError(f"duplicate pending sample_id: {sid}")
    seen_pending.add(sid)
    pending.append(sample)
if args.limit:
    pending = pending[: args.limit]
```

并补充一个测试：同一 input JSONL 内重复 sample_id 时 `client.call` 不应被调用两次，最好直接抛错。

---

_Reviewed: 2026-05-08T16:07:08Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
