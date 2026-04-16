---
phase: 09-8b
status: passed
verified: 2026-04-16
---

# Phase 9: 8B 训练与导出 — Verification

## Must-Haves Check

### From Plan 09-01 (SFT + GGUF)

| # | Truth/Artifact | Status | Evidence |
|---|---------------|--------|---------|
| 1 | SFT 训练完成，模型目录含 config.json + tokenizer.json | ✅ PASS | 文件已存在 |
| 2 | outputs/sft/qwen3-8b/model/ 含 safetensors 权重文件 | ✅ PASS | 4 个 shard（4.6/4.6/4.7/1.5GB） |
| 3 | outputs/sft/qwen3-8b/gguf/model-Q4_K_M.gguf 存在 | ✅ PASS | 4.7GB |
| 4 | outputs/sft/qwen3-8b/gguf/model-Q8_0.gguf 存在 | ✅ PASS | 8.2GB |
| 5 | outputs/sft/qwen3-8b/gguf/model-F16.gguf 存在 | ✅ PASS | 16GB |
| 6 | 文件大小关系 F16 > Q8_0 > Q4_K_M | ✅ PASS | 16G > 8.2G > 4.7G |

### From Plan 09-02 (GRPO + GGUF)

| # | Truth/Artifact | Status | Evidence |
|---|---------------|--------|---------|
| 1 | GRPO 训练完成，模型目录含 config.json + tokenizer.json | ✅ PASS | 文件已存在 |
| 2 | outputs/grpo_simple/qwen3-8b/model/ 含 safetensors 权重文件 | ✅ PASS | 4 个 shard（4.6/4.6/4.7/1.5GB） |
| 3 | outputs/grpo_simple/qwen3-8b/gguf/model-Q4_K_M.gguf 存在 | ✅ PASS | 4.7GB |
| 4 | outputs/grpo_simple/qwen3-8b/gguf/model-Q8_0.gguf 存在 | ✅ PASS | 8.2GB |
| 5 | outputs/grpo_simple/qwen3-8b/gguf/model-F16.gguf 存在 | ✅ PASS | 16GB |
| 6 | 文件大小关系 F16 > Q8_0 > Q4_K_M | ✅ PASS | 16G > 8.2G > 4.7G |

## Phase Success Criteria

| # | Criterion | Status |
|---|-----------|--------|
| 1 | SFT 训练完成，outputs/sft/qwen3-8b/model 包含完整 Qwen3-8B SFT 模型 | ✅ PASS |
| 2 | 使用 SFT 产出完成 GRPO 训练，outputs/grpo_simple/qwen3-8b/model 包含完整模型 | ✅ PASS |
| 3 | SFT 模型导出 GGUF（Q4_K_M、Q8_0、F16）到 outputs/sft/qwen3-8b/gguf/ | ✅ PASS |
| 4 | GRPO 模型导出 GGUF（Q4_K_M、Q8_0、F16）到 outputs/grpo_simple/qwen3-8b/gguf/ | ✅ PASS |

## Summary

**Score: 4/4 must-pass criteria verified**

Phase 9 完全通过。SFT 和 GRPO 训练链路完整，全部 6 个 GGUF 文件（SFT 3 + GRPO 3）均已正确导出至隔离目录。Phase 10 的验证任务可以直接对 outputs/grpo_simple/qwen3-8b/model 运行。
