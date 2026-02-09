# Architecture

**Analysis Date:** 2026-02-09

## Pattern Overview

**Overall:** Event-driven Simulation and Data Generation Pipeline

**Key Characteristics:**
- **Simulation-Centric:** Built around the SUMO (Simulation of Urban MObility) engine using the TraCI interface.
- **Task Parallelism:** Uses multi-processing to run multiple SUMO instances concurrently for large-scale data generation.
- **Predictive Sampling:** Employs counterfactual reasoning (saving/loading simulation state) to evaluate multiple traffic signal control decisions from the same state.
- **Modular Pipeline:** Decoupled stages for network processing, traffic simulation, and training data synthesis.

## Layers

**Simulation Layer:**
- Purpose: Manages the lifecycle of SUMO processes and provides a Pythonic API for traffic control.
- Location: `sumo_simulation/sumo_simulator.py`
- Contains: `SUMOSimulator` class handling TraCI connections, warmup, stepping, and state management.
- Depends on: SUMO binaries and `traci` library.
- Used by: Data Generation Layer, Scripts.

**Processing Layer (Phase Processor):**
- Purpose: Extracts and cleans traffic signal phase information from SUMO network files.
- Location: `src/phase_processor/`
- Contains: Logic for conflict resolution (`conflict.py`), validation (`validator.py`), and time configuration (`time_config.py`).
- Depends on: XML parser and internal models.
- Used by: Data Generation Layer.

**Data Generation Layer:**
- Purpose: Orchestrates simulation runs to collect traffic metrics and generate structured training samples.
- Location: `src/data_generator/`
- Contains: `DaySimulator` for single-run management, `TrafficCollector` for metrics, and `PredictiveSampler` for state-save/load evaluations.
- Depends on: Simulation Layer, Phase Processor.
- Used by: Orchestration Scripts.

**Orchestration Layer:**
- Purpose: Provides CLI tools for batch processing across multiple environments and intersections.
- Location: `src/scripts/`
- Contains: `generate_training_data.py` (multi-process runner) and `process_phases.py`.
- Depends on: Data Generation Layer.

## Data Flow

**Training Data Generation Flow:**

1. **Environment Discovery:** `discover_environments` scans directories for `.sumocfg`, `.net.xml`, and `.rou.xml`.
2. **Phase Analysis:** `process_traffic_lights` parses the network and generates a `phase_config.json`.
3. **Task Mapping:** The orchestrator flattens the task space (Scenario × Intersection) and submits them to a `ProcessPoolExecutor`.
4. **Simulation Step:** `SUMOSimulator.step()` advances time; `CycleDetector` monitors for phase changes.
5. **Predictive Sampling:** At cycle boundaries, the state is saved. Multiple potential phases/durations are simulated in parallel "alternate realities".
6. **Sample Synthesis:** `PromptBuilder` combines historical state and future outcomes into a JSONL sample.
7. **Consolidation:** Individual task outputs are merged into a final `train.jsonl`.

**State Management:**
- Simulation state is handled via SUMO's `saveState` and `loadState` XML files, allowing non-linear exploration of decision outcomes.

## Key Abstractions

**SUMOSimulator:**
- Purpose: Encapsulates TraCI complexity and provides high-level methods like `calculate_phase_pressure` and `step_with_state_reload`.
- Examples: `sumo_simulation/sumo_simulator.py`

**DaySimulator:**
- Purpose: Manages the context of a "simulation day", including temporary configs and resource cleanup.
- Examples: `src/data_generator/day_simulator.py`

**TrainingSample:**
- Purpose: Represents a single unit of LLM training data (instruction, input, output).
- Examples: `src/data_generator/models.py`

## Entry Points

**generate_training_data.py:**
- Location: `src/scripts/generate_training_data.py`
- Triggers: Manual CLI execution (`python -m src.scripts.generate_training_data`).
- Responsibilities: Discovery, parallel worker management, and final result merging.

**sumo_simulator.py (as main):**
- Location: `sumo_simulation/sumo_simulator.py`
- Triggers: CLI execution for testing or single-run GRPO data generation.
- Responsibilities: Standalone simulation runner with optional GUI.

## Error Handling

**Strategy:** Fail-Fast for batch processing; localized recovery for individual TraCI commands.

**Patterns:**
- **Task Termination:** If a parallel worker fails, the orchestrator cancels all pending tasks and exits immediately to prevent corrupted datasets.
- **TraCI Protection:** Wrapped in try-except blocks to handle disconnection or invalid lane IDs gracefully during metrics collection.

## Cross-Cutting Concerns

**Logging:** Configured in `src/utils/logging_config.py`, used primarily in the phase processor and simulator for audit trails.
**Validation:** Strict schema checks for SUMO network integrity in `src/phase_processor/validator.py`.
**Configuration:** Centralized JSON configuration in `config/config.json` managing both simulation parameters and ML hyperparameters.

---

*Architecture analysis: 2026-02-09*
