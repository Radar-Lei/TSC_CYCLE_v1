# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-18)

**Core value:** 训练能通过思维链推理优化交通信号配时的 AI 模型，提升交通效率，减少拥堵
**Current focus:** Phase 3 - SFT 训练

## Current Position

Milestone: v1.1 模型迁移
Phase: 3 of 4 (SFT 训练)
Plan: 1 of 2 in current phase
Status: In Progress
Last activity: 2026-02-20 - Completed quick task 2: Qwen3-4B SFT 训练并导出 F16/Q4_K_M GGUF

Progress: [=====50%====] 50% (2/4 phases complete)

## Performance Metrics

**v1.0 Milestone:**
- Phases: 1
- Plans: 1
- Duration: 14 days
- Files modified: 6
- Tests: 21 passing

**v1.1 Milestone (in progress):**
- Phase 03-01: 4 minutes, 2 files modified

## Accumulated Context

### Decisions

All decisions logged in PROJECT.md Key Decisions table.

Recent decisions affecting current work:
- [v1.0]: 使用 samples length 作为加权平均权重
- [v1.0]: Throughput 计算方式：先按周期再加权
- [v1.1-03-01]: GLM 使用与 Qwen 相同的 target_modules (LLaMA-style 架构)
- [v1.1-03-01]: 双重加载策略 - Unsloth 优先，Hugging Face 回退
- [v1.1-03-02]: 模型切换为 `unsloth/GLM-4.7-Flash`（FP8-Dynamic 有问题）
- [v1.1-03-02]: LoRA 配置：r=16, alpha=16, dropout=0（参考 Unsloth notebook）
- [Phase quick-2-qwen3-4b-sft-qwen3-home-samuel-tsc-cycle]: SFT 基座切换为 model/Qwen3-4B-Base，模型来源标识使用 Qwen/Qwen3-4B-Base。
- [Phase quick-2-qwen3-4b-sft-qwen3-home-samuel-tsc-cycle]: Qwen3 训练采用 <|im_start|>user 与 <|im_start|>assistant 响应掩码边界以避免全 -100 标签。
- [Phase quick-2-qwen3-4b-sft-qwen3-home-samuel-tsc-cycle]: SFT 保存阶段输出合并后完整权重，确保 GGUF 导出包含真实张量。

### Pending Todos

None.

### Blockers/Concerns

**Resolved:**
- GLM tokenizer 兼容性检查已添加 (03-01)

**Critical from Project Memory:**
- Qwen3 tokenizer 中 `aises`/` termina` 是 added tokens，不能用于 SFT 自定义标签
- GLM tokenizer 必须验证无类似问题 (Phase 2 重点) - 已在 03-01 添加检测

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 1 | 修改 sft_test.sh 支持 GGUF 模型测试 | 2026-02-19 | 7387a94 | [1-sft-test-sh-gguf](./quick/1-sft-test-sh-gguf/) |
| Phase quick-2-qwen3-4b-sft-qwen3-home-samuel-tsc-cycle P2 | 28min | 3 tasks | 3 files |

## Session Continuity

Last session: 2026-02-20
Status: In Progress - Phase 3 (SFT 训练)
Current: 已完成 quick task 2（Qwen3-4B SFT + 双 GGUF 导出），可继续进行后续验证/集成
