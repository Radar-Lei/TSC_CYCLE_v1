---
phase: 05-data-filtering
plan: 01
subsystem: grpo-training
tags: [data-quality, filtering, preprocessing]
dependency_graph:
  requires: [04-02-reward-validation]
  provides: [filtered-training-data, data-filter-tool]
  affects: [grpo-training-pipeline, baseline-computation]
tech_stack:
  added: []
  patterns: [regex-extraction, streaming-jsonl-processing, statistical-reporting]
key_files:
  created:
    - src/scripts/filter_grpo_data.py
    - docker/filter_data.sh
  modified:
    - config/config.json
decisions:
  - "阈值设定: saturation_sum < 0.1 剔除空交叉口和极低流量样本 (基于数据分析: 14% 样本 total_sat=0, 18% < 0.1)"
  - "双输出文件: filtered + rejected，保留原始数据不变，支持后续分析"
  - "统计报告: 终端 + 文本文件，包含样本数、剔除比例、流量分布（min/max/mean/median）"
  - "Docker 串联: filter_data.sh 自动执行 过滤 → baseline 重算，支持 --skip-baseline 跳过"
  - "复用 baseline.py 的正则模式提取 phase_waits，保证一致性"
metrics:
  duration_seconds: 331
  completed_date: "2026-02-11T08:18:40Z"
---

# Phase 05 Plan 01: GRPO Data Filtering Summary

**一句话总结:** 创建过滤脚本从 grpo_train.jsonl 中剔除 17.9% 的空交叉口/极低流量样本（16788 → 13781 条），提升训练效率。

## 执行概览

**目标:** 从 GRPO 训练数据中剔除所有相位 pred_saturation 总和低于阈值的样本，提升训练数据质量和效率。

**背景:** 数据分析显示约 14% 样本所有相位 pred_saturation=0（空交叉口），另有约 4% 极低流量样本。这些样本在 GRPO 训练中无贡献（baseline passed=0, queue=0 时 reward 无法产生有意义梯度），浪费计算资源。

**成果:**
- ✅ 过滤脚本 `src/scripts/filter_grpo_data.py` (260+ 行)
- ✅ Docker 入口脚本 `docker/filter_data.sh` (135 行)
- ✅ 配置驱动的过滤参数 `config.json` (data_filter 配置块)
- ✅ 实际过滤结果: 16788 → 13781 条（剔除 3007 条，17.9%）

## 任务执行详情

### Task 1: 创建过滤脚本 + 更新 config.json

**Commit:** `03ee5fd`

**文件修改:**
- `config/config.json`: 新增 `training.grpo.data_filter` 配置块
  - `saturation_sum_threshold`: 0.1（阈值）
  - `output_suffix`: "_filtered"
  - `rejected_suffix`: "_rejected"

- `src/scripts/filter_grpo_data.py`: 新建过滤脚本（260 行）
  - `parse_saturation_sum(sample)`: 从 prompt 提取 phase_waits JSON，计算 saturation_sum
  - `filter_data(...)`: 主过滤函数，逐行读取 jsonl，按阈值分流到 filtered/rejected
  - `calculate_distribution_stats(values)`: 计算 min/max/mean/median
  - `format_report(stats)`: 生成中文统计报告
  - `main()`: argparse + config 加载 + 执行过滤 + 输出报告

**关键实现细节:**
- 复用 baseline.py 的正则模式: `r'"phase_waits"\s*:\s*(\[.*?\])'` 提取 JSON 数组
- 流式处理: 逐行读取避免内存占用（16k+ 样本）
- 统计收集: 所有样本/保留/剔除的 saturation_sum 分布
- 双输出: 终端打印 + 文本文件（grpo_train_filter_report.txt）

**实际运行结果:**
```
过滤前: 16788 条
过滤后: 13781 条
剔除: 3007 条 (17.9%)

流量分布 (saturation_sum):
  全部样本: min=0.0000 max=5.7468 mean=0.9031 median=0.8110
  保留样本: min=0.1000 max=5.7468 mean=1.0973 median=0.9140
  剔除样本: min=0.0000 max=0.0999 mean=0.0127 median=0.0000
```

**验证通过:**
- ✅ Python 语法检查
- ✅ Config 字段验证（data_filter 存在且包含必需字段）
- ✅ 实际运行生成 filtered + rejected + report 文件
- ✅ 行数验证: 13781 + 3007 = 16788

---

### Task 2: 创建 Docker 入口脚本 filter_data.sh

**Commit:** `c860380`

**文件创建:**
- `docker/filter_data.sh`: Docker 容器入口脚本（135 行，可执行）

**脚本功能:**
1. **步骤 1: 数据过滤**
   - 容器名 `grpo-filter`
   - 执行 `python3 -m src.scripts.filter_grpo_data --config config/config.json`
   - 透传参数（如 `--threshold 0.2`）

2. **步骤 2: Baseline 重算**（可选）
   - 容器名 `grpo-baseline-filtered`
   - 基于 `grpo_train_filtered.jsonl` 重新计算 baseline.json
   - 执行 `python3 -m src.grpo.baseline --input outputs/grpo/grpo_train_filtered.jsonl --output outputs/grpo/baseline.json --workers 16`
   - 支持 `--skip-baseline` 跳过此步骤

**参数处理:**
- 解析 `--skip-baseline` 标志（从 `$@` 提取）
- 其他参数透传给 filter_grpo_data.py

**Docker 配置:**（参照 grpo_baseline.sh）
- `--rm`, `--gpus all`, `--shm-size=32GB`
- `--user "$(id -u):$(id -g)"` 保持文件权限
- 挂载项目目录 `-v "${PROJECT_DIR}:${CONTAINER_WORKDIR}:rw"`
- 环境变量 `SUMO_HOME=/usr/share/sumo`

**验证通过:**
- ✅ Bash 语法检查 (`bash -n`)
- ✅ 可执行权限（`chmod +x`）
- ✅ 包含 `filter_grpo_data` 调用
- ✅ 包含 `baseline` 调用
- ✅ 包含 `skip-baseline` 标志处理

---

## Deviations from Plan

无 - 计划严格按照规范执行。所有任务均按预期完成，无需偏离。

---

## Technical Notes

### 过滤脚本设计亮点

1. **配置驱动 + CLI 覆盖:** 默认从 config.json 读取，CLI 参数可覆盖任何配置
2. **路径自动推导:** 基于输入文件名 + suffix 自动生成输出路径（`grpo_train.jsonl` → `grpo_train_filtered.jsonl`）
3. **健壮的 JSON 提取:** 使用 `re.DOTALL` 处理多行 JSON，异常时返回 0.0 而非崩溃
4. **统计分布完整:** 计算 min/max/mean/median，分别统计全部/保留/剔除三个集合
5. **双输出报告:** 终端（实时反馈）+ 文本文件（存档分析）

### Docker 脚本设计亮点

1. **串联自动化:** 一键完成 过滤 → baseline 重算，减少人工介入
2. **可选步骤:** `--skip-baseline` 支持快速测试过滤效果
3. **参数透传:** 灵活支持覆盖阈值等参数，无需修改脚本
4. **容器隔离:** 每步使用独立容器名，避免冲突，支持并发/调试

### 过滤效果数据

- **剔除比例:** 17.9%（与预期 18% 接近，数据分析准确）
- **保留样本流量:** mean=1.0973（显著高于全部样本 0.9031），median=0.9140
- **剔除样本流量:** mean=0.0127, median=0.0（确认为空/极低流量样本）
- **阈值合理性:** 0.1 是有效分界点（保留样本 min=0.1，剔除样本 max=0.0999）

---

## Files Changed

### Created (2 files)
- `src/scripts/filter_grpo_data.py` (260 行)
- `docker/filter_data.sh` (135 行)

### Modified (1 file)
- `config/config.json` (新增 4 行配置)

---

## Dependencies

**Requires:**
- Phase 04-02: Reward validation（依赖现有 grpo_train.jsonl 和 baseline.py 的 phase_waits 提取逻辑）

**Provides:**
- `grpo_train_filtered.jsonl`: 过滤后的高质量训练数据
- `filter_grpo_data.py`: 可复用的数据过滤工具
- `filter_data.sh`: 自动化过滤 + baseline 重算流程

**Affects:**
- GRPO 训练流程: 后续训练将使用 filtered 数据，提升效率和收敛速度
- Baseline 预计算: 需要基于 filtered 数据重新计算（已集成到 filter_data.sh）

---

## Next Steps

1. **验证过滤效果:** 使用 filtered 数据训练一个小 epoch，观察 reward 分布和收敛情况
2. **更新训练脚本:** 修改 `docker/grpo_train.sh` 默认使用 `grpo_train_filtered.jsonl`
3. **Baseline 重算:** 运行 `./docker/filter_data.sh` 完整流程（不跳过 baseline），生成新 baseline.json
4. **进入 Phase 05-02:** 继续下一个计划（如有）

---

## Self-Check: PASSED

验证所有声明的文件和提交是否存在：

**创建的文件:**
- ✅ `/home/samuel/TSC_CYCLE/src/scripts/filter_grpo_data.py` 存在
- ✅ `/home/samuel/TSC_CYCLE/docker/filter_data.sh` 存在（可执行）

**修改的文件:**
- ✅ `/home/samuel/TSC_CYCLE/config/config.json` 包含 `data_filter` 字段

**生成的输出文件:**
- ✅ `/home/samuel/TSC_CYCLE/outputs/grpo/grpo_train_filtered.jsonl` 存在 (13781 行)
- ✅ `/home/samuel/TSC_CYCLE/outputs/grpo/grpo_train_rejected.jsonl` 存在 (3007 行)
- ✅ `/home/samuel/TSC_CYCLE/outputs/grpo/grpo_train_filter_report.txt` 存在

**提交记录:**
- ✅ Commit `03ee5fd` 存在（Task 1: filter script + config）
- ✅ Commit `c860380` 存在（Task 2: Docker entry script）

**验证命令已执行:**
- ✅ 行数验证: 13781 + 3007 = 16788（总和匹配）
- ✅ 语法检查: Python 和 Bash 脚本均通过
- ✅ 配置字段: data_filter 存在且包含必需字段

所有检查通过 ✅
