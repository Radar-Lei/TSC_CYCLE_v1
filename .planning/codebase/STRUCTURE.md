# Codebase Structure

**Analysis Date:** 2026-02-21

## Directory Layout

```
TSC_CYCLE/
├── benchmark/           # LLM Evaluation framework and metrics
├── config/              # Global project configurations (JSON)
├── docker/              # Deployment and environment containers
├── model/               # Model weights and tokenizer files
├── outputs/             # Generated datasets, metrics, and logs
│   ├── data/            # Final training JSONL files
│   ├── grpo/            # GRPO checkoints and logs
│   ├── sft/             # SFT checkpoints and logs
│   └── states/          # Simulation state snapshots
├── src/                 # Core Python source code
│   ├── data_generator/  # Simulation-based data collection
│   ├── grpo/            # GRPO training and rewards
│   ├── sft/             # SFT training and inference
│   ├── phase_processor/ # SUMO signal logic processing
│   ├── scripts/         # CLI entry points for data/training
│   └── utils/           # Shared helper functions
├── sumo_simulation/     # Traffic network and demand scenarios
│   └── environments/    # Individual case studies (e.g., chengdu)
└── llama.cpp/           # Submodule for efficient GGUF inference
```

## Directory Purposes

**benchmark/:**
- Purpose: Automated testing suite for comparing LLM-guided TSC against baselines.
- Contains: LLM clients, SUMO wrappers, and reporting tools.
- Key files: `benchmark/run_benchmark.py`, `benchmark/metrics.py`.

**src/data_generator/:**
- Purpose: Logic for converting raw SUMO simulation steps into LLM instruction pairs.
- Contains: Prompt templates, traffic collectors, and predictive samplers.
- Key files: `src/data_generator/prompt_builder.py`, `src/data_generator/traffic_collector.py`.

**src/phase_processor/:**
- Purpose: Low-level parsing and validation of SUMO Signal phases.
- Contains: Conflict detection and sequence validation logic.
- Key files: `src/phase_processor/processor.py`, `src/phase_processor/conflict.py`.

**sumo_simulation/environments/:**
- Purpose: Real-world or synthetic traffic networks.
- Contains: `.net.xml` (road network), `.rou.xml` (vehicle flow).
- Key files: `sumo_simulation/environments/chengdu/chengdu.sumocfg`.

## Key File Locations

**Entry Points:**
- `benchmark/run_benchmark.py`: Main evaluation entry point.
- `src/scripts/generate_training_data.py`: Main data generation entry point.
- `src/sft/train.py`: SFT training launch script.
- `src/grpo/train.py`: GRPO training launch script.

**Configuration:**
- `config/config.json`: Core simulation and training parameters.
- `benchmark/config/batch_config.json`: Model list and schema for batch benchmarks.

**Core Logic:**
- `src/data_generator/day_simulator.py`: Orchestrates a full day of simulation for data collection.
- `benchmark/simulation.py`: Wrapper for TraCI connection management.

**Testing:**
- `benchmark/tests/`: Unit tests for metrics and parsers.
- `conftest.py`: Root level pytest configuration.

## Naming Conventions

**Files:**
- Snake case for modules/scripts: `prompt_builder.py`.
- Suffix for scripts: `_generator.py`, `_processor.py`.

**Directories:**
- Snake case: `phase_processor`, `data_generator`.

## Where to Add New Code

**New Scenario:**
- Primary network files: `sumo_simulation/environments/[scenario_name]/`.
- Update scenario discovery by ensuring a `.sumocfg` exists in the folder.

**New Reward for GRPO:**
- Implementation: `src/grpo/rewards.py`.

**New Metrics for Evaluation:**
- Implementation: `benchmark/metrics.py`.

**New Data Generation Strategy:**
- Implementation: `src/data_generator/`.
- Corresponding CLI: `src/scripts/`.

## Special Directories

**unsloth/:**
- Purpose: Contains model checkpoints used with the Unsloth library.
- Committed: No (usually partially tracked or .gitignored).

**llama.cpp/:**
- Purpose: External dependency for high-performance GGUF inference.
- Committed: Yes (as a submodule or source clone).

**.planning/:**
- Purpose: GSD (Get Stuff Done) documentation and codebase mapping.
- Committed: Yes.

---

*Structure analysis: 2026-02-21*
