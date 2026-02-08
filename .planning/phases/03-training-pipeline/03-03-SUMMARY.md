---
phase: 03-training-pipeline
plan: 03
subsystem: training
tags: [grpo, reinforcement-learning, trl, unsloth, bf16, lora, reward-function]

# Dependency graph
requires:
  - phase: 03-01
    provides: SFT trained model with LoRA adapter at outputs/sft/final/
  - phase: 03-02
    provides: graded_format_reward (3-level grading), NaN-safe simulation reward
  - phase: 02-data-generation
    provides: Training data in outputs/training/ (chat format JSONL)
provides:
  - GRPO model loading with bf16 full precision (no 4-bit quantization)
  - GRPO training script using graded_format_reward
  - Training log output to terminal + {output_dir}/training.log
  - Checkpoint recovery via --resume-from argument
  - Rolling checkpoint deletion (save_total_limit=3)
affects: [04-inference, grpo-deployment, model-evaluation]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "bf16 full precision LoRA training (no quantization)"
    - "Multi-reward GRPO (format + validity + simulation)"
    - "Graded format reward (3-level: think/JSON/fields)"
    - "Logging to both file and terminal"
    - "Checkpoint recovery with auto-detection"

key-files:
  created: []
  modified:
    - src/grpo/trainer.py
    - src/scripts/train_grpo.py

key-decisions:
  - "Use bf16 full precision instead of 4-bit quantization (locked decision from phase planning)"
  - "Read LoRA config from adapter_config.json instead of hardcoding"
  - "Use graded_format_reward with 3-level grading (aligned with Phase 2 CoT placeholder strategy)"
  - "Default data path changed to outputs/training (aligned with Phase 2 output)"
  - "Add logging to both file and terminal for better debugging"
  - "Support checkpoint recovery via --resume-from"

patterns-established:
  - "LoRA parameter loading: read from adapter_config.json and pass explicitly to get_peft_model"
  - "Training config: bf16=True, save_total_limit=3, logging_dir template expansion"
  - "Reward function migration: remove old exact/approximate matching, use graded reward"
  - "Logging pattern: configure both file handler and stream handler at script start"

# Metrics
duration: 4min
completed: 2026-02-08
---

# Phase 03 Plan 03: GRPO Training Fix Summary

**GRPO trainer with bf16 precision, graded format reward (3-level), and logging to file + terminal**

## Performance

- **Duration:** 4 min
- **Started:** 2026-02-08T05:06:00Z
- **Completed:** 2026-02-08T05:10:00Z (approximate)
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- GRPO model loading uses bf16 full precision (load_in_4bit=False) instead of 4-bit quantization
- LoRA parameters (r, lora_alpha, target_modules) read from adapter_config.json and passed explicitly
- Training script uses graded_format_reward (3-level grading: think/JSON/fields) instead of old exact/approximate matching
- Training logs output to both terminal and {output_dir}/training.log for better debugging
- Checkpoint recovery supported via --resume-from with auto-detection of existing checkpoints
- Rolling checkpoint deletion (save_total_limit=3) to manage disk space

## Task Commits

Each task was committed atomically:

1. **Task 1: 修复 GRPO 模型加载和训练器配置** - `02fc590` (fix)
2. **Task 2: 修复 GRPO 训练入口脚本，更新奖励函数引用和添加日志** - `cc3d47b` (fix)

## Files Created/Modified
- `src/grpo/trainer.py` - Updated load_sft_model to use bf16 (load_in_4bit=False), read LoRA config from adapter_config.json, added GRPOConfig fields (bf16, save_total_limit, logging_dir)
- `src/scripts/train_grpo.py` - Replaced old reward imports with graded_format_reward, added logging to file + terminal, added --resume-from support, changed default data_dir to outputs/training

## Decisions Made

1. **bf16 full precision**: Changed load_in_4bit=True to False (locked decision from phase planning - "去掉 4-bit 量化，使用 bf16 全精度 LoRA")
2. **LoRA config loading**: Read r, lora_alpha, target_modules from adapter_config.json instead of relying on auto-detection (more explicit, less error-prone)
3. **Graded reward migration**: Replaced match_format_exactly/match_format_approximately with graded_format_reward (3-level grading aligned with Phase 2 CoT placeholder strategy)
4. **Data path alignment**: Changed default data_dir from data/training to outputs/training (matches Phase 2 output path from 02-03)
5. **Dual logging**: Added logging.basicConfig with both FileHandler and StreamHandler for comprehensive debugging
6. **Checkpoint recovery**: Added --resume-from argument and auto-detection logic for existing checkpoints

## Deviations from Plan

None - plan executed exactly as written.

All changes were specified in the plan:
- Task 1: bf16 precision, LoRA config loading, GRPOConfig field additions
- Task 2: reward function migration, logging, checkpoint recovery, path fixes

## Issues Encountered

None - implementation proceeded smoothly. All verification steps passed.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

**Ready for next phase:**
- GRPO training script is executable with corrected configuration
- Uses SFT model from outputs/sft/final/ (Phase 03-01 output)
- Uses training data from outputs/training/ (Phase 2 output)
- Reward function stack: graded_format_reward + check_phase_validity + compute_simulation_reward
- Logging and checkpoint recovery support in place

**Blockers:**
- None

**Next steps:**
- Run GRPO training to verify end-to-end flow
- Evaluate trained model performance
- Proceed to Phase 4 (inference/deployment)

---
*Phase: 03-training-pipeline*
*Completed: 2026-02-08*

## Self-Check: PASSED

All files and commits verified:
- ✓ FOUND: src/grpo/trainer.py
- ✓ FOUND: src/scripts/train_grpo.py
- ✓ FOUND: 02fc590 (Task 1 commit)
- ✓ FOUND: cc3d47b (Task 2 commit)
