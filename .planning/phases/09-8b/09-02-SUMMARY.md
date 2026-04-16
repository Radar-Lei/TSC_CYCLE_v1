---
phase: 09-8b
plan: 02
subsystem: training
tags: [grpo, qwen3-8b, gguf, reinforcement-learning, safetensors]

requires:
  - phase: 09-8b plan01
    provides: outputs/sft/qwen3-8b/model — SFT 产出作为 GRPO 基座

provides:
  - Qwen3-8B GRPO 模型（outputs/grpo_simple/qwen3-8b/model/，4 × safetensors）
  - GRPO 模型 GGUF 导出：F16（16GB）、Q8_0（8.2GB）、Q4_K_M（4.7GB）

affects: [10-4000]

tech-stack:
  added: []
  patterns: ["grpo_simple 训练使用 SFT 产出作为基座，learning_rate 降至 5e-6"]

key-files:
  created:
    - outputs/grpo_simple/qwen3-8b/model/config.json
    - outputs/grpo_simple/qwen3-8b/model/tokenizer.json
    - outputs/grpo_simple/qwen3-8b/model/model-00001-of-00004.safetensors
    - outputs/grpo_simple/qwen3-8b/model/model-00002-of-00004.safetensors
    - outputs/grpo_simple/qwen3-8b/model/model-00003-of-00004.safetensors
    - outputs/grpo_simple/qwen3-8b/model/model-00004-of-00004.safetensors
    - outputs/grpo_simple/qwen3-8b/gguf/model-F16.gguf
    - outputs/grpo_simple/qwen3-8b/gguf/model-Q8_0.gguf
    - outputs/grpo_simple/qwen3-8b/gguf/model-Q4_K_M.gguf
  modified: []

key-decisions:
  - "GRPO 基座为 SFT 产出（outputs/sft/qwen3-8b/model），而非原始预训练权重"
  - "learning_rate=5e-6（比 SFT 的 2e-4 小 40 倍，符合 RL fine-tuning 惯例）"
  - "全精度加载（load_in_4bit=false），与 SFT 保持一致"

patterns-established:
  - "GRPO 输出隔离：outputs/grpo_simple/qwen3-8b/ 独立目录"
  - "SFT → GRPO 链路：grpo_simple.model.model_name 指向 SFT 产出路径"

requirements-completed: [TRAIN-02, TRAIN-03]

duration: ~12h（GRPO 训练 200 steps + GGUF 转换）
completed: 2026-04-12
---

# Phase 9 Plan 02: 8B GRPO 训练与 GGUF 导出 Summary

**基于 SFT 产出的 Qwen3-8B GRPO 强化学习训练完成，产出完整模型及 F16/Q8_0/Q4_K_M 三种 GGUF 格式**

## Performance

- **Duration:** ~12h（GRPO 训练 + 三次 GGUF 转换）
- **Completed:** 2026-04-12
- **Tasks:** 2
- **Files created:** 9（4 safetensors + config/tokenizer + 3 GGUF）

## Accomplishments

- 以 SFT 产出（outputs/sft/qwen3-8b/model）为基座完成 GRPO 强化学习训练
- 产出完整可加载 GRPO 模型：4 个 safetensors shard（各约 4.6-4.7GB）
- 三种 GGUF 格式导出：F16（16GB）、Q8_0（8.2GB）、Q4_K_M（4.7GB）

## Files Created/Modified

- `outputs/grpo_simple/qwen3-8b/model/` — 完整 GRPO 模型目录
- `outputs/grpo_simple/qwen3-8b/gguf/model-F16.gguf` — 16-bit 精度 GGUF（16GB）
- `outputs/grpo_simple/qwen3-8b/gguf/model-Q8_0.gguf` — 8-bit 量化 GGUF（8.2GB）
- `outputs/grpo_simple/qwen3-8b/gguf/model-Q4_K_M.gguf` — 4-bit K-means 量化 GGUF（4.7GB）

## Decisions Made

- config_8b.json 中 grpo_simple.model.model_name = "outputs/sft/qwen3-8b/model"，确保从 SFT 而非预训练权重继续训练

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## Next Phase Readiness

- GRPO 模型就绪，Phase 10 的 4000 条验证可以对 outputs/grpo_simple/qwen3-8b/model 直接运行
- GGUF 格式已备份用于部署

---
*Phase: 09-8b*
*Completed: 2026-04-12*
