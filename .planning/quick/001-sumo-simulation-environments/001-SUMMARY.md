---
phase: quick-001
plan: 01
subsystem: data-generation
tags: [sumo, multi-scenario, training-data, environments]

# Dependency graph
requires:
  - phase: 05-docker-deployment
    provides: Docker部署环境和训练流程脚本
provides:
  - 多场景数据生成支持（51个SUMO场景）
  - discover_environments() 场景自动发现
  - 每场景独立 phase_config 生成
affects: [future-training, multi-scenario-learning]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "场景目录自动发现模式（*.sumocfg + *.net.xml + *.rou.xml）"
    - "多场景并行数据生成"
    - "每场景独立配置文件命名：phase_config_{name}.json"

key-files:
  created: []
  modified:
    - config/config.json
    - src/scripts/generate_training_data.py
    - docker/publish.sh

key-decisions:
  - "使用 environments_dir 替代单场景 net_file/sumocfg 配置"
  - "每个场景生成独立的 phase_config_{name}.json"
  - "使用场景名作为 base_date 标识（替代日期解析）"
  - "场景间并行而非交叉口内并行（每场景只有1个rou文件）"
  - "保留 --rou-dir 参数向后兼容，优先使用 --environments-dir"

patterns-established:
  - "场景发现：遍历目录查找 *.sumocfg/*.net.xml/*.rou.xml 三件套"
  - "预处理阶段：批量生成所有场景的 phase_config"
  - "数据生成阶段：场景级别并行（不再需要交叉口级别并行）"

# Metrics
duration: 9min
completed: 2026-02-07
---

# Quick Task 001: SUMO 多场景数据生成支持

**将数据生成从单个 chengdu 场景切换为 environments 目录下 51 个场景的自动遍历和并行处理**

## Performance

- **Duration:** 9 分钟
- **Started:** 2026-02-07T03:44:45Z
- **Completed:** 2026-02-07T03:54:21Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- 实现了 discover_environments() 函数自动发现 51 个 SUMO 场景
- 数据生成脚本支持多场景模式（--environments-dir 参数）
- publish.sh 预处理阶段遍历所有场景生成 phase_config
- 移除对 rou_month_generator.py 的依赖，直接使用场景原始文件

## Task Commits

每个任务都已原子化提交：

1. **Task 1: 重构 generate_training_data.py 支持多场景遍历** - `1aba9b4` (feat)
2. **Task 2: 更新 publish.sh 预处理和数据生成流程** - `8cc9560` (feat)

## Files Created/Modified

- `config/config.json` - 将 paths.net_file/sumocfg 替换为 paths.environments_dir
- `src/scripts/generate_training_data.py` - 添加 discover_environments() 和 run_multi_scenario_mode()
- `docker/publish.sh` - 更新 stage_preprocessing 和 stage_data_generation 支持多场景

## Decisions Made

1. **使用 environments_dir 配置** - 统一管理所有场景目录，不再为每个场景单独配置路径
2. **场景自动发现** - 遍历目录查找必需的 .sumocfg/.net.xml/.rou.xml 三个文件，缺失任一则跳过
3. **独立 phase_config 命名** - 每个场景生成 `phase_config_{scenario_name}.json`，避免冲突
4. **场景名作为日期标识** - 使用 `base_date: scenario_name` 而非从文件名解析日期
5. **场景级并行而非交叉口并行** - 每个场景只有 1 个 .rou.xml，不需要 --intersection-parallel

## Deviations from Plan

无 - 计划按原样执行。

## Issues Encountered

无 - 所有验证通过：

- ✓ 发现 51 个场景，所有场景的 .sumocfg/.net.xml/.rou.xml 文件都存在
- ✓ publish.sh 语法检查通过
- ✓ 不再引用 rou_month_generator.py
- ✓ config.json 正确配置 environments_dir

## User Setup Required

无 - 不需要外部服务配置。

## Next Phase Readiness

**准备就绪** - 可以执行 `./docker/publish.sh` 进行 51 个场景的完整数据生成。

**影响范围：**
- 数据生成时间将显著增加（51 个场景 vs 1 个场景）
- 每个场景生成独立的训练数据目录 `outputs/data/{scenario_name}/`
- 每个场景有独立的 phase_config 文件 `output/phase_config_{scenario_name}.json`

**潜在优化：**
- 可以考虑添加场景筛选参数（如只处理特定类型的场景）
- 可以考虑添加场景优先级排序（先处理重要场景）

---
*Phase: quick-001*
*Completed: 2026-02-07*

## Self-Check: PASSED

所有提交已验证存在:
- ✓ 1aba9b4 (Task 1)
- ✓ 8cc9560 (Task 2)

所有修改的文件已验证:
- ✓ config/config.json
- ✓ src/scripts/generate_training_data.py
- ✓ docker/publish.sh
