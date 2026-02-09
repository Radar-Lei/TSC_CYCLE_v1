# Architecture

**Analysis Date:** 2026-02-09

## Pattern Overview

**Overall:** 模块化流水线架构 (Modular Pipeline Architecture)

**Key Characteristics:**
- **Pipeline-driven:** 整个项目围绕交通信号优化（TSC）的训练数据生成和模型训练流水线展开。
- **Decoupled Components:** 仿真、数据处理和模型训练模块高度解耦，通过标准化的 JSON/JSONL 格式进行数据交换。
- **Fail-fast Task Pool:** 并行任务处理采用 "Fail-fast" 模式，确保任一子任务失败时能够立即终止并报错。

## Layers

**Scripts/Entry Layer:**
- Purpose: 提供 CLI 接口，协调各模块执行完整任务。
- Location: `src/scripts/`
- Contains: `generate_training_data.py`, `train_sft.py`, `process_phases.py`
- Depends on: `src/data_generator/`, `src/sft/`, `src/phase_processor/`
- Used by: Developer via CLI or Docker (`docker/run.sh`)

**Logic/Generator Layer:**
- Purpose: 执行核心业务逻辑，如 SUMO 仿真控制、数据采样、格式转换。
- Location: `src/data_generator/`, `src/phase_processor/`
- Contains: `day_simulator.py`, `traffic_collector.py`, `processor.py`
- Depends on: `sumo_simulation/`
- Used by: `src/scripts/`

**Simulation Layer:**
- Purpose: 封装 SUMO 仿真器，提供底层的交通控制和状态获取接口。
- Location: `sumo_simulation/`
- Contains: `sumo_simulator.py`
- Depends on: SUMO (external)
- Used by: `src/data_generator/`

**Training/SFT Layer:**
- Purpose: 处理大模型（LLM）的 SFT 训练流程。
- Location: `src/sft/`
- Contains: `trainer.py`, `model_loader.py`
- Depends on: `unsloth` (external), `outputs/sft/`
- Used by: `src/scripts/train_sft.py`

## Data Flow

**Training Data Generation Flow:**

1. `src.scripts.generate_training_data` 扫描 `sumo_simulation/environments/` 发现场景。
2. 调用 `src.phase_processor` 解析 `.net.xml` 生成 `phase_config.json`。
3. 创建任务池，每个任务由 `DaySimulator` 调用 `sumo_simulation.sumo_simulator` 运行 SUMO。
4. 在仿真周期边界调用 `PredictiveSampler` 收集状态并计算预测饱和度。
5. 保存原始样本到 `outputs/data/`。
6. 合并并转换为 SFT 格式（CoT 风格），输出到 `outputs/sft/train.jsonl`。

**SFT Training Flow:**

1. `src.scripts.train_sft` 加载 `config/config.json` 中的训练参数。
2. 通过 `src.sft.model_loader` 加载 Qwen3-4B 模型并注入 LoRA。
3. `src.sft.trainer` 加载 SFT 格式的 JSONL 数据。
4. 执行训练并保存 adapter 到 `outputs/sft/model/`。

## Key Abstractions

**DaySimulator:**
- Purpose: 封装单天仿真的完整生命周期，包括环境准备、采样逻辑和资源清理。
- Examples: `src/data_generator/day_simulator.py`
- Pattern: Worker pattern

**PhaseInfo/ProcessingResult:**
- Purpose: 抽象交通信号灯相位数据及其处理统计。
- Examples: `src/phase_processor/models.py`
- Pattern: Data Transfer Object (DTO)

**SUMOSimulator:**
- Purpose: 对 TraCI 接口的封装，提供一致的仿真控制接口。
- Examples: `sumo_simulation/sumo_simulator.py`
- Pattern: Adapter pattern

## Entry Points

**Data Generator CLI:**
- Location: `src/scripts/generate_training_data.py`
- Triggers: User command `python -m src.scripts.generate_training_data`
- Responsibilities: 全量生成训练数据，包括仿真并行管理和格式转换。

**SFT Trainer CLI:**
- Location: `src/scripts/train_sft.py`
- Triggers: User command `python -m src.scripts.train_sft`
- Responsibilities: 执行 SFT 训练流程。

**Docker Runner:**
- Location: `docker/run.sh`
- Triggers: `docker run`
- Responsibilities: 在容器环境下协调整个流水线。

## Error Handling

**Strategy:** Fail-fast (对于仿真任务池) & Centralized Logging

**Patterns:**
- **Task Fail-fast:** 在 `concurrent.futures` 线程池/进程池中，任一任务异常都会导致 `executor.shutdown(wait=False)` 并退出。
- **Validation Blocks:** 每一阶段都有验证（如场景文件检查），不满足条件立即报错。

## Cross-Cutting Concerns

**Logging:** 使用标准 `logging` 库，支持控制台和文件同步输出，配置位于 `src/utils/logging_config.py`。
**Validation:** 相位有效性验证位于 `src/phase_processor/validator.py`。
**Configuration:** 全局配置驱动，核心配置在 `config/config.json`。

---

*Architecture analysis: 2026-02-09*
