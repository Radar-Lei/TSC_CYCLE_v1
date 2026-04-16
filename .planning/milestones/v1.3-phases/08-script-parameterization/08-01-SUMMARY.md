---
phase: 08-script-parameterization
plan: 01
subsystem: config
tags: [config, qwen3-8b, parameterization]
dependency_graph:
  requires: []
  provides: [config_8b_json]
  affects: [sft_training, grpo_training]
tech_stack:
  added: []
  patterns: [model-specific-config-isolation]
key_files:
  created:
    - config/config_8b.json
  modified: []
decisions:
  - "8B 全精度加载（load_in_4bit=false），DGX-Spark 显存充足无需量化"
  - "SFT epochs 设为 2，与 MEMORY.md 经验一致"
  - "GRPO max_steps 设为 10000，与 4B 配置保持一致"
  - "输出路径包含 qwen3-8b 隔离段，不影响 4B 产物"
metrics:
  duration: "72s"
  completed: "2026-04-11T03:03:51Z"
  tasks_completed: 2
  tasks_total: 2
---

# Phase 08 Plan 01: config_8b.json 验证与固化 Summary

Qwen3-8B 全精度训练配置文件，模型名参数化 + 输出目录按 qwen3-8b 隔离 + load_in_4bit=false

## Results

### Task 1: 验证并完善 config_8b.json 配置

**Commit:** 7404202

创建 `config/config_8b.json`，基于 config_32b.json 结构适配 8B 参数：
- `training.sft.model.model_name` = `unsloth/Qwen3-8B`
- `training.sft.model.model_id` = `unsloth/Qwen3-8B`
- `training.sft.model.load_in_4bit` = `false`（全精度）
- `training.sft.num_train_epochs` = `2`
- `training.grpo_simple.model.model_name` = `outputs/sft/qwen3-8b/model`
- `training.grpo_simple.model.load_in_4bit` = `false`
- `paths.sft_output` = `outputs/sft/qwen3-8b/model`
- `paths.grpo_simple_output` = `outputs/grpo_simple/qwen3-8b/model`
- `paths.grpo_simple_checkpoints` = `outputs/grpo_simple/qwen3-8b/checkpoints`

所有 8 项自动校验通过。

### Task 2: 端到端 dry-run 验证脚本可用性

**Commit:** N/A（纯验证，无文件变更）

验证内容：
1. SFT load_config 正确解析 config_8b.json，提取 model_name 和 sft_output 路径
2. GRPO load_config 正确解析，提取 grpo_simple model_name 和 output 路径
3. Docker shell 脚本路径提取（python3 -c 模拟）正确返回隔离路径
4. 4B 配置 config/config.json 的 paths.sft_output 和 paths.grpo_simple_output 未被修改

注：由于 worktree 环境缺少 torch，无法直接 import src.sft.train，改用等效的 json.load 函数模拟 load_config 行为（load_config 本身就是 json.load 的封装）。

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] config_8b.json 不存在，需从头创建**
- **Found during:** Task 1
- **Issue:** 计划假设文件已存在只需验证，但实际文件尚未创建
- **Fix:** 基于 config_32b.json 结构创建 config_8b.json，适配所有 8B 参数
- **Files modified:** config/config_8b.json
- **Commit:** 7404202

**2. [Rule 3 - Blocking] torch 未安装导致无法直接 import 训练脚本**
- **Found during:** Task 2
- **Issue:** worktree 环境没有 torch，无法执行 `from src.sft.train import load_config`
- **Fix:** 用等效的 json.load 函数替代（load_config 的实现就是 json.load），验证结果完全等价
- **Files modified:** 无

## Verification

- [x] config/config_8b.json 存在且为合法 JSON
- [x] SFT model_name = unsloth/Qwen3-8B, load_in_4bit = false
- [x] GRPO model_name 指向 SFT 8B 产出路径
- [x] 所有输出路径包含 qwen3-8b 隔离段
- [x] 4B config/config.json 未受影响
- [x] load_config 函数可正确解析 config_8b.json

## Self-Check: PASSED
