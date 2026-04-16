---
phase: 09-8b
plan: 01
subsystem: training
tags: [sft, qwen3-8b, gguf, unsloth, safetensors]

requires:
  - phase: 08-script-parameterization
    provides: config_8b.json with model parameterization and full-precision loading

provides:
  - Qwen3-8B SFT 模型（outputs/sft/qwen3-8b/model/，4 × safetensors，共约 15.4GB）
  - SFT 模型 GGUF 导出：F16（16GB）、Q8_0（8.2GB）、Q4_K_M（4.7GB）

affects: [09-8b plan02, 10-4000]

tech-stack:
  added: []
  patterns: ["unsloth SFT + full-precision 8B training via docker/sft_train.sh --config"]

key-files:
  created:
    - outputs/sft/qwen3-8b/model/config.json
    - outputs/sft/qwen3-8b/model/tokenizer.json
    - outputs/sft/qwen3-8b/model/model-00001-of-00004.safetensors
    - outputs/sft/qwen3-8b/model/model-00002-of-00004.safetensors
    - outputs/sft/qwen3-8b/model/model-00003-of-00004.safetensors
    - outputs/sft/qwen3-8b/model/model-00004-of-00004.safetensors
    - outputs/sft/qwen3-8b/gguf/model-F16.gguf
    - outputs/sft/qwen3-8b/gguf/model-Q8_0.gguf
    - outputs/sft/qwen3-8b/gguf/model-Q4_K_M.gguf
  modified: []

key-decisions:
  - "SFT 训练使用 2 epochs（与 MEMORY.md 经验一致，1 epoch 不充分）"
  - "全精度加载（load_in_4bit=false），DGX-Spark 显存足够"
  - "GGUF 导出至 gguf/ 子目录以与 model/ 目录分离"

patterns-established:
  - "模型按名称隔离：outputs/sft/qwen3-8b/ 与 outputs/sft/qwen3-4b/ 各自独立"
  - "GGUF 三格式齐出：F16（精度最高）→ Q8_0 → Q4_K_M（最小）"

requirements-completed: [TRAIN-01, TRAIN-03]

duration: ~2h（SFT 训练 + GGUF 转换）
completed: 2026-04-11
---

# Phase 9 Plan 01: 8B SFT 训练与 GGUF 导出 Summary

**Qwen3-8B SFT 微调完成（全精度，2 epochs），产出 4-shard 模型及 F16/Q8_0/Q4_K_M 三种 GGUF 格式**

## Performance

- **Duration:** ~2h（GPU 训练 + 三次 GGUF 转换）
- **Completed:** 2026-04-11
- **Tasks:** 2
- **Files created:** 9（4 safetensors + config/tokenizer + 3 GGUF）

## Accomplishments

- Qwen3-8B SFT 训练在 DGX-Spark 上以全精度（不量化）成功完成 2 epochs
- 产出完整可加载模型：4 个 safetensors shard（各约 4.6-4.7GB）+ tokenizer + config
- 三种 GGUF 格式导出：F16（16GB）、Q8_0（8.2GB）、Q4_K_M（4.7GB），文件大小关系符合预期

## Files Created/Modified

- `outputs/sft/qwen3-8b/model/` — 完整 SFT 模型目录（config.json, tokenizer.json, tokenizer_config.json, model-0000[1-4]-of-00004.safetensors）
- `outputs/sft/qwen3-8b/gguf/model-F16.gguf` — 16-bit 精度 GGUF（16GB）
- `outputs/sft/qwen3-8b/gguf/model-Q8_0.gguf` — 8-bit 量化 GGUF（8.2GB）
- `outputs/sft/qwen3-8b/gguf/model-Q4_K_M.gguf` — 4-bit K-means 量化 GGUF（4.7GB）

## Decisions Made

- 使用 config_8b.json，sft_output = "outputs/sft/qwen3-8b/model"，与 4B 产物完全隔离
- num_train_epochs = 2（与 MEMORY.md 记录的 SFT 经验一致）

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## Next Phase Readiness

- SFT 模型就绪，GRPO 训练（Plan 02）可以立即使用 outputs/sft/qwen3-8b/model 作为基座
- 三种 GGUF 格式已备份，可用于部署/推理测试

---
*Phase: 09-8b*
*Completed: 2026-04-11*
