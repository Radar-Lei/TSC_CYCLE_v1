# Phase 2: Data Generation - Context

**Gathered:** 2026-02-08
**Status:** Ready for planning

<domain>
## Phase Boundary

数据生成流程能够稳定运行并产出训练数据。系统自动发现场景、解析交叉口配置、以交叉口为单位并行执行 SUMO 仿真、检测信号周期边界并采样、输出 JSONL 格式的训练数据。SFT/GRPO 训练属于 Phase 3。

</domain>

<decisions>
## Implementation Decisions

### 并行执行策略
- 任一交叉口仿真失败时，立即停止所有执行（fail-fast）
- 最大并发数由用户在 config.json 中配置
- 不设置超时机制，信任 SUMO 正常结束
- 日志输出采用简洁模式：只显示当前进度和最终结果

### 数据输出与格式
- TrainingSample 字段结构保持不变：prompt / prediction / state_file / metadata
- CoT 数据保持 Prompt 引导方式：不预生成 CoT，通过 `<think>...</think>` 标签引导模型在训练时生成
- 所有输出路径统一到 outputs/ 目录（包括原 data/training/ 和 data/states/ 的内容）

### 周期检测与采样
- 保持现有的 CycleDetector + PredictiveSampler 前瞻仿真采样逻辑
- 全量采样：每个周期边界都采样，不跳过

### 场景发现与配置
- 默认扫描 environments/ 下所有场景子目录
- 支持通过参数指定场景子集（只控制场景选择，不支持其他参数覆盖）
- 缺少必要配置文件（.net.xml / .sumocfg）时立即报错停止
- 交叉口配置解析方式保持不变

### 仿真状态快照
- 保持每个周期边界保存 SUMO 状态快照，供 GRPO 训练使用
- 不压缩，直接保存 .xml 格式
- 快照路径统一到 outputs/ 目录

### Claude's Discretion
- JSONL 文件的粒度拆分方式（按场景 vs 按交叉口）
- 具体的输出子目录结构
- 并行任务的调度实现细节

</decisions>

<specifics>
## Specific Ideas

- 已有扁平任务池基础（Phase 1 重构成果），并行调度应基于此继续
- 前瞻仿真是核心特性：推进一个完整周期计算预测饱和度，然后恢复状态，不改变仿真进度

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 02-data-generation*
*Context gathered: 2026-02-08*
