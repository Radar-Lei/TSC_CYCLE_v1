# Project State: TSC-CYCLE

**Last Updated:** 2026-02-09T16:38:44Z

---

## Project Reference

**Core Value:**
给定交叉口实时交通状态,大模型输出的信号配时方案能最大化车辆通过量、最小化排队车辆数

**Current Focus:**
Phase 1 已完成。Phase 2: GRPO 数据准备 进行中

---

## Current Position

**Active Phase:** Phase 2 - GRPO 数据准备
**Active Plan:** 02-02 (Plan 01 已完成)
**Current Status:** In Progress

**Progress:**
```
Phase 1: [█████████░] 3/9 requirements (33%) - Completed
Phase 2: [█████░░░░░] 1/2 requirements (50%)
Phase 3: [░░░░░░░░░░] 0/7 requirements

Overall: [███░░░░░░░] 4/18 requirements (22%)
```

---

## Performance Metrics

**Velocity:** 1 plan/session (稳定进行)

**Phase History:**
- Phase 1: Completed (33% - 3/9 完成)
- Phase 2: In Progress (50% - 1/2 完成)
- Phase 3: Not Started (0%)

| Phase | Plan | Duration | Tasks | Files | Completed |
|-------|------|----------|-------|-------|-----------|
| 01    | 01   | 259s     | 1     | 2     | 2026-02-09T12:24:12Z |
| 01    | 02   | 497s     | 2     | 3     | 2026-02-09T12:36:00Z |
| 01    | 03   | 217s     | 2     | 3     | 2026-02-09T12:44:44Z |
| 02    | 01   | 282s     | 2     | 3     | 2026-02-09T16:38:44Z |

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
| SYSTEM_PROMPT 与 SFT 一致 | 保证训练一致性，强调分析和推理过程 | 02-01 | 2026-02-09 |
| build_prompt() 不拼入 SYSTEM_PROMPT | 分离 system 和 user content，便于 GRPO 格式组装 | 02-01 | 2026-02-09 |
| State file 相对路径 | 提高数据可移植性，避免硬编码绝对路径 | 02-01 | 2026-02-09 |
| GRPO 数据无 answer 字段 | Reward 由 SUMO 仿真实时计算，方案空间大无法预计算 | 02-01 | 2026-02-09 |

### Active Todos

- [x] 执行 Plan 01-01: 样本抽取
- [x] 执行 Plan 01-02: SFT 数据组装
- [x] 执行 Plan 01-03: SFT 训练流水线
- [x] 执行 Plan 02-01: GRPO 数据准备与格式转换
- [ ] 继续执行 Phase 2 后续计划

### Blockers

无

---

## Session Continuity

### Last Session Summary

**What:** 执行 Phase 2 Plan 01 - GRPO 数据准备与格式转换

**Outcome:**
- 更新 src/data_generator/prompt_builder.py SYSTEM_PROMPT 包含 <think> 和 <CyclePlan> 标签格式说明
- 修改 build_prompt() 方法不再将 SYSTEM_PROMPT 拼入返回字符串
- 创建 src/scripts/generate_grpo_data.py GRPO 数据生成脚本（171 行）
- 生成 outputs/grpo/grpo_train.jsonl (1588 条 GRPO 格式样本)
- GRPO 格式：prompt 为 messages 数组（system + user），metadata 包含 state_file（相对路径）和原始 metadata 字段
- State file 全部成功从绝对路径转换为相对路径
- 提交 c490733: feat(02-01): update prompt_builder SYSTEM_PROMPT with think/CyclePlan tags
- 提交 77f31dd: feat(02-01): create GRPO data generation script and grpo_train.jsonl

**Next:** 继续执行 Phase 2 Plan 02

**Stopped At:** Completed 02-01-PLAN.md

### Context for Next Session

Phase 2 进行中(1/2 完成)。Plan 01 已成功完成 GRPO 数据准备与格式转换。更新了 prompt_builder.py 的 SYSTEM_PROMPT 使其与 SFT 阶段一致（包含 <think> 和 <CyclePlan> 标签说明），创建了 generate_grpo_data.py 脚本将全部 1588 条样本转换为 GRPO 训练格式（prompt messages + state_file 相对路径关联）。数据已准备就绪供 Phase 3 GRPO 训练使用。下一步需要继续 Phase 2 Plan 02。

---

*State initialized: 2026-02-09*
