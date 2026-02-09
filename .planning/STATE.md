# Project State: TSC-CYCLE

**Last Updated:** 2026-02-10T04:12:47Z

---

## Project Reference

**Core Value:**
给定交叉口实时交通状态,大模型输出的信号配时方案能最大化车辆通过量、最小化排队车辆数

**Current Focus:**
Phase 3: GRPO 训练 - 全部完成，验证通过

---

## Current Position

**Active Phase:** Phase 3 - GRPO 训练 (Complete)
**Active Plan:** N/A (All plans complete)
**Current Status:** Phase 3 Complete, All Phases Complete

**Progress:**
```
Phase 1: [██████████] 9/9 requirements (100%) - Completed
Phase 2: [██████████] 2/2 requirements (100%) - Completed
Phase 3: [██████████] 7/7 requirements (100%) - Completed

Overall: [██████████] 18/18 requirements (100%)
```

---

## Performance Metrics

**Velocity:** 1 plan/session (稳定进行)

**Phase History:**
- Phase 1: Completed (100% - 9/9 完成)
- Phase 2: Completed (100% - 2/2 完成)
- Phase 3: Completed (100% - 7/7 完成)

| Phase | Plan | Duration | Tasks | Files | Completed |
|-------|------|----------|-------|-------|-----------|
| 01    | 01   | 259s     | 1     | 2     | 2026-02-09T12:24:12Z |
| 01    | 02   | 497s     | 2     | 3     | 2026-02-09T12:36:00Z |
| 01    | 03   | 217s     | 2     | 3     | 2026-02-09T12:44:44Z |
| 02    | 01   | 282s     | 2     | 3     | 2026-02-09T16:38:44Z |
| 03    | 01   | 246s     | 2     | 4     | 2026-02-09T19:54:45Z |
| 03    | 02   | 402s     | 3     | 3     | 2026-02-10T04:12:47Z |

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
| outputs/sft/model 作为 GRPO base model | 基于 SFT 训练后的模型进行 GRPO 强化学习 | 03-01 | 2026-02-09 |
| num_generations=4 | GRPO 采样时每个 prompt 生成 4 个候选方案 | 03-01 | 2026-02-09 |
| Baseline 去重策略 | 按 state_file 去重避免重复计算相同状态 | 03-01 | 2026-02-09 |
| 渐进式 L2 约束评分 | 部分满足约束给部分分，引导学习过程 | 03-02 | 2026-02-10 |
| L3 SUMO reward 门控 | 仅当 L1+L2 全满足时运行 SUMO，避免浪费计算 | 03-02 | 2026-02-10 |
| ProcessPoolExecutor 并行 SUMO | 每批 num_generations 个候选方案并行仿真评估 | 03-02 | 2026-02-10 |
| SUMO 系统错误终止程序 | 系统级 SUMO 故障表明环境问题非模型问题 | 03-02 | 2026-02-10 |

### Active Todos

- [x] 执行 Plan 01-01: 样本抽取
- [x] 执行 Plan 01-02: SFT 数据组装
- [x] 执行 Plan 01-03: SFT 训练流水线
- [x] 执行 Plan 02-01: GRPO 数据准备与格式转换
- [x] 执行 Plan 03-01: GRPO 配置和 baseline 预计算
- [x] 执行 Plan 03-02: GRPO 训练脚本实现

### Blockers

无

---

## Session Continuity

### Last Session Summary

**What:** 执行 Phase 3 Plan 02 - GRPO 训练脚本实现

**Outcome:**
- 创建 src/grpo/rewards.py (572 LOC): 5 个 reward 函数实现三层评分体系
  - L1: match_format_exactly + match_format_approximately (格式匹配)
  - L2: check_constraints (渐进式约束评分)
  - L3: sumo_simulation_reward (SUMO 仿真 + baseline 归一化)
  - think_length_reward (思考长度惩罚)
  - init_rewards() 初始化函数
- 创建 src/grpo/train.py (326 LOC): GRPO 训练流水线
  - 加载 SFT 模型 (outputs/sft/model)
  - 使用 GRPOTrainer + 5 个 reward 函数
  - fast_inference=False (无 vLLM)
  - 保存 merged_16bit 到 outputs/grpo/model
- 创建 docker/grpo_train.sh (87 LOC): Docker 入口脚本
  - 验证 3 个前置条件 (SFT 模型, GRPO 数据, baseline.json)
  - 配置与 sft_train.sh 一致
- 3 个任务全部完成，每个任务原子提交
- 验证结果: 语法验证通过，导入成功，关键组件确认

**Next:** Phase 3 后续计划（可能需要 baseline 计算和实际 GRPO 训练执行）

**Stopped At:** Completed 03-02-PLAN.md

### Context for Next Session

Phase 3 Plan 02 已完成。GRPO 训练基础设施已就绪 (rewards + train + docker)。三层 reward 体系: L1 格式匹配, L2 渐进式约束检查, L3 SUMO 仿真 (仅在 L1+L2 全满足时运行)。GRPO 训练脚本加载 SFT 模型, 使用 GRPOTrainer, 无 vLLM。下一步可能需要: 1) 运行 baseline 预计算 (./docker/grpo_baseline.sh), 2) 执行 GRPO 训练 (./docker/grpo_train.sh), 3) 评估和测试。

---

*State initialized: 2026-02-09*
