# Roadmap: TSC-CYCLE

**Created:** 2026-02-09
**Depth:** Quick (3-5 phases)
**Total Phases:** 3

## Overview

基于 SUMO 仿真的交通信号配时优化大模型微调流水线。通过 SFT 阶段让 Qwen3-4B-Base 学会输出格式,然后通过 GRPO 阶段结合实时 SUMO 仿真优化配时方案质量。项目分为 3 个阶段:准备 SFT 数据并完成监督微调、准备 GRPO 数据、完成 GRPO 强化学习训练。

---

## Phase 1: SFT 数据与训练

**Goal:** 模型学会按照指定格式输出交通信号配时方案

**Dependencies:** 无 (基础数据 train.jsonl 已存在)

**Requirements:** SFT-01, SFT-02, SFT-03, SFT-04, SFT-05, SFTT-01, SFTT-02, SFTT-03, SFTT-04

**Plans:** 3 plans

Plans:
- [x] 01-01-PLAN.md — 从 train.jsonl 抽取约 100 条代表性样本
- [x] 01-02-PLAN.md — 为每条样本生成 think+solution 内容，构造 SFT 训练数据
- [x] 01-03-PLAN.md — 创建 SFT 训练流水线（Docker 脚本 + Python 训练脚本）

**Success Criteria:**
1. 从 train.jsonl 成功抽取 100 条样本,覆盖不同场景和饱和度分布
2. 生成的 SFT 数据每条包含中文短思考(50-200 token)和正确格式的 solution
3. SFT 数据中所有 final 值满足硬约束(min_green ≤ final ≤ max_green)
4. docker/sft_train.sh 脚本能在容器中成功运行 SFT 训练
5. 训练后模型生成的输出符合 `<think>...<think><solution>...<solution>` 格式
6. SFT 模型权重成功保存到 outputs/sft/model 目录

**Status:** Complete (2026-02-09) ✓

---

## Phase 2: GRPO 数据准备

**Goal:** 准备好用于 GRPO 训练的 prompt 和状态文件对

**Dependencies:** Phase 1 (需要确认数据格式要求)

**Requirements:** GRPD-01, GRPD-02

**Plans:** 1 plan

Plans:
- [ ] 02-01-PLAN.md — 更新 prompt_builder 并创建 GRPO 数据生成脚本

**Success Criteria:**
1. 从 train.jsonl 成功提取 GRPO 训练集(prompt + state_file)
2. 每个 prompt 包含 system 角色设定和 user 交通状态说明两部分
3. prompt 不包含思考过程或答案,仅包含任务描述
4. 每个样本正确关联到对应的 SUMO state_file 用于 reward 计算

**Status:** Not Started

---

## Phase 3: GRPO 训练

**Goal:** 通过实时 SUMO 仿真 reward 优化模型配时方案质量

**Dependencies:** Phase 1 (SFT 模型), Phase 2 (GRPO 数据)

**Requirements:** GRPT-01, GRPT-02, GRPT-03, GRPT-04, GRPT-05, GRPT-06, GRPT-07

**Success Criteria:**
1. docker/grpo_train.sh 脚本能在容器中成功运行 GRPO 训练
2. reward 函数能正确验证输出格式(匹配 `<think>...<think><solution>...<solution>`)
3. reward 函数能通过 loadState 加载 SUMO 状态并执行模型方案
4. reward 函数能统计车辆通过量和排队车辆数作为奖励信号
5. think 长度惩罚机制生效(过短或过长的思考受到惩罚)
6. 多进程并行 reward 计算正常工作(多个候选方案并行 SUMO 仿真)
7. GRPO 训练后的模型权重成功保存到 outputs/grpo/model 目录

**Status:** Not Started

---

## Progress

| Phase | Requirements | Status | Completion |
|-------|--------------|--------|------------|
| 1 - SFT 数据与训练 | 9 | Complete ✓ | 100% |
| 2 - GRPO 数据准备 | 2 | Not Started | 0% |
| 3 - GRPO 训练 | 7 | Not Started | 0% |

**Overall:** 9/18 requirements completed (50%)

---

## Next Steps

Execute Phase 2:
```
/gsd:execute-phase 2
```

---

*Roadmap created: 2026-02-09*
*Last updated: 2026-02-10*
