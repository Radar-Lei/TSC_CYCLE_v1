# TSC-CYCLE v2: GLM-5 大规模 SFT 数据生成

## What This Is

TSC-CYCLE 是一个基于 LLM 的交通信号配时优化系统，通过 SFT + GRPO 两阶段训练 Qwen3-4B-Base 模型。当前 SFT 数据仅 100 条且思考链模板化，导致过拟合和推理深度不足。本里程碑的目标是利用 GLM-5 API 生成 5000 条高质量 SFT 训练数据，包含丰富多样的思考链和自主计算的 solution，并导出 GGUF 量化模型。

## Core Value

生成足够多样和深度的 SFT 训练数据，使 Qwen3-4B 学会真正的交通配时推理，而非模板化复读。

## Requirements

### Validated

- ✓ SUMO 仿真数据生成流水线 — existing
- ✓ 16,788 条原始训练样本 (train.jsonl) — existing
- ✓ SFT 训练框架 (Unsloth + LoRA) — existing
- ✓ GRPO 训练与奖励系统 — existing
- ✓ 约束校验体系 (相位顺序 + 绿灯范围) — existing
- ✓ 自定义标签体系 (start_working_out/SOLUTION) — existing
- ✓ Benchmark 评估系统 — existing

### Active

- [ ] GLM-5 API 客户端（OpenAI 兼容接口，并发 4，指数退避重试）
- [ ] 从 train.jsonl 中均匀抽样 5000 条样本
- [ ] GLM-5 生成 think 链 + solution（端到端推理）
- [ ] 约束校验 + 丢弃重试（最多 3 次）
- [ ] 组装最终 SFT 训练数据（messages 格式）
- [ ] 进度追踪与断点续传（大规模 API 调用容错）
- [ ] SFT 训练验证（用新数据重新训练确认效果，1 epoch）
- [ ] 模型导出（Q4_K_M、Q8_0、F16 三种 GGUF 量化格式）

### Out of Scope

- GRPO 训练调整 — 本里程碑聚焦 SFT 数据质量
- Benchmark 评估 — 训练完成后单独进行
- 新 SUMO 场景添加 — 现有 16,788 条足够

## Context

- **当前问题**：SFT 数据仅 100 条，think 链是公式化模板（"饱和度为 X，分配 Y"），模型过拟合，生成的推理链过短
- **GLM-5 API**：智谱 AI 提供，OpenAI 兼容接口
  - 端点：`https://open.bigmodel.cn/api/coding/paas/v4`
  - 模型：`glm-5`
  - 参考实现：`/home/samuel/projects/signalclaw` 中的 LLM 客户端
- **数据格式**：messages 格式 `[system, user, assistant]`，assistant 内容为 `<start_working_out>...<end_working_out><SOLUTION>...</SOLUTION>`
- **硬约束**：
  - 相位顺序必须与输入一致
  - 每个相位 `min_green ≤ final ≤ max_green`
  - solution 为 JSON 数组 `[{"phase_id": N, "final": N}, ...]`
- **现有基线**：saturation-proportional allocation（确定性公式）

## Constraints

- **API 并发**：4 个并发请求 — 避免触发 rate limit
- **重试策略**：约束违反时丢弃重试，最多 3 次 — 保证数据质量
- **平台**：DGX-Spark，无 vllm — 只能用远程 API
- **标签**：必须使用 `<start_working_out>/<end_working_out>/<SOLUTION>` — 避免 Qwen3 tokenizer 冲突
- **训练环境**：Phase 3 训练验证和模型导出必须在项目已有的 Unsloth Docker 容器中执行（`docker/Dockerfile` 基于 `unsloth/unsloth:dgxspark-latest`，含 SUMO + CUDA + Unsloth 全套依赖）。相关脚本：`docker/sft_train.sh`、`docker/entrypoint.sh`、`docker/run.sh`

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| 用 GLM-5 生成 think + solution | 端到端推理更自然，think 和 solution 内在一致 | — Pending |
| 5000 条数据量 | 50x 现有数据，充分覆盖多样场景 | — Pending |
| SFT 训练 1 epoch | 数据量充足，1 epoch 防止过拟合 | — Pending |
| 丢弃重试策略 | 保证每条数据约束完全满足，避免 think/solution 不一致 | — Pending |
| 并发 4 | 用户指定，稳定可控 | — Pending |
| 导出 Q4_K_M/Q8_0/F16 三种 GGUF | 覆盖不同精度-性能需求 | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd:transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-03-25 after revision (5000 samples, 1 epoch, GGUF export)*
