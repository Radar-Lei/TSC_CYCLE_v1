# Project State: TSC-CYCLE

**Last Updated:** 2026-02-09T12:44:44Z

---

## Project Reference

**Core Value:**
给定交叉口实时交通状态,大模型输出的信号配时方案能最大化车辆通过量、最小化排队车辆数

**Current Focus:**
准备开始 Phase 1: SFT 数据与训练

---

## Current Position

**Active Phase:** Phase 1 - SFT 数据与训练
**Active Plan:** 01-04 (Plan 03 已完成)
**Current Status:** In Progress

**Progress:**
```
Phase 1: [███░░░░░░░] 3/9 requirements (33%)
Phase 2: [░░░░░░░░░░] 0/2 requirements
Phase 3: [░░░░░░░░░░] 0/7 requirements

Overall: [██░░░░░░░░] 3/18 requirements (17%)
```

---

## Performance Metrics

**Velocity:** 1 plan/session (稳定进行)

**Phase History:**
- Phase 1: In Progress (33% - 3/9 完成)
- Phase 2: Not Started (0%)
- Phase 3: Not Started (0%)

| Phase | Plan | Duration | Tasks | Files | Completed |
|-------|------|----------|-------|-------|-----------|
| 01    | 01   | 259s     | 1     | 2     | 2026-02-09T12:24:12Z |
| 01    | 02   | 497s     | 2     | 3     | 2026-02-09T12:36:00Z |
| 01    | 03   | 217s     | 2     | 3     | 2026-02-09T12:44:44Z |

---

## Accumulated Context

### Key Decisions

| Decision | Rationale | Phase | Date |
|----------|-----------|-------|------|
| 3 阶段结构 | quick 深度,SFT 和 GRPO 流程紧密但独立 | Roadmap | 2026-02-09 |
| SFT 数据手工构造 | 只需 100 条学格式,AI 根据 prediction 推算 final 值 | Roadmap | 2026-02-09 |
| GRPO 实时仿真 reward | 方案空间大无法预计算,实时仿真保证准确性 | Roadmap | 2026-02-09 |
| 分层抽样策略 | 确保覆盖所有 34 个交叉口和不同饱和度区间 | 01-01 | 2026-02-09 |
| High 饱和度优先 | high 饱和度训练价值高但原始数据中占比少 | 01-01 | 2026-02-09 |
| 样本饱和度=max(相位饱和度) | 最大值代表该样本最严重的交通压力状况 | 01-01 | 2026-02-09 |
| think 内容 AI 手工生成 | think 内容由 AI 直接撰写，非程序化模板生成 | 01-02 | 2026-02-09 |
| <think><solution> 标签格式 | 使用重复开标签作为关闭标签的格式 | 01-02 | 2026-02-09 |
| Saturation 线性映射 | solution 值基于 saturation 线性映射到 [min_green, max_green] 范围 | 01-02 | 2026-02-09 |
| 双重校验机制 | 约束校验 + think 非空校验确保数据质量 | 01-02 | 2026-02-09 |
| unsloth + LoRA 微调 | 使用 unsloth 对 Qwen3-4B-Base 进行 LoRA 微调提高训练效率 | 01-03 | 2026-02-09 |
| 合并保存完整模型 | 训练后合并 LoRA 保存 merged_16bit 完整模型便于直接推理 | 01-03 | 2026-02-09 |
| Docker 脚本统一模式 | SFT 训练脚本遵循 data.sh 模式确保环境一致性 | 01-03 | 2026-02-09 |

### Active Todos

- [x] 执行 Plan 01-01: 样本抽取
- [x] 执行 Plan 01-02: SFT 数据组装
- [x] 执行 Plan 01-03: SFT 训练流水线
- [ ] 继续执行 Phase 1 后续计划

### Blockers

无

---

## Session Continuity

### Last Session Summary

**What:** 执行 Phase 1 Plan 03 - SFT 训练流水线创建

**Outcome:**
- 创建 src/sft/train.py SFT 训练脚本（253 行）
- 实现完整训练流程：配置加载、模型设置、chat template、数据加载、训练、模型保存
- 使用 unsloth FastLanguageModel + LoRA 微调 Qwen3-4B-Base
- 自定义 chat template 支持 <think><solution> 标签格式
- 训练后合并 LoRA 保存 merged_16bit 完整模型
- 创建 docker/sft_train.sh Docker 执行脚本（55 行）
- 遵循 data.sh 模式确保环境一致性
- 提交 44dc096: feat(01-03): create SFT training script
- 提交 d42925c: feat(01-03): create Docker SFT training shell script

**Next:** 继续执行 Phase 1 Plan 04

**Stopped At:** Completed 01-03-PLAN.md

### Context for Next Session

Phase 1 进行中(3/9 完成)。Plan 03 已成功创建 SFT 训练流水线。包含完整的 Python 训练脚本（使用 unsloth + LoRA 微调 Qwen3-4B-Base，支持 <think><solution> 标签格式）和 Docker 执行脚本（遵循 data.sh 模式）。训练后合并 LoRA 保存为 merged_16bit 完整模型到 outputs/sft/model。下一步需要继续 Phase 1 后续计划。

---

*State initialized: 2026-02-09*
