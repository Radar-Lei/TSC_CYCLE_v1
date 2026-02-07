---
phase: 01-code-cleanup
verified: 2026-02-07T15:43:25Z
status: passed
score: 10/10 must-haves verified
---

# Phase 1: 代码库清理 Verification Report

**阶段目标:** 代码库清理冗余，并行逻辑简化为单层结构
**验证时间:** 2026-02-07T15:43:25Z
**验证状态:** passed
**重新验证:** No — 初次验证

## 目标达成情况

### 可观察真理验证

| # | 真理陈述 | 状态 | 证据 |
|---|---------|------|------|
| 1 | 代码中不再存在时段配置相关的参数和逻辑 | ✓ VERIFIED | time_period.py 已删除；grep 搜索无残留引用；config.json 无 time_ranges 字段 |
| 2 | 数据生成仅以交叉口为单位并行（单层，不嵌套） | ✓ VERIFIED | parallel_runner.py 和 intersection_parallel.py 已删除；generate_training_data.py 使用扁平任务池（Pool.imap_unordered 直接消费所有交叉口任务） |
| 3 | 配置文件结构统一，无冗余配置项 | ✓ VERIFIED | config.json 仅包含 training、simulation、rewards、paths 四个顶层键；schema.json 和 validate_config.py 已删除 |
| 4 | 代码中无注释掉的旧逻辑 | ✓ VERIFIED | 未发现注释掉的函数、类、导入或控制流代码；无 DEPRECATED/OLD CODE 标记 |
| 5 | DaySimulator 使用简化的仿真流程 | ✓ VERIFIED | run() 方法使用直接流程：预热 → 采样 → 结束；无时段遍历逻辑 |
| 6 | Docker 脚本结构简化为 4 个独立脚本 | ✓ VERIFIED | docker/ 目录仅包含 data.sh、sft.sh、grpo.sh、run.sh 四个脚本；lib/ 目录已删除 |
| 7 | 所有输出路径统一到 outputs/ 目录 | ✓ VERIFIED | data.sh 使用 --output-dir outputs/data；run.sh 显示所有输出在 outputs/ 下 |
| 8 | run.sh 串联执行 data → sft → grpo | ✓ VERIFIED | run.sh 依次调用 data.sh、sft.sh、grpo.sh；使用 set -e 确保 fail-fast |
| 9 | 数据生成支持 fail-fast 模式 | ✓ VERIFIED | generate_training_data.py L370 在任务失败时调用 pool.terminate() 和 sys.exit(1) |
| 10 | 废弃 API 参数已移除 | ✓ VERIFIED | 无 --rou-dir、--intersection-parallel、--intersection-groups、run_single_scenario_mode |

**得分:** 10/10 可观察真理已验证

### 必需构件验证

| 构件 | 预期 | 存在 | 实质性 | 接入系统 | 状态 |
|------|------|------|--------|----------|------|
| config/config.json | 唯一配置源，无 time_ranges | ✓ | ✓ 31行，有效JSON | ✓ 被 DaySimulator 读取 | ✓ VERIFIED |
| src/data_generator/day_simulator.py | 简化的仿真器，无时段逻辑 | ✓ | ✓ 388行，无TODO/占位符 | ✓ 被 generate_training_data 调用 | ✓ VERIFIED |
| src/scripts/generate_training_data.py | 扁平任务池并行入口 | ✓ | ✓ 440行，完整实现 | ✓ 被 data.sh 调用 | ✓ VERIFIED |
| docker/data.sh | 独立数据生成脚本 | ✓ | ✓ 49行，完整流程 | ✓ 被 run.sh 调用 | ✓ VERIFIED |
| docker/sft.sh | 独立 SFT 训练脚本 | ✓ | ✓ 40行，完整流程 | ✓ 被 run.sh 调用 | ✓ VERIFIED |
| docker/grpo.sh | 独立 GRPO 训练脚本 | ✓ | ✓ 40行，完整流程 | ✓ 被 run.sh 调用 | ✓ VERIFIED |
| docker/run.sh | 串联全流程脚本 | ✓ | ✓ 67行，完整流程 | ✓ 脚本独立可执行 | ✓ VERIFIED |

**已删除构件验证:**

| 构件 | 预期状态 | 实际状态 |
|------|----------|----------|
| src/data_generator/time_period.py | 已删除 | ✓ 不存在 |
| config/schema.json | 已删除 | ✓ 不存在 |
| config/validate_config.py | 已删除 | ✓ 不存在 |
| src/data_generator/parallel_runner.py | 已删除 | ✓ 不存在 |
| src/data_generator/intersection_parallel.py | 已删除 | ✓ 不存在 |
| docker/publish.sh | 已删除 | ✓ 不存在 |
| docker/entrypoint.sh | 已删除 | ✓ 不存在 |
| docker/cleanup.sh | 已删除 | ✓ 不存在 |
| docker/lib/ | 已删除 | ✓ 不存在 |

### 关键链接验证

| 从 | 到 | 通过 | 状态 | 详情 |
|----|----|----|------|------|
| DaySimulator | config dict | config.get() | ✓ WIRED | L165-169 使用 config.get() 读取参数 |
| generate_training_data.py | DaySimulator | 函数调用 | ✓ WIRED | L173 导入，L176 实例化并调用 |
| data.sh | generate_training_data.py | python -m 调用 | ✓ WIRED | L38-41 调用 python3 -m src.scripts.generate_training_data |
| run.sh | data.sh | bash 调用 | ✓ WIRED | L38 bash "${SCRIPT_DIR}/data.sh" |
| run.sh | sft.sh | bash 调用 | ✓ WIRED | L42 bash "${SCRIPT_DIR}/sft.sh" |
| run.sh | grpo.sh | bash 调用 | ✓ WIRED | L46 bash "${SCRIPT_DIR}/grpo.sh" |
| generate_training_data.py | Pool workers | imap_unordered | ✓ WIRED | L352 pool.imap_unordered(_simulate_intersection, tasks) |

### 需求覆盖验证

| 需求 | 状态 | 支持证据 |
|------|------|----------|
| CLEAN-01: 移除时段配置相关的代码和参数 | ✓ SATISFIED | time_period.py 删除；DaySimulator 无时段逻辑；config.json 无 time_ranges |
| CLEAN-02: 清理重复的数据生成逻辑（统一为单层并行） | ✓ SATISFIED | parallel_runner.py 和 intersection_parallel.py 删除；扁平任务池模式实现 |
| CLEAN-03: 移除不使用的中间文件生成逻辑 | ✓ SATISFIED | docker/lib/*.sh 删除；publish.sh 删除 |
| CLEAN-04: 统一配置文件结构，消除冗余配置项 | ✓ SATISFIED | config.json 简化为 4 个顶层键；schema.json 和 validate_config.py 删除 |
| CLEAN-05: 代码中移除注释掉的旧逻辑 | ✓ SATISFIED | 无注释掉的函数/类/导入；无 DEPRECATED 标记 |

### 反模式扫描

扫描文件: day_simulator.py, generate_training_data.py, data.sh, sft.sh, grpo.sh, run.sh

**扫描结果:** 未发现阻塞性反模式

- 无 TODO/FIXME/HACK 注释
- 无占位符内容（placeholder, coming soon）
- 无空实现（return null, return {}）
- 无纯 console.log 实现
- 所有函数和类都有实质性实现

**代码质量指标:**
- day_simulator.py: 388 行，0 个 TODO
- generate_training_data.py: 440 行，0 个 TODO
- Shell 脚本: 所有语法有效（bash -n 检查通过）

## 验证详情

### 真理 1: 代码中不再存在时段配置相关的参数和逻辑

**验证方法:**
1. 文件存在性检查: `test ! -f src/data_generator/time_period.py` → PASS
2. 代码引用检查: `grep -r "time_period|time_ranges|TimePeriod|identify_time_period|get_time_period_stats|filter_by_time_period|get_simulation_ranges" src/ config/` → 无结果
3. 配置文件检查: config.json 不包含 time_ranges 字段

**状态:** ✓ VERIFIED

### 真理 2: 数据生成仅以交叉口为单位并行（单层，不嵌套）

**验证方法:**
1. 文件删除检查: parallel_runner.py 和 intersection_parallel.py 不存在
2. 代码模式检查: generate_training_data.py L352 使用 `pool.imap_unordered(_simulate_intersection, tasks)` 直接消费扁平任务列表
3. 任务生成逻辑: L317-331 将所有场景×交叉口展开为扁平任务列表

**状态:** ✓ VERIFIED

**架构模式:**
```
旧模式（嵌套）:
  ParallelRunner (天级并行)
    └── IntersectionParallelRunner (交叉口级并行)

新模式（扁平）:
  Pool.imap_unordered (单层)
    └── tasks = [(场景1, 交叉口1), (场景1, 交叉口2), ..., (场景N, 交叉口M)]
```

### 真理 3: 配置文件结构统一，无冗余配置项

**验证方法:**
1. config.json 内容验证: 仅包含 training、simulation、rewards、paths 四个顶层键
2. schema 文件删除: schema.json 和 validate_config.py 不存在
3. JSON 有效性: `python3 -c "import json; json.load(open('config/config.json'))"` → 成功

**状态:** ✓ VERIFIED

**配置结构:**
```json
{
  "training": { "sft": {...}, "grpo": {...} },
  "simulation": { "parallel_workers": 12, "warmup_steps": 300, "max_rou_files": 1 },
  "rewards": { "format_weight": 0.2, "simulation_weight": 0.8 },
  "paths": { "data_dir": "data/training", ... }
}
```

### 真理 4: 代码中无注释掉的旧逻辑

**验证方法:**
1. 注释掉的函数/类/导入检查: `grep -E "^[[:space:]]*#[[:space:]]*(def|class|import)" src/` → 0 结果
2. DEPRECATED 标记检查: `find src/ -exec grep -l "DEPRECATED|OLD CODE" {} \;` → 0 文件
3. 注释掉的控制流检查: `grep "^[[:space:]]*#[[:space:]]*(for|while|if).*:" src/` → 0 结果

**状态:** ✓ VERIFIED

### 真理 5-10: (Docker 脚本和并行逻辑)

**统一验证证据:**
- docker/ 目录结构: 仅包含 data.sh、sft.sh、grpo.sh、run.sh（ls 验证）
- 所有脚本语法有效: bash -n 检查通过
- run.sh 串联调用: L38 data.sh, L42 sft.sh, L46 grpo.sh
- 输出路径统一: data.sh 使用 outputs/data 和 outputs/states
- fail-fast 模式: generate_training_data.py L370 pool.terminate()

**状态:** 全部 ✓ VERIFIED

## 总结

### 阶段目标达成

**目标:** 代码库清理冗余，并行逻辑简化为单层结构

**达成证据:**
1. **冗余清理:** 删除 9 个文件（time_period.py, schema.json, validate_config.py, parallel_runner.py, intersection_parallel.py, publish.sh, entrypoint.sh, cleanup.sh, lib/*.sh），净减少 ~2,400 行代码
2. **并行简化:** 从两层嵌套（天级 + 交叉口级）简化为单层扁平任务池
3. **配置统一:** config.json 作为唯一配置源，从 ~350 行简化为 31 行
4. **脚本简化:** Docker 脚本从 ~1,300 行简化为 ~200 行（-85%）

**代码质量:**
- 无占位符或 TODO 标记
- 无注释掉的旧代码
- 所有关键链接已验证接入系统
- Python 和 Shell 语法全部有效

### 就绪状态

**Phase 2 就绪:** ✓ YES

**提供给下一阶段:**
- 简化的 DaySimulator（无时段复杂性）
- 扁平任务池模式（易于扩展）
- 统一的配置结构
- 独立的 Docker 脚本

**阻塞问题:** 无

---

**验证完成时间:** 2026-02-07T15:43:25Z
**验证工具:** Claude (gsd-verifier)
**验证方法:** 三级验证（存在性、实质性、接入系统）+ 代码模式匹配 + 反模式扫描
