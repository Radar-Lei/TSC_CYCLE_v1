# TSC-CYCLE v2: GLM-5 大规模 SFT 数据生成

## What This Is

TSC-CYCLE 是一个基于 LLM 的交通信号配时优化系统，通过 SFT + GRPO 两阶段训练 Qwen3-4B-Base 模型。v1.0 里程碑完成了 GLM-5 数据生成管道的全部代码实现：从 API 客户端、分层抽样、批量推理链生成到 SFT 数据组装，形成了完整的端到端流水线。

## Core Value

生成足够多样和深度的 SFT 训练数据，使 Qwen3-4B 学会真正的交通配时推理，而非模板化复读。

## Current State

**Shipped:** v1.0 (2026-04-01)
**Codebase:** `src/glm5/` 模块 1,356 行 Python，22 commits，43 files changed
**Tech stack:** Python 3, OpenAI SDK, ThreadPoolExecutor, pytest

已交付的能力：
- GLM-5 API 客户端（4 并发，指数退避重试，max_tokens=8192）
- 分层抽样器（按 tl_id × 饱和度桶从 16,788 条中抽 5,000 条）
- Prompt 构建器 + 约束校验器（相位顺序、绿灯范围、整数约束）
- 批量生成编排器（断点续传、逐条写入、实时进度）
- SFT 数据组装脚本（results.jsonl → sft_train.jsonl）

待手动执行（Docker 环境）：
- `./docker/sft_train.sh` — SFT 训练验证
- `./docker/convert_gguf.sh` — GGUF 模型导出

## Requirements

### Validated

- ✓ GLM-5 API 客户端（OpenAI 兼容接口，并发 4，指数退避重试）— v1.0
- ✓ 从 train.jsonl 中均匀抽样 5000 条样本 — v1.0
- ✓ GLM-5 生成 think 链 + solution（端到端推理）— v1.0
- ✓ 约束校验 + 丢弃重试（最多 3 次）— v1.0
- ✓ 组装最终 SFT 训练数据（messages 格式）— v1.0
- ✓ 进度追踪与断点续传（大规模 API 调用容错）— v1.0

### Active

- [ ] SFT 训练验证（用新数据重新训练确认效果，1 epoch）— deferred from v1.0
- [ ] 模型导出（Q4_K_M、Q8_0、F16 三种 GGUF 量化格式）— deferred from v1.0

### Out of Scope

- GRPO 训练调整 — 本里程碑聚焦 SFT 数据质量
- Benchmark 评估 — 训练完成后单独进行
- 新 SUMO 场景添加 — 现有 16,788 条足够
- 多模型对比 — 先用 GLM-5 跑通流程

## Context

- **数据管道已就绪**：`src/glm5/` 包含 client、sampler、prompt_builder、validator、batch_generator、assembler 六个模块
- **标签体系**：使用 `<start_working_out>/<end_working_out>/<SOLUTION>` 避免 Qwen3 tokenizer 冲突
- **训练配置**：1 epoch，max_steps=-1（无限制），AdamW 8-bit，BF16
- **已知技术债**：config.json 中的 SFT 训练 epoch 数已从 2 调为 1

## Constraints

- **API 并发**：4 个并发请求 — 避免触发 rate limit
- **重试策略**：约束违反时丢弃重试，最多 3 次 — 保证数据质量
- **平台**：DGX-Spark，无 vllm — 只能用远程 API
- **标签**：必须使用 `<start_working_out>/<end_working_out>/<SOLUTION>` — 避免 Qwen3 tokenizer 冲突
- **训练环境**：Docker 容器 (`unsloth/unsloth:dgxspark-latest`)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| 用 GLM-5 生成 think + solution | 端到端推理更自然，think 和 solution 内在一致 | ✓ Good — 管道已就绪 |
| 5000 条数据量 | 50x 现有数据，充分覆盖多样场景 | ✓ Good — 抽样器覆盖全部 34 个交叉口 |
| SFT 训练 1 epoch | 数据量充足，1 epoch 防止过拟合 | — Pending (待训练验证) |
| 丢弃重试策略 | 保证每条数据约束完全满足 | ✓ Good — BatchGenerator 已实现 |
| 并发 4 | 用户指定，稳定可控 | ✓ Good |
| 导出 Q4_K_M/Q8_0/F16 三种 GGUF | 覆盖不同精度-性能需求 | — Pending (待导出) |
| 按 (tl_id, 饱和度桶) 二维分层抽样 | 保证每个交叉口和饱和度级别至少有 1 个样本 | ✓ Good |
| ThreadPoolExecutor 而非 asyncio | 简单可靠，worker 数与并发数一致 | ✓ Good |
| validate_constraints fail-fast | 遇到第一个违反立即返回，减少无效计算 | ✓ Good |
| assemble_sft_record 兼容双格式 | 适配 BatchGenerator 嵌套输出和简化格式 | ✓ Good |

## Evolution

This document evolves at phase transitions and milestone boundaries.

---
*Last updated: 2026-04-01 after v1.0 milestone*
