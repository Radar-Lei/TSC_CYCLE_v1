# TSC-CYCLE v2: SFT + 简化版 GRPO 训练

## What This Is

TSC-CYCLE 是一个基于 LLM 的交通信号配时优化系统，目标是在给定各相位预测饱和度和绿灯约束的条件下，输出下一周期的相位绿灯分配方案。v1.0 已完成 GLM-5 数据生成、SFT 训练验证和 GGUF 导出；v1.1 已实现不依赖 SUMO 仿真的简化版 GRPO 训练链路；v1.2 聚焦把这条链路真正跑通，并对训练产出的模型做自动测试验证。

## Core Value

让模型在严格输出格式和绿灯约束下，稳定学会按输入饱和度分配合理的相位绿灯时间。

## Current Milestone: v1.3 Qwen3-8B SFT + GRPO 训练

**Goal:** 用 Qwen3-8B 基座重跑完整训练链路（SFT → GRPO → GGUF），并用 4000 条数据做自动验证。

**Target features:**
- 用现有 SFT 数据对 unsloth/Qwen3-8B 做 SFT 微调，产出 SFT 模型（全精度，不用 BnB）
- 用 SFT 产出的 8B 模型做简化版 GRPO 训练，产出 GRPO 模型
- 将 SFT 和 GRPO 模型分别导出 GGUF 格式
- 输出目录按模型名隔离（如 `outputs/sft/qwen3-8b/`、`outputs/grpo_simple/qwen3-8b/`）
- 用 validate.py 对 GRPO 产出模型跑 4000 条数据的格式/约束/饱和度自动验证

## Current State

**Shipped:** v1.0 (2026-04-01), v1.1 (2026-04-02), v1.2 (2026-04-07)
**Codebase:** 已包含 `src/glm5/`、`src/sft/`、`src/grpo/`、`src/grpo_simple/` 四套主流程代码，其中 `src/grpo/` 为带 SUMO reward 的完整版实现，`src/grpo_simple/` 为无仿真的简化版实现
**Tech stack:** Python 3、OpenAI SDK、Unsloth、TRL、pytest、Docker、SUMO

已交付的能力：
- GLM-5 API 客户端（4 并发，指数退避重试，max_tokens=8192）
- 分层抽样器（按 tl_id × 饱和度桶从 16,788 条中抽 5,000 条）
- Prompt 构建器 + 约束校验器（相位顺序、绿灯范围、整数约束）
- 批量生成编排器（断点续传、逐条写入、实时进度）
- SFT 数据组装脚本（results.jsonl → sft_train.jsonl）
- SFT 训练验证（1 epoch）
- GGUF 导出（Q4_K_M、Q8_0、F16）
- 简化版 reward（格式 + 约束 + 饱和度比例）
- 简化版 GRPO 数据生成与 Docker 训练入口
- benchmark 批量评测子系统（模型列表配置、结果目录、comparison CSV 汇总）
- Qwen3-4B 简化版 GRPO 训练已跑通，产出模型和 GGUF

当前缺口：
- 尚未验证 Qwen3-8B 基座在同一链路上的效果

## Requirements

### Validated

- ✓ GLM-5 API 客户端（OpenAI 兼容接口，并发 4，指数退避重试）— v1.0
- ✓ 从 train.jsonl 中均匀抽样 5000 条样本 — v1.0
- ✓ GLM-5 生成 think 链 + solution（端到端推理）— v1.0
- ✓ 约束校验 + 丢弃重试（最多 3 次）— v1.0
- ✓ 组装最终 SFT 训练数据（messages 格式）— v1.0
- ✓ 进度追踪与断点续传（大规模 API 调用容错）— v1.0
- ✓ SFT 训练验证（用新数据重新训练确认效果，1 epoch）— completed post-v1.0
- ✓ 模型导出（Q4_K_M、Q8_0、F16 三种 GGUF 量化格式）— completed post-v1.0
- ✓ 在独立新目录中实现简化版 GRPO 训练入口，不覆盖现有 `src/grpo/` — v1.1
- ✓ reward 保持 SFT 输出格式要求，并继续校验 phase 顺序、整数 final、最小/最大绿约束 — v1.1
- ✓ reward 基于 `pred_saturation` 比例分配目标绿灯时间，不再通过 SUMO 仿真计算 — v1.1
- ✓ 补充基础测试，验证 reward 在命中、偏离、越界和格式错误时的行为 — v1.1
- ✓ 用 Qwen3-4B 跑通简化版 GRPO 真实训练，产出模型和训练日志 — v1.2
- ✓ GRPO 模型导出 GGUF 格式（Q4_K_M、Q8_0、F16）— v1.2

### Active

- [ ] 用现有 SFT 数据对 unsloth/Qwen3-8B 做 SFT 微调，产出模型（全精度，不用 BnB）
- [ ] 用 SFT 产出的 Qwen3-8B 模型做简化版 GRPO 训练，产出 GRPO 模型
- [ ] 将 SFT 和 GRPO 模型分别导出 GGUF 格式
- [ ] 输出目录按模型名隔离（outputs/sft/qwen3-8b/、outputs/grpo_simple/qwen3-8b/）
- [ ] 用 validate.py 对 GRPO 产出模型跑 4000 条数据验证（格式/约束/饱和度）

### Out of Scope

- 旧版 `src/grpo/` 重构或与 `src/grpo_simple/` 合并 — 保留现有完整版流水线
- 接入 benchmark 批测框架 — 本里程碑用独立验证脚本，不走 benchmark/run_batch.py
- 多目标 reward 调参 — 先验证现有闭环能否训练出合格模型
- 大规模超参数搜索 — 先跑通单次训练和验证

## Context

- **现有 SFT 模型已可用**：`outputs/sft/model` 已由前序工作产出，可作为 GRPO 初始模型
- **旧版 GRPO 已存在**：`src/grpo/`、`docker/grpo_train.sh` 和 `src/grpo/rewards.py` 当前依赖 SUMO baseline 与仿真 reward
- **提示词与输出协议已稳定**：继续使用 `<start_working_out>/<end_working_out>/<SOLUTION>` 标签和相同的 solution JSON 结构
- **输入信号已足够支撑简化 reward**：prompt 中包含 `phase_waits[*].pred_saturation`、`min_green`、`max_green`
- **简化版数据源已明确**：直接使用 `outputs/data/train.jsonl` 派生 GRPO prompt 数据，不依赖 GLM-5 SFT 样本
- **简化版训练链路已具备**：`docker/grpo_simple_data.sh` 可真实生成数据，`docker/grpo_simple_train.sh` 已具备前置检查和独立输出目录
- **benchmark 子系统已具备批测框架**：`benchmark/run_batch.py` 通过 `benchmark/config/batch_config.json` 组织多模型评测，并输出 comparison CSV
- **benchmark 调用路径是 API 驱动**：`benchmark/llm_client.py` 通过 OpenAI-compatible API 调模型，不会直接读取本地模型目录
- **里程碑策略变化**：本阶段不追求高保真 reward 扩展，先验证“训练完成 -> benchmark 自动验证”的闭环

## Constraints

- **输出协议**：必须保持 `<start_working_out>/<end_working_out>/<SOLUTION>` — 兼容现有 SFT 模型与数据格式
- **约束要求**：`final` 必须为整数，且满足 `min_green <= final <= max_green` — 这是硬约束
- **隔离实现**：简化版 GRPO 代码必须放在新目录 — 避免影响现有完整版 `src/grpo/`
- **训练环境**：必须使用 Unsloth Docker — 与现有训练镜像保持一致
- **数据来源**：默认不使用 GLM-5 SFT 数据作为简化版 GRPO 数据源 — 直接从原始 `train.jsonl` 生成
- **验证方式**：用独立验证脚本直接加载模型推理，不通过 benchmark API 链路 — 轻量、快速、无外部依赖
- **自动化目标**：验证脚本自动喂数据、解析输出、检查格式/约束/饱和度比例，输出通过/失败结论

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| 用 GLM-5 生成 think + solution | 端到端推理更自然，think 和 solution 内在一致 | ✓ Good — 管道已就绪 |
| 5000 条数据量 | 50x 现有数据，充分覆盖多样场景 | ✓ Good — 抽样器覆盖全部 34 个交叉口 |
| SFT 训练 1 epoch | 数据量充足，1 epoch 防止过拟合 | ✓ Good — 已完成训练验证 |
| 丢弃重试策略 | 保证每条数据约束完全满足 | ✓ Good — BatchGenerator 已实现 |
| 并发 4 | 用户指定，稳定可控 | ✓ Good |
| 导出 Q4_K_M/Q8_0/F16 三种 GGUF | 覆盖不同精度-性能需求 | ✓ Good — 已完成导出 |
| 按 (tl_id, 饱和度桶) 二维分层抽样 | 保证每个交叉口和饱和度级别至少有 1 个样本 | ✓ Good |
| ThreadPoolExecutor 而非 asyncio | 简单可靠，worker 数与并发数一致 | ✓ Good |
| validate_constraints fail-fast | 遇到第一个违反立即返回，减少无效计算 | ✓ Good |
| assemble_sft_record 兼容双格式 | 适配 BatchGenerator 嵌套输出和简化格式 | ✓ Good |
| v1.1 新增 `src/grpo_simple/` 而非直接改 `src/grpo/` | 简化版与完整版目标不同，隔离实现更安全 | ✓ Good |
| v1.1 reward 改为“格式 + 约束 + 饱和度比例” | 先去掉 SUMO 外部依赖，验证最小可用 RL 闭环 | ✓ Good |
| v1.1 数据默认来自 `outputs/data/train.jsonl` | 避免沿用可能不满足新目标的 GLM-5 SFT 样本 | ✓ Good |
| v1.2 先跑通训练再考虑 reward 扩展 | 先证明当前最小闭环能产出合格模型 | — Pending |
| v1.2 用独立验证脚本而非 benchmark 批测 | 轻量快速，专注格式/约束/饱和度比例三项核心检查 | — Pending |
| v1.3 用 Qwen3-8B 替代 32B | 8B 全精度在 DGX-Spark 显存无压力，不需要 BnB 量化 | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `$gsd-transition`):
1. Requirements invalidated? -> Move to Out of Scope with reason
2. Requirements validated? -> Move to Validated with phase reference
3. New requirements emerged? -> Add to Active
4. Decisions to log? -> Add to Key Decisions
5. "What This Is" still accurate? -> Update if drifted

**After each milestone** (via `$gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check -> still the right priority?
3. Audit Out of Scope -> reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-04-11 after redefining v1.3 milestone (Qwen3-8B, no BnB)*
