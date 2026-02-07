---
phase: 02-data-generation
plan: 02
subsystem: data-pipeline
tags: [cot, sft, jsonl, training-data, llm]

# Dependency graph
requires:
  - phase: 02-01
    provides: 周期边界全量采样和原始 JSONL 数据生成
provides:
  - CoT 格式 SFT 训练数据转换管线（原始 JSONL → SFT chat 格式）
  - 基于 pred_saturation 的智能 final 绿灯时间计算逻辑
  - 空占位 <think></think> 标签设计（由模型在训练时自主学习填充）
affects: [03-sft-training, 04-grpo-training]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "CoT 空占位模式：<think>\n\n</think> 不预生成推理文本"
    - "饱和度线性插值：final = min_green + (max_green - min_green) * saturation"

key-files:
  created: []
  modified:
    - src/scripts/generate_training_data.py

key-decisions:
  - "使用空 <think></think> 标签，不预生成 CoT 分析文本（让模型自主学习推理内容）"
  - "基于 pred_saturation 智能计算 final：高饱和度偏向 max_green，低饱和度偏向 min_green，中等线性插值"

patterns-established:
  - "SFT chat 格式：system/user/assistant 三角色消息结构"
  - "CoT 输出格式：<think>...</think> + JSON 数组"

# Metrics
duration: 4min
completed: 2026-02-07
---

# Phase 2 Plan 2: CoT Format Conversion Summary

**实现原始 JSONL 到 CoT 格式 SFT 训练数据的完整转换管线，包含智能饱和度插值和空 think 标签设计**

## Performance

- **Duration:** 4 min
- **Started:** 2026-02-07T18:46:08Z
- **Completed:** 2026-02-07T18:50:15Z
- **Tasks:** 2
- **Files modified:** 1

## Accomplishments

- 实现 `convert_to_sft_format()` 函数：原始 JSONL → SFT chat 格式转换
- 集成 CoT 格式转换为数据生成流程的阶段 6
- 验证周期边界全量采样、JSONL 输出管线和端到端数据一致性（所有检查通过）

## Task Commits

1. **Task 1: 实现 CoT 格式转换函数并集成到数据生成流程** - `60ffb1e` (feat)
2. **Task 2: 验证周期边界全量采样、JSONL 输出管线和端到端数据一致性** - 无需提交（纯验证任务，所有检查通过）

## Files Created/Modified

- `src/scripts/generate_training_data.py` - 添加 `convert_to_sft_format()` 函数和阶段 6 CoT 格式转换

## Decisions Made

1. **CoT 空占位策略**：使用 `<think>\n\n</think>` 空占位符，不预生成任何推理文本。这让模型在 SFT 训练时自主学习如何填充思考内容，避免人为规定推理模式。

2. **智能饱和度插值算法**：
   - 饱和度 > 1.0：final = max_green（高饱和度优先最大绿灯）
   - 饱和度 < 0.5：final = min_green（低饱和度使用最小绿灯）
   - 0.5 ≤ 饱和度 ≤ 1.0：final = min_green + (max_green - min_green) × saturation（线性插值）

3. **SFT 输出路径**：遵循 config.json 中的 `paths.sft_output` 配置（默认 `outputs/sft/`），与现有路径配置体系保持一致。

## Deviations from Plan

None - 计划执行完全符合规范。

## Issues Encountered

None - 所有实现和验证顺利完成。

## Verification Results

### A. 周期边界全量采样验证
- ✓ CycleDetector 存在于 day_simulator.py (line 60, 234)
- ✓ sample_at_cycle_start 在周期边界触发 (line 271)
- ✓ 无跳过采样条件（无 skip_count, sample_rate, min_vehicles, min_queue）

### B. JSONL 输出管线验证
- ✓ 单场景写出 samples_{date}.jsonl (line 580)
- ✓ 合并输出到 train.jsonl (line 597)
- ✓ 输出目录配置正确（paths_config.data_dir = 'data/training'）

### C. 端到端数据一致性验证
- ✓ DaySimulator.run() 返回 metadata 字段 (line 349)
- ✓ TrainingSample.to_dict() 包含完整 prediction.phase_waits
- ✓ 数据格式链路完整：DaySimulator → TrainingSample → JSONL → SFT

## Next Phase Readiness

- ✓ SFT 训练数据格式就绪（outputs/sft/train.jsonl）
- ✓ CoT 格式符合预期（空 think 标签 + JSON 输出）
- ✓ 原始 JSONL 数据保留（data/training/train.jsonl，供 GRPO 使用）
- ✓ 数据流水线完整验证通过

**Blockers:** None

**Concerns:** None

---
*Phase: 02-data-generation*
*Completed: 2026-02-07*
