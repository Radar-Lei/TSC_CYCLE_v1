# Architecture

**Analysis Date:** 2026-02-09

## Pattern Overview

**Overall:** Simulation-to-Training Pipeline for Traffic Signal Control (TSC).

**Key Characteristics:**
- **Decoupled Simulation and Training:** SUMO simulations are used to generate high-fidelity traffic data, which is then processed into a format suitable for Large Language Model (LLM) fine-tuning.
- **Task-Based Parallelism:** Simulations are distributed across multiple workers using a flat task pool to handle large numbers of intersection scenarios efficiently.
- **CoT (Chain of Thought) Integration:** The system explicitly structures model outputs with `<think>` tags to facilitate reasoning-based traffic light timing optimization.

## Layers

**Simulation Layer:**
- Purpose: Provides the physical environment for traffic data collection.
- Location: `sumo_simulation/`
- Contains: SUMO network (`.net.xml`), route (`.rou.xml`), and configuration (`.sumocfg`) files.
- Depends on: SUMO binaries and `sumo_simulation/sumo_simulator.py`.
- Used by: `src/data_generator/day_simulator.py`.

**Data Generation Layer:**
- Purpose: orchestrates simulations to collect traffic samples and build training prompts.
- Location: `src/data_generator/`
- Contains: `day_simulator.py`, `traffic_collector.py`, `prompt_builder.py`, `state_manager.py`.
- Depends on: Simulation Layer, Phase Processing Layer.
- Used by: `src/scripts/generate_training_data.py`.

**Phase Processing Layer:**
- Purpose: Encapsulates traffic light logic, phase definitions, and timing constraints.
- Location: `src/phase_processor/`
- Contains: `processor.py`, `conflict.py`, `parser.py`, `models.py`.
- Depends on: None (Core domain logic).
- Used by: Data Generation Layer, SFT Layer.

**SFT (Supervised Fine-Tuning) Layer:**
- Purpose: Handles model training and data formatting for LLM optimization.
- Location: `src/sft/`
- Contains: `trainer.py`, `model_loader.py`, `chat_template.py`, `format_validator.py`.
- Depends on: Phase Processing Layer.
- Used by: `src/scripts/train_sft.py`.

## Data Flow

**Training Data Generation Flow:**

1. **Phase Discovery:** `src/scripts/process_phases.py` parses SUMO network files to generate `phase_config.json`.
2. **Simulation Tasking:** `src/scripts/generate_training_data.py` discovers environments and creates a task list (scenario x intersection).
3. **Execution:** Workers run `src/data_generator/day_simulator.py` which interfaces with SUMO via TraCI.
4. **Collection:** `src/data_generator/traffic_collector.py` captures queue lengths and waiting times.
5. **Prompting:** `src/data_generator/prompt_builder.py` converts raw data into structured text prompts.
6. **Formatting:** Raw results are converted into SFT/CoT JSONL format in `outputs/sft/`.

**State Management:**
- `src/data_generator/state_manager.py` handles saving and loading simulation snapshots to allow for reproducibility and segmented data generation.

## Key Abstractions

**DaySimulator:**
- Purpose: High-level manager for a single intersection's full-day simulation.
- Examples: `src/data_generator/day_simulator.py`
- Pattern: Facade for SUMO interaction and data collection.

**PromptBuilder:**
- Purpose: Transforms traffic state into natural language / JSON prompts for LLMs.
- Examples: `src/data_generator/prompt_builder.py`
- Pattern: Strategy pattern for different prompt templates.

**PhaseProcessor:**
- Purpose: Core logic for interpreting traffic light states and ensuring safety/validity.
- Examples: `src/phase_processor/processor.py`
- Pattern: Domain Model.

## Entry Points

**Data Generation CLI:**
- Location: `src/scripts/generate_training_data.py`
- Triggers: Manual execution via `python -m src.scripts.generate_training_data`.
- Responsibilities: Discovery of scenarios, parallel worker management, and final data merging.

**SFT Training CLI:**
- Location: `src/scripts/train_sft.py`
- Triggers: Manual execution.
- Responsibilities: Loading data, configuring the trainer, and saving the model.

## Error Handling

**Strategy:** Fail-fast for simulation tasks to ensure data integrity.

**Patterns:**
- **Worker Level:** `_simulate_intersection` in `generate_training_data.py` catches exceptions and returns error status to the main process.
- **Fail-Fast:** Main process terminates all workers if any task fails to prevent partial/corrupt dataset generation.

## Cross-Cutting Concerns

**Logging:** Centralized configuration in `src/utils/logging_config.py`.
**Validation:** Schema and format validation for both phase configurations and SFT data (`src/phase_processor/validator.py`, `src/sft/format_validator.py`).
**Configuration:** Centralized JSON config in `config/config.json`.

---

*Architecture analysis: 2026-02-09*
