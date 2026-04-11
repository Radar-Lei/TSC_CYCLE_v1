# Roadmap: TSC-CYCLE v2

## Milestones

- ✅ **v1.0 GLM-5 SFT 数据生成** — Phases 1-3 (shipped 2026-04-01)
- ✅ **v1.1 简化版 GRPO 训练** — Phases 4-5 (shipped 2026-04-02)
- ✅ **v1.2 简化版 GRPO 训练与验证** — Phases 6-7 (shipped 2026-04-07)
- ◆ **v1.3 Qwen3-32B SFT + GRPO 训练** — Phases 8-9 (active)

## Phases

### ◆ v1.3 Qwen3-32B SFT + GRPO 训练 (Phases 8-9) — ACTIVE

**Milestone goal:** 用 Qwen3-32B 基座重跑完整训练链路（SFT -> GRPO -> GGUF），验证大模型在交通信号配时任务上的效果。

- [ ] **Phase 8: 环境与脚本适配** - 显存检查、BnB 量化配置、输出目录按模型名参数化
- [ ] **Phase 9: 32B 训练与导出** - SFT 微调、GRPO 训练、GGUF 导出完整流水线

## Phase Details

### Phase 8: 环境与脚本适配
**Goal**: 开发者可以确认本机显存满足 32B 模型需求，并且训练脚本已适配 BnB 4-bit 量化和模型名参数化输出目录
**Depends on**: Phase 7
**Requirements**: ENV-01, ENV-02, ENV-03
**Success Criteria** (what must be TRUE):
  1. 开发者可以运行显存检查命令，确认可用显存足够加载 Qwen3-32B 4-bit 量化模型（或已释放足够空间）
  2. 训练脚本中 Unsloth + BnB 4-bit 量化配置已就绪，可以成功加载 Qwen3-32B 模型而不 OOM
  3. SFT 和 GRPO 训练脚本的输出目录按模型名参数化（如 `outputs/sft/qwen3-32b/`、`outputs/grpo_simple/qwen3-32b/`），不覆盖已有的 4B 产物
**Plans**: TBD

### Phase 9: 32B 训练与导出
**Goal**: 开发者完成 Qwen3-32B 的 SFT -> GRPO -> GGUF 完整训练链路，产出可用模型文件
**Depends on**: Phase 8
**Requirements**: TRAIN-01, TRAIN-02, TRAIN-03
**Success Criteria** (what must be TRUE):
  1. SFT 训练完成，`outputs/sft/qwen3-32b/model` 目录包含可加载的完整 Qwen3-32B SFT 模型
  2. 使用 SFT 产出模型完成简化版 GRPO 训练，`outputs/grpo_simple/qwen3-32b/model` 目录包含可加载的完整 GRPO 模型
  3. SFT 和 GRPO 模型均已导出 GGUF 格式（Q4_K_M、Q8_0、F16），文件存在于各自输出目录下
**Plans**: TBD

<details>
<summary>✅ v1.2 简化版 GRPO 训练与验证 (Phases 6-7) — SHIPPED 2026-04-07</summary>

- [x] Phase 6: GRPO 训练执行与产物固化 — completed
- [x] Phase 7: 自动验证脚本 — completed

Full details: `.planning/milestones/v1.2-ROADMAP.md`

</details>

<details>
<summary>✅ v1.1 简化版 GRPO 训练 (Phases 4-5) — SHIPPED 2026-04-02</summary>

- [x] Phase 4: 简化版 Reward 与解析核心 (1/1 plans) — completed 2026-04-02
- [x] Phase 5: 简化版训练入口与验证 (1/1 plans) — completed 2026-04-02

Full details: `.planning/milestones/v1.1-ROADMAP.md`

</details>

<details>
<summary>✅ v1.0 GLM-5 SFT 数据生成 (Phases 1-3) — SHIPPED 2026-04-01</summary>

- [x] Phase 1: API 客户端与数据采样 (2/2 plans) — completed 2026-03-25
- [x] Phase 2: 批量推理链生成 (2/2 plans) — completed 2026-03-25
- [x] Phase 3: 数据组装、训练验证与模型导出 (3/3 plans) — completed 2026-03-25

Full details: `.planning/milestones/v1.0-ROADMAP.md`

</details>

## Current Status

Active milestone: **v1.3 Qwen3-32B SFT + GRPO 训练**.
Next up: **Phase 8: 环境与脚本适配**.
Coverage: **6/6 v1.3 需求已映射**。

## Next Candidates

- `EVAL-02`: 比较简化版 GRPO 与完整版 SUMO reward GRPO 的训练结果差异
- `ARWD-01`: 在饱和度比例 reward 之上叠加 queue、delay 或 throughput 目标
- `COMP-01`: 对比 Qwen3-4B 和 Qwen3-32B 在同一评测集上的效果差异

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. API 客户端与数据采样 | v1.0 | 2/2 | Complete | 2026-03-25 |
| 2. 批量推理链生成 | v1.0 | 2/2 | Complete | 2026-03-25 |
| 3. 数据组装、训练验证与模型导出 | v1.0 | 3/3 | Complete | 2026-03-25 |
| 4. 简化版 Reward 与解析核心 | v1.1 | 1/1 | Complete | 2026-04-02 |
| 5. 简化版训练入口与验证 | v1.1 | 1/1 | Complete | 2026-04-02 |
| 6. GRPO 训练执行与产物固化 | v1.2 | — | Complete | 2026-04-07 |
| 7. 自动验证脚本 | v1.2 | — | Complete | 2026-04-07 |
| 8. 环境与脚本适配 | v1.3 | 0/0 | Not started | — |
| 9. 32B 训练与导出 | v1.3 | 0/0 | Not started | — |
