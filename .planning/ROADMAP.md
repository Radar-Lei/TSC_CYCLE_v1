# Roadmap: TSC-CYCLE v2

## Milestones

- ✅ **v1.0 GLM-5 SFT 数据生成** — Phases 1-3 (shipped 2026-04-01)
- ✅ **v1.1 简化版 GRPO 训练** — Phases 4-5 (shipped 2026-04-02)
- ✅ **v1.2 简化版 GRPO 训练与验证** — Phases 6-7 (shipped 2026-04-07)
- ✅ **v1.3 Qwen3-8B SFT + GRPO 训练** — Phases 8-10 (shipped 2026-04-14)

## Phases

<details>
<summary>✅ v1.3 Qwen3-8B SFT + GRPO 训练 (Phases 8-10) — SHIPPED 2026-04-14</summary>

- [x] Phase 8: 脚本参数化与全精度适配 (1/1 plans) — completed 2026-04-11
- [x] Phase 9: 8B 训练与导出 (2/2 plans) — completed 2026-04-12
- [x] Phase 10: 4000 条数据自动验证 (1/1 plan) — completed 2026-04-14

Full details: `.planning/milestones/v1.3-ROADMAP.md`

</details>

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

All milestones through v1.3 complete. Start `/gsd-new-milestone` for next milestone.

## Next Candidates

- `EVAL-02`: 比较简化版 GRPO 与完整版 SUMO reward GRPO 的训练结果差异
- `ARWD-01`: 在饱和度比例 reward 之上叠加 queue、delay 或 throughput 目标
- `COMP-01`: 对比 Qwen3-4B 和 Qwen3-8B 在同一评测集上的效果差异

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. API 客户端与数据采样 | v1.0 | 2/2 | Complete | 2026-03-25 |
| 2. 批量推理链生成 | v1.0 | 2/2 | Complete | 2026-03-25 |
| 3. 数据组装、训练验证与模型导出 | v1.0 | 3/3 | Complete | 2026-03-25 |
| 4. 简化版 Reward 与解析核心 | v1.1 | 1/1 | Complete | 2026-04-02 |
| 5. 简化版训练入口与验证 | v1.1 | 1/1 | Complete | 2026-04-02 |
| 6. GRPO 训练执行与产物固化 | v1.2 | — | Complete | 2026-04-07 |
| 7. 自动验证脚本 | v1.2 | — | Complete | 2026-04-07 |
| 8. 脚本参数化与全精度适配 | v1.3 | 1/1 | Complete | 2026-04-11 |
| 9. 8B 训练与导出 | v1.3 | 2/2 | Complete | 2026-04-12 |
| 10. 4000 条数据自动验证 | v1.3 | 1/1 | Complete | 2026-04-14 |
