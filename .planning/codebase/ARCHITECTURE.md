# Architecture

**Analysis Date:** 2026-02-09

## Pattern Overview

**Overall:** Modular Simulation and Data Generation Framework

**Key Characteristics:**
- **Decoupled Simulation and Processing:** The SUMO simulation environment is decoupled from the data collection and processing logic.
- **Task-Based Parallelism:** Data generation is parallelized across multiple intersection tasks using a worker pool pattern.
- **Fail-Fast Execution:** Scripts are designed to exit immediately upon encountering critical errors to prevent corrupted data generation.

## Layers

**Simulation Layer:**
- Purpose: Manages the low-level traffic simulation using SUMO and TraCI.
- Location: `sumo_simulation/`
- Contains: SUMO configuration files, network definitions, and the core simulator wrapper.
- Depends on: SUMO (external runtime), TraCI (Python client).
- Used by: Data Generation Layer.

**Data Generation Layer:**
- Purpose: Collects traffic metrics from the simulation and formats them for training.
- Location: `src/data_generator/`
- Contains: `traffic_collector.py`, `day_simulator.py`, `sampler.py`.
- Depends on: Simulation Layer, Phase Processing Layer.
- Used by: Scripts Layer.

**Phase Processing Layer:**
- Purpose: Parses, validates, and optimizes traffic light phases from SUMO network files.
- Location: `src/phase_processor/`
- Contains: `processor.py`, `parser.py`, `validator.py`, `conflict.py`.
- Depends on: Native Python libraries, standard models.
- Used by: Data Generation Layer, Scripts Layer.

**Scripts Layer:**
- Purpose: Provides CLI entry points for end-to-end tasks like training data generation.
- Location: `src/scripts/`
- Contains: `generate_training_data.py`, `process_phases.py`.
- Depends on: All other layers.
- Used by: Users/Operators via terminal.

## Data Flow

**Training Data Generation Flow:**

1. **Phase Discovery:** `src/scripts/generate_training_data.py` discovers environments and runs `src/phase_processor/processor.py` to extract phase configurations for each scenario.
2. **Task Distribution:** A `ProcessPoolExecutor` creates tasks for each intersection in each scenario.
3. **Simulation Loop:** `src/data_generator/day_simulator.py` initializes a `sumo_simulation/sumo_simulator.py` instance.
4. **Metric Collection:** `src/data_generator/traffic_collector.py` queries TraCI for vehicle counts and queues at defined intervals.
5. **Sample Serialization:** Samples are collected into JSONL format and merged into a final `train.jsonl`.

**State Management:**
- Simulation state can be saved and restored using SUMO's `saveState` and `loadState` for counterfactual reasoning (GRPO mode) in `sumo_simulation/sumo_simulator.py`.

## Key Abstractions

**SUMOSimulator:**
- Purpose: Wraps TraCI to provide high-level methods for controlling the simulation and extracting metrics.
- Examples: `sumo_simulation/sumo_simulator.py`
- Pattern: Wrapper / Facade

**TrafficCollector:**
- Purpose: Higher-level collector that maps simulation data to specific traffic light phases.
- Examples: `src/data_generator/traffic_collector.py`
- Pattern: Collector

**PhaseProcessor:**
- Purpose: Orchestrates the transformation of raw XML phase data into validated, conflict-free configurations.
- Examples: `src/phase_processor/processor.py`
- Pattern: Pipeline

## Entry Points

**generate_training_data.py:**
- Location: `src/scripts/generate_training_data.py`
- Triggers: Manual CLI execution.
- Responsibilities: Main orchestrator for parallel training data generation across multiple scenarios.

**sumo_simulator.py (main):**
- Location: `sumo_simulation/sumo_simulator.py`
- Triggers: Manual CLI execution or imported as a library.
- Responsibilities: Standalone testing or GRPO training data generation for a single scenario.

## Error Handling

**Strategy:** Fail-fast with explicit logging.

**Patterns:**
- **CRITICAL Exit:** Use `sys.exit(1)` when required files (like `.sumocfg`) are missing.
- **Graceful TraCI Shutdown:** `try...except` blocks around TraCI calls to ensure connections are closed and PID files cleaned up in `sumo_simulation/sumo_simulator.py`.

## Cross-Cutting Concerns

**Logging:** Configured in `src/utils/logging_config.py` (referenced by imports).
**Validation:** Phase validation logic centralized in `src/phase_processor/validator.py`.
**Path Management:** Dynamic discovery of `SUMO_HOME` and absolute path resolution across modules.

---

*Architecture analysis: 2026-02-09*
