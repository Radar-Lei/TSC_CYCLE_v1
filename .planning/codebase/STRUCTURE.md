# Codebase Structure

**Analysis Date:** 2026-02-09

## Directory Layout

```
TSC_CYCLE/
├── config/             # Configuration files (JSON)
├── data/               # Persistent data storage
│   └── training/       # Merged raw training samples
├── docker/             # Dockerization and shell scripts
├── model/              # Local model weights and base models
├── outputs/            # Pipeline outputs (data, models, logs)
│   ├── data/           # Per-scenario raw samples
│   ├── sft/            # SFT training data and trained models
│   └── states/         # SUMO simulation state snapshots
├── src/                # Primary source code
│   ├── data_generator/ # Simulation logic and data collection
│   ├── phase_processor/# SUMO network analysis logic
│   ├── scripts/        # CLI entry points and orchestration scripts
│   ├── sft/            # Model training and formatting logic
│   └── utils/          # Shared utilities (logging, etc.)
├── sumo_simulation/    # SUMO environment and simulator core
│   └── environments/   # Individual traffic scenarios (net, rou, sumocfg)
├── rou_month_generator.py # Helper for generating traffic demand
└── sample_prompt_result.md# Documentation/Samples
```

## Directory Purposes

**src/data_generator/:**
- Purpose: Logic for running simulations and sampling traffic states.
- Contains: `day_simulator.py`, `predictive_sampler.py`, `cycle_detector.py`.
- Key files: `predictive_sampler.py` (lookahead logic).

**src/phase_processor/:**
- Purpose: Analyzing SUMO `.net.xml` files to extract signal phase information.
- Contains: `parser.py`, `processor.py`, `conflict.py`.
- Key files: `processor.py` (orchestrates parsing and validation).

**src/scripts/:**
- Purpose: Top-level scripts for running the pipeline.
- Key files: `generate_training_data.py`, `train_sft.py`.

**sumo_simulation/environments/:**
- Purpose: Source of truth for traffic network and demand.
- Contains: Subdirectories for each scenario (e.g., `arterial4x4_1/`).

**outputs/sft/:**
- Purpose: Storage for SFT-specific artifacts.
- Contains: `train.jsonl` (converted CoT data), `model/` (trained weights).

## Key File Locations

**Entry Points:**
- `src/scripts/generate_training_data.py`: Primary data generation entry.
- `src/scripts/train_sft.py`: Model training entry.

**Configuration:**
- `config/config.json`: Main project configuration.
- `outputs/data/phase_config_<scenario>.json`: Intermediate phase configuration generated from networks.

**Core Logic:**
- `src/data_generator/predictive_sampler.py`: Implementation of future-state sampling.
- `src/sft/trainer.py`: Implementation of SFT training loop.

**Testing:**
- (Implicit) `src/sft/format_validator.py`: Used to validate model outputs.

## Naming Conventions

**Files:**
- [snake_case.py]: Most python modules.
- [UPPERCASE.md]: Planning and documentation files.
- [samples_YYYY-MM-DD.jsonl]: Raw simulation data files.

**Directories:**
- [snake_case/]: Source directories.

## Where to Add New Code

**New Feature (Simulation logic):**
- Primary code: `src/data_generator/`
- Integration: `src/scripts/generate_training_data.py`

**New Model Strategy:**
- Implementation: `src/sft/`
- Training script: `src/scripts/train_sft.py` (or a new script in `src/scripts/`)

**New Traffic Scenario:**
- Path: `sumo_simulation/environments/<scenario_name>/`
- Required files: `.sumocfg`, `.net.xml`, `.rou.xml`.

**Utilities:**
- Shared helpers: `src/utils/`

## Special Directories

**outputs/states/:**
- Purpose: Contains large binary state files from SUMO simulations.
- Generated: Yes
- Committed: No (usually gitignored)

**model/models/unsloth/:**
- Purpose: Cache for base model weights from HuggingFace.
- Generated: No (Downloaded)
- Committed: No

---

*Structure analysis: 2026-02-09*
