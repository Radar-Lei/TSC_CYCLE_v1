---
phase: 01-code-cleanup
plan: 01
subsystem: data-generation
tags: [cleanup, refactor, config, simulation]
requires: []
provides:
  - simplified-day-simulator
  - cleaned-config-structure
affects:
  - 02-data-generation
tech-stack:
  added: []
  patterns: [simplified-simulation-flow]
key-files:
  created: []
  modified:
    - src/data_generator/day_simulator.py
    - src/data_generator/models.py
    - src/grpo/data_loader.py
    - src/grpo/__init__.py
    - config/config.json
    - config/__init__.py
  deleted:
    - src/data_generator/time_period.py
    - config/schema.json
    - config/validate_config.py
key-decisions:
  - title: Remove time period configuration entirely
    rationale: Fixed 3600s simulation duration makes time periods unnecessary
    impact: Simplified codebase, removed ~370 lines of unused code
    alternatives: Keep but disable - rejected for code cleanliness
  - title: Delete schema validation
    rationale: Single config.json source, no runtime validation needed
    impact: Removed external validation dependency, config is self-documenting
duration: 6m
completed: 2026-02-07
---

# Phase 01 Plan 01: Remove Time Period Configuration Summary

清理时段配置相关代码和冗余配置验证逻辑

## Performance

**Duration:** 6 minutes
**Started:** 2026-02-07T15:16:44Z
**Completed:** 2026-02-07T15:22:56Z
**Tasks:** 2/2 (100%)
**Files modified:** 6
**Files deleted:** 3
**Lines removed:** ~670

## Accomplishments

移除了所有时段配置（早高峰/晚高峰/平峰）相关代码，简化了 DaySimulator 仿真流程，删除了不再使用的 schema 验证逻辑。

**What was built:**
1. 简化的 DaySimulator - 移除时段遍历，采用直接的预热+采样流程
2. 清洁的配置结构 - config.json 作为唯一配置源，无冗余字段
3. 精简的数据模型 - TrainingSample 不再包含 time_period 元数据

**Key improvements:**
- 仿真流程从"遍历时段"简化为"预热 → 采样 → 结束"
- 移除 `get_simulation_ranges()` 函数及相关时段计算逻辑
- 移除 `filter_by_time_period()` 数据过滤函数
- 配置文件从 ~350 行简化为 32 行（包含 schema.json 和 validate_config.py 的删除）

## Task Commits

| Task | Description | Commit | Files Changed |
|------|-------------|--------|---------------|
| 1 | 删除时段配置模块和清理引用 | a2233b0 | 5 files: day_simulator.py, models.py, data_loader.py, __init__.py, time_period.py (deleted) |
| 2 | 删除 schema 验证和清理配置文件 | a3a8e15 | 4 files: schema.json (deleted), validate_config.py (deleted), config.json, __init__.py |

## Files Created

None - this was a cleanup plan (deletions only).

## Files Modified

**src/data_generator/day_simulator.py:**
- Removed `from src.data_generator.time_period import identify_time_period` import
- Deleted `get_simulation_ranges()` function (L70-L108)
- Removed `self.time_ranges` and `self.simulation_ranges` from `__init__`
- Simplified `run()` method:
  - Removed time range loop structure
  - Direct warmup phase (0 → warmup_steps)
  - Direct sampling phase (warmup_steps → sim_end)
  - Removed `time_period = identify_time_period(sim_time)` call
  - Removed 'time_period' from TrainingSample metadata
- Updated module docstring (removed get_simulation_ranges reference)

**src/data_generator/models.py:**
- Updated TrainingSample docstring: removed "time_period" from metadata description

**src/grpo/data_loader.py:**
- Deleted `filter_by_time_period()` function (L89-L117)
- Deleted filter_by_time_period test code from `__main__` block (L204-L218)
- Updated module docstring (removed filter_by_time_period reference)

**src/grpo/__init__.py:**
- Removed `filter_by_time_period` from imports (L44)
- Removed `filter_by_time_period` from `__all__` exports (L75)

**config/config.json:**
- Removed `"time_ranges": []` from simulation section (L20)

**config/__init__.py:**
- Cleared imports (removed validate_config, load_config, get_config_value)
- Cleared `__all__` exports

## Files Deleted

**src/data_generator/time_period.py:**
- Entire module deleted (118 lines)
- Contained: TimePeriod enum, identify_time_period(), get_time_period_stats(), sim_time_to_hours()

**config/schema.json:**
- Entire file deleted (187 lines)
- Was: JSON Schema validation specification

**config/validate_config.py:**
- Entire file deleted (153 lines)
- Was: Configuration validation script with jsonschema dependency

## Decisions Made

**1. Remove time period configuration entirely**
- **Context:** Original design supported early/evening/off-peak time periods for targeted sampling
- **Decision:** Delete all time period logic (enum, identification, filtering)
- **Rationale:** Fixed 3600s simulation makes time periods unnecessary; adds complexity without value
- **Impact:** -237 lines of code, simpler data model, cleaner simulation flow
- **Alternatives considered:** Keep but disable → rejected (dead code adds maintenance burden)

**2. Delete schema validation infrastructure**
- **Context:** schema.json + validate_config.py provided JSON Schema validation
- **Decision:** Delete both files and config/__init__.py wrapper
- **Rationale:** Single config.json is self-documenting; no runtime validation needed; reduces dependencies
- **Impact:** -340 lines of config code, removed jsonschema dependency
- **Alternatives considered:** Keep for future → rejected (YAGNI principle)

**3. Simplify DaySimulator flow to single-pass**
- **Context:** Original flow: for each time_range → fast-forward → warmup → sample
- **Decision:** Direct flow: warmup → sample until sim_end
- **Rationale:** With no time ranges, multi-pass logic is unnecessary overhead
- **Impact:** Cleaner run() method, easier to understand and debug
- **Trade-offs:** None - strictly better with current requirements

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Cleared config/__init__.py imports**
- **Found during:** Task 2 validation
- **Issue:** config/__init__.py imported from deleted validate_config.py, would cause ImportError
- **Fix:** Cleared imports and __all__ exports in config/__init__.py
- **Files modified:** config/__init__.py
- **Commit:** a3a8e15 (included in Task 2 commit)
- **Rationale:** Blocking issue - config module would fail to import without this fix

No other deviations - plan executed exactly as written after fixing the blocking import issue.

## Issues Encountered

**None.** All tasks completed without issues.

The only adjustment was proactively fixing the config/__init__.py import, which was handled automatically under deviation rule 3 (auto-fix blocking issues).

## Next Phase Readiness

**Ready for Phase 01 Plan 02** (Refactor parallel execution structure)

**Dependencies provided:**
✓ Simplified DaySimulator.run() flow (no time ranges to complicate parallel logic)
✓ Cleaned config structure (simulation section only has parallel_workers, warmup_steps, max_rou_files)

**Concerns for next plan:**
- DaySimulator still has nested parallel logic (交叉口级并行) that needs refactoring
- Port assignment uses random range (20000-50000) - may need coordination in parallel mode

**Blockers:** None

**Validation:** All verification checks passed:
- `grep` for time period references: ✓ No results
- File deletions: ✓ time_period.py, schema.json, validate_config.py deleted
- JSON validity: ✓ config.json parses correctly
- Import check: ✓ No broken imports

## Self-Check: PASSED

All created files verified to exist.
All commits verified to exist in git log:
- a2233b0 ✓
- a3a8e15 ✓
