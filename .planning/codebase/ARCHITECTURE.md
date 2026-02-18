# Architecture

**Analysis Date:** 2026-02-18

## Pattern Overview

**Overall:** ML Pipeline Architecture with Simulation Feedback Loop

**Key Characteristics:**
- Multi-stage training pipeline: Data Generation -> SFT -> GRPO (Reinforcement Learning)
- SUMO traffic simulation integration for both data generation and reward computation
- Docker-based execution environment for reproducibility
- Fail-fast pipeline orchestration with pre-validation

## Layers

**Data Generation Layer:**
- Purpose: Generate training samples from SUMO traffic simulations
- Location: `src/data_generator/`, `src/phase_processor/`
- Contains: Phase configuration parsing, traffic state collection, predictive sampling, prompt building, noise generation
- Depends on: SUMO/TraCI, config files in `config/`
- Used by: Training pipeline via `src/scripts/generate_training_data.py`

**Training Layer:**
- Purpose: Execute SFT and GRPO training on Qwen3-4B model
- Location: `src/sft/`, `src/grpo/`
- Contains: Model setup with LoRA, chat template configuration, training loops, multi-layer reward functions
- Depends on: Unsloth, TRL (SFTTrainer/GRPOTrainer), HuggingFace Transformers
- Used by: Docker shell scripts in `docker/`

**Evaluation Layer:**
- Purpose: Benchmark trained models against baseline and other LLMs
- Location: `benchmark/`
- Contains: LLM client with OpenAI-compatible API, simulation runner, metrics calculation, timing parser, report generation
- Depends on: SUMO/TraCI, loguru logging
- Used by: Benchmark CLI scripts

**Orchestration Layer:**
- Purpose: Coordinate pipeline stages via CLI and shell scripts
- Location: `src/scripts/`, `docker/`
- Contains: Data generation CLI, SFT/GRPO data preparation, full pipeline scripts
- Depends on: All other layers
- Used by: End users via command line or Docker

## Data Flow

**Training Data Generation Flow:**

1. `src/scripts/generate_training_data.py` discovers SUMO scenarios from `sumo_simulation/environments/`
2. For each scenario, `src/phase_processor/processor.py` parses `.net.xml` to extract traffic light phases
3. Phase config saved to `outputs/data/phase_config_<scenario>.json`
4. `src/data_generator/day_simulator.py` runs parallel SUMO simulations with `PredictiveSampler`
5. `PredictiveSampler` saves simulation states (`.xml.gz`) and collects traffic predictions
6. `src/data_generator/prompt_builder.py` builds training prompts from predictions
7. Samples collected and merged into `outputs/data/train.jsonl`

**SFT Training Flow:**

1. `src/scripts/generate_sft_data.py prepare` generates solutions based on saturation
2. Manual/AI think text added to workspace file
3. `src/scripts/generate_sft_data.py assemble` converts to messages format
4. `src/sft/train.py` loads Qwen3-4B-Base, configures LoRA (rank 32), trains with SFTTrainer
5. Custom chat template with `<start_working_out>/<end_working_out>/<SOLUTION>` tags
6. Merged model saved to `outputs/sft/model/`

**GRPO Training Flow:**

1. `src/scripts/generate_grpo_data.py` converts train.jsonl to GRPO prompt format (messages array)
2. `src/grpo/baseline.py` precomputes baseline metrics for each state file
3. `src/grpo/rewards.py` initialized with baseline for reward normalization
4. `src/grpo/train.py` loads SFT model, trains with GRPOTrainer using 5 reward functions
5. Merged model saved to `outputs/grpo/model/`

**Reward Calculation Flow (GRPO):**

1. `match_format_exactly`: Check exact tag pattern match (+3.0 or 0)
2. `match_format_approximately`: Gradual score for tag presence (+0.5/-1.0 per tag)
3. `check_constraints`: Validate phase order and green time ranges (weighted score)
4. `sumo_simulation_reward`: Run SUMO replay, compare with baseline (log-compressed score, max 5.0)
5. `think_length_reward`: Penalize too short/long reasoning (penalty -0.5, bonus +0.5)

**State Management:**
- Simulation states saved as compressed XML (`.xml.gz`) in `outputs/states/<scenario>/`
- State files enable deterministic GRPO reward computation via SUMO state restore

## Key Abstractions

**PhaseWait / Prediction / TrainingSample:**
- Purpose: Core data models for training samples
- Location: `src/data_generator/models.py`
- Pattern: Dataclass with `to_dict()`/`from_dict()` serialization
```python
@dataclass
class PhaseWait:
    phase_id: int
    pred_saturation: float
    min_green: int
    max_green: int
    capacity: int = 30

@dataclass
class TrainingSample:
    prompt: str
    prediction: Prediction
    state_file: str  # Path to SUMO state snapshot
    metadata: Dict[str, Any]
```

**PredictiveSampler:**
- Purpose: Collect traffic predictions at cycle start using SUMO state save/restore
- Location: `src/data_generator/predictive_sampler.py`
- Pattern: Stateful sampler with save-state -> simulate cycle -> restore-state flow
- Key method: `sample_at_cycle_start()` returns `CyclePredictionResult`

**Reward Functions:**
- Purpose: Multi-level reward computation for GRPO training
- Location: `src/grpo/rewards.py`
- Pattern: Functions following TRL GRPOTrainer interface
```python
def reward_func(completions, **kwargs) -> List[float]
def reward_func(prompts, completions, **kwargs) -> List[float]
```
- Initialization: `init_rewards(config_path, baseline_path)` sets module-level state

**BenchmarkSimulation:**
- Purpose: Run controlled SUMO simulations for model evaluation
- Location: `benchmark/simulation.py`
- Pattern: Context-managed simulation with warmup and cycle-by-cycle LLM integration
- Key method: `apply_timing_plan(tl_id, timing_plan)` executes plan and collects metrics

**TimingPlan:**
- Purpose: Represents LLM output for signal timing
- Location: `benchmark/timing_parser.py`
```python
@dataclass
class TimingPlan:
    phases: List[PhaseTiming]

@dataclass
class PhaseTiming:
    phase_id: int        # LLM-friendly index
    sumo_phase_index: int  # Actual SUMO phase index
    final: int           # Green time in seconds
```

## Entry Points

**Data Generation:**
- Location: `src/scripts/generate_training_data.py`
- Triggers: `python -m src.scripts.generate_training_data` or `docker/data.sh`
- Responsibilities: Discover scenarios, run parallel simulations, collect samples

**SFT Training:**
- Location: `src/sft/train.py`
- Triggers: `python -m src.sft.train --config config/config.json` or `docker/sft_train.sh`
- Responsibilities: Load base model, configure LoRA, set chat template, train, save merged model

**GRPO Training:**
- Location: `src/grpo/train.py`
- Triggers: `python -m src.grpo.train --config config/config.json` or `docker/grpo_train.sh`
- Responsibilities: Load SFT model, initialize rewards, train with GRPO, save merged model

**Benchmark:**
- Location: `benchmark/run_benchmark.py`
- Triggers: `python -m benchmark.run_benchmark --config benchmark/config/config.json`
- Responsibilities: Load scenarios, run simulations with LLM, collect metrics, write reports

**Full GRPO Pipeline:**
- Location: `docker/grpo_pipeline.sh`
- Triggers: `./docker/grpo_pipeline.sh`
- Responsibilities: Orchestrate 5 steps (data gen, filter, baseline, train, analysis) with fail-fast

## Error Handling

**Strategy:** Fail-fast with explicit pre-validation

**Patterns:**
- Pre-training validation in `grpo_pipeline.sh`: checks file existence, sample count, baseline coverage, reward config
- Simulation errors propagate as RuntimeError, terminating training
- SUMO timeout in rewards: configurable via `sumo_timeout_seconds` in config
- Data validation in `generate_sft_data.py`: verifies phase order and green time constraints
- Benchmark: Graceful degradation with warning logs on non-critical failures

## Cross-Cutting Concerns

**Logging:**
- Training: Print statements with `[标签]` prefixes (e.g., `[模型]`, `[配置]`, `[数据]`)
- Benchmark: loguru with file and console handlers, configurable level
- Pipeline: Individual step logs in `outputs/grpo/grpo_*.log`

**Validation:**
- SFT data: Token length filtering (max_seq_length / 2)
- GRPO data: 90th percentile prompt length filtering
- Constraints: Phase order and green time range in reward functions
- Format: Regex-based tag matching in reward functions

**Authentication:**
- ModelScope: Optional, for downloading base model if not present locally
- LLM API: OpenAI-compatible, base URL configured in benchmark config

**Configuration:**
- Central file: `config/config.json`
- Hierarchical: `training.sft`, `training.grpo` (with `model` and `reward` sub-keys), `simulation`, `paths`
- All scripts load via `load_config()` function

---

*Architecture analysis: 2026-02-18*
