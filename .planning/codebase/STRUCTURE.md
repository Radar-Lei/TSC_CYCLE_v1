# Codebase Structure

**Analysis Date:** 2026-02-09

## Directory Layout

```
TSC_CYCLE/
├── sumo_simulation/     # Core SUMO simulation management
│   ├── environments/    # Traffic scenarios (sumocfg, net, rou)
│   └── sumo_simulator.py # Main Simulator class
├── src/
│   ├── phase_processor/ # Network parsing and phase extraction
│   ├── data_generator/  # Simulation-driven data collection logic
│   ├── scripts/         # CLI tools for batch processing
│   └── utils/           # Shared helpers (logging, etc.)
├── model/               # Model checkpoints and fine-tuning results
├── config/              # Global configuration (JSON)
├── outputs/             # Generated datasets and simulation states
│   ├── data/            # JSONL training files
│   └── states/          # Temporary XML state snapshots
├── docker/              # Containerization for SUMO environments
└── rou_month_generator.py # Utility for traffic demand generation
```

## Directory Purposes

**sumo_simulation/:**
- Purpose: Interface with the SUMO engine.
- Contains: TraCI wrappers and environment management.
- Key files: `sumo_simulator.py` (core logic).

**src/phase_processor/:**
- Purpose: Processes SUMO `.net.xml` files to identify valid, non-conflicting traffic phases.
- Contains: Parsers, validators, and conflict resolution logic.
- Key files: `processor.py`, `conflict.py`.

**src/data_generator/:**
- Purpose: The "Brain" of the data collection pipeline.
- Contains: Sampling strategies, noise models, and traffic collectors.
- Key files: `day_simulator.py`, `predictive_sampler.py`, `cycle_detector.py`.

**src/scripts/:**
- Purpose: User-facing entry points for high-level tasks.
- Contains: Implementation of parallel task pools and batch processing.
- Key files: `generate_training_data.py`.

**environments/:**
- Purpose: Holds discrete traffic simulations (e.g., `arterial4x4`, `chengdu`).
- Contains: `.sumocfg` (simulation config), `.net.xml` (road network), `.rou.xml` (traffic demand).

## Key File Locations

**Entry Points:**
- `src/scripts/generate_training_data.py`: Main tool for generating the training dataset.
- `sumo_simulation/sumo_simulator.py`: Core simulator interface.

**Configuration:**
- `config/config.json`: Master configuration for workers, paths, and training params.

**Core Logic:**
- `src/data_generator/day_simulator.py`: Manages the sampling lifecycle.
- `src/phase_processor/processor.py`: Orchestrates network analysis.

**Testing/Sample Data:**
- `sample_prompt_result.md`: Documentation of generated prompt formats.

## Naming Conventions

**Files:**
- Snake Case: `predictive_sampler.py`, `traffic_collector.py`.

**Directories:**
- Snake Case: `phase_processor`, `data_generator`.

**Training Data:**
- Pattern: `samples_[DATE].jsonl` for individual runs; `train.jsonl` for aggregated sets.

## Where to Add New Code

**New Feature (e.g., a new sampling strategy):**
- Primary code: `src/data_generator/` (create a new sampler class).
- Integration: Update `DaySimulator.run()` to use the new strategy.

**New CLI Script:**
- Implementation: `src/scripts/`.

**New Utility:**
- Shared helpers: `src/utils/`.

**New Simulation Environment:**
- Implementation: `sumo_simulation/environments/[env_name]/`.

## Special Directories

**outputs/states/:**
- Purpose: Stores temporary SUMO XML state files during predictive sampling.
- Generated: Yes (automatically by simulator).
- Committed: No (usually gitignored).

**model/models/unsloth/:**
- Purpose: Cache for base LLM models and fine-tuned weights.
- Generated: Yes (during training).
- Committed: No.

---

*Structure analysis: 2026-02-09*
