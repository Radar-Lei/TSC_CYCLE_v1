# Codebase Structure

**Analysis Date:** 2026-02-09

## Directory Layout

```
TSC_CYCLE/
├── config/             # Configuration files (JSON)
├── data/               # Final training datasets
│   └── training/       # Combined train.jsonl
├── docker/             # Containerization scripts and Dockerfile
├── model/              # Model definitions and weights
├── outputs/            # Intermediate simulation outputs
│   ├── data/           # Raw JSONL samples per scenario
│   └── states/         # Simulation state snapshots
├── src/                # Primary source code
│   ├── data_generator/ # Simulation logic and metrics collection
│   ├── phase_processor/# SUMO network/phase parsing and validation
│   ├── scripts/        # CLI tools for orchestration
│   └── utils/          # Shared helpers (logging, etc.)
├── sumo_simulation/    # SUMO-specific logic and environments
│   ├── environments/   # Simulation scenarios (net.xml, rou.xml, sumocfg)
│   └── sumo_simulator.py# Core SUMO/TraCI wrapper
└── [scripts].py        # Root level utility and experiment scripts
```

## Directory Purposes

**src/phase_processor:**
- Purpose: Logic for handling SUMO Traffic Light Program (TLP) configurations.
- Contains: Parsers, conflict resolvers, and duration generators.
- Key files: `src/phase_processor/processor.py`, `src/phase_processor/parser.py`.

**src/data_generator:**
- Purpose: Bridge between the raw simulation and the training data format.
- Contains: Traffic collectors, day simulators, and prompt builders.
- Key files: `src/data_generator/traffic_collector.py`, `src/data_generator/day_simulator.py`.

**sumo_simulation/environments:**
- Purpose: Storage for diverse simulation scenarios.
- Contains: Folders for each scenario (e.g., `chengdu`, `arterial4x4_10`).
- Key files: `*.net.xml`, `*.rou.xml`, `*.sumocfg`.

**outputs/data:**
- Purpose: Storage for generated samples before merging.
- Contains: Subdirectories per scenario containing `samples_[date].jsonl`.

## Key File Locations

**Entry Points:**
- `src/scripts/generate_training_data.py`: Primary CLI for large-scale data generation.
- `sumo_simulation/sumo_simulator.py`: Core simulator interface and standalone tester.

**Configuration:**
- `config/config.json`: Global settings for workers, paths, and simulation parameters.

**Core Logic:**
- `src/phase_processor/processor.py`: Orchestrates phase extraction.
- `src/data_generator/day_simulator.py`: Manages the lifecycle of a single simulation run.

**Testing:**
- Not detected in a centralized directory; likely relies on script-based verification.

## Naming Conventions

**Files:**
- Snake Case: `traffic_collector.py`, `generate_training_data.py`.

**Directories:**
- Snake Case: `data_generator`, `phase_processor`.

**SUMO Assets:**
- Standard SUMO suffixes: `.net.xml` (network), `.rou.xml` (routes), `.sumocfg` (config).

## Where to Add New Code

**New Feature (e.g., New Metric):**
- Primary code: `src/data_generator/traffic_collector.py`
- Integration: Update `src/data_generator/models.py` or `src/data_generator/prompt_builder.py`.

**New Simulation Scenario:**
- Implementation: Add a new folder in `sumo_simulation/environments/` containing necessary XML and CFG files.

**Utilities:**
- Shared helpers: `src/utils/`

## Special Directories

**sumo_simulation/environments:**
- Purpose: Ground truth for simulation logic.
- Generated: No (typically hand-crafted or exported from tools).
- Committed: Yes.

**outputs/:**
- Purpose: Ephemeral and intermediate data.
- Generated: Yes.
- Committed: Typically ignored (check `.gitignore`).

---

*Structure analysis: 2026-02-09*
