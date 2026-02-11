# Phase 5: Data Filtering - Context

**Gathered:** 2026-02-11
**Status:** Ready for planning

<domain>
## Phase Boundary

过滤 GRPO 训练数据中的空交叉口和极低流量样本，生成清洁的训练数据集并输出统计信息。过滤目标是 grpo_train.jsonl（主数据），过滤后自动重跑 baseline.py 让 baseline.json 同步。

</domain>

<decisions>
## Implementation Decisions

### 过滤标准
- 过滤目标文件：grpo_train.jsonl（训练主数据），不直接过滤 baseline.json
- 过滤粒度：按单条记录（state_file + tl_id）过滤，不按整个场景过滤
- 过滤范围：空交叉口 + 极低流量样本，不处理高端异常值
- 判断数据源：从 grpo_train.jsonl 的原始数据判断（prompt 中的 phase_waits），不依赖 baseline.json
- 过滤指标：基于各相位 pred_saturation 的总和或类似指标判断流量水平
- 阈值：可配置，写入 config.json

### 输出文件设计
- 生成新文件，保留原始 grpo_train.jsonl 不动
- 输出路径可配置（config.json），默认后缀 _filtered
- 同时输出被剔除样本的 rejected 文件，不标注剔除原因

### 统计报告
- 输出到终端 + 纯文本文件
- 包含基本计数（过滤前后样本数、剔除数、剔除比例）
- 包含流量分布统计（min/max/mean/median）

### 脚本集成方式
- 新建独立 Python 脚本（如 src/scripts/filter_grpo_data.py）
- 新建 Docker 入口脚本（如 docker/filter_data.sh），串联：过滤 → baseline 重算
- 配置方式：config.json 驱动 + CLI 参数可覆盖

### Claude's Discretion
- 具体过滤指标的选择（pred_saturation 总和 vs passed+queue 等）
- 极低流量阈值的默认值
- 统计报告的具体格式和措辞
- rejected 文件的命名和路径规则
- baseline.py 串联调用的具体实现方式

</decisions>

<specifics>
## Specific Ideas

- 数据关联机制：grpo_train.jsonl 和 baseline.json 通过 state_file 关联，baseline.json 是查询表（由 baseline.py 从 grpo_train.jsonl 自动生成）
- baseline.py 按 state_file 去重，每个 state_file 只跑一次仿真 — 所以过滤 grpo_train.jsonl 后重跑 baseline.py 即可同步
- pred_saturation = pred_queue / capacity，可以从 prompt 中的 phase_waits 解析获得
- 所有相位 pred_saturation 接近 0 → 空/极低流量交叉口
- 原有 grpo_baseline.sh 的功能可以合并到新的 filter_data.sh 中，过滤后自动调用 baseline.py

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 05-data-filtering*
*Context gathered: 2026-02-11*
