# Roadmap: TSC-CYCLE

## Milestones

- ✅ **v1.0 MVP** — Phases 1-3 (shipped 2026-02-10)
- 🚧 **v1.1 Improve Reward & GRPO Data Filter** — Phases 4-6 (in progress)

## Phases

<details>
<summary>✅ v1.0 MVP (Phases 1-3) — SHIPPED 2026-02-10</summary>

- [x] Phase 1: SFT 数据与训练 (3/3 plans) — completed 2026-02-09
- [x] Phase 2: GRPO 数据准备 (1/1 plan) — completed 2026-02-10
- [x] Phase 3: GRPO 训练 (2/2 plans) — completed 2026-02-10

See: `.planning/milestones/v1.0-ROADMAP.md` for full details.

</details>

### 🚧 v1.1 Improve Reward & GRPO Data Filter (In Progress)

**Milestone Goal:** 解决 GRPO 训练中 reward 二值化（0 或满分）和无效样本问题，让 reward 信号更有区分度，数据集更干净。

#### Phase 4: Reward Enhancement
**Goal**: 改进 SUMO reward 公式和 baseline 基准策略，使不同质量的方案获得有区分度的分数，消除二值化问题
**Depends on**: Phase 3
**Requirements**: RWD-01, RWD-02, RWD-03, RWD-04
**Success Criteria** (what must be TRUE):
  1. SUMO reward 公式使用非线性压缩函数（log/sqrt），不同质量的配时方案得到有区分度的连续分数，不再出现 0 和满分的二值化
  2. Baseline 策略改为饱和度启发式基准（按 pred_saturation 比例分配绿灯时间），提供更高质量的比较基准
  3. 新的 baseline.json 文件生成完成，包含全部场景的饱和度启发式 baseline 数据（含 delay 指标）
  4. SUMO 仿真 reward 新增延误时间（delay）指标，reward 公式综合 throughput + queue + delay 三维评估
  5. 使用新 reward 公式和 baseline 运行测试仿真，验证 reward 分布呈现连续梯度而非二值分布
**Plans**: 2 plans

Plans:
- [ ] 04-01-PLAN.md — 核心逻辑：config 更新 + baseline 饱和度启发式重写 + reward 公式改善率/log压缩/delay
- [ ] 04-02-PLAN.md — 验证集成：SUMO reward 分布验证 + grpo_train.sh 训练前检查

#### Phase 5: Data Filtering
**Goal**: 过滤 GRPO 训练数据中的空交叉口样本，生成清洁的训练数据集并输出统计信息
**Depends on**: Phase 4
**Requirements**: DAT-01, DAT-02
**Success Criteria** (what must be TRUE):
  1. 数据过滤脚本能从 grpo_train.jsonl 中识别并剔除 baseline passed=0 且 queue=0 的空交叉口样本
  2. 生成过滤后的训练数据集文件（如 grpo_train_filtered.jsonl）
  3. 输出详细的统计报告，包括过滤前后样本数、各场景分布、各过滤原因的样本数量
**Plans**: TBD

Plans:
- [ ] 05-01: TBD

#### Phase 6: Integration
**Goal**: 将新的 reward 和数据过滤逻辑集成到配置、训练脚本和 Docker 流程中，形成完整的端到端流水线
**Depends on**: Phase 5
**Requirements**: INT-01, INT-02, INT-03
**Success Criteria** (what must be TRUE):
  1. config.json 中新增 reward 相关配置项（非线性压缩函数类型和参数），训练流程可通过配置切换 reward 策略
  2. GRPO 训练脚本 train.py 能加载过滤后的数据集，训练流程正常运行
  3. Docker 入口脚本（grpo_baseline.sh + 数据过滤 + grpo_train.sh）能串联执行完整流程：baseline 重新计算 → 数据过滤 → GRPO 训练
  4. 端到端运行测试通过，训练过程中 zero-std 无效步显著减少或消除
**Plans**: TBD

Plans:
- [ ] 06-01: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 4 → 5 → 6

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. SFT 数据与训练 | v1.0 | 3/3 | Complete | 2026-02-09 |
| 2. GRPO 数据准备 | v1.0 | 1/1 | Complete | 2026-02-10 |
| 3. GRPO 训练 | v1.0 | 2/2 | Complete | 2026-02-10 |
| 4. Reward Enhancement | v1.1 | 0/2 | Planning complete | - |
| 5. Data Filtering | v1.1 | 0/TBD | Not started | - |
| 6. Integration | v1.1 | 0/TBD | Not started | - |

**Overall:** 6 phases total, 6 plans complete (v1.0 finished)

---

*Roadmap created: 2026-02-09*
*Last updated: 2026-02-11 after Phase 4 planning*
