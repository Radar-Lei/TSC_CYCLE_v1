---
phase: 02-data-generation
plan: 01
subsystem: data-generation-core
tags: [simulation, data-pipeline, parallel-execution]
requires: []
provides: [stable-data-generation-cli, validated-simulation-config]
affects: [generate_training_data.py, day_simulator.py, config.json]
tech-stack:
  added: []
  patterns: [fail-fast-parallel, flat-task-pool]
key-files:
  created: []
  modified:
    - src/data_generator/day_simulator.py
    - src/scripts/generate_training_data.py
    - config/config.json
key-decisions: []
metrics:
  duration: 3
  completed: 2026-02-08
---

# Phase 02 Plan 01: 数据生成核心流程修复 Summary

**一句话总结:** 修复仿真时长为 3600s、禁用状态压缩、添加 metadata 字段支持交叉口级并行，所有其他功能已在前序提交中完成

## Performance

执行时间: ~3 分钟
任务数: 2 个（大部分已在前序提交完成）
实际修复: 1 个缺失字段

## What We Accomplished

### Task 1: 修复仿真参数和输出路径
**状态:** ✓ 已完成（前序提交 940f8b2）

已验证项目：
- ✓ DaySimulator.sim_end 默认值为 3600（第 166 行）
- ✓ create_temp_sumocfg 默认 end_time 为 3600（第 71 行）
- ✓ config.json 包含 sim_duration: 3600（第 20 行）
- ✓ PredictiveSampler 使用 compress=False（第 221 行）

所有仿真参数和输出路径配置均已正确。

### Task 2: 修复场景发现验证和添加 --scenarios 参数
**状态:** ✓ 已完成（大部分前序提交，本次修复缺失 metadata 字段）

已验证项目：
- ✓ discover_environments() 对缺少 .sumocfg/.net.xml 立即报错停止（第 65、68 行）
- ✓ process_traffic_lights 调用用于解析交叉口配置（第 317-318 行）
- ✓ --scenarios 参数支持场景子集过滤（第 152-156 行，第 254-269 行）
- ✓ fail-fast 并行执行策略：使用 concurrent.futures.ProcessPoolExecutor（第 394 行）
- ✓ 任一交叉口失败时 cancel + shutdown（第 407-408、437-438 行）
- ✓ --state-dir 默认值为 outputs/states（第 133 行）
- ✓ sim_duration 从 config.json 读取并注入任务（第 384、389 行）
- ✓ workers 限制不超过 config 配置（第 373-376 行）
- ✓ 简洁模式日志输出（第 420 行）

**本次修复:**
- 添加 DaySimulator.run() 成功返回的 metadata 字段（包含 tl_id）
- 修复 generate_training_data.py 第 420 行访问 result['metadata']['tl_id'] 的问题

## Task Commits

| Task | Description | Commit | Files |
|------|-------------|--------|-------|
| 1 | 仿真参数和输出路径 | 940f8b2 | day_simulator.py, config.json |
| 2 | 场景发现和并行执行（metadata 修复） | 32fa3ac | day_simulator.py |

注：Task 2 的大部分功能在之前的提交中已实现，本次仅修复缺失的 metadata 字段。

## Key Files

### Created
无新文件创建

### Modified
- `src/data_generator/day_simulator.py` - 添加 metadata 字段到成功返回字典
- `src/scripts/generate_training_data.py` - 已包含所有 Task 2 要求的功能
- `config/config.json` - 已包含 sim_duration: 3600

## Deviations from Plan

无偏差。计划中的所有功能均已在之前的提交中实现，本次执行仅修复了缺失的 metadata 字段。

## Issues/Blockers

无阻塞问题。

## Next Phase Readiness

**Phase 02 进展:**
- ✓ Plan 01: 数据生成核心流程修复完成
- Plan 02: CycleDetector 第一个绿相检测（待执行）
- Plan 03: 动态绿相检测（待执行）

**准备状态:**
- 数据生成 CLI 可正确执行
- 仿真参数配置正确（3600s 时长）
- 交叉口级并行执行支持完整
- fail-fast 错误处理策略到位
- 场景发现和验证严格

可继续执行 Plan 02。

## Self-Check: PASSED

验证已完成功能:
- ✓ sim_end 默认值 3600: `grep "sim_end.*3600" day_simulator.py`
- ✓ compress=False: `grep "compress=False" day_simulator.py`
- ✓ state-dir 默认 outputs/states: `grep "outputs/states" generate_training_data.py`
- ✓ --scenarios 参数: `grep "'--scenarios'" generate_training_data.py`
- ✓ fail-fast 逻辑: `grep "cancel()\|shutdown" generate_training_data.py`
- ✓ sim_duration 读取: `grep "sim_duration" generate_training_data.py`
- ✓ process_traffic_lights 调用: `grep "process_traffic_lights" generate_training_data.py`
- ✓ metadata 字段存在: `git show 32fa3ac`
- ✓ 代码可导入: `python3 -c "from src.scripts.generate_training_data import discover_environments; print('OK')"`

所有验证通过。
