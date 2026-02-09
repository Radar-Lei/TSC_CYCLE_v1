# Architecture

**Analysis Date:** 2026-02-09

## Pattern Overview

**Overall:** Pipeline-based AI Training and Simulation (SFT for Traffic Signal Control)

**Key Characteristics:**
- **Modular Pipeline:** Distinct phases for data generation, preprocessing, and model training.
- **Simulation-Driven Data:** Training data is generated through closed-loop SUMO simulations with counterfactual state reloads.
- **CoT (Chain of Thought) Learning:** Focuses on teaching the model (Qwen3-4B) to reason through saturation levels before outputting signal timings.

## Layers

**Simulation Layer:**
- Purpose: Provides the realistic traffic environment and TraCI interface.
- Location: `sumo_simulation/`
- Contains: SUMO configuration files, net/route files, and `sumo_simulator.py`.
- Depends on: Eclipse SUMO (external).
- Used by: `src/data_generator/`

**Data Generation Layer:**
- Purpose: Executes simulation runs to collect raw traffic data and state snapshots.
- Location: `src/data_generator/`
- Contains: `day_simulator.py`, `predictive_sampler.py`, `cycle_detector.py`.
- Depends on: `sumo_simulation/`, `src/phase_processor/`
- Used by: `src/scripts/generate_training_data.py`

**Processing & Validation Layer:**
- Purpose: Parses SUMO network files, identifies phases, resolves conflicts, and formats data for training.
- Location: `src/phase_processor/`, `src/sft/`
- Contains: `processor.py`, `parser.py`, `chat_template.py`, `format_validator.py`.
- Depends on: `src/data_generator/`
- Used by: `src/scripts/`

**Training Layer:**
- Purpose: Handles model loading, LoRA configuration, and SFT (Supervised Fine-Tuning).
- Location: `src/sft/`
- Contains: `trainer.py`, `model_loader.py`.
- Depends on: `transformers`, `trl`, `peft`, `unsloth`.
- Used by: `src/scripts/train_sft.py`

## Data Flow

**1. Scenario Discovery & Phase Parsing:**
- `generate_training_data.py` discovers environments.
- `process_phases.py` parses `.net.xml` to generate `phase_config_<scenario>.json`.

**2. Simulation & Sampling:**
- `DaySimulator` runs SUMO.
- `CycleDetector` identifies the start of a signal cycle.
- `PredictiveSampler` saves state, pushes simulation forward one cycle to see accumulation, then reloads state.
- Raw samples are saved to `outputs/data/<scenario>/samples_<date>.jsonl`.

**3. Dataset Conversion:**
- Raw samples are merged into `data/training/train.jsonl`.
- `convert_to_sft_format` (in `generate_training_data.py`) converts raw samples to Chat/CoT format in `outputs/sft/train.jsonl`.

**4. Model Training:**
- `train_sft.py` loads `outputs/sft/train.jsonl`.
- `SFTTrainerWrapper` executes training and saves the model to `outputs/sft/model/final`.

**State Management:**
- SUMO state snapshots (`.xml` or `.xml.gz`) are managed by `PredictiveSampler` and stored in `outputs/states/`.

## Key Abstractions

**SUMOSimulator:**
- Purpose: Pythonic wrapper for TraCI and SUMO process management.
- Examples: `sumo_simulation/sumo_simulator.py`
- Pattern: Adapter/Wrapper.

**PredictiveSampler:**
- Purpose: Implements the "simulation-lookahead" logic to calculate future saturation.
- Examples: `src/data_generator/predictive_sampler.py`
- Pattern: Strategy.

**SFTTrainerWrapper:**
- Purpose: Abstracts the complexity of `trl.SFTTrainer` and model loading.
- Examples: `src/sft/trainer.py`
- Pattern: Wrapper.

## Entry Points

**generate_training_data.py:**
- Location: `src/scripts/generate_training_data.py`
- Triggers: CLI execution.
- Responsibilities: End-to-end data generation pipeline (discovery, simulation, merging, CoT conversion).

**train_sft.py:**
- Location: `src/scripts/train_sft.py`
- Triggers: CLI execution.
- Responsibilities: Model training entry point.

**process_phases.py:**
- Location: `src/scripts/process_phases.py`
- Triggers: CLI or imported by generator.
- Responsibilities: Analyzing network files to define signal phases.

## Error Handling

**Strategy:** Fail-fast in data generation, logging with retry/skip in training.

**Patterns:**
- **Task Failure:** `generate_training_data.py` uses a fail-fast mode where any worker failure terminates the entire process.
- **TraCI Robustness:** `SUMOSimulator` handles port conflicts and TraCI connection losses with retries and process cleanup (`_kill_sumo_on_port`).

## Cross-Cutting Concerns

**Logging:** Configured in `src/utils/logging_config.py` and locally in scripts; outputs to both console and files in `outputs/`.
**Validation:** `src/phase_processor/validator.py` ensures signal phases are viable; `src/sft/format_validator.py` checks model output syntax.
**Configuration:** Centralized in `config/config.json`.

---

*Architecture analysis: 2026-02-09*
