---
phase: 02-data-generation
plan: 03
subsystem: data-generation
tags: [bugfix, cycle-detection, phase-config]
dependencies:
  requires: [02-01, 02-02]
  provides: [dynamic-phase-detection]
  affects: [cycle-detector, day-simulator]
tech-stack:
  added: []
  patterns: [dynamic-config-extraction]
key-files:
  created: []
  modified:
    - src/data_generator/cycle_detector.py
    - src/data_generator/day_simulator.py
decisions:
  - id: DYN-PHASE-01
    title: 动态检测首绿相位 index
    choice: 从 phase_config 提取第一个绿灯相位 phase_index，替代硬编码 0
    rationale: 相位处理后保留原始 phase_index，首绿相位 ID 不一定是 0，硬编码会导致零采样
    alternatives: ["重新编号相位为 0,1,2...", "在 TrafficCollector 中映射相位 ID"]
    impact: 修复首绿相位非 0 场景下的周期边界检测失败
metrics:
  duration_minutes: 4
  completed_date: 2026-02-07
---

# Phase 2 Plan 3: 动态首绿相位检测 Summary

**一句话总结:** 修复 CycleDetector 硬编码 phase 0 bug，改为从 phase_config 动态检测首绿相位 index，支持任意相位序列。

## What Was Built

修复了 CycleDetector 中硬编码 `current_phase == 0` 导致的周期边界检测失败问题：

1. **CycleDetector 动态配置支持**
   - 修改 `__init__()` 接受 `phase_config` 参数
   - 从 `phase_config['traffic_lights'][tl_id]` 提取首绿相位 `phase_index`
   - 设置 `self.first_green_phase` 属性，回退默认值 0

2. **周期边界检测逻辑更新**
   - 将 `current_phase == 0` 替换为 `current_phase == self.first_green_phase`
   - 将 `self.last_phase != 0` 替换为 `self.last_phase != self.first_green_phase`
   - 支持任意首绿相位 index（如 2, 4, 6...）

3. **DaySimulator 集成**
   - 修改 CycleDetector 实例化调用，传入 `phase_config` 参数
   - 更新模块 docstring 说明动态检测机制

## Impact

**修复的场景:**
- 场景：相位过滤后首绿相位 index 为 2（phase 0 和 1 被过滤）
- 修复前：`current_phase == 0` 永远不触发，采样数 = 0
- 修复后：`current_phase == 2` 正确触发周期边界，正常采样

**验证结果:**
- ✓ 首绿相位 index=2 时，phase 5→2 触发周期边界
- ✓ 首绿相位 index=2 时，phase 5→0 不触发（正确）
- ✓ tl_id 不在 phase_config 时回退默认值 0
- ✓ docstring 和 __repr__ 包含 first_green_phase 说明

## Deviations from Plan

无偏差 — 计划按原定执行。

## Commits

| Task | Commit | Files Modified |
|------|--------|----------------|
| Task 1: 修改 CycleDetector 支持动态首绿相位检测 | 59f3814 | src/data_generator/cycle_detector.py |
| Task 2: 修改 DaySimulator 传递 phase_config 给 CycleDetector | 053597a | src/data_generator/day_simulator.py |

## Verification Results

所有验证步骤通过：

1. ✓ CycleDetector 首绿相位 index=2 时正确检测周期边界
2. ✓ CycleDetector 首绿相位非 0 时不误触发 phase 0
3. ✓ CycleDetector 在 tl_id 缺失时回退默认值 0
4. ✓ day_simulator.py 中 CycleDetector 构造调用包含 phase_config
5. ✓ cycle_detector.py 中包含 first_green_phase 字段
6. ✓ cycle_detector.py 中不再硬编码 current_phase == 0

## Next Phase Readiness

**Phase 2 完成状态:**
- ✓ 02-01: 仿真参数修复（3600s 时长、未压缩状态输出）
- ✓ 02-02: CoT 格式训练数据转换
- ✓ 02-03: 动态首绿相位检测（本计划）

**Phase 2 阻塞问题:** 无

**Phase 3 就绪:** ✓ 数据生成流程完整，可开始 SFT/GRPO 训练流水线

## Self-Check: PASSED

验证文件和提交存在性：

```bash
# 文件检查
FOUND: src/data_generator/cycle_detector.py
FOUND: src/data_generator/day_simulator.py

# 提交检查
FOUND: 59f3814 (feat(02-03): 实现 CycleDetector 动态首绿相位检测)
FOUND: 053597a (feat(02-03): DaySimulator 传递 phase_config 给 CycleDetector)
```

所有声明的文件和提交均已验证存在。
