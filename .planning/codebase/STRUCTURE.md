# Codebase Structure

**Analysis Date:** 2026-02-09

## Directory Layout

```
TSC_CYCLE/
├── config/             # Global configurations (JSON)
├── data/               # Training datasets (raw and processed)
│   └── training/       # Final merged train.jsonl files
├── docker/             # Containerization scripts and Dockerfile
├── model/              # Model weights and related assets
├── outputs/            # Simulation and training outputs
│   ├── data/           # Raw simulation samples by scenario
│   ├── sft/            # Processed CoT/SFT JSONL data
│   └── states/         # SUMO simulation state snapshots
├── src/                # Primary source code
│   ├── data_generator/ # Simulation orchestration and prompt building
│   ├── phase_processor/# Traffic light domain logic and validation
│   ├── scripts/        # CLI entry points for data/training
│   ├── sft/            # LLM training and formatting logic
│   └── utils/          # Shared utilities (logging, etc.)
├── sumo_simulation/    # SUMO environment files and simulator wrapper
│   ├── arterial4x4/    # Specific 4x4 intersection scenarios
│   ├── environments/   # Grouped scenario directories
│   └── sumo_simulator.py # Low-level SUMO/TraCI interface
└── rou_month_generator.py # Utility for generating traffic routes
```

## Directory Purposes

**src/data_generator/:**
- Purpose: Bridge between raw simulation and training data.
- Contains: Logic for running simulations, collecting traffic metrics, and building LLM prompts.
- Key files: `day_simulator.py`, `traffic_collector.py`, `prompt_builder.py`.

**src/phase_processor/:**
- Purpose: Domain-specific logic for Traffic Signal Control.
- Contains: Parsers for SUMO net files, phase conflict detection, and state models.
- Key files: `processor.py`, `models.py`.

**src/scripts/:**
- Purpose: Operational CLI tools.
- Contains: Scripts that tie modules together for specific tasks like data generation or training.
- Key files: `generate_training_data.py`, `train_sft.py`.

**sumo_simulation/:**
- Purpose: The simulation environment.
- Contains: XML-based configurations for SUMO and the core simulator Python class.
- Key files: `sumo_simulator.py`.

**outputs/sft/:**
- Purpose: Storage for model-ready training data.
- Contains: JSONL files formatted with `messages` and `<think>` tags.

## Key File Locations

**Entry Points:**
- `src/scripts/generate_training_data.py`: Main data generation pipeline.
- `src/scripts/train_sft.py`: Model fine-tuning script.
- `src/scripts/process_phases.py`: Network analysis tool.

**Configuration:**
- `config/config.json`: Global simulation, path, and model parameters.

**Core Logic:**
- `src/phase_processor/processor.py`: Phase management logic.
- `src/data_generator/day_simulator.py`: Simulation runner.

**Testing:**
- *Not detected (standard test directory missing; logic appears validated via CLI scripts)*.

## Naming Conventions

**Files:**
- Python files: `snake_case.py` (e.g., `day_simulator.py`).
- JSON config: `snake_case.json` (e.g., `phase_config_arterial4x4_1.json`).

**Directories:**
- Package directories: `snake_case` (e.g., `data_generator`).
- Data output directories: scenario names (e.g., `outputs/data/arterial4x4_1/`).

## Where to Add New Code

**New Feature (Simulation Logic):**
- Primary code: `src/data_generator/`
- Helper logic: `src/phase_processor/` if it involves traffic light mechanics.

**New SFT Format/Template:**
- Implementation: `src/sft/chat_template.py` or `src/sft/format_validator.py`.

**New Scenario:**
- Path: `sumo_simulation/environments/[scenario_name]/`
- Requirements: Must contain `.sumocfg`, `.net.xml`, and `.rou.xml`.

**Utilities:**
- Shared helpers: `src/utils/`.

## Special Directories

**outputs/states/:**
- Purpose: Stores binary snapshots of SUMO simulations.
- Generated: Yes
- Committed: No (usually ignored by git).

**sumo_simulation/sumo_docs/:**
- Purpose: Reference documentation for SUMO.
- Generated: No
- Committed: Yes

---

*Structure analysis: 2026-02-09*
