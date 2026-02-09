---
phase: 01-sft-data-and-training
plan: 01
subsystem: data-preparation
tags: [sampling, data-quality, coverage]
dependency_graph:
  requires: [outputs/data/train.jsonl]
  provides: [outputs/sft/sampled_100.jsonl, src/scripts/sample_selector.py]
  affects: [SFT-01]
tech_stack:
  added: [Python-random-sampling, stratified-sampling]
  patterns: [multi-strategy-sampling, coverage-based-selection]
key_files:
  created: [src/scripts/sample_selector.py, outputs/sft/sampled_100.jsonl]
  modified: []
decisions:
  - desc: "采用分层抽样策略而非纯随机抽样"
    rationale: "确保覆盖所有 34 个交叉口和不同饱和度区间"
  - desc: "优先补充 high 饱和度样本(40% 配额)"
    rationale: "high 饱和度样本训练价值高但在原始数据中占比较少"
  - desc: "样本饱和度按最大相位饱和度计算"
    rationale: "代表该样本最严重的交通压力状况"
metrics:
  duration_seconds: 259
  tasks_completed: 1
  files_created: 2
  lines_of_code: 231
  completed_at: 2026-02-09T12:24:12Z
---

# Phase 01 Plan 01: Sample Selector Summary

从 train.jsonl (1588 条) 中成功抽取 100 条代表性样本,采用分层抽样策略确保覆盖所有交叉口和不同饱和度分布。

## Objective

为后续 AI 生成 think+solution 内容提供代表性样本集 (SFT-01),从 1588 条训练数据中均匀抽取约 100 条样本,确保覆盖所有 34 个交叉口、不同饱和度分布和两个场景。

## What Was Built

### 1. Sample Selector Script (src/scripts/sample_selector.py)

实现了智能分层抽样脚本,包含以下功能:

**抽样策略:**
- 第一步:确保覆盖所有 34 个 tl_id,每个至少抽 1 条 → 34 条基础样本
- 第二步:在剩余配额(66 条)中按饱和度分布补充:
  - high (≥1.0): 28 条 (40%)
  - medium (0.5-1.0): 19 条 (30%)
  - low (0-0.5): 13 条 (20%)
  - zero (0.0): 6 条 (10%)
- 饱和度计算:取样本所有相位中的最大 pred_saturation
- 随机种子固定为 42,确保可复现

**命令行接口:**
```bash
python3 -m src.scripts.sample_selector \
  --input outputs/data/train.jsonl \
  --output outputs/sft/sampled_100.jsonl \
  --count 100 \
  --seed 42
```

**统计输出:**
脚本自动打印分布统计:场景、tl_id、饱和度区间、相位数

### 2. Sampled Dataset (outputs/sft/sampled_100.jsonl)

成功生成 100 条样本,分布特征:

**场景覆盖:**
- arterial4x4_10: 53 条 (53%)
- chengdu: 47 条 (47%)

**交叉口覆盖:**
- 覆盖全部 34 个 tl_id
- 每个交叉口 1-6 条样本

**饱和度分布:**
- high (≥1.0): 35 条 (35%)
- medium (0.5-1.0): 30 条 (30%)
- low (0-0.5): 27 条 (27%)
- zero (0.0): 8 条 (8%)

**相位数分布:**
- 2 相位: 40 条 (40%)
- 3 相位: 57 条 (57%)
- 4 相位: 3 条 (3%)

## Tasks Completed

| Task | Name                              | Commit  | Files                                         |
|------|-----------------------------------|---------|-----------------------------------------------|
| 1    | 创建样本抽取脚本并执行抽取        | bbdf8be | src/scripts/sample_selector.py, sampled_100.jsonl |

## Verification Results

所有验证步骤通过:

1. **行数验证:** `wc -l outputs/sft/sampled_100.jsonl` → 100 行 ✓
2. **JSON 格式验证:** 所有 100 行均为合法 JSON ✓
3. **覆盖验证:**
   - 34 个 tl_id 全部覆盖 ✓
   - 两个场景都有样本 ✓
   - 所有饱和度区间都有覆盖 ✓
   - 2/3/4 相位都有覆盖 ✓

## Deviations from Plan

无偏差 - 计划完全按预期执行。

实际饱和度分布(high 35%)略高于计划配额(28%),这是因为第一步(每个 tl_id 至少 1 条)已包含部分 high 饱和度样本,符合预期且有利于训练。

## Key Decisions Made

### 1. 分层抽样 vs 纯随机抽样

**决策:** 采用分层抽样策略

**理由:**
- 原始数据中 tl_id 分布不均(有些交叉口样本很少)
- 饱和度分布不均(high 饱和度样本仅占 28%)
- 纯随机抽样可能导致某些 tl_id 或饱和度区间缺失

**影响:** 确保了样本的代表性和多样性

### 2. High 饱和度优先策略

**决策:** 在第二步配额分配中给 high 饱和度 40% 配额

**理由:**
- high 饱和度场景训练价值最高(复杂决策场景)
- 原始数据中 high 饱和度样本相对较少(仅 448/4743 个相位,约 9%)
- 需要确保充足的 high 饱和度样本用于训练

**影响:** 最终抽样集中 high 饱和度占 35%,远高于原始分布

### 3. 样本饱和度定义

**决策:** 样本饱和度 = max(各相位饱和度)

**理由:**
- 一个样本包含多个相位,需要单一指标代表该样本的复杂度
- 最大值代表该样本最严重的交通压力状况
- 符合信号配时优化的实际需求(瓶颈相位决定整体复杂度)

**影响:** 样本分类更符合实际应用场景

## Success Criteria Met

- [x] outputs/sft/sampled_100.jsonl 包含约 100 条样本
- [x] 覆盖所有 34 个 tl_id
- [x] 覆盖两个场景(arterial4x4_10 和 chengdu)
- [x] 覆盖不同饱和度区间(zero/low/medium/high)
- [x] 覆盖不同相位数(2/3/4 相位)
- [x] 统计信息已打印确认

## Next Steps

下一个计划将使用这 100 条样本作为输入,由 AI 生成对应的 `<think>` 和 `<solution>` 内容,构建完整的 SFT 训练数据集。

## Self-Check

检查创建的文件:

```bash
# 检查脚本文件
ls -lh src/scripts/sample_selector.py
# 输出: -rw-rw-r-- 1 samuel samuel 7.4K  2月  9 20:21 sample_selector.py

# 检查样本文件
ls -lh outputs/sft/sampled_100.jsonl
# 输出: -rw-rw-r-- 1 samuel samuel 235K  2月  9 20:21 sampled_100.jsonl

# 检查提交
git log --oneline -1
# 输出: bbdf8be feat(01-01): implement sample selector script
```

## Self-Check: PASSED

所有文件已创建,提交已记录。
