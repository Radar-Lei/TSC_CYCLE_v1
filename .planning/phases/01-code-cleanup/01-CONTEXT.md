# Phase 1: Code Cleanup - Context

**Gathered:** 2026-02-07 (updated 2026-02-07)
**Status:** Ready for planning

<domain>
## Phase Boundary

清理冗余代码和配置，简化并行逻辑为单层结构。不添加新功能，不改变业务逻辑。代码库清理后应更简洁、配置统一、并行逻辑扁平化。

</domain>

<decisions>
## Implementation Decisions

### 时段配置清理
- 完全删除 `time_period.py` 文件（早高峰/晚高峰/平峰识别逻辑）
- 完全删除 `config.json` 中的 `time_ranges` 配置项
- 删除 `DaySimulator` 类及其时间范围解析、快进逻辑
- 仿真流程简化为：启动场景 → 逐步收集数据 → 场景自然结束（由 `.sumocfg` 的 `end` 值决定）
- 训练数据中不再包含时段标注
- 代码中不再维护独立的仿真时长配置

### 并行逻辑重构
- 删除三层嵌套并行（场景级、天级、交叉口级），改为扁平任务池模式
- 所有场景的所有交叉口展开为统一的任务列表，一个 worker 池并行消费
- 每个交叉口一个独立的 SUMO 实例
- Worker 处理完一个交叉口后直接从池中取下一个任务，不受场景边界限制
- 删除 `parallel_runner.py`（天级并行）
- 删除 `intersection_parallel.py`（交叉口级并行的旧实现）
- 错误处理：任一交叉口仿真失败则整体停止（fail-fast）

### 配置文件统一
- `config.json` 作为唯一配置源，移除各脚本中分散的硬编码默认值
- 保留命令行参数作为覆盖手段（命令行 > config.json）
- 删除 `schema.json` 及相关验证逻辑
- 清理配置中的冗余项（time_ranges 等）

### 输出路径统一
- 所有输出统一到 `outputs/` 目录下
- 消除 `output/`（单数）和 `data/` 的分散引用
- 子目录结构由 Claude 根据代码分析决定

### Shell 脚本清理
- Docker 中现有的 .sh 脚本大部分删除，最终只保留 4 个：data.sh、sft.sh、grpo.sh、run.sh
- 每个脚本完全独立可运行，不依赖其他脚本
- run.sh 串联执行全流程（data → sft → grpo）
- 其余所有 .sh 脚本全部删除

### 旧代码处理
- 全部清除：注释掉的代码、废弃参数（如 `--rou-dir`）、向后兼容函数（如 `run_single_scenario_mode`）
- 整文件删除废弃模块（time_period.py、DaySimulator 等），不保留占位符
- 不在清理后的代码中添加解释性注释，由 git 历史记录即可

### Claude's Discretion
- 仿真时长获取方式（从 `.sumocfg` 读取 or 让 SUMO 自行结束）
- `outputs/` 下的子目录结构设计
- 配置文件清理后的具体结构
- 清理过程中发现的其他小问题的处理方式
- 每个 .sh 脚本的薄厚程度（shell vs Python 分层）

</decisions>

<specifics>
## Specific Ideas

- 并行模式参考任务池/worker pool 模式，不按场景分批，而是全局调度
- 用户明确表示"把场景跑完就行"，仿真时长不需要代码层面控制
- 当前 `output/` vs `outputs/` 的不一致导致流程衔接可能出现"文件未找到"错误

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 01-code-cleanup*
*Context gathered: 2026-02-07*
