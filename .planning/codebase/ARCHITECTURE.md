# Architecture

**Analysis Date:** 2026-02-09

## Pattern Overview

**Overall:** Modular Simulation and Data Generation Framework

**Key Characteristics:**
- **Decoupled Simulation and Logic:** The SUMO simulator is encapsulated in a dedicated class, separating traffic simulation mechanics from higher-level data processing.
- **Data-Driven Pipelines:** Heavy reliance on JSON configurations for traffic light phases, road networks, and model training parameters.
- **ML-Oriented Generation:** The architecture is specifically designed to bridge the gap between traffic simulation (SUMO) and Large Language Model (LLM) training (GRPO, Prompt Building).

## Layers

**Simulation Layer:**
- Purpose: Interfaces with SUMO (Simulation of Urban MObility) to run traffic scenarios.
- Location: `sumo_simulation/`
- Contains: `sumo_simulator.py` (TraCI wrapper), environment definitions, and SUMO configuration files.
- Depends on: SUMO binaries and TraCI library.
- Used by: Data Generation Layer.

**Data Generation Layer:**
- Purpose: Orchestrates simulation runs to collect traffic metrics and build training samples.
- Location: `src/data_generator/`
- Contains: `day_simulator.py` (Worker), `traffic_collector.py` (Metrics), `prompt_builder.py` (LLM prompt construction).
- Depends on: Simulation Layer, Phase Processor.
- Used by: CLI scripts in `src/scripts/`.

**Phase Processing Layer:**
- Purpose: Analyzes SUMO network files to extract and validate traffic light phase configurations.
- Location: `src/phase_processor/`
- Contains: `processor.py`, `parser.py`, `validator.py`, `conflict.py`.
- Depends on: Python standard libraries (XML parsing).
- Used by: Data Generation Layer and standalone CLI scripts.

**Model/Training Layer:**
- Purpose: Logic for fine-tuning LLMs using the generated data.
- Location: `model/`, root
- Contains: `qwen3_(4b)_grpo.py`, model definitions.
- Depends on: PyTorch, Unsloth, and generated output data.

## Data Flow

**Training Data Generation Flow:**

1. **Phase Extraction:** `src/scripts/process_phases.py` reads a `.net.xml` file and generates a `phase_config.json`.
2. **Simulation Initialization:** `src/data_generator/day_simulator.py` creates a temporary SUMO environment using the network and demand files.
3. **Runtime Collection:** `src/data_generator/traffic_collector.py` queries the simulator via TraCI at cycle boundaries to get queue lengths and saturation.
4. **Prompt Construction:** `src/data_generator/prompt_builder.py` formats the collected metrics into natural language prompts and JSON structures for LLM training.
5. **Output:** Samples are saved as JSON/JSONL for the training layer.

**State Management:**
- Handled via `src/data_generator/state_manager.py` and temporary XML/JSON files during simulation runs.

## Key Abstractions

**SUMOSimulator:**
- Purpose: High-level wrapper for TraCI to manage simulation lifecycle.
- Examples: `sumo_simulation/sumo_simulator.py`
- Pattern: Adapter/Facade.

**TrafficCollector:**
- Purpose: Abstracts the complexity of mapping SUMO lane indices to logical traffic light phases.
- Examples: `src/data_generator/traffic_collector.py`

**PromptBuilder:**
- Purpose: Decouples raw traffic data from the specific format required by the LLM.
- Examples: `src/data_generator/prompt_builder.py`

## Entry Points

**Phase Processor CLI:**
- Location: `src/scripts/process_phases.py`
- Triggers: Manual execution to prepare road network data.
- Responsibilities: Parses network XML, resolves conflicts, and outputs phase config.

**Training Data Generator:**
- Location: `src/scripts/generate_training_data.py`
- Triggers: Main data generation pipeline.
- Responsibilities: Runs multiple simulations to build the training dataset.

**Model Trainer:**
- Location: `qwen3_(4b)_grpo.py`
- Triggers: LLM training phase.
- Responsibilities: Fine-tunes the model using GRPO and Unsloth.

## Error Handling

**Strategy:** Exception-based with centralized logging.

**Patterns:**
- **Validation Gates:** `src/phase_processor/validator.py` ensures configurations are sane before simulation.
- **Environment Checks:** Extensive checking for `SUMO_HOME` and `traci` availability in entry points.

## Cross-Cutting Concerns

**Logging:** Centralized configuration in `src/utils/logging_config.py`.
**Configuration:** JSON-based configs in `config/config.json`.
**Dockerization:** Deployment and execution environment defined in `docker/`.

---

*Architecture analysis: 2026-02-09*
