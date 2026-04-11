# Roadmap: TSC-CYCLE v2

## Milestones

- ✅ **v1.0 GLM-5 SFT 数据生成** — Phases 1-3 (shipped 2026-04-01)
- ✅ **v1.1 简化版 GRPO 训练** — Phases 4-5 (shipped 2026-04-02)
- ✅ **v1.2 简化版 GRPO 训练与验证** — Phases 6-7 (shipped 2026-04-07)
- ◆ **v1.3 Qwen3-8B SFT + GRPO 训练** — Phases 8-10 (active)

## Phases

### ◆ v1.3 Qwen3-8B SFT + GRPO 训练 (Phases 8-10) — ACTIVE

**Milestone goal:** 用 Qwen3-8B 基座重跑完整训练链路（SFT → GRPO → GGUF），并用 4000 条数据做自动验证。

- [ ] **Phase 8: 脚本参数化与全精度适配** - 训练脚本支持模型名参数化输出目录，移除 BnB 量化逻辑以适配 8B 全精度加载
- [ ] **Phase 9: 8B 训练与导出** - SFT 微调、GRPO 训练、GGUF 导出完整流水线
- [ ] **Phase 10: 4000 条数据自动验证** - 用 validate.py 对 GRPO 产出的 8B 模型跑 4000 条数据验证

## Phase Details

### Phase 8: 脚本参数化与全精度适配
**Goal**: 开发者可以通过参数指定模型名，训练脚本自动将产物输出到按模型名隔离的目录，且 8B 模型以全精度加载无需量化
**Depends on**: Phase 7
**Requirements**: ENV-01, ENV-02
**Success Criteria** (what must be TRUE):
  1. 开发者运行 SFT 训练脚本时可以通过参数指定模型名（如 `unsloth/Qwen3-8B`），输出目录自动变为 `outputs/sft/qwen3-8b/`，不覆盖已有的 4B 产物
  2. 开发者运行 GRPO 训练脚本时可以通过参数指定模型名，输出目录自动变为 `outputs/grpo_simple/qwen3-8b/`
  3. SFT 训练脚本中 BnB 4-bit 量化相关逻辑已移除或跳过，Qwen3-8B 以全精度成功加载到 GPU 上
**Plans:** 1 plan
Plans:
- [ ] 08-01-PLAN.md — 验证并固化 config_8b.json 配置与脚本兼容性

### Phase 9: 8B 训练与导出
**Goal**: 开发者完成 Qwen3-8B 的 SFT -> GRPO -> GGUF 完整训练链路，产出可用模型文件
**Depends on**: Phase 8
**Requirements**: TRAIN-01, TRAIN-02, TRAIN-03
**Success Criteria** (what must be TRUE):
  1. SFT 训练完成，`outputs/sft/qwen3-8b/model` 目录包含可加载的完整 Qwen3-8B SFT 模型（tokenizer + 权重文件齐全）
  2. 使用 SFT 产出的 8B 模型完成简化版 GRPO 训练，`outputs/grpo_simple/qwen3-8b/model` 目录包含可加载的完整 GRPO 模型
  3. SFT 模型已导出 GGUF 格式（Q4_K_M、Q8_0、F16），文件存在于 `outputs/sft/qwen3-8b/gguf/` 下
  4. GRPO 模型已导出 GGUF 格式（Q4_K_M、Q8_0、F16），文件存在于 `outputs/grpo_simple/qwen3-8b/gguf/` 下
**Plans**: TBD

### Phase 10: 4000 条数据自动验证
**Goal**: 用 validate.py 对 GRPO 产出的 8B 模型跑 4000 条数据验证，确认格式/约束/饱和度通过率达标
**Depends on**: Phase 9
**Requirements**: VAL-01
**Success Criteria** (what must be TRUE):
  1. validate.py 以 `--num-samples 4000` 对 `outputs/grpo_simple/qwen3-8b/model` 完成推理和验证，产出 JSON 结果
  2. 格式通过率 ≥ 80%，约束通过率 ≥ 80%（与 v1.2 验证标准一致）
  3. 验证结果 JSON 保存到 `outputs/grpo_simple/qwen3-8b/validation_results.json`
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

Active milestone: **v1.3 Qwen3-8B SFT + GRPO 训练**.
Next up: **Phase 8: 脚本参数化与全精度适配**.
Coverage: **6/6 v1.3 需求已映射**。

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
| 8. 脚本参数化与全精度适配 | v1.3 | 0/1 | Planning | — |
| 9. 8B 训练与导出 | v1.3 | 0/0 | Not started | — |
| 10. 4000 条数据自动验证 | v1.3 | 0/0 | Not started | — |
