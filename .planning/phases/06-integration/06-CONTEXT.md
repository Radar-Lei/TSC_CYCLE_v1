# Phase 6: Integration - Context

**Gathered:** 2026-02-11
**Status:** Ready for planning

<domain>
## Phase Boundary

将新的 reward 公式、数据过滤逻辑和 baseline 计算集成到统一的 Docker 流水线中，形成完整的端到端流程：GRPO 数据生成 → 数据过滤 → baseline 计算 → GRPO 训练 → 结果分析。用户通过单一入口脚本执行完整流程。

</domain>

<decisions>
## Implementation Decisions

### Docker 流程串联
- 新建 `docker/grpo_pipeline.sh` 作为单一入口脚本，内部按顺序执行：数据生成 → 过滤 → baseline 计算 → 训练 → 结果分析
- 正确的执行顺序：先生成 GRPO 数据，然后过滤，基于过滤后数据算 baseline，最后训练
- Fail-fast 行为：任何一步失败立即停止整个流程
- 支持 `--skip-xxx` 参数跳过已完成的步骤（如 `--skip-filter`、`--skip-baseline`、`--skip-data` 等）
- 纯配置驱动：除 skip 参数外，所有训练参数从 config.json 读取，脚本不接受额外自定义参数
- 保留现有独立脚本（grpo_data.sh、grpo_train.sh 等）不变，pipeline 脚本调用它们

### 进度提示与日志
- 终端打印步骤进度：`[2/5] 过滤数据...` 格式
- 每个子步骤独立日志文件（如 grpo_generate.log、grpo_filter.log、grpo_baseline.log、grpo_train.log），保存到 `outputs/grpo/`
- 日志采用覆盖模式（非续写），每次运行重新生成
- 子步骤的详细输出同时显示在终端和写入日志文件（tee 行为）

### 配置驱动策略
- config.json 中只保留新的 reward 配置，删除旧配置，不支持新旧切换
- 过滤后的数据和 baseline **直接覆盖原始文件**（grpo_train.jsonl 和 baseline.json），训练脚本不需要改路径
- 训练脚本硬编码使用标准路径（grpo_train.jsonl、baseline.json）

### 训练前检查
- 检查内容：文件存在性（grpo_train.jsonl、baseline.json）、baseline 完整性（覆盖所有训练场景）、最少样本数阈值、reward 配置合法性
- 最少样本数阈值在 config.json 中配置
- 检查失败行为：Claude's Discretion

### Claude's Discretion
- 训练前检查的具体实现位置（shell 层 vs Python 层 vs 双层）
- 检查失败时的行为（fail-fast vs 汇总报告后停止）
- 具体的 skip 参数命名和组合逻辑
- 分析脚本的具体实现细节

</decisions>

<specifics>
## Specific Ideas

- 用户强调正确的流水线顺序：生成数据 → 过滤 → 基于过滤后数据算 baseline → 训练
- 日志保存到 `outputs/grpo/` 目录，采用覆盖模式
- 训练完成后自动运行分析脚本，输出 zero-std 比例、reward 分布统计、reward 表现趋势
- 分析报告保存到 `outputs/grpo/` 目录（如 grpo_analysis.txt）

### 端到端验证标准
- Zero-std 无效步比例显著下降（从之前的 ~20%）
- Reward 分布呈现连续梯度而非 0/5 二值化
- Reward 有稳步提升表现
- 完整流程无报错地跑完
- 需要跑完整训练来验证，不是只跑几步

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 06-integration*
*Context gathered: 2026-02-11*
