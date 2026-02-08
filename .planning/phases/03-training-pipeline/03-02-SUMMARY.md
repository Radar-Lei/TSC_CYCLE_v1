---
phase: 03-training-pipeline
plan: 02
subsystem: training
tags: [grpo, reward-function, trl, sumo-evaluation]

# Dependency graph
requires:
  - phase: 02-data-generation
    provides: Training samples in outputs/training/ with CoT empty placeholder strategy
provides:
  - Graded format reward (3-level scoring: think tags / JSON parseable / complete fields)
  - NaN skip strategy for simulation failures (no gradient computation on SUMO crashes)
  - GRPO data loader with correct path alignment to Phase 2 output
affects: [03-03-grpo-training, future-training-iterations]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Three-level graded reward (0.0 → 0.5 → 1.5 → 3.0) for progressive format learning"
    - "NaN skip strategy for failed evaluations (TRL automatic gradient exclusion)"

key-files:
  created: []
  modified:
    - src/grpo/format_reward.py
    - src/grpo/simulation_reward.py
    - src/grpo/data_loader.py
    - src/grpo/__init__.py

key-decisions:
  - "Unified graded_format_reward replaces binary exact/approximate matching"
  - "Simulation failures return NaN instead of fixed negative rewards"
  - "Empty <think></think> tags receive Level 1 credit (CoT placeholder strategy)"

patterns-established:
  - "Graded reward scoring: incremental credit for partial correctness"
  - "NaN-based sample skipping: let framework handle gradient exclusion"

# Metrics
duration: 7min
completed: 2026-02-08
---

# Phase 03 Plan 02: GRPO Reward Refactor Summary

**Three-level graded format reward (think/JSON/fields) and NaN skip for simulation failures, aligned with Phase 2 CoT placeholder strategy**

## Performance

- **Duration:** 7 min
- **Started:** 2026-02-08T04:51:56Z
- **Completed:** 2026-02-08T04:58:51Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Graded format reward system with three progressive levels (0.5 / 1.5 / 3.0 total)
- NaN skip strategy for simulation failures (automatic gradient exclusion by TRL)
- Data loader path alignment to Phase 2 outputs (outputs/training/)

## Task Commits

Each task was committed atomically:

1. **Task 1: 重构格式奖励为分级评分系统** - `d50971e` (refactor)
2. **Task 2: 修复仿真奖励的失败跳过机制和数据加载路径** - `337f0c2` (fix)

## Files Created/Modified
- `src/grpo/format_reward.py` - Replaced binary exact/approximate matching with unified graded_format_reward function (3 levels)
- `src/grpo/simulation_reward.py` - Returns float('nan') on parse/evaluation failure instead of 0.0/-1.0, added evaluation statistics logging
- `src/grpo/data_loader.py` - Changed default data_dir from "data/training" to "outputs/training"
- `src/grpo/__init__.py` - Updated exports to use graded_format_reward instead of old functions

## Decisions Made

**1. Three-level graded format scoring:**
- Level 0 (0.0): No format features
- Level 1 (+0.5): `<think>...</think>` tags present (content can be empty per CoT placeholder strategy)
- Level 2 (+1.0, total 1.5): JSON array parseable after `</think>`
- Level 3 (+1.5, total 3.0): Complete fields (phase_id int, final float in range 5-120)

Rationale: Progressive credit gives model finer-grained learning signal than binary pass/fail.

**2. NaN skip strategy for simulation failures:**
- JSON parse failure: return `float('nan')`
- Evaluation failure (SUMO crash/timeout): return `float('nan')`
- TRL GRPOTrainer automatically excludes NaN values from gradient computation

Rationale: Avoids incorrect gradients from failed evaluations. Previous approach (-1.0 penalty) could mislead training.

**3. Data path alignment:**
- Changed load_training_data default from "data/training" to "outputs/training"
- Matches Phase 2 generate_training_data.py output location

Rationale: Eliminate path mismatch between data generation and training phases.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None - all tasks completed without problems.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

**Ready for Phase 03 Plan 03 (GRPO Training):**
- ✓ Format reward function signature compatible with TRL GRPOTrainer reward_funcs
- ✓ Simulation reward returns NaN for failed samples (gradient exclusion)
- ✓ Data loader reads from correct path (outputs/training/)
- ✓ Graded scoring provides fine-grained learning signal

**Note:** Graded format reward weight (0.2) and simulation reward weight (0.8) configuration will be set in Plan 03-03 train_grpo.py.

---
*Phase: 03-training-pipeline*
*Completed: 2026-02-08*

## Self-Check: PASSED

All claimed files and commits verified:
- ✓ src/grpo/format_reward.py exists
- ✓ src/grpo/simulation_reward.py exists
- ✓ src/grpo/data_loader.py exists
- ✓ src/grpo/__init__.py exists
- ✓ Commit d50971e exists (Task 1)
- ✓ Commit 337f0c2 exists (Task 2)
