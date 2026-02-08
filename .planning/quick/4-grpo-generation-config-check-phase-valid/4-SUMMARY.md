---
phase: quick-4
plan: 01
subsystem: grpo-training
tags: [grpo, generation-config, phase-validity, simulation-optimization]
dependency-graph:
  requires: [quick-3]
  provides: [grpo-generation-config-fix, phase-validity-trl-compat, simulation-skip-invalid]
  affects: [src/grpo/trainer.py, src/grpo/format_reward.py, src/grpo/simulation_reward.py]
tech-stack:
  patterns: [phase-config-extraction-from-prompt, pre-simulation-validation]
key-files:
  modified:
    - src/grpo/trainer.py
    - src/grpo/format_reward.py
    - src/grpo/simulation_reward.py
decisions:
  - temperature 0.9 作为 GRPO 探索温度 (覆盖 Qwen3 默认 0.6)
  - phase_config 从 prompt JSON 自动提取而非外部传入
  - phase 不合法返回 -1.0 惩罚 (而非 NaN 跳过,因为无效相位是模型可学习的错误)
metrics:
  duration: 10 min
  completed: 2026-02-08
---

# Quick Task 4: GRPO generation_config / check_phase_validity / simulation skip Summary

修复 GRPO 训练三个关键问题: Qwen3 generation_config 默认值覆盖训练参数、check_phase_validity 签名不兼容 TRL、phase 不合法仍触发 SUMO 仿真

## Changes Made

### Task 1: 修复 generation_config 默认值 + GRPOConfig.temperature (fd17130)

- `GRPOConfig.temperature` 默认值从 `1.0` 改为 `0.9`
- `load_base_model()` 在 `from_pretrained` 后覆盖 `generation_config`:
  - `max_length=2048` (匹配 max_seq_length,覆盖 Qwen3 默认 262144)
  - `temperature=0.9` (GRPO 探索温度,覆盖 Qwen3 默认 0.6)
  - `top_p=0.95`
- `load_sft_model()` 同样添加 generation_config 覆盖
- 更新自测试断言

### Task 2: 重构 check_phase_validity 签名兼容 TRL (749b451)

- 新增 `extract_phase_config_from_prompt(prompt)` 辅助函数:
  - 支持 conversational (List[Dict]) 和纯文本 (str) 两种 prompt 格式
  - 从 prompt JSON 中解析 `phase_waits` 字段
  - 构建 `{phase_id: {min_green, max_green}}` 格式
- `check_phase_validity` 签名从 `(completions, phase_config, **kwargs)` 改为 `(completions, **kwargs)`
  - 从 `kwargs["prompts"]` 自动提取 phase_config
  - phase_config 提取失败时返回 0.0 (不奖不罚)
- 完善自测试覆盖有效/无效/解析失败三种情况

### Task 3: phase 不合法时跳过 SUMO 仿真 (7f69747)

- 新增 `is_plan_phase_valid(plan, phase_config_dict)` 辅助函数
- `compute_simulation_reward` 在 SUMO 仿真前先检查 phase 有效性
- 使用 `skip_indices` 字典记录需要跳过的索引
- 不合法的 completion 直接返回 `-1.0` 惩罚,不触发 SUMO 仿真
- 打印跳过统计信息

## Deviations from Plan

None - plan executed exactly as written.

## Verification Results

- GRPOConfig().temperature == 0.9: PASS
- create_sampling_params temperature == 0.9: PASS
- check_phase_validity (completions, **kwargs) 签名: PASS
- simulation_reward import (无循环导入): PASS
- is_plan_phase_valid 有效/无效测试: PASS

## Self-Check: PASSED

All 3 files exist, all 3 commits verified (fd17130, 749b451, 7f69747).
