---
phase: 03-grpo-training
plan: 01
subsystem: training
tags: [grpo, baseline, sumo, reward-normalization, multiprocessing]

# Dependency graph
requires:
  - phase: 02-grpo-data-preparation
    provides: grpo_train.jsonl with prompt messages and state_file metadata
provides:
  - config.json with training.grpo section (hyperparameters, reward weights)
  - Baseline precomputation pipeline for SUMO simulation
  - paths.grpo_baseline, paths.grpo_output, paths.grpo_data_dir configuration
affects: [03-02-grpo-training, reward-calculation]

# Tech tracking
tech-stack:
  added: [multiprocessing (ProcessPoolExecutor), traci baseline computation]
  patterns: [Docker shell script pattern for GRPO baseline, scenario-to-sumocfg mapping]

key-files:
  created:
    - src/grpo/__init__.py
    - src/grpo/baseline.py
    - docker/grpo_baseline.sh
  modified:
    - config/config.json

key-decisions:
  - "使用 outputs/sft/model 作为 GRPO 训练的基础模型"
  - "num_generations=4 用于 GRPO 采样"
  - "use_vllm=False (不添加 vllm_sampling_params)"
  - "Baseline 脚本通过 scenario 名称映射到对应的 sumocfg 路径"
  - "Baseline 计算去重 state_file 避免重复计算"

patterns-established:
  - "GRPO reward 配置集中在 config.json training.grpo.reward"
  - "Baseline 预计算使用 ProcessPoolExecutor 并行处理"
  - "arterial4x4_* 场景映射到 sumo_simulation/arterial4x4/{scenario}/arterial4x4.sumocfg"
  - "chengdu 场景映射到 sumo_simulation/environments/chengdu/chengdu.sumocfg"

# Metrics
duration: 4min
completed: 2026-02-09
---

# Phase 03 Plan 01: GRPO 配置和 Baseline 预计算 Summary

**config.json 添加 GRPO 训练超参数和 reward 权重配置，创建 baseline 预计算流程用于 SUMO 仿真 reward 归一化**

## Performance

- **Duration:** 4min 6s
- **Started:** 2026-02-09T19:50:39Z
- **Completed:** 2026-02-09T19:54:45Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- 在 config.json 中添加完整的 training.grpo 配置（模型参数、训练超参数、reward 子配置）
- 添加 paths.grpo_data_dir、paths.grpo_output、paths.grpo_baseline 路径配置
- 创建 src/grpo/baseline.py 基线预计算脚本，支持多进程并行处理
- 创建 docker/grpo_baseline.sh Docker 入口脚本遵循 data.sh 模式
- Baseline 脚本自动去重 state_file 并映射到正确的 sumocfg 路径

## Task Commits

Each task was committed atomically:

1. **Task 1: Add GRPO configuration to config.json** - `cdb097a` (feat)
2. **Task 2: Create baseline precomputation pipeline** - `af1dd77` (feat)

## Files Created/Modified
- `config/config.json` - 添加 training.grpo 配置和 GRPO 相关路径
- `src/grpo/__init__.py` - GRPO 模块包初始化
- `src/grpo/baseline.py` - Baseline 预计算脚本（支持多进程、scenario 映射、state 去重）
- `docker/grpo_baseline.sh` - Docker baseline 预计算入口脚本

## Decisions Made

1. **使用 outputs/sft/model 作为 GRPO base model** - 基于 SFT 训练后的模型进行 GRPO 强化学习
2. **num_generations=4** - GRPO 采样时每个 prompt 生成 4 个候选方案
3. **use_vllm=False** - 根据用户决策不使用 vllm，不添加 vllm_sampling_params
4. **Reward 权重配置** - sumo_throughput_weight=0.6, sumo_queue_weight=0.4, 格式 exact_score=3.0
5. **Baseline 去重策略** - 按 state_file 去重避免重复计算相同状态
6. **Scenario 映射规则** - arterial4x4_* 和 chengdu 场景分别映射到不同的 sumocfg 路径

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- GRPO 配置已完成，包含所有必需的超参数和 reward 配置
- Baseline 预计算流程已就绪，可通过 `./docker/grpo_baseline.sh` 执行
- 下一步需要创建 GRPO 训练脚本（使用 baseline.json 进行 reward 归一化）

## Self-Check: PASSED

All files verified:
- ✓ config/config.json
- ✓ src/grpo/__init__.py
- ✓ src/grpo/baseline.py
- ✓ docker/grpo_baseline.sh

All commits verified:
- ✓ cdb097a (Task 1)
- ✓ af1dd77 (Task 2)

---
*Phase: 03-grpo-training*
*Completed: 2026-02-09*
