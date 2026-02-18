# Codebase Structure

**Analysis Date:** 2026-02-18

## Directory Layout

```
TSC_CYCLE/
├── benchmark/           # LLM benchmark evaluation system
├── config/              # Central configuration files
├── docker/              # Training pipeline scripts (run in Docker)
├── model/               # Base model storage (Qwen3-4B-Base)
├── outputs/             # Training outputs, data, and logs
├── src/                 # Main source code
│   ├── data_generator/  # Training data generation
│   ├── grpo/            # GRPO reinforcement learning training
│   ├── phase_processor/ # SUMO network parsing
│   ├── scripts/         # Entry point scripts
│   ├── sft/             # Supervised fine-tuning training
│   └── utils/           # Shared utilities
├── sumo_simulation/     # SUMO simulation environments
│   ├── arterial4x4/     # Arterial4x4 scenarios (1400+ variants)
│   └── environments/    # Primary scenarios (chengdu, arterial4x4_*)
└── unsloth_compiled_cache/  # Unsloth trainer compilation cache
```

## Directory Purposes

**benchmark/:**
- Purpose: LLM traffic signal benchmark evaluation system
- Contains: Simulation controller, LLM client, metrics collector, timing parser, report generator
- Key files: `run_benchmark.py`, `simulation.py`, `llm_client.py`, `metrics.py`, `timing_parser.py`, `config.py`

**config/:**
- Purpose: Central configuration for all training and simulation parameters
- Contains: Single `config.json` with nested structure
- Key files: `config.json`

**docker/:**
- Purpose: Shell scripts for running training pipelines (typically in Docker containers)
- Contains: End-to-end pipeline orchestration, individual step scripts
- Key files: `grpo_pipeline.sh`, `sft_train.sh`, `grpo_train.sh`, `grpo_baseline.sh`, `filter_data.sh`, `data.sh`, `merge_checkpoint.sh`

**model/:**
- Purpose: Storage for base model (downloaded from ModelScope on first use)
- Contains: Qwen3-4B-Base model files
- Key files: `Qwen3-4B-Base/config.json`, `Qwen3-4B-Base/model.safetensors`, `Qwen3-4B-Base/tokenizer.json`

**outputs/:**
- Purpose: All training outputs, generated data, state snapshots, and logs
- Contains: SFT model, GRPO model, training data, SUMO state files, pipeline logs
- Structure:
  ```
  outputs/
  ├── data/          # Phase configs and raw training data
  ├── sft/           # SFT outputs (model/, sft_train.jsonl)
  ├── grpo/          # GRPO outputs (model/, grpo_train.jsonl, baseline.json, logs)
  └── states/        # SUMO state snapshots by scenario
  ```

**src/:**
- Purpose: Main Python source code for training and data generation
- Contains: All modules organized by function
- Structure: See subdirectories below

**src/data_generator/:**
- Purpose: Generate training data from SUMO simulations
- Contains: Traffic collector, prompt builder, predictive sampler, state manager, noise generators, day simulator
- Key files: `models.py`, `prompt_builder.py`, `predictive_sampler.py`, `traffic_collector.py`, `day_simulator.py`, `noise.py`, `state_manager.py`

**src/grpo/:**
- Purpose: GRPO reinforcement learning training
- Contains: Trainer, reward functions, baseline precomputation, test utilities
- Key files: `train.py`, `rewards.py`, `baseline.py`, `test_rewards.py`

**src/phase_processor/:**
- Purpose: Parse SUMO network files and extract phase configurations
- Contains: Parser, validator, conflict resolver, time config generator, processor
- Key files: `processor.py`, `parser.py`, `validator.py`, `conflict.py`, `time_config.py`, `models.py`

**src/scripts/:**
- Purpose: Entry point scripts for data generation and processing
- Contains: Data generation CLI, SFT data assembly, GRPO data conversion, filtering, analysis
- Key files: `generate_training_data.py`, `generate_sft_data.py`, `generate_grpo_data.py`, `filter_grpo_data.py`, `analyze_grpo_training.py`, `merge_checkpoint.py`

**src/sft/:**
- Purpose: Supervised fine-tuning training
- Contains: SFT trainer, inference test
- Key files: `train.py`, `test_inference.py`

**src/utils/:**
- Purpose: Shared utility functions
- Contains: Logging configuration
- Key files: `logging_config.py`, `__init__.py`

**sumo_simulation/:**
- Purpose: SUMO traffic simulation environments and core simulator
- Contains: Multiple scenarios (arterial4x4 variants, chengdu), SUMO documentation
- Key files: `sumo_simulator.py`, `arterial4x4/` (1400+ variants), `environments/` (active scenarios)

**unsloth_compiled_cache/:**
- Purpose: Cached compiled Unsloth trainers for faster loading
- Contains: Pre-compiled trainer modules (SFT, GRPO, DPO, etc.)
- Generated: Yes (by Unsloth library on first use)
- Committed: Yes

## Key File Locations

**Entry Points:**
- `src/sft/train.py`: SFT training main entry
- `src/grpo/train.py`: GRPO training main entry
- `src/scripts/generate_training_data.py`: Data generation CLI
- `src/scripts/generate_sft_data.py`: SFT data preparation (prepare/assemble)
- `src/scripts/generate_grpo_data.py`: GRPO data conversion
- `benchmark/run_benchmark.py`: Benchmark evaluation entry
- `docker/grpo_pipeline.sh`: Full GRPO pipeline orchestration

**Configuration:**
- `config/config.json`: Central configuration with all hyperparameters

**Core Logic:**
- `src/grpo/rewards.py`: Multi-layer reward functions (647 lines)
- `src/data_generator/prompt_builder.py`: Training prompt construction
- `src/data_generator/predictive_sampler.py`: Cycle-level sampling with state save/restore
- `benchmark/simulation.py`: SUMO simulation control
- `src/phase_processor/processor.py`: Phase processing pipeline

**Training Data:**
- `outputs/sft/sft_train.jsonl`: SFT training data (messages format)
- `outputs/grpo/grpo_train.jsonl`: GRPO training data (prompt format)
- `outputs/grpo/baseline.json`: Precomputed baseline metrics
- `outputs/data/train.jsonl`: Raw training samples from all scenarios

**Model Outputs:**
- `outputs/sft/model/`: SFT-trained merged model
- `outputs/grpo/model/`: GRPO-trained merged model
- `outputs/grpo/checkpoints/`: Training checkpoints

**Testing:**
- `src/grpo/test_rewards.py`: Reward function unit tests
- `src/sft/test_inference.py`: SFT model inference test

**Docker Scripts:**
- `docker/grpo_pipeline.sh`: Full 5-step GRPO pipeline
- `docker/sft_train.sh`: SFT training runner
- `docker/grpo_train.sh`: GRPO training runner
- `docker/grpo_baseline.sh`: Baseline computation
- `docker/filter_data.sh`: Data filtering
- `docker/data.sh`: Data generation

## Naming Conventions

**Files:**
- Python modules: `snake_case.py` (e.g., `traffic_collector.py`, `prompt_builder.py`)
- Shell scripts: `snake_case.sh` (e.g., `sft_train.sh`, `grpo_pipeline.sh`)
- Configuration: `snake_case.json` (e.g., `config.json`, `phase_config_<scenario>.json`)
- SUMO files: Scenario-based (e.g., `arterial4x4.sumocfg`, `chengdu.net.xml`)
- State files: `state_<date>_T<time>_<tl_id>.xml.gz`

**Directories:**
- Python packages: `snake_case/` (e.g., `data_generator/`, `phase_processor/`)
- Scenarios: `snake_case` or `snake_case_NNN` (e.g., `chengdu/`, `arterial4x4_10/`)

**Classes:**
- PascalCase (e.g., `PredictiveSampler`, `BenchmarkSimulation`, `PhaseWait`)

**Functions:**
- snake_case (e.g., `load_config`, `setup_model`, `calculate_solution`, `match_format_exactly`)

**Dataclasses:**
- PascalCase with `@dataclass` decorator (e.g., `PhaseWait`, `Prediction`, `TrainingSample`, `CyclePredictionResult`)

## Where to Add New Code

**New Training Phase:**
- Create directory: `src/<phase_name>/`
- Entry script: `src/<phase_name>/train.py`
- Config section: Add to `config/config.json` under `training.<phase_name>`
- Docker script: `docker/<phase_name>_train.sh`

**New Feature/Script:**
- Entry script: `src/scripts/<feature_name>.py`
- Docker script: `docker/<feature_name>.sh`

**New Benchmark Metric:**
- Metrics logic: `benchmark/metrics.py`
- Collection: `benchmark/simulation.py` in `apply_timing_plan()`
- Report: `benchmark/report.py`

**New Reward Function:**
- Implementation: `src/grpo/rewards.py`
- Registration: Add to `reward_funcs` list in `src/grpo/train.py` main()
- Config: Add weights to `config/config.json` under `training.grpo.reward`

**New Simulation Scenario:**
- Directory: `sumo_simulation/environments/<scenario_name>/`
- Required files: `*.sumocfg`, `*.net.xml`, route files
- Update mapping: `get_sumocfg_for_state()` in `src/grpo/rewards.py`

**New Data Processing Step:**
- Script: `src/scripts/<process_name>.py`
- Integration: Add step to `docker/grpo_pipeline.sh`

**Utilities:**
- Shared helpers: `src/utils/`
- Logging: `src/utils/logging_config.py`

## Special Directories

**outputs/:**
- Purpose: All generated outputs
- Generated: Yes
- Committed: Should be in .gitignore (partially committed currently)
- Notable: `outputs/grpo/` contains all GRPO pipeline artifacts

**outputs/states/:**
- Purpose: SUMO simulation state snapshots for GRPO reward computation
- Generated: Yes (by PredictiveSampler)
- Committed: No
- Format: Gzip-compressed XML (`.xml.gz`)

**sumo_simulation/arterial4x4/:**
- Purpose: 1400+ arterial4x4 scenario variants
- Generated: Yes (by external script)
- Committed: Yes
- Size: Very large (~53MB directory)

**unsloth_compiled_cache/:**
- Purpose: Pre-compiled Unsloth trainers
- Generated: Yes (by Unsloth on first use)
- Committed: Yes
- Size: Moderate

**.venv/:**
- Purpose: Python virtual environment
- Generated: Yes
- Committed: No

**.planning/:**
- Purpose: GSD planning documents (phases, milestones, codebase analysis)
- Generated: Yes (by GSD commands)
- Committed: Partially

## Import Patterns

**Within src/ (relative imports):**
```python
from src.data_generator.models import TrainingSample, Prediction, PhaseWait
from src.phase_processor.processor import process_traffic_lights
from src.utils.logging_config import setup_logging
from src.data_generator.noise import add_gaussian_noise, calculate_saturation
```

**Benchmark module (package imports):**
```python
from TSC_CYCLE.benchmark.config import BenchmarkConfig, load_config
from TSC_CYCLE.benchmark.simulation import BenchmarkSimulation, discover_scenarios
from TSC_CYCLE.benchmark.metrics import calculate_traffic_metrics, CycleTrafficMetrics
from TSC_CYCLE.benchmark.llm_client import LLMClient
from TSC_CYCLE.benchmark.timing_parser import parse_llm_timing, TimingPlan
```

**External dependencies:**
```python
from unsloth import FastLanguageModel
from trl import SFTTrainer, GRPOTrainer, SFTConfig, GRPOConfig
from datasets import Dataset
import traci  # SUMO traffic control interface
from loguru import logger  # Used in benchmark
```

## Data File Formats

**Training samples (`outputs/data/train.jsonl`):**
```json
{
  "prompt": "Full prompt text with JSON input...",
  "prediction": {"as_of": "...", "phase_waits": [...]},
  "state_file": "/path/to/state.xml.gz",
  "metadata": {"tl_id": "...", "sim_time": ..., "date": "..."}
}
```

**SFT data (`outputs/sft/sft_train.jsonl`):**
```json
{
  "messages": [
    {"role": "system", "content": "You are..."},
    {"role": "user", "content": "Task prompt..."},
    {"role": "assistant", "content": "<start_working_out>...<end_working_out><SOLUTION>[...]</SOLUTION>"}
  ]
}
```

**GRPO data (`outputs/grpo/grpo_train.jsonl`):**
```json
{
  "prompt": [
    {"role": "system", "content": "You are..."},
    {"role": "user", "content": "Task prompt..."}
  ],
  "metadata": {"state_file": "...", "tl_id": "...", ...}
}
```

**Baseline (`outputs/grpo/baseline.json`):**
```json
{
  "outputs/states/scenario/state_xxx.xml.gz": {
    "passed_vehicles": 10,
    "queue_vehicles": 5,
    "total_delay": 120.5
  }
}
```

---

*Structure analysis: 2026-02-18*
