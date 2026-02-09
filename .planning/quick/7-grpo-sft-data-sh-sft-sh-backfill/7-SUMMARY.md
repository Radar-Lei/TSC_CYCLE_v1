---
phase: quick-7
plan: 01
subsystem: pipeline
tags: [cleanup, grpo-removal, sft-only]
dependency_graph:
  requires: []
  provides: [simplified-sft-pipeline]
  affects: [training-workflow, config-structure]
tech_stack:
  added: []
  patterns: [simplified-pipeline]
key_files:
  created: []
  modified:
    - config/config.json
    - docker/run.sh
  deleted:
    - src/grpo/ (整个目录)
    - src/scripts/train_grpo.py
    - docker/grpo.sh
    - Qwen3_(4B)_GRPO.ipynb
decisions: []
metrics:
  duration: 168s
  completed: 2026-02-09T03:45:53Z
---

# Quick Task 7: GRPO 代码移除与 SFT 流水线简化

**一句话:** 删除所有 GRPO 相关代码,将训练流水线简化为数据生成 → SFT 训练

## 背景

项目不再使用 GRPO 训练,需要清理所有 GRPO 相关代码以减少代码库维护负担并避免混淆。

## 执行内容

### Task 1: 删除所有 GRPO 文件和目录

**删除的文件:**
- `src/grpo/` — 整个 GRPO 模块目录(包含 data_loader.py, format_reward.py, reward_combiner.py, simulation_reward.py, sumo_evaluator.py, trainer.py, __init__.py 等 9 个文件)
- `src/scripts/train_grpo.py` — GRPO 训练入口脚本
- `docker/grpo.sh` — GRPO Docker 启动脚本
- `Qwen3_(4B)_GRPO.ipynb` — GRPO Jupyter notebook

**验证:**
- 所有指定的 GRPO 核心文件已删除
- SFT 流水线文件(src/sft/, src/scripts/train_sft.py, docker/data.sh, docker/sft.sh)完整保留

**Commit:** 3afaabd

### Task 2: 清理 config.json 并简化 docker/run.sh

**config/config.json 修改:**
- 删除 `training.grpo` 对象(包含所有 GRPO 训练超参数)
- 删除 `rewards` 对象(GRPO 奖励权重配置)
- 删除 `paths.grpo_output` 键
- 保留 `training.sft`, `simulation`, `paths` 的其他键

**docker/run.sh 修改:**
- 更新标题: "GRPO 交通信号优化 - 完整训练流程" → "SFT 交通信号优化 - 训练流程"
- 移除 `direct` 阶段(data → grpo)
- 移除 `grpo` 阶段
- 默认 STAGE 从 `direct` 改为 `all`
- 支持的阶段: `all` (data → sft), `data`, `sft`
- 阶段编号: 从 1/3, 2/3, 3/3 改为 1/2, 2/2
- 输出目录显示: 固定显示 SFT 输出,移除 GRPO 输出

**验证:**
- config.json 结构正确(无 grpo/rewards/grpo_output)
- docker/run.sh 无任何 GRPO 引用
- bash 语法检查通过

**Commit:** 73bf89b

## 偏差处理

### 自动修复问题

无偏差 — 计划完全按照预期执行。

## 验证结果

✅ 所有 GRPO 核心文件已删除(src/grpo/, src/scripts/train_grpo.py, docker/grpo.sh, Qwen3_(4B)_GRPO.ipynb)

✅ config.json 仅包含 training.sft, simulation, paths(无 grpo_output)

✅ docker/run.sh 无 GRPO 引用,编排 data → sft 流水线

✅ SFT 流水线文件完整保留

**注:** unsloth_compiled_cache/ 和 outputs/grpo/ 等缓存/输出目录未删除,但不影响代码功能。

## 影响范围

**直接影响:**
- 训练流水线简化为 data → sft 两阶段
- 配置文件结构更清晰
- 代码库减少约 2545 行 GRPO 相关代码

**间接影响:**
- 降低新开发者的学习成本(无 GRPO 干扰)
- 减少配置维护负担
- 简化 Docker 编排逻辑

## 后续建议

1. **清理缓存(可选):** 如需进一步清理,可删除 `unsloth_compiled_cache/UnslothGRPOTrainer.*` 和 `outputs/grpo/`
2. **更新文档:** 如有项目文档提及 GRPO,需同步更新
3. **验证流程:** 执行 `./docker/run.sh` 验证完整 SFT 流水线可正常运行

## Self-Check: PASSED

检查创建/修改的文件:
- ✅ config/config.json 存在且格式正确
- ✅ docker/run.sh 存在且无 GRPO 引用

检查提交记录:
- ✅ 3afaabd: chore(quick-7): 删除所有 GRPO 相关文件和目录
- ✅ 73bf89b: chore(quick-7): 清理 config.json 并简化 docker/run.sh 为 SFT 流水线
