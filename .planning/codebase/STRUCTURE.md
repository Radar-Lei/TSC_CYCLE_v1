# Codebase Structure

**Analysis Date:** 2026-02-09

## Directory Layout

```
TSC_CYCLE/
├── config/                 # Global configuration files
├── docker/                 # Containerization and execution scripts
├── model/                  # LLM model definitions and weights
├── outputs/                # Generated data, logs, and simulation states
│   ├── data/               # Final training datasets
│   └── states/             # Temporary simulation state files
├── src/                    # Primary source code
│   ├── data_generator/     # Logic for traffic data collection and prompt building
│   ├── phase_processor/    # Network analysis and traffic light logic
│   ├── scripts/            # CLI entry points for pipelines
│   └── utils/              # Shared helpers (logging, etc.)
├── sumo_simulation/        # SUMO-specific files and simulator wrapper
│   ├── arterial4x4/        # Road network definitions
│   └── environments/       # Environment-specific configurations
├── qwen3_(4b)_grpo.py      # LLM training script (GRPO)
├── rou_month_generator.py  # Traffic demand generation script
└── sumo_simulator.py       # (Legacy/Symlink) Core SUMO interface
```

## Directory Purposes

**src/data_generator/:**
- Purpose: Converts simulation results into machine learning training data.
- Contains: Samplers, prompt builders, and collectors.
- Key files: `day_simulator.py`, `prompt_builder.py`, `traffic_collector.py`.

**src/phase_processor/:**
- Purpose: Logic to understand SUMO `.net.xml` structures and extract signal phases.
- Contains: Parsers, validators, and conflict resolution logic.
- Key files: `processor.py`, `parser.py`, `conflict.py`.

**sumo_simulation/:**
- Purpose: The "World" where simulations happen.
- Contains: Network files (`.net.xml`), route files (`.rou.xml`), and the Python wrapper.
- Key files: `sumo_simulator.py`.

**outputs/data/:**
- Purpose: Storage for generated JSON/JSONL datasets ready for model consumption.

## Key File Locations

**Entry Points:**
- `src/scripts/process_phases.py`: Prep phase (Network -> JSON).
- `src/scripts/generate_training_data.py`: Main generation loop.
- `qwen3_(4b)_grpo.py`: Training start point.

**Configuration:**
- `config/config.json`: System-wide settings.
- `sumo_simulation/environments/`: Scenario-specific settings.

**Core Logic:**
- `sumo_simulation/sumo_simulator.py`: The bridge to SUMO.
- `src/data_generator/prompt_builder.py`: The LLM "interface" logic.

**Testing:**
- (Note: Explicit test directory not detected; testing appears to be manual/script-based via `src/scripts/`)

## Naming Conventions

**Files:**
- Python files: `snake_case.py` (e.g., `day_simulator.py`).
- Configuration: `config.json`.
- Output data: Usually timestamped or named by scenario.

**Directories:**
- `snake_case` (e.g., `data_generator`).

## Where to Add New Code

**New Traffic Logic/Feature:**
- Implementation: `src/data_generator/` (if it affects data collection) or `src/phase_processor/` (if it affects signal logic).

**New Simulation Scenario:**
- Configuration: `sumo_simulation/environments/[scenario_name]/`.
- Network files: `sumo_simulation/[network_name]/`.

**New ML Training Strategy:**
- Implementation: Root directory (following `qwen3_...` pattern) or within `model/`.

**Utilities:**
- Shared helpers: `src/utils/`.

## Special Directories

**outputs/:**
- Purpose: Volatile data (logs, temp states, generated datasets).
- Generated: Yes.
- Committed: Generally no (except placeholders or small samples).

**docker/:**
- Purpose: Ensures reproducible execution environments.
- Contains: `Dockerfile`, `run.sh`.

---

*Structure analysis: 2026-02-09*
