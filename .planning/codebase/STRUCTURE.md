# Codebase Structure

**Analysis Date:** 2026-02-09

## Directory Layout

```
TSC_CYCLE/
├── config/             # 配置文件目录
├── data/               # 训练数据持久化存储
├── docker/             # Docker 构建与运行脚本
├── outputs/            # 仿真输出、模型 checkpoints 与临时数据
├── src/                # 源代码根目录
│   ├── data_generator/ # SUMO 仿真与样本采集逻辑
│   ├── phase_processor/# SUMO 网络文件解析与相位处理
│   ├── scripts/        # CLI 入口脚本
│   ├── sft/            # SFT 训练相关代码
│   └── utils/          # 通用工具类 (日志等)
├── sumo_simulation/    # SUMO 环境与基础模拟器类
└── unsloth_compiled_cache/ # Unsloth 训练优化缓存
```

## Directory Purposes

**src/scripts/:**
- Purpose: 存放项目的 CLI 入口，负责各模块的协调。
- Contains: 数据生成、模型训练、相位处理的启动脚本。
- Key files: `generate_training_data.py`, `train_sft.py`

**src/data_generator/:**
- Purpose: 核心仿真逻辑，负责从 SUMO 中提取交通数据。
- Contains: 仿真 worker、周期检测、预测采样、提示词构建。
- Key files: `day_simulator.py`, `predictive_sampler.py`, `prompt_builder.py`

**src/phase_processor/:**
- Purpose: 解析 SUMO 的 `.net.xml` 文件，提取信号灯和相位信息。
- Contains: 解析器、相位验证器、冲突处理器。
- Key files: `processor.py`, `parser.py`, `validator.py`

**src/sft/:**
- Purpose: 大模型微调（SFT）逻辑。
- Contains: 模型加载（Unsloth LoRA）、训练器封装、数据转换。
- Key files: `trainer.py`, `model_loader.py`

**sumo_simulation/:**
- Purpose: SUMO 相关资源和基础封装。
- Contains: 各种路口场景环境 (`environments/`) 和基础模拟器类。
- Key files: `sumo_simulator.py`

## Key File Locations

**Entry Points:**
- `src/scripts/generate_training_data.py`: 数据生成总入口。
- `src/scripts/train_sft.py`: SFT 训练总入口。
- `docker/run.sh`: Docker 容器内的任务协调脚本。

**Configuration:**
- `config/config.json`: 项目全局参数配置（包含路径、仿真参数、训练参数）。

**Core Logic:**
- `src/data_generator/day_simulator.py`: 驱动单次仿真的核心逻辑。
- `src/sft/trainer.py`: 封装的微调训练器。

**Testing:**
- 目前测试主要通过 `src/scripts/` 下的脚本带参数运行（如 `--dry-run`）或在 `trainer.py` 中的验证函数。

## Naming Conventions

**Files:**
- [snake_case]: `day_simulator.py`, `train_sft.py`

**Directories:**
- [snake_case]: `data_generator`, `phase_processor`

**Classes:**
- [PascalCase]: `DaySimulator`, `SUMOSimulator`, `PredictiveSampler`

## Where to Add New Code

**New Feature (Simulation Related):**
- Primary code: `src/data_generator/`
- If it's a new sampling strategy: `src/data_generator/sampler.py` or new file in that dir.

**New Feature (Training Related):**
- Implementation: `src/sft/`

**New CLI Task:**
- Implementation: `src/scripts/`

**New SUMO Environment:**
- Implementation: `sumo_simulation/environments/[scenario_name]/`

## Special Directories

**outputs/:**
- Purpose: 存放仿真产生的临时 JSONL 样本、状态快照和模型 checkpoint。
- Generated: Yes
- Committed: No (通常在 .gitignore 中)

**unsloth_compiled_cache/:**
- Purpose: 存放 Unsloth 编译后的优化 kernel。
- Generated: Yes
- Committed: No

---

*Structure analysis: 2026-02-09*
