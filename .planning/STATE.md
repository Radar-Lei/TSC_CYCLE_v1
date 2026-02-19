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
Last activity: 2026-02-19 — 模型切换为 GLM-4.7-Flash (非 FP8-Dynamic)，需重新训练

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

### Pending Todos

None.

### Blockers/Concerns

**Resolved:**
- GLM tokenizer 兼容性检查已添加 (03-01)

**Critical from Project Memory:**
- Qwen3 tokenizer 中 `aises`/` termina` 是 added tokens，不能用于 SFT 自定义标签
- GLM tokenizer 必须验证无类似问题 (Phase 2 重点) - 已在 03-01 添加检测

## Session Continuity

Last session: 2026-02-19
Status: In Progress - Phase 3 (SFT 训练)
Current: 模型切换为 GLM-4.7-Flash，需更新训练代码并重新训练
