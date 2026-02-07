---
phase: quick-001
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - src/scripts/generate_training_data.py
  - docker/publish.sh
  - config/config.json
autonomous: true

must_haves:
  truths:
    - "数据生成遍历 sumo_simulation/environments/ 下所有场景子目录"
    - "每个场景使用自己的 .rou.xml / .net.xml / .sumocfg 文件"
    - "不再依赖 rou_month_generator.py 生成数据"
    - "每个场景生成独立的 phase_config.json 和训练数据"
  artifacts:
    - path: "src/scripts/generate_training_data.py"
      provides: "多场景数据生成入口"
    - path: "docker/publish.sh"
      provides: "多场景预处理和数据生成流程"
    - path: "config/config.json"
      provides: "environments 目录配置"
  key_links:
    - from: "docker/publish.sh"
      to: "src/scripts/generate_training_data.py"
      via: "CLI 调用"
    - from: "src/scripts/generate_training_data.py"
      to: "sumo_simulation/environments/*/\*.sumocfg"
      via: "遍历场景目录"
---

<objective>
将数据生成源从 rou_month_generator.py 切换为 sumo_simulation/environments/ 下的 51 个场景子目录。

Purpose: 每个场景都有现成的 .rou.xml / .net.xml / .sumocfg 文件和默认信号配时方案，不再需要用 rou_month_generator.py 生成月度数据。
Output: 修改后的 generate_training_data.py 和 publish.sh，支持遍历所有场景目录生成训练数据。
</objective>

<execution_context>
@/home/samuel/.claude/get-shit-done/workflows/execute-plan.md
@/home/samuel/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@config/config.json
@src/scripts/generate_training_data.py
@docker/publish.sh
@src/data_generator/day_simulator.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: 重构 generate_training_data.py 支持多场景遍历</name>
  <files>
    src/scripts/generate_training_data.py
    config/config.json
  </files>
  <action>
**修改 config/config.json:**
- 将 `paths.net_file` 和 `paths.sumocfg` 替换为 `paths.environments_dir: "sumo_simulation/environments"`
- 删除旧的 `net_file` 和 `sumocfg` 单场景路径

**重构 generate_training_data.py 的核心逻辑:**

1. 新增 `--environments-dir` 参数（默认值 `sumo_simulation/environments`），替代旧的 `--rou-dir` 参数。保留 `--rou-dir` 作为向后兼容但标记 deprecated。

2. 新增 `discover_environments(environments_dir)` 函数:
   - 遍历 `environments_dir` 下所有子目录
   - 每个子目录需要找到 `*.sumocfg`、`*.net.xml`、`*.rou.xml` 各一个文件
   - 返回场景列表: `[{"name": "arterial4x4_1", "sumocfg": "...", "net_file": "...", "rou_file": "...", "dir": "..."}, ...]`
   - 如果某个子目录缺少必要文件，打印警告并跳过

3. 修改 `main()` 函数:
   - 新增 `--environments-dir` 参数时的分支逻辑
   - 遍历每个场景:
     a. 为每个场景生成独立的 phase_config: `output/phase_config_{scenario_name}.json`
        - 调用 `process_traffic_lights(net_file)` 和 `save_result_to_json()`
        - 如果 phase_config 已存在则跳过（增量模式）
     b. 构建 config 字典，设置该场景的 `sumocfg` 和 `phase_config_path`
     c. 该场景的 rou_files 就是其目录下的 `*.rou.xml` 文件列表（不需要 daily 拆分，直接用原始的 .rou.xml）
     d. 输出目录为 `outputs/data/{scenario_name}/`
     e. 调用 IntersectionParallelRunner 或 run_parallel_simulation 执行仿真

4. 因为每个场景只有 1 个 .rou.xml（不是按天拆分的），需要修改 DaySimulator 的日期逻辑:
   - 当 rou_file 文件名中不含日期时（如 `arterial4x4_1.rou.xml`），使用场景名作为标识而不是日期
   - 在 config 中新增 `base_date` 字段，传入场景名或固定日期 `"2026-01-01"`
   - 在 generate_training_data.py 中，给 config 设置 `base_date: scenario_name`

5. 修改 `stage_data_generation` 在 publish.sh 中的调用:
   - 改为 `python3 -m src.scripts.generate_training_data --environments-dir sumo_simulation/environments --workers "$PARALLEL_WORKERS" --warmup-steps "$WARMUP_STEPS" --output-dir "outputs/data"`
   - 去掉 `--intersection-parallel` 参数（对单文件场景不需要交叉口级别并行，每个场景本身就是独立并行单元）

**关键设计决策:**
- 51 个场景间的并行: 使用 multiprocessing.Pool 并行处理不同场景（每个场景是一个独立的 SUMO 实例）
- 每个场景只有 1 个 rou 文件，所以不需要 daily 拆分逻辑
- 每个场景有独立的 phase_config，因为不同路网的信号灯配置不同
- 输出结构: `outputs/data/{scenario_name}/samples.jsonl`
  </action>
  <verify>
    python3 -m src.scripts.generate_training_data --environments-dir sumo_simulation/environments --dry-run
    应该列出 51 个场景及其文件路径，不报错。
  </verify>
  <done>
    - `--dry-run` 模式正确发现并列出 51 个场景
    - 每个场景的 sumocfg/net_file/rou_file 路径正确
    - config.json 更新为 environments_dir 配置
  </done>
</task>

<task type="auto">
  <name>Task 2: 更新 publish.sh 预处理和数据生成流程</name>
  <files>
    docker/publish.sh
  </files>
  <action>
**修改 `stage_preprocessing()` 函数:**
- 不再只处理 chengdu 一个场景的 phase_config
- 改为: 将相位配置生成的责任移交给 generate_training_data.py（Task 1 中已实现按场景生成 phase_config）
- 简化 stage_preprocessing(): 只检查 environments 目录是否存在，打印发现了多少个场景
- 或者: 遍历 environments_dir 下每个子目录，对每个场景的 .net.xml 运行 `python3 -m src.scripts.process_phases`，输出到 `output/phase_config_{name}.json`
- 选择后者（在 bash 中遍历），因为预处理和数据生成是独立阶段

具体实现:
```bash
stage_preprocessing() {
    local config_file="${PROJECT_DIR}/config/config.json"
    local env_dir="${PROJECT_DIR}/sumo_simulation/environments"

    echo -e "${BLUE}[预处理]${NC} 检查相位配置文件..."

    if [[ ! -d "$env_dir" ]]; then
        echo -e "${RED}[ERROR] 环境目录不存在: $env_dir${NC}" >&2
        return 1
    fi

    mkdir -p "${PROJECT_DIR}/output"

    local total=0
    local skipped=0
    local generated=0

    for scenario_dir in "$env_dir"/*/; do
        local name=$(basename "$scenario_dir")
        local net_file=$(find "$scenario_dir" -name "*.net.xml" -maxdepth 1 | head -1)
        local phase_config="${PROJECT_DIR}/output/phase_config_${name}.json"

        if [[ -z "$net_file" ]]; then
            echo -e "${YELLOW}  跳过 $name (未找到 .net.xml)${NC}"
            continue
        fi

        ((total++))

        if [[ -f "$phase_config" ]]; then
            ((skipped++))
            continue
        fi

        if python3 -m src.scripts.process_phases -i "$net_file" -o "$phase_config"; then
            ((generated++))
        else
            echo -e "${YELLOW}  警告: $name 相位处理失败${NC}"
        fi
    done

    echo -e "${GREEN}✓ 相位配置: ${total} 个场景, ${generated} 个新生成, ${skipped} 个已存在${NC}"
}
```

**修改 `stage_data_generation()` 函数:**
- 将命令从:
  ```
  python3 -m src.scripts.generate_training_data \
      --workers "$PARALLEL_WORKERS" \
      --warmup-steps "$WARMUP_STEPS" \
      --intersection-parallel \
      --output-dir "outputs/data"
  ```
  改为:
  ```
  python3 -m src.scripts.generate_training_data \
      --environments-dir sumo_simulation/environments \
      --workers "$PARALLEL_WORKERS" \
      --warmup-steps "$WARMUP_STEPS" \
      --output-dir "outputs/data"
  ```
  去掉 `--intersection-parallel` 参数

**修改 `load_json_config()` 函数:**
- 新增读取 `ENVIRONMENTS_DIR` 配置:
  ```
  export ENVIRONMENTS_DIR=$(jq -r '.paths.environments_dir // "sumo_simulation/environments"' "$config_file")
  ```
  </action>
  <verify>
    bash -n docker/publish.sh (语法检查通过)
    grep -q "environments" docker/publish.sh (确认新参数存在)
  </verify>
  <done>
    - publish.sh 语法正确
    - stage_preprocessing 遍历所有场景生成 phase_config
    - stage_data_generation 使用 --environments-dir 参数
    - 不再硬编码 chengdu 路径
  </done>
</task>

</tasks>

<verification>
1. `python3 -m src.scripts.generate_training_data --environments-dir sumo_simulation/environments --dry-run` 列出所有 51 个场景
2. `bash -n docker/publish.sh` 语法检查通过
3. `grep -r "rou_month_generator" docker/ src/scripts/` 无结果（不再引用旧脚本）
4. `jq '.paths.environments_dir' config/config.json` 返回 "sumo_simulation/environments"
</verification>

<success_criteria>
- generate_training_data.py 支持 --environments-dir 参数，遍历所有场景目录
- 每个场景使用自己的 .sumocfg / .net.xml / .rou.xml
- publish.sh 的预处理阶段为每个场景生成独立的 phase_config
- 数据生成流程不再依赖 rou_month_generator.py
- --dry-run 模式能正确发现 51 个场景
</success_criteria>

<output>
After completion, create `.planning/quick/001-sumo-simulation-environments/001-SUMMARY.md`
</output>
