---
phase: 04-simple-grpo-reward
plan: 01
subsystem: rl-reward
tags: [grpo, reward, parsing, constraints, saturation]

requires:
  - phase: 03-assembly-export
    provides: "SFT model artifact and stable output protocol"
provides:
  - "src/grpo_simple/rewards.py — 简化版 reward 核心"
  - "tests/test_grpo_simple_rewards.py — reward 行为测试"
  - "config/config.json — grpo_simple reward 配置"
affects: [05-01, grpo-simple-training]

tech-stack:
  added: [python, pytest]
  patterns: [tag-based-parsing, constraint-validation, saturation-target-scoring]

key-files:
  created:
    - src/grpo_simple/__init__.py
    - src/grpo_simple/rewards.py
    - tests/test_grpo_simple_rewards.py
  modified:
    - config/config.json

key-decisions:
  - "复用现有 <end_working_out><SOLUTION> 协议，不把 reward 重新耦合到 SUMO"
  - "目标绿灯时间按 round(max_green * pred_saturation) 计算，再裁剪到 [min_green, max_green]"
  - "简化版 reward 与完整版 grpo/rewards.py 物理隔离到 src/grpo_simple/"

patterns-established:
  - "reward 配置与训练配置分离到 training.grpo_simple"
  - "prompt 中直接解析 phase_waits，无需 baseline 或仿真回放"

requirements-completed: [FORM-01, FORM-02, CONS-01, CONS-02, SATR-01, SATR-02]

duration: 22min
completed: 2026-04-02
---

# Phase 04 Plan 01: Simplified Reward Summary

**实现了不依赖 SUMO 的简化版 GRPO reward：覆盖 completion 解析、格式匹配、约束校验和饱和度比例目标打分。**

## Performance

- **Duration:** 22 min
- **Completed:** 2026-04-02T16:21:01Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- 创建 `src/grpo_simple/rewards.py`，实现 `extract_solution_from_completion`、`check_constraints`、`calculate_target_green`、`saturation_proportional_reward`
- 将 reward 配置独立加入 `config/config.json > training.grpo_simple.reward`
- 新增 `tests/test_grpo_simple_rewards.py`，覆盖命中目标、偏离目标、越界、顺序错误、格式检查
- 通过 `pytest -q tests/test_grpo_simple_rewards.py` 和 `python -m py_compile` 完成自动验证

## Files Created/Modified

- `src/grpo_simple/rewards.py` - 简化版 GRPO reward 核心
- `tests/test_grpo_simple_rewards.py` - reward 单元测试
- `config/config.json` - `training.grpo_simple.reward` 配置

## Decisions Made

- 简化版 reward 不再依赖 baseline 或 SUMO 仿真结果，只依据 prompt 中的 `phase_waits`
- 格式与约束检查继续复用现有标签协议和 phase 列表 JSON 约束
- 饱和度 reward 采用相对距离评分，使更接近目标分配的 completion 得到更高 reward

## Deviations from Plan

None - plan executed as intended.

## Issues Encountered

None blocking. 验证阶段确认 reward 与测试均可在宿主机直接运行，不需要额外容器依赖。

## User Setup Required

None.

## Next Phase Readiness

- `src/grpo_simple/rewards.py` 已可被 `src/grpo_simple/train.py` 直接引用
- `tests/test_grpo_simple_rewards.py` 可作为 Phase 5 基础验证的一部分持续复用

---
*Phase: 04-simple-grpo-reward*
*Completed: 2026-04-02*
