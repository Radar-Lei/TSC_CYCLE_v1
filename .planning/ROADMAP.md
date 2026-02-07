# Roadmap: TSC_CYCLE

## Overview

从当前存在并行问题和配置冗余的代码库出发，通过清理重构、修复数据生成、完善训练流程，最终提供统一的执行入口和验证机制，实现一键执行完整训练流水线的目标。

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Code Cleanup** - 清理冗余代码和配置，简化并行逻辑
- [x] **Phase 2: Data Generation** - 修复数据生成流程，实现稳定的交叉口级并行
- [ ] **Phase 3: Training Pipeline** - 完善 SFT 和 GRPO 训练流程
- [ ] **Phase 4: Execution & Validation** - 提供统一执行入口和验证机制

## Phase Details

### Phase 1: Code Cleanup
**Goal**: 代码库清理冗余，并行逻辑简化为单层结构
**Depends on**: Nothing (first phase)
**Requirements**: CLEAN-01, CLEAN-02, CLEAN-03, CLEAN-04, CLEAN-05
**Success Criteria** (what must be TRUE):
  1. 代码中不再存在时段配置相关的参数和逻辑
  2. 数据生成仅以交叉口为单位并行（单层，不嵌套）
  3. 配置文件结构统一，无冗余配置项
  4. 代码中无注释掉的旧逻辑
**Plans**: 3 plans

Plans:
- [x] 01-01-PLAN.md — 移除时段配置代码和冗余配置文件
- [x] 01-02-PLAN.md — 删除嵌套并行模块，重构为扁平任务池
- [x] 01-03-PLAN.md — 重构 Shell 脚本，统一输出路径

### Phase 2: Data Generation
**Goal**: 数据生成流程能够稳定运行并产出训练数据
**Depends on**: Phase 1
**Requirements**: DATA-01, DATA-02, DATA-03, DATA-04, DATA-05, DATA-06, DATA-07
**Success Criteria** (what must be TRUE):
  1. 系统能够自动发现所有场景并解析交叉口配置
  2. 数据生成能够以交叉口为单位成功并行执行
  3. 每个场景运行 3600 秒并检测周期边界
  4. 原始数据和 CoT 格式训练数据都能正确生成为 JSONL
**Plans**: 3 plans

Plans:
- [x] 02-01-PLAN.md — 修复仿真参数、输出路径和场景发现验证
- [x] 02-02-PLAN.md — 实现 CoT 格式训练数据转换（二度生成）
- [x] 02-03-PLAN.md — 修复 CycleDetector 动态检测首绿相位

### Phase 3: Training Pipeline
**Goal**: SFT 和 GRPO 训练能够正常执行并产出模型
**Depends on**: Phase 2
**Requirements**: TRAIN-01, TRAIN-02, TRAIN-03, TRAIN-04, TRAIN-05
**Success Criteria** (what must be TRUE):
  1. SFT 训练能够从 JSONL 数据学习并输出符合格式的信号周期
  2. GRPO 训练能够基于 SFT 模型进行强化学习
  3. 训练过程在 GPU 上正常运行并保存 checkpoint
**Plans**: TBD

Plans:
- [ ] 03-01: TBD (to be planned)

### Phase 4: Execution & Validation
**Goal**: 提供统一执行接口和完整流程验证机制
**Depends on**: Phase 3
**Requirements**: EXEC-01, EXEC-02, EXEC-03, EXEC-04, EXEC-05, EXEC-06, VALID-01, VALID-02, VALID-03, VALID-04
**Success Criteria** (what must be TRUE):
  1. run.sh 支持 --stage 参数分别执行 data/sft/grpo/all 阶段
  2. 所有执行在 Docker 中进行，失败时输出清晰错误
  3. 小规模验证模式能够在 10 分钟内完成端到端验证
  4. JSONL 格式自动验证通过
**Plans**: TBD

Plans:
- [ ] 04-01: TBD (to be planned)

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Code Cleanup | 3/3 | ✓ Complete | 2026-02-07 |
| 2. Data Generation | 3/3 | ✓ Complete | 2026-02-08 |
| 3. Training Pipeline | 0/TBD | Not started | - |
| 4. Execution & Validation | 0/TBD | Not started | - |

---
*Roadmap created: 2026-02-07*
*Last updated: 2026-02-08*
