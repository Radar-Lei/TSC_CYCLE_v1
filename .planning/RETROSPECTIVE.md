# Project Retrospective

*A living document updated after each milestone. Lessons feed forward into future planning.*

## Milestone: v1.0 — GLM-5 SFT 数据生成

**Shipped:** 2026-04-01
**Phases:** 3 | **Plans:** 7 | **Sessions:** ~3

### What Was Built
- GLM-5 API 客户端（并发 4，指数退避重试，max_tokens=8192）
- 分层抽样器（按 tl_id × 饱和度桶二维分层，覆盖 34 个交叉口）
- Prompt 构建器 + 约束校验器（相位顺序、绿灯范围、整数约束）
- 批量生成编排器（断点续传、约束重试 3 次、实时进度）
- SFT 数据组装脚本（results.jsonl → sft_train.jsonl）

### What Worked
- TDD 流程高效：先写测试、再实现，每个模块都有对应的 test 文件
- 复用现有 PromptBuilder 设计，GLM-5 prompt 只需追加 think 链引导
- 二维分层抽样设计精准覆盖所有场景维度
- BatchGenerator 的断点续传设计，对大规模 API 调用非常关键

### What Was Inefficient
- Phase 3 的 Docker 训练和导出任务全部 deferred，说明计划阶段对 Docker 依赖的工作划分不够细致
- 所有 22 个 commit 在同一天完成，集中度过高

### Patterns Established
- `src/glm5/` 作为独立模块，与现有 `src/` 代码解耦
- assemble_sft_record 的双格式兼容模式，应对上游输出格式变化
- validate_constraints 的 fail-fast 模式

### Key Lessons
1. Docker 环境任务应在计划阶段明确标记为"需手动执行"，避免 deferred 积累
2. 大规模 API 调用的编排器设计（断点续传 + 逐条写入）是必备能力
3. 二维分层抽样（entity × feature bucket）是确保数据覆盖的有效模式

### Cost Observations
- Model mix: 100% opus
- Sessions: ~3
- Notable: 整个里程碑代码实现在单日内完成，效率较高

---

## Milestone: v1.3 — Qwen3-8B SFT + GRPO 训练

**Shipped:** 2026-04-14
**Phases:** 3 | **Plans:** 4 | **Sessions:** ~3 (2026-04-11 → 2026-04-14)

### What Was Built
- config_8b.json 参数化配置（模型名隔离输出路径，load_in_4bit=false）
- Qwen3-8B SFT 训练（全精度，2 epochs，4-shard 15.4GB 模型）
- SFT 模型 GGUF 导出（F16/Q8_0/Q4_K_M，共 ~29GB）
- Qwen3-8B GRPO 训练（基于 SFT 产出，全精度）
- GRPO 模型 GGUF 导出（F16/Q8_0/Q4_K_M，共 ~29GB）
- 4000 条自动验证（格式 100%，约束 98.6%，整体 PASS）

### What Worked
- 训练实际在规划期间就已完成——规划系统只需补文档，不需要重新运行训练
- config 文件隔离策略完全避免了 4B 与 8B 产物的覆盖问题
- 2 epochs SFT（与 MEMORY.md 经验一致）直接产出高质量模型，无需调参

### What Was Inefficient
- GSD 规划文档（SUMMARY/VERIFICATION）在训练后才补写，规划与执行脱节
- Phase 10 的 PLAN 文档描述的命令接口（--model-path）与实际脚本（--config）不一致，属于文档错误

### Patterns Established
- 长时间 GPU 训练任务先执行、后补文档的工作模式（对 DGX-Spark 本地训练更务实）
- 按模型名隔离输出目录（outputs/sft/qwen3-8b/、outputs/grpo_simple/qwen3-8b/）已成为标准目录结构

### Key Lessons
1. 实际训练比规划先行时，GSD 工作流应切换到"补文档"模式——核查产物、创建 SUMMARY/VERIFICATION，而非重新执行
2. SFT epochs 已在 MEMORY.md 中固化为 2，无需每次里程碑重新讨论
3. validate.sh 脚本的 config 参数硬编码问题需在下个里程碑修复（低优先级技术债）

### Cost Observations
- Sessions: ~3
- Notable: 训练链路已完全可重复——换基座只需改 config，不需要改代码

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Sessions | Phases | Key Change |
|-----------|----------|--------|------------|
| v1.0 | ~3 | 3 | 首次使用 GSD 工作流，TDD 贯穿全程 |

### Cumulative Quality

| Milestone | Tests | Coverage | Zero-Dep Additions |
|-----------|-------|----------|-------------------|
| v1.0 | 6 test files | ~80% glm5 module | 0 |

### Top Lessons (Verified Across Milestones)

1. TDD + 模块化设计能在单日内交付完整的数据管道
2. Docker 环境任务需要额外的执行策略（不能假设自动化）
