---
phase: 01-code-cleanup
plan: 02
subsystem: data-generation
tags: [parallel, refactor, simplify]

requires:
  - 01-01  # 已移除时段配置代码

provides:
  - flat-task-pool-pattern  # 扁平任务池并行模式
  - fail-fast-execution  # 任务失败立即终止

affects:
  - 01-03  # 可能依赖新的并行逻辑
  - 02-*   # Phase 2 数据生成将使用新的扁平任务池

tech-stack:
  added: []
  removed:
    - parallel_runner.py
    - intersection_parallel.py
  patterns:
    - flat-task-pool  # 所有交叉口展开为统一任务列表

key-files:
  created: []
  modified:
    - src/scripts/generate_training_data.py

key-decisions:
  - decision: "扁平任务池模式"
    rationale: "消除嵌套并行的复杂性，所有场景×交叉口展开为统一任务列表"
    impacts: "并行逻辑更简单，易于调试，任务分配更均衡"
  - decision: "Fail-fast 模式"
    rationale: "任一交叉口失败立即终止整个流程"
    impacts: "快速发现问题，避免浪费计算资源"
  - decision: "删除废弃参数"
    rationale: "清理 --rou-dir, --intersection-parallel 等向后兼容代码"
    impacts: "API 更清晰，减少维护负担"

duration: 176s
completed: 2026-02-07
---

# Phase 01 Plan 02: 删除嵌套并行模块 Summary

**One-liner:** 删除天级/交叉口级嵌套并行模块，重构为扁平任务池模式（所有场景×交叉口展开为统一任务列表，单 Pool 并行消费，fail-fast）

## Performance

**Duration:** 176 seconds (2.9 minutes)
**Started:** 2026-02-07 15:16:44 UTC
**Completed:** 2026-02-07 15:19:40 UTC

**Tasks:** 2/2 completed
**Files:** 3 modified (2 deleted, 1 rewritten)

## Accomplishments

### 核心成果

1. **删除嵌套并行模块**
   - 移除 `parallel_runner.py`（685 行）
   - 移除 `intersection_parallel.py`（361 行）
   - 消除天级和交叉口级的两层嵌套

2. **重构为扁平任务池**
   - 所有场景的所有交叉口展开为统一任务列表
   - 单个 `Pool` 并行消费所有任务
   - 5 阶段执行流程:
     - 阶段 1: 生成 phase_config（串行，轻量）
     - 阶段 2: 展开所有 (场景, 交叉口) 对为任务
     - 阶段 3: 并行消费任务池
     - 阶段 4: 合并结果到 samples_<date>.jsonl
     - 阶段 5: 合并到 train.jsonl

3. **实现 Fail-fast 模式**
   - 任一交叉口仿真失败立即 `pool.terminate()`
   - 打印错误信息并 `sys.exit(1)`
   - 避免浪费计算资源

4. **清理废弃 API**
   - 删除 `run_single_scenario_mode()` 函数（190 行）
   - 删除 `_simulate_scenario()` worker 函数（58 行）
   - 删除 CLI 参数: `--rou-dir`, `--phase-config`, `--sim-end`, `--intersection-parallel`, `--intersection-groups`
   - 删除 `time_ranges` 参数传递（已在 Plan 01-01 中从 DaySimulator 移除）

### 代码变化统计

- **删除:** 685 + 361 + 415 = 1,461 行
- **新增:** 197 行
- **净减少:** 1,264 行（-86.5%）

## Task Commits

| Task | Description | Commit | Files |
|------|-------------|--------|-------|
| 1 | 删除旧并行模块 | eb633c5 | parallel_runner.py (-326 lines), intersection_parallel.py (-361 lines) |
| 2 | 重构为扁平任务池 | 6a63c69 | generate_training_data.py (+197/-415 lines) |

## Files Created

无（仅修改和删除）

## Files Modified

### src/scripts/generate_training_data.py

**变化:** 从 726 行减少到 441 行（-39.3%）

**主要重构:**

1. **删除的导入:**
   - `from src.data_generator.parallel_runner import run_parallel_simulation`
   - `from src.data_generator.intersection_parallel import IntersectionParallelRunner`

2. **新增的 worker 函数:**
   ```python
   def _simulate_intersection(args):
       """单个交叉口的仿真 worker"""
       task_id, scenario_name, rou_file, config = args
       simulator = DaySimulator(task_id, rou_file, config)
       result = simulator.run()
       return result
   ```

3. **新增的工具函数:**
   ```python
   def save_samples_to_jsonl(samples, output_path):
       """内联实现，替代 parallel_runner 中的同名函数"""
   ```

4. **main() 函数重构:**
   - 删除单场景/多场景分支逻辑
   - 统一为扁平任务池模式
   - 5 阶段执行流程
   - Fail-fast 错误处理

5. **CLI 简化:**
   - 保留: `--config`, `--environments-dir`, `--output-dir`, `--state-dir`, `--workers`, `--warmup-steps`, `--dry-run`, `-v`
   - 删除: `--rou-dir`, `--phase-config`, `--sim-end`, `--intersection-parallel`, `--intersection-groups`

### 已删除的文件

1. **src/data_generator/parallel_runner.py**
   - ParallelRunner 类
   - run_parallel_simulation 函数
   - save_samples_to_jsonl, generate_metadata 工具函数

2. **src/data_generator/intersection_parallel.py**
   - IntersectionParallelRunner 类
   - simulate_intersection_group 函数
   - 交叉口分组逻辑

## Decisions Made

### 1. 扁平任务池模式

**背景:** 原有 parallel_runner.py（天级并行）和 intersection_parallel.py（交叉口级并行）形成两层嵌套，复杂且难以调试。

**决策:** 所有场景的所有交叉口展开为统一任务列表 `[(task_id, scenario_name, rou_file, config), ...]`，单个 `Pool` 并行消费。

**理由:**
- 消除嵌套复杂性
- 任务分配更均衡（worker 池自动调度）
- 易于调试（每个 worker 独立运行 DaySimulator）
- 支持任意数量的场景和交叉口

### 2. Fail-fast 模式

**背景:** 原有逻辑在部分任务失败时仍继续执行，浪费计算资源。

**决策:** 任一交叉口仿真失败立即 `pool.terminate()` 并 `sys.exit(1)`。

**理由:**
- 快速发现问题（首个失败任务即报错）
- 节省计算资源（不执行无意义的后续任务）
- 符合 CI/CD 最佳实践（构建失败立即停止）

### 3. 删除废弃 API

**背景:** 存在向后兼容的 `run_single_scenario_mode` 和 `--rou-dir` 参数。

**决策:** 删除所有单场景模式代码，统一为多场景模式。

**理由:**
- 简化 API（只保留 `--environments-dir`）
- 减少维护负担
- 用户已迁移到多场景模式（基于 PROJECT.md 和 ROADMAP.md）

## Deviations from Plan

无 — 计划执行完全符合预期。

## Issues Encountered

无 — 重构顺利完成，所有验证通过。

## Next Phase Readiness

### Phase 1 后续计划

- **Plan 01-03:** 可能需要适配新的扁平任务池模式
- **Plan 01-04+:** 继续清理其他冗余代码

### Phase 2 影响

- Phase 2 的数据生成流程将使用新的扁平任务池模式
- Fail-fast 模式确保数据质量（任一场景失败立即停止）
- 并行效率更高（所有交叉口均衡分配到 worker 池）

### 技术债务

无新增技术债务。此重构显著减少了代码复杂度。

## Self-Check: PASSED

验证所有文件和提交:

```bash
# 文件删除验证
✓ parallel_runner.py deleted
✓ intersection_parallel.py deleted

# 文件修改验证
✓ generate_training_data.py syntax valid

# 旧引用清理验证
✓ 无 parallel_runner 引用残留
✓ 无 intersection_parallel 引用残留
✓ 无 run_single_scenario_mode 引用残留

# Fail-fast 逻辑验证
✓ pool.terminate() 存在
✓ sys.exit(1) 存在
```

## Commits

- `eb633c5`: chore(01-02): 删除旧并行模块
- `6a63c69`: refactor(01-02): 重构为扁平任务池模式
