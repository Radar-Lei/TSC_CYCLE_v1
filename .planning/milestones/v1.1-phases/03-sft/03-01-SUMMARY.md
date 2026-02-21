---
phase: 03-sft
plan: 01
subsystem: sft-training
tags: [model-migration, glm, lora, tokenizer]
requires:
  - Phase 02 complete (tokenizer verification)
provides:
  - GLM-4.7-Flash-FP8-Dynamic model loading support
  - Tokenizer compatibility validation
affects:
  - src/sft/train.py
  - config/config.json
tech-stack:
  added:
    - Hugging Face transformers fallback for FP8 models
    - PEFT for native LoRA support
  patterns:
    - Try/fallback pattern for model loading
key-files:
  created: []
  modified:
    - config/config.json
    - src/sft/train.py
decisions:
  - GLM uses same target_modules as Qwen (LLaMA-style architecture)
  - Fallback to Hugging Face native loading if Unsloth fails with FP8
metrics:
  duration: 4 minutes
  completed: 2026-02-18
  tasks_completed: 3
  files_modified: 2
---

# Phase 3 Plan 1: SFT Training Migration to GLM Summary

## One-liner

将 SFT 训练代码从 Qwen3-4B-Base 迁移到 GLM-4.7-Flash-FP8-Dynamic，添加模型加载回退机制和 tokenizer 兼容性检查。

## Changes Made

### Task 1: 更新配置文件适配 GLM 模型

**文件:** `config/config.json`

- 修改 `training.sft.model.model_name` 为 `"model/GLM-4.7-Flash-FP8-Dynamic"`
- 修改 `training.sft.model.model_id` 为 `"zai-org/GLM-4.7-Flash-FP8-Dynamic"`
- 保持 target_modules 不变（GLM 使用 LLaMA-style 架构）

**Commit:** a28e360

### Task 2: 更新 train.py 支持 GLM 模型加载

**文件:** `src/sft/train.py`

- 更新文档字符串引用 GLM-4.7-Flash-FP8-Dynamic
- 添加 GLM 模型检测逻辑
- 实现 try/fallback 模式：
  - 首先尝试 Unsloth 加载
  - 如果失败（如 FP8 不支持），回退到 Hugging Face 原生加载 + PEFT
- 更新 `ensure_model()` 函数注释说明 ModelScope 下载来源

**Commit:** 3aa61fd

### Task 3: 验证数据格式兼容性

**文件:** `src/sft/train.py`

- 添加 `test_tokenizer_compatibility()` 函数
- 测试自定义标签 (`<start_working_out>`, `<end_working_out>`, `<SOLUTION>`, `</SOLUTION>`) 的 tokenization
- 检测 added token 冲突（类似 Qwen3 的问题）
- 在 `main()` 中调用兼容性测试

**Commit:** b2fe042

## Key Decisions

1. **target_modules 保持不变** - GLM 使用与 Qwen 相同的 LLaMA-style attention 架构，target_modules 配置兼容

2. **双重加载策略** - 优先使用 Unsloth 加载（性能更好），失败时回退到 Hugging Face 原生加载（兼容性更广）

3. **tokenizer 兼容性检查** - 训练前自动检测自定义标签是否被正确处理，避免 Qwen3 added token 问题复现

## Deviations from Plan

None - plan executed exactly as written.

## Verification Results

- [x] `config/config.json` 中 model_name 指向 GLM-4.7-Flash-FP8-Dynamic
- [x] `train.py` 包含 GLM 模型加载代码
- [x] tokenizer 兼容性检查函数已添加
- [x] Python 语法检查通过

## Next Steps

1. 下载 GLM-4.7-Flash-FP8-Dynamic 模型到本地
2. 运行 SFT 训练验证流程
3. 检查 tokenizer 兼容性测试输出
