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
