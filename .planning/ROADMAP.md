# Roadmap: TSC-CYCLE v2

## Milestones

- ✅ **v1.0 GLM-5 SFT 数据生成** — Phases 1-3 (shipped 2026-04-01)
- ✅ **v1.1 简化版 GRPO 训练** — Phases 4-5 (shipped 2026-04-02)
- ◆ **v1.2 简化版 GRPO 训练与验证** — Phases 6-7 (active)

## Phases

### ◆ v1.2 简化版 GRPO 训练与验证 (Phases 6-7) — ACTIVE

**Milestone goal:** 在本机用现有 Docker 链路跑通一次简化版 GRPO 真实训练，并用独立验证脚本确认产出模型满足格式约束和饱和度比例分配。

- [ ] **Phase 6: GRPO 训练执行与产物固化** - 用现有 Docker 链路完成一次真实训练，产出模型、checkpoints 和日志
- [ ] **Phase 7: 自动验证脚本** - 编写独立验证脚本，加载模型推理并检查格式/约束/饱和度比例，输出通过/失败结论

## Phase Details

### Phase 6: GRPO 训练执行与产物固化
**Goal**: 开发者可以通过一条命令完成简化版 GRPO 真实训练，并在指定目录得到可复用的模型和完整训练记录
**Depends on**: Phase 5
**Requirements**: TRAIN-01, TRAIN-02
**Success Criteria** (what must be TRUE):
  1. 开发者运行 `docker/grpo_simple_train.sh` 后，训练从头到尾完成，无需手工干预
  2. 训练完成后 `outputs/grpo_simple/model` 目录包含可加载的完整模型文件
  3. `outputs/grpo_simple/` 下同时存在 checkpoints 子目录和带时间戳的训练日志文件
**Plans**: TBD

### Phase 7: 自动验证脚本
**Goal**: 开发者可以运行一个独立脚本，自动加载训练产出模型、喂测试数据、解析输出并给出格式/约束/饱和度比例的通过/失败结论
**Depends on**: Phase 6
**Requirements**: VERI-01, VERI-02, VERI-03, VERI-04, VERI-05
**Success Criteria** (what must be TRUE):
  1. 开发者运行验证脚本后，脚本自动加载 `outputs/grpo_simple/model` 并对测试数据集做推理，无需手工拼接命令
  2. 脚本检查每条输出的格式正确性（`<start_working_out>`/`<end_working_out>`/`<SOLUTION>` 标签完整、JSON 可解析）并报告格式通过率
  3. 脚本检查每条输出的约束满足情况（final 为整数、min_green <= final <= max_green、相位顺序正确）并报告约束通过率
  4. 脚本检查各相位绿灯时间是否与 pred_saturation 成比例，并报告饱和度比例偏差统计
  5. 脚本最终输出机器可读的 JSON 摘要，包含各项通过率和总体 PASS/FAIL 结论
**Plans**: TBD

<details>
<summary>✅ v1.0 GLM-5 SFT 数据生成 (Phases 1-3) — SHIPPED 2026-04-01</summary>

- [x] Phase 1: API 客户端与数据采样 (2/2 plans) — completed 2026-03-25
- [x] Phase 2: 批量推理链生成 (2/2 plans) — completed 2026-03-25
- [x] Phase 3: 数据组装、训练验证与模型导出 (3/3 plans) — completed 2026-03-25

Full details: `.planning/milestones/v1.0-ROADMAP.md`

</details>

<details>
<summary>✅ v1.1 简化版 GRPO 训练 (Phases 4-5) — SHIPPED 2026-04-02</summary>

- [x] Phase 4: 简化版 Reward 与解析核心 (1/1 plans) — completed 2026-04-02
- [x] Phase 5: 简化版训练入口与验证 (1/1 plans) — completed 2026-04-02

Full details: `.planning/milestones/v1.1-ROADMAP.md`

</details>

## Current Status

Active milestone: **v1.2 简化版 GRPO 训练与验证**.
Next up: **Phase 6: GRPO 训练执行与产物固化**.
Coverage: **7/7 v1.2 需求已映射**。

## Latest Milestone Outcome

- 已交付 `src/grpo_simple/` 简化版 reward 与训练入口
- 已交付 Docker 数据生成 / 训练脚本，输出目录隔离到 `outputs/grpo_simple/`
- 已归档完整 phase 细节到 `.planning/milestones/v1.1-ROADMAP.md`

## Next Candidates

- `EVAL-02`: 比较简化版 GRPO 与完整版 SUMO reward GRPO 的训练结果差异
- `ARWD-01`: 在饱和度比例 reward 之上叠加 queue、delay 或 throughput 目标
- `ARWD-02`: 探索不同的 target 归一化与全周期预算分配策略

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. API 客户端与数据采样 | v1.0 | 2/2 | Complete | 2026-03-25 |
| 2. 批量推理链生成 | v1.0 | 2/2 | Complete | 2026-03-25 |
| 3. 数据组装、训练验证与模型导出 | v1.0 | 3/3 | Complete | 2026-03-25 |
| 4. 简化版 Reward 与解析核心 | v1.1 | 1/1 | Complete | 2026-04-02 |
| 5. 简化版训练入口与验证 | v1.1 | 1/1 | Complete | 2026-04-02 |
| 6. GRPO 训练执行与产物固化 | v1.2 | 0/0 | Not started | — |
| 7. 自动验证脚本 | v1.2 | 0/0 | Not started | — |
