# Architecture

**Analysis Date:** 2026-03-25

## System Overview

TSC-CYCLE is an LLM-based traffic signal cycle timing optimization system. It uses SUMO (Simulation of Urban Mobility) traffic simulator to generate training data and evaluate model performance. The system fine-tunes a Qwen3-4B-Base model through a two-stage training pipeline (SFT then GRPO) to produce traffic signal timing plans, and benchmarks the resulting model against baseline heuristics via a separate benchmarking subsystem.

The core task: given predicted traffic saturation per phase at an intersection, output optimal green light durations (in seconds) for each phase, respecting min/max constraints.

## Core Components

### 1. Phase Processor (`src/phase_processor/`)
- Purpose: Parse SUMO `.net.xml` network files to extract valid traffic light phases, resolve conflicts, generate timing constraints (min_green, max_green)
- Key files:
  - `src/phase_processor/processor.py` - Orchestrates the full pipeline: parse -> filter -> resolve conflicts -> validate -> generate time config
  - `src/phase_processor/parser.py` - Parses `.net.xml` XML to extract raw phase data
  - `src/phase_processor/validator.py` - Filters invalid phases, validates traffic lights have >= 2 mutually exclusive phases
  - `src/phase_processor/conflict.py` - Resolves lane conflicts between phases
  - `src/phase_processor/time_config.py` - Generates min/max green time configurations
  - `src/phase_processor/models.py` - `PhaseInfo` dataclass
- Output: `phase_config_<scenario>.json` containing per-intersection phase definitions with green lanes, min/max durations

### 2. Data Generator (`src/data_generator/`)
- Purpose: Run SUMO simulations to collect traffic states at cycle boundaries, build training prompts with predicted saturation data, save SUMO state snapshots for reward computation
- Key files:
  - `src/data_generator/day_simulator.py` - `DaySimulator` class: runs one SUMO simulation instance, detects cycle boundaries, collects samples
  - `src/data_generator/traffic_collector.py` - `TrafficCollector`: reads queue vehicles per phase from TraCI
  - `src/data_generator/cycle_detector.py` - `CycleDetector`: detects when a new signal cycle begins
  - `src/data_generator/predictive_sampler.py` - `PredictiveSampler`: saves SUMO state snapshots, computes predicted saturation
  - `src/data_generator/prompt_builder.py` - `PromptBuilder`: constructs training prompts with JSON-formatted prediction data and task description
  - `src/data_generator/noise.py` - Adds Gaussian noise and time variation to training data for robustness
  - `src/data_generator/models.py` - `PhaseWait`, `Prediction`, `TrainingSample` dataclasses
- Dependencies: `sumo_simulation/sumo_simulator.py` (SUMOSimulator), TraCI, phase_config JSON

### 3. Training Data Scripts (`src/scripts/`)
- Purpose: CLI entry points for data generation pipeline
- Key files:
  - `src/scripts/generate_training_data.py` - Main data generation CLI. Flat task pool: discovers all scenarios, creates per-intersection tasks, runs in parallel via `ProcessPoolExecutor`, merges results to `outputs/data/train.jsonl`
  - `src/scripts/process_phases.py` - Wrapper for `phase_processor.processor.process_traffic_lights()`
  - `src/scripts/generate_sft_data.py` - Two-step SFT data assembly: `prepare` (compute solutions via saturation-proportional allocation) and `assemble` (combine with think text into messages format)
  - `src/scripts/generate_grpo_data.py` - Converts `train.jsonl` to GRPO format (prompt as messages array + metadata with state_file)
  - `src/scripts/filter_grpo_data.py` - Filters low-traffic samples (saturation_sum < threshold)
  - `src/scripts/merge_checkpoint.py` - Merge LoRA checkpoints
  - `src/scripts/analyze_grpo_training.py` - Post-training log analysis

### 4. SFT Training (`src/sft/`)
- Purpose: Supervised fine-tuning stage using Unsloth + LoRA on Qwen3-4B-Base
- Key files:
  - `src/sft/train.py` - Full SFT pipeline: load config -> ensure model -> setup LoRA -> patch chat template (replace `<think>` with `<start_working_out>`) -> load data -> train with `SFTTrainer` (train on responses only) -> merge LoRA -> save
  - `src/sft/test_inference.py` - Test inference on trained SFT model
- Input: `outputs/sft/sft_train.jsonl` (messages format with system/user/assistant roles)
- Output: `outputs/sft/model/` (merged full model)
- Tags: `<start_working_out>`, `<end_working_out>`, `<SOLUTION>`, `</SOLUTION>`

### 5. GRPO Training (`src/grpo/`)
- Purpose: Group Relative Policy Optimization stage using SUMO simulation feedback as reward
- Key files:
  - `src/grpo/train.py` - Full GRPO pipeline: load SFT model -> setup LoRA -> setup chat template -> init rewards -> load data -> train with `GRPOTrainer` -> save
  - `src/grpo/rewards.py` - Five reward functions for `GRPOTrainer`:
    - `match_format_exactly` (L1.1): Regex match for exact `<end_working_out><SOLUTION>...</SOLUTION>` format
    - `match_format_approximately` (L1.2): Gradual tag counting score
    - `check_constraints` (L2): Phase order + green time range validation
    - `sumo_simulation_reward` (L3): Runs SUMO simulation, computes improvement over baseline (gated by L1+L2)
    - `think_length_reward`: Penalizes too-short or too-long reasoning
  - `src/grpo/baseline.py` - Pre-computes baseline metrics (passed_vehicles, queue_vehicles, total_delay) for each state file using saturation heuristic
- Input: `outputs/grpo/grpo_train.jsonl` + `outputs/grpo/baseline.json`
- Output: `outputs/grpo/model/`

### 6. Model Export (`src/`)
- Purpose: Convert trained models to deployable formats
- Key files:
  - `src/export_gguf.py` - Merge LoRA and export to GGUF format (for LM Studio deployment)
  - `src/merge_lora.py` - Standalone LoRA merge utility
  - `src/test_gguf.py` - Test GGUF model inference
  - `src/test_lmstudio.py` - Test LM Studio API endpoint

### 7. Benchmark (`benchmark/`)
- Purpose: Evaluate LLM-driven signal timing against baseline on SUMO scenarios. Independent subsystem with its own config.
- Key files:
  - `benchmark/run_benchmark.py` - Main benchmark entry: discovers scenarios -> filters valid intersections -> runs per-intersection simulations -> collects metrics -> writes reports
  - `benchmark/run_batch.py` - Batch runner: evaluates multiple models across scenarios
  - `benchmark/simulation.py` - `BenchmarkSimulation`: SUMO controller with cycle-based pausing, warmup, timing plan application, traffic metrics collection
  - `benchmark/llm_client.py` - `LLMClient`: OpenAI-compatible API client (targets LM Studio) with retry + structured output support
  - `benchmark/prompt_builder.py` - `BenchmarkPromptBuilder`: builds prompts for benchmark evaluation
  - `benchmark/timing_parser.py` - Parses LLM output to extract `TimingPlan` (supports both SOLUTION tags and raw JSON)
  - `benchmark/metrics.py` - `TrafficMetricsCollector`, `CycleTrafficMetrics`, weighted metric calculation
  - `benchmark/default_timing.py` - Loads default timing from `.net.xml` as fallback
  - `benchmark/tl_filter.py` - Filters traffic lights to valid ones
  - `benchmark/config.py` - `BenchmarkConfig` dataclass + JSON loader
  - `benchmark/output.py` - Output directory management, CSV/JSON writing
  - `benchmark/report.py` - Report generation
  - `benchmark/logger.py` - Loguru-based logging setup
  - `benchmark/batch_config.py` - Batch configuration

### 8. SUMO Simulation (`sumo_simulation/`)
- Purpose: SUMO environment definitions and simulator wrapper
- Key files:
  - `sumo_simulation/sumo_simulator.py` - `SUMOSimulator` class: manages SUMO process lifecycle via TraCI, supports headless and GUI modes
  - `sumo_simulation/environments/` - 1400+ SUMO scenario directories (arterial4x4_*), each containing `.sumocfg`, `.net.xml`, `.rou.xml`
  - `sumo_simulation/arterial4x4/` - Parallel copy of scenarios (used by rewards/baseline)

## Data Flow

### Training Pipeline (end-to-end)

```
[SUMO .net.xml files]
        |
        v
  Phase Processor (process_phases.py)
        |
        v
  [phase_config_<scenario>.json]
        |
        v
  Data Generator (generate_training_data.py)
   - Runs SUMO simulations in parallel (per-intersection tasks)
   - Saves state snapshots to outputs/states/
   - Collects samples at cycle boundaries
        |
        v
  [outputs/data/train.jsonl]
        |
        +-------> generate_sft_data.py (prepare + assemble)
        |              |
        |              v
        |         [outputs/sft/sft_train.jsonl]
        |              |
        |              v
        |         SFT Training (src/sft/train.py)
        |              |
        |              v
        |         [outputs/sft/model/]
        |
        +-------> generate_grpo_data.py
                       |
                       v
                  [outputs/grpo/grpo_train.jsonl]
                       |
                       +-> filter_grpo_data.py -> [grpo_train_filtered.jsonl]
                       |
                       +-> baseline.py -> [outputs/grpo/baseline.json]
                       |
                       v
                  GRPO Training (src/grpo/train.py)
                       |
                       v
                  [outputs/grpo/model/]
                       |
                       v
                  export_gguf.py -> [GGUF model for LM Studio]
```

### Benchmark Flow

```
[SUMO scenarios] + [LLM model via LM Studio API]
        |
        v
  run_benchmark.py
   - For each scenario:
     - For each valid intersection:
       1. Start SUMO simulation (warmup)
       2. Per cycle:
          a. Collect traffic state (queue, saturation)
          b. Build prompt
          c. Call LLM API (with optional structured output)
          d. Parse timing plan from LLM response
          e. Apply timing plan to SUMO
          f. Collect metrics (passed, queue, delay)
       3. Write per-cycle JSON + summary CSV
        |
        v
  [benchmark/results/<model>/<timestamp>/]
   - cycle_*.json, summary.csv, final.json
```

### GRPO Reward Computation Flow (during training)

```
[Model generates completion]
        |
        v
  L1: Format check (regex match for tags)
        |  pass?
        v
  L2: Constraint check (phase order + green range)
        |  all satisfied?
        v
  L3: SUMO simulation (parallel via ProcessPoolExecutor)
   1. Load saved state file
   2. Execute model's timing plan in SUMO
   3. Collect: passed_vehicles, queue_vehicles, total_delay
   4. Compare against baseline (improvement ratio)
   5. Apply log(1+x) compression for positive, linear penalty for negative
        |
        v
  [Reward score: -2.5 to +5.0]
```

## Key Patterns

### Flat Task Pool Parallelism
- Used in: `src/scripts/generate_training_data.py`, `src/grpo/baseline.py`
- Pattern: All (scenario x intersection) combinations are flattened into a single task list, consumed by `ProcessPoolExecutor`. Each task gets its own SUMO instance with a randomly assigned port.
- Why: Maximizes GPU/CPU utilization, avoids idle workers when scenarios have uneven intersection counts.

### Cycle-Boundary Sampling
- Used in: `src/data_generator/day_simulator.py`
- Pattern: `CycleDetector` monitors phase transitions. When the first green phase of a new cycle is detected, a SUMO state snapshot is saved and traffic data is collected.
- Why: Training samples represent decision points where timing plans must be made.

### Three-Layer Reward Gating
- Used in: `src/grpo/rewards.py`
- Pattern: L1 (format) -> L2 (constraints) -> L3 (SUMO simulation). Each layer gates the next. SUMO simulation (expensive) only runs when format and constraints are fully satisfied.
- Why: Prevents wasting compute on SUMO for invalid outputs; provides gradient signal at every layer.

### Tag-Based Output Format
- Used throughout training and evaluation
- Pattern: Model outputs `<start_working_out>reasoning<end_working_out><SOLUTION>[JSON array]</SOLUTION>`
- Why: Custom tags avoid collision with Qwen3's native `<think>`/`</think>` tokens (see MEMORY.md).

### Docker-Wrapped Execution
- Used in: `docker/` shell scripts
- Pattern: All training and data generation steps run inside Docker containers (`qwen3-tsc-grpo:latest` image based on `unsloth/unsloth:dgxspark-latest`). Project directory is bind-mounted. Scripts are idempotent.
- Why: Reproducible environment with SUMO + CUDA + Unsloth dependencies.

### Dual Prompt Builder
- Training: `src/data_generator/prompt_builder.py` (`PromptBuilder`) - uses `Prediction` dataclass, outputs full prompt string
- Benchmark: `benchmark/prompt_builder.py` (`BenchmarkPromptBuilder`) - uses `PhaseWaitData`, outputs prompt for LLM API call
- Why: Training and benchmark have different prompt construction needs (training includes system prompt in text, benchmark uses separate system/user messages).

## Entry Points

### Data Generation
- **`python -m src.scripts.generate_training_data`**: Main data generation. Discovers environments, runs parallel SUMO simulations, outputs `outputs/data/train.jsonl`
- **`python -m src.scripts.generate_sft_data prepare/assemble`**: SFT data preparation
- **`python -m src.scripts.generate_grpo_data`**: GRPO data conversion
- **`python -m src.scripts.filter_grpo_data`**: GRPO data filtering

### Training
- **`python -m src.sft.train --config config/config.json`**: SFT training
- **`python -m src.grpo.train --config config/config.json`**: GRPO training
- **`python -m src.grpo.baseline --config config/config.json`**: Baseline precomputation

### Model Export
- **`python src/export_gguf.py`**: Export to GGUF format

### Benchmark
- **`python -m TSC_CYCLE.benchmark.run_benchmark --config benchmark/config/config.json`**: Single model benchmark
- **`python -m TSC_CYCLE.benchmark.run_batch`**: Batch benchmark across models

### Docker Pipeline Scripts
- **`./docker/data.sh`**: Data generation pipeline
- **`./docker/sft_train.sh`**: SFT training in Docker
- **`./docker/grpo_pipeline.sh`**: Full GRPO pipeline (data -> filter -> baseline -> train -> analyze)

## Error Handling

**Strategy:** Fail-fast in pipelines, graceful fallback in benchmark.

**Patterns:**
- Data generation (`generate_training_data.py`): Any task failure triggers immediate cancellation of all pending tasks and `sys.exit(1)`
- GRPO rewards (`rewards.py`): SUMO simulation errors raise `RuntimeError` to terminate training (per design decision)
- Benchmark (`run_benchmark.py`): LLM failures fall back to default timing from `.net.xml`; parse failures are logged and counted in metrics
- SFT model loading (`sft/train.py`): Unsloth load failure falls back to HuggingFace PEFT

## Cross-Cutting Concerns

**Logging:**
- Training scripts: `print()` with Chinese-language prefixed tags like `[模型]`, `[数据]`, `[训练]`
- Benchmark: `loguru` logger with file + console output

**Validation:**
- Phase constraints validated at multiple points: data generation, SFT data assembly, GRPO reward L2 check
- Benchmark config validated via `BenchmarkConfig.validate()`

**Configuration:**
- Training: Single `config/config.json` with nested `training.sft`, `training.grpo`, `simulation`, `paths` sections
- Benchmark: Separate `benchmark/config/config.json` with `simulation`, `paths`, `logging`, `llm` sections

**State Management:**
- SUMO state snapshots saved to `outputs/states/<scenario>/` during data generation
- State files referenced by relative path in training data for portability
- Baseline metrics cached in `outputs/grpo/baseline.json`

---

*Architecture analysis: 2026-03-25*
