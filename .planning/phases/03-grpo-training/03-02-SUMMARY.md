---
phase: 03-grpo-training
plan: 02
subsystem: grpo-training
tags: [grpo, rewards, training, sumo-simulation, reinforcement-learning]

dependency-graph:
  requires:
    - phase: 03
      plan: 01
      artifact: baseline.json
      reason: "Baseline metrics for reward normalization"
    - phase: 01
      plan: 03
      artifact: outputs/sft/model
      reason: "SFT-trained model as GRPO starting point"
    - phase: 02
      plan: 01
      artifact: grpo_train.jsonl
      reason: "GRPO training data with prompts and metadata"
  provides:
    - artifact: src/grpo/rewards.py
      interface: "5 reward functions for GRPOTrainer"
      consumers: ["src/grpo/train.py"]
    - artifact: src/grpo/train.py
      interface: "GRPO training pipeline"
      consumers: ["docker/grpo_train.sh"]
    - artifact: docker/grpo_train.sh
      interface: "Docker entrypoint for GRPO training"
      consumers: ["manual execution"]
  affects:
    - component: outputs/grpo/model
      impact: "Creates GRPO-trained model"
    - component: outputs/grpo/checkpoints
      impact: "Stores training checkpoints"

tech-stack:
  added:
    - name: trl.GRPOTrainer
      purpose: "GRPO reinforcement learning trainer"
    - name: concurrent.futures.ProcessPoolExecutor
      purpose: "Parallel SUMO simulation execution"
    - name: TraCI labeled connections
      purpose: "Concurrent SUMO instance management"
  patterns:
    - name: "Three-layer reward structure"
      rationale: "L1 format → L2 constraints → L3 simulation with gating"
    - name: "Gradual constraint scoring"
      rationale: "Partial satisfaction gets partial reward (not binary)"
    - name: "Baseline normalization"
      rationale: "Relative improvement vs. original timing"

key-files:
  created:
    - path: src/grpo/rewards.py
      loc: 572
      purpose: "5 reward functions with L1/L2/L3 evaluation"
      exports:
        - match_format_exactly
        - match_format_approximately
        - check_constraints
        - sumo_simulation_reward
        - think_length_reward
        - init_rewards
    - path: src/grpo/train.py
      loc: 326
      purpose: "GRPO training pipeline"
      exports:
        - main
    - path: docker/grpo_train.sh
      loc: 87
      purpose: "Docker entrypoint for GRPO training"
      exports: []
  modified: []

decisions:
  - summary: "Gradual L2 constraint scoring"
    rationale: "Partial constraint satisfaction gives partial reward to guide learning"
    alternatives: ["Binary all-or-nothing scoring"]
    date: 2026-02-10
  - summary: "Gate L3 SUMO reward on L1+L2 full pass"
    rationale: "Avoid wasting SUMO computation on invalid/non-compliant outputs"
    alternatives: ["Always run SUMO and combine all scores"]
    date: 2026-02-10
  - summary: "ProcessPoolExecutor for parallel SUMO"
    rationale: "Each GRPO batch generates num_generations candidates - evaluate in parallel"
    alternatives: ["Sequential evaluation", "Multiprocessing Pool"]
    date: 2026-02-10
  - summary: "Terminate on SUMO system errors"
    rationale: "System-level SUMO failures indicate environment issues, not model issues"
    alternatives: ["Return penalty score on SUMO errors"]
    date: 2026-02-10

metrics:
  duration: 402
  tasks_completed: 3
  files_created: 3
  lines_added: 985
  commits: 3
  completed_at: 2026-02-10T04:12:47Z
---

# Phase 3 Plan 02: GRPO 训练脚本实现 Summary

**一句话:** 实现三层 reward 函数体系 (L1 格式 + L2 约束 + L3 SUMO 仿真) 和 GRPO 训练流水线，基于 SFT 模型进行强化学习优化

## Overview

创建了完整的 GRPO 训练基础设施:
- **src/grpo/rewards.py**: 5 个 reward 函数实现三层评分体系 (L1 精确/近似格式匹配, L2 渐进式约束检查, L3 SUMO 仿真 reward, think 长度惩罚)
- **src/grpo/train.py**: GRPO 训练脚本 (加载 SFT 模型, 应用 LoRA, 使用 GRPOTrainer 训练, 保存 merged_16bit 模型)
- **docker/grpo_train.sh**: Docker 入口脚本 (验证 3 个前置条件, 启动容器化训练)

## What Was Built

### Task 1: Reward Functions Module (src/grpo/rewards.py, 572 LOC)

**L1: Format Matching**
- `match_format_exactly`: 正则匹配 `</think>\s*<CyclePlan>content</CyclePlan>\s*$` 格式 (精确匹配给 3.0 分)
- `match_format_approximately`: 统计标签出现次数 (`</think>`, `<CyclePlan>`, `</CyclePlan>` 各 1 次给 +0.5, 否则 -1.0)

**L2: Constraint Checking (Gradual Scoring)**
- `check_constraints`: 提取 CyclePlan JSON 并验证:
  - Phase order correctness: (正确位置数 / 总相位数) × weight
  - Green time range: (满足约束相位数 / 总相位数) × weight
  - 部分满足给部分分 (非二元制)

**L3: SUMO Simulation Reward**
- `sumo_simulation_reward`: 仅当 L1 格式正确 + L2 约束全部满足时执行
  - 使用 ProcessPoolExecutor 并行运行 SUMO 仿真
  - 每个候选方案: loadState → 执行模型配时 → 统计通过量和排队数
  - Baseline 归一化:
    - throughput_ratio = model_passed / max(baseline_passed, 1)
    - queue_ratio = baseline_queue / max(model_queue, 1)
    - combined = 0.6 × throughput + 0.4 × queue
    - score = min(combined, 1.0) × 5.0
  - SUMO 崩溃/超时: raise error (系统级异常不容忍)

**Think Length Penalty**
- `think_length_reward`: 估算 think 内容 token 数 (char_count / 2), 惩罚 <50 或 >200 token 的思考

**Module-level State**
- `init_rewards(config_path, baseline_path)`: 加载 config 和 baseline.json (训练前调用一次)
- 全局变量缓存 config 和 baseline 数据

### Task 2: GRPO Training Script (src/grpo/train.py, 326 LOC)

**结构镜像 src/sft/train.py, 适配 GRPO:**
- `ensure_model()`: 检查 SFT 模型存在 (outputs/sft/model), 不从 modelscope 下载
- `setup_model()`: 加载 SFT 模型, 配置 LoRA, **fast_inference=False** (无 vLLM)
- `setup_chat_template()`: 与 SFT 完全相同 (reasoning_start=`<think>`, solution_start=`<CyclePlan>`)
- `load_grpo_data()`: 加载 grpo_train.jsonl, 按 90% 分位数过滤 prompt 长度, 返回 Dataset + max_prompt_length
- `train_model()`:
  - GRPOConfig 参数: temperature, num_generations=4, kl_coef, max_prompt_length, max_completion_length, 优化器配置
  - GRPOTrainer: 传入 model, tokenizer, reward_funcs (5 个函数列表), dataset
  - **无 vLLM**: use_vllm=False 隐含在 fast_inference=False 中
- `save_model()`: 合并 LoRA 保存 merged_16bit 到 outputs/grpo/model
- `main()`: 流程串联 (加载 config → 确保 SFT 模型 → 设置模型 → 初始化 rewards → 加载数据 → 训练 → 保存)

### Task 3: Docker GRPO Training Shell Script (docker/grpo_train.sh, 87 LOC)

**遵循 sft_train.sh/data.sh 模式:**
- 前置检查:
  1. outputs/sft/model/ 存在 (SFT 模型)
  2. outputs/grpo/grpo_train.jsonl 存在 (GRPO 数据)
  3. outputs/grpo/baseline.json 存在 (基准结果)
- Docker 配置与 sft_train.sh 完全一致:
  - IMAGE_NAME=qwen3-tsc-grpo:latest
  - --gpus all, --shm-size=32GB
  - -e SUMO_HOME=/usr/share/sumo
  - --user, -v, -w 参数一致
- 执行: `python3 -m src.grpo.train --config config/config.json "$@"`

## Deviations from Plan

无 - 计划严格执行:
- 所有 5 个 reward 函数按计划实现 (L1 精确/近似, L2 约束, L3 SUMO, think 长度)
- L2 约束检查实现渐进式评分 (部分满足给部分分)
- L3 SUMO reward 正确实现 gate 机制 (仅当 L1+L2 全满足时运行)
- GRPO 训练脚本加载 SFT 模型, 使用 GRPOTrainer, 无 vLLM
- Docker 脚本验证全部 3 个前置条件, 配置与 sft_train.sh 一致

## Testing Evidence

**Syntax Validation:**
```bash
✓ Python 语法验证通过 (rewards.py + train.py)
✓ Bash 语法验证通过 (grpo_train.sh)
```

**Import Verification:**
```bash
✓ 5 reward 函数 + init_rewards 导入成功
✓ GRPOTrainer, GRPOConfig, FastLanguageModel 引用正确
```

**Component Checks:**
```bash
✓ rewards.py: 10 个函数 (5 reward + init + 4 helper)
✓ train.py: 9 个函数 (完整训练流水线)
✓ grpo_train.sh: 可执行权限设置
✓ 标签格式: <think>...</think><CyclePlan>...</CyclePlan> 贯穿全部文件
✓ SFT 模型路径配置: outputs/sft/model (config.json 确认)
✓ fast_inference=False 配置: train.py 中确认
✓ baseline.json 前置检查: grpo_train.sh 中确认
```

**Integration Points:**
```bash
✓ rewards.py → train.py: init_rewards() 调用, 5 个 reward 函数传入 GRPOTrainer
✓ train.py → grpo_train.sh: -m src.grpo.train 入口正确
✓ config.json: training.grpo 配置完整 (model, hyperparams, reward)
✓ baseline.json: 路径配置在 paths.grpo_baseline
```

## Success Criteria Check

- [x] rewards.py: L1 格式 regex 匹配 `<think>...</think><CyclePlan>...</CyclePlan>`
- [x] rewards.py: L2 约束检查渐进式 (部分满足给部分分)
- [x] rewards.py: L3 SUMO reward 仅在 L1+L2 全满足时触发, 使用 baseline 归一化
- [x] rewards.py: think 长度惩罚应用于 <50 或 >200 token 思考
- [x] train.py: 加载 SFT 模型, 应用 LoRA, 使用 GRPOTrainer (无 vLLM)
- [x] train.py: 保存 merged_16bit 模型到 outputs/grpo/model
- [x] grpo_train.sh: 检查 SFT 模型, GRPO 数据, baseline.json 存在
- [x] grpo_train.sh: Docker 配置与 data.sh/sft_train.sh 模式一致

## Files Created

```
src/grpo/rewards.py          572 LOC    5 reward functions + init + helpers
src/grpo/train.py            326 LOC    GRPO training pipeline
docker/grpo_train.sh          87 LOC    Docker entrypoint
```

**Total: 985 lines added**

## Next Steps

Phase 3 Plan 02 完成后, GRPO 训练基础设施已就绪:
1. **执行 baseline 预计算**: `./docker/grpo_baseline.sh` (生成 baseline.json)
2. **执行 GRPO 训练**: `./docker/grpo_train.sh` (训练 GRPO 模型)
3. **Phase 3 Plan 03**: GRPO 模型测试与评估 (对比 SFT 模型和 GRPO 模型性能)

## Self-Check: PASSED

**检查创建文件存在:**
```bash
✓ src/grpo/rewards.py: FOUND
✓ src/grpo/train.py: FOUND
✓ docker/grpo_train.sh: FOUND (可执行)
```

**检查提交记录:**
```bash
✓ 5656f87: feat(03-02): implement GRPO reward functions module
✓ 643eb9d: feat(03-02): create GRPO training script
✓ 6b9b1f6: feat(03-02): create Docker GRPO training entrypoint
```

**验证文件内容:**
```bash
✓ rewards.py: 5 个 reward 函数全部导出
✓ train.py: GRPOTrainer 引用正确, SFT 模型路径配置正确
✓ grpo_train.sh: 3 个前置条件检查完整
```

所有检查通过 ✓

---

*Plan executed: 2026-02-10*
*Duration: 402 seconds*
*Tasks: 3/3 completed*
