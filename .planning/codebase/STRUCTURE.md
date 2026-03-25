# Codebase Structure

**Analysis Date:** 2026-03-25

## Directory Layout

```
TSC_CYCLE/
├── config/                         # Central configuration
│   ├── config.json                 # Training + simulation + paths config
│   └── __init__.py
├── src/                            # Main source code
│   ├── data_generator/             # SUMO data collection and prompt building
│   ├── phase_processor/            # .net.xml phase extraction pipeline
│   ├── scripts/                    # CLI entry points for data/training pipelines
│   ├── sft/                        # Supervised fine-tuning
│   ├── grpo/                       # Group Relative Policy Optimization
│   ├── utils/                      # Shared utilities
│   ├── export_gguf.py              # GGUF export
│   ├── merge_lora.py               # LoRA merge utility
│   ├── test_gguf.py                # GGUF inference test
│   ├── test_lmstudio.py            # LM Studio API test
│   └── __init__.py
├── benchmark/                      # LLM benchmarking subsystem (independent)
│   ├── config/                     # Benchmark-specific config
│   │   ├── config.json
│   │   └── batch_config.json
│   ├── docker/                     # Benchmark Dockerfile
│   ├── tests/                      # Benchmark unit tests
│   ├── run_benchmark.py            # Single model benchmark entry
│   ├── run_batch.py                # Multi-model batch benchmark
│   ├── simulation.py               # SUMO simulation controller
│   ├── llm_client.py               # OpenAI-compatible LLM client
│   ├── prompt_builder.py           # Benchmark prompt construction
│   ├── timing_parser.py            # LLM output parsing
│   ├── metrics.py                  # Traffic metrics computation
│   ├── default_timing.py           # Fallback timing from .net.xml
│   ├── tl_filter.py                # Valid traffic light filtering
│   ├── config.py                   # BenchmarkConfig dataclass
│   ├── output.py                   # Result file writing
│   ├── report.py                   # Report generation
│   ├── logger.py                   # Loguru setup
│   ├── batch_config.py             # Batch config handling
│   └── __init__.py
├── sumo_simulation/                # SUMO environments and simulator
│   ├── sumo_simulator.py           # SUMOSimulator wrapper class
│   ├── environments/               # 1400+ scenario directories
│   │   ├── arterial4x4_1/          # Each contains .sumocfg + .net.xml + .rou.xml
│   │   ├── arterial4x4_2/
│   │   ├── ...
│   │   └── chengdu/
│   └── arterial4x4/                # Copy of scenarios (used by reward/baseline)
│       ├── arterial4x4_1/
│       └── ...
├── docker/                         # Docker execution scripts
│   ├── Dockerfile                  # Based on unsloth/unsloth:dgxspark-latest + SUMO
│   ├── entrypoint.sh               # Container entrypoint
│   ├── data.sh                     # Data generation pipeline
│   ├── sft_train.sh                # SFT training
│   ├── sft_test.sh                 # SFT inference test
│   ├── grpo_pipeline.sh            # Full GRPO pipeline (5 steps)
│   ├── grpo_data.sh                # GRPO data generation step
│   ├── grpo_train.sh               # GRPO training step
│   ├── grpo_baseline.sh            # Baseline computation step
│   ├── filter_data.sh              # Data filtering step
│   ├── merge_checkpoint.sh         # Checkpoint merge
│   ├── convert_gguf.sh             # GGUF conversion
│   ├── deploy_lmstudio.sh          # LM Studio deployment
│   ├── sft_test_lmstudio.sh        # LM Studio test
│   └── run.sh                      # General Docker run wrapper
├── model/                          # Base model weights
│   └── Qwen3-4B-Base/              # Qwen3-4B-Base safetensors + tokenizer
├── outputs/                        # Generated artifacts (gitignored)
│   ├── data/                       # Raw training data (train.jsonl)
│   ├── states/                     # SUMO state snapshots
│   ├── sft/                        # SFT outputs (model, checkpoints, sft_train.jsonl)
│   └── grpo/                       # GRPO outputs (model, checkpoints, baseline.json)
├── .planning/                      # GSD planning documents
├── qwen3_(4b)_grpo.py              # Reference training script
├── sample_prompt_result.md         # Prompt format reference
├── conftest.py                     # Pytest configuration
└── .gitignore
```

## Module Organization

### `src/data_generator/` - Training Data Generation
- `models.py`: Core dataclasses (`PhaseWait`, `Prediction`, `TrainingSample`)
- `day_simulator.py`: `DaySimulator` - runs single SUMO instance, manages lifecycle, collects samples at cycle boundaries
- `traffic_collector.py`: `TrafficCollector` - reads queue vehicles from TraCI; `load_phase_config()`, `estimate_capacity()`
- `cycle_detector.py`: `CycleDetector` - detects signal cycle start via phase transition monitoring
- `predictive_sampler.py`: `PredictiveSampler` - saves SUMO state snapshots, computes predicted saturation with noise
- `prompt_builder.py`: `PromptBuilder` - constructs structured prompts with JSON prediction data; `format_timestamp()`
- `noise.py`: `add_gaussian_noise()`, `apply_time_variation()`, `calculate_saturation()`

### `src/phase_processor/` - Network File Processing
- `processor.py`: `process_traffic_lights()` - orchestration function; `save_result_to_json()`
- `parser.py`: `parse_net_file()` - XML parsing of `.net.xml`
- `validator.py`: `filter_invalid_phases()`, `validate_traffic_light()`
- `conflict.py`: `resolve_conflicts()` - resolves lane sharing between phases
- `time_config.py`: `generate_time_config()` - computes min/max green durations
- `models.py`: `PhaseInfo` dataclass

### `src/scripts/` - CLI Entry Points
- `generate_training_data.py`: Main data generation (`python -m src.scripts.generate_training_data`)
- `process_phases.py`: Phase processing wrapper
- `generate_sft_data.py`: SFT data assembly (subcommands: `prepare`, `assemble`)
- `generate_grpo_data.py`: GRPO format conversion
- `filter_grpo_data.py`: Low-traffic sample filtering
- `merge_checkpoint.py`: LoRA checkpoint merge
- `analyze_grpo_training.py`: Training log analysis

### `src/sft/` - Supervised Fine-Tuning
- `train.py`: Complete SFT pipeline (model setup, data loading, training, saving)
- `test_inference.py`: Inference testing

### `src/grpo/` - GRPO Reinforcement Learning
- `train.py`: Complete GRPO pipeline
- `rewards.py`: Five reward functions (format, constraints, SUMO simulation, think length)
- `baseline.py`: Baseline precomputation via parallel SUMO runs

### `benchmark/` - Independent Benchmarking Subsystem
- Uses package-style imports: `from TSC_CYCLE.benchmark.xxx import yyy`
- Has its own config at `benchmark/config/config.json`
- `simulation.py`: `BenchmarkSimulation` - SUMO controller with cycle-based execution
- `llm_client.py`: `LLMClient` - OpenAI-compatible API client targeting LM Studio
- `metrics.py`: `TrafficMetricsCollector`, `CycleTrafficMetrics`, aggregate metric calculators

## Key File Locations

**Entry Points:**
- `src/scripts/generate_training_data.py`: Data generation CLI
- `src/sft/train.py`: SFT training
- `src/grpo/train.py`: GRPO training
- `src/grpo/baseline.py`: Baseline computation
- `benchmark/run_benchmark.py`: Benchmark execution
- `benchmark/run_batch.py`: Batch benchmark

**Configuration:**
- `config/config.json`: Central config (training hyperparameters, simulation params, paths)
- `benchmark/config/config.json`: Benchmark-specific config (cycle duration, LLM API settings)
- `benchmark/config/batch_config.json`: Batch benchmark model list

**Core Logic:**
- `src/grpo/rewards.py`: GRPO reward functions (most complex logic)
- `src/data_generator/day_simulator.py`: Data generation simulation loop
- `benchmark/simulation.py`: Benchmark simulation controller

**Data Models:**
- `src/data_generator/models.py`: `PhaseWait`, `Prediction`, `TrainingSample`
- `src/phase_processor/models.py`: `PhaseInfo`
- `benchmark/config.py`: `BenchmarkConfig`

**Testing:**
- `conftest.py`: Root pytest config
- `benchmark/tests/test_weighted_stats.py`: Benchmark metric tests
- `src/grpo/test_rewards.py`: Reward function tests

## Naming Conventions

**Files:**
- Python modules: `snake_case.py` (e.g., `day_simulator.py`, `prompt_builder.py`)
- Shell scripts: `snake_case.sh` (e.g., `sft_train.sh`, `grpo_pipeline.sh`)
- Config files: `config.json`, `batch_config.json`
- Generated data: `<type>_<qualifier>.jsonl` (e.g., `sft_train.jsonl`, `grpo_train_filtered.jsonl`)

**Directories:**
- Source modules: `snake_case` (e.g., `data_generator`, `phase_processor`)
- SUMO scenarios: `arterial4x4_<seed>` (numbered scenarios)

**Classes:**
- PascalCase: `DaySimulator`, `TrafficCollector`, `PromptBuilder`, `BenchmarkSimulation`

**Functions:**
- snake_case: `load_config()`, `setup_model()`, `compute_single_baseline()`

## Where to Add New Code

**New Reward Function:**
- Add to `src/grpo/rewards.py` following the existing pattern: `def new_reward(completions, **kwargs) -> List[float]`
- Register in `src/grpo/train.py` in the `reward_funcs` list
- Add config weights to `config/config.json` under `training.grpo.reward`

**New SUMO Scenario:**
- Create directory under `sumo_simulation/environments/<scenario_name>/`
- Include: `<name>.sumocfg`, `<name>.net.xml`, `<name>.rou.xml`
- Auto-discovered by `generate_training_data.py` and `benchmark/simulation.py`

**New Benchmark Metric:**
- Add computation to `benchmark/metrics.py`
- Integrate into `benchmark/run_benchmark.py` summary calculation
- Add to CSV output in `benchmark/output.py`

**New Training Script:**
- Place in `src/scripts/` for CLI tools
- Place in `src/sft/` or `src/grpo/` for training-related code
- Add corresponding Docker wrapper in `docker/`

**New Data Processing Step:**
- Add to `src/scripts/` as a standalone CLI script
- Follow pattern: argparse CLI with `--config` and `--input`/`--output` args
- Integrate into pipeline shell script in `docker/`

**Utility Functions:**
- Shared helpers: `src/utils/` (currently only `logging_config.py`)
- Module-specific helpers: within the module directory

## Special Directories

**`outputs/`:**
- Purpose: All generated artifacts (data, models, checkpoints, states)
- Generated: Yes
- Committed: No (gitignored)
- Structure: `outputs/{data,sft,grpo,states}/`

**`model/`:**
- Purpose: Base model weights (Qwen3-4B-Base)
- Generated: Downloaded from HuggingFace/ModelScope
- Committed: No (large files)

**`sumo_simulation/environments/`:**
- Purpose: 1400+ SUMO scenario definitions
- Generated: Pre-created
- Committed: Yes
- Note: Each subdirectory is a self-contained SUMO scenario

**`sumo_simulation/arterial4x4/`:**
- Purpose: Duplicate of environments for reward/baseline SUMO runs
- Generated: Pre-created
- Committed: Yes
- Note: Referenced by `src/grpo/rewards.py` and `src/grpo/baseline.py` via path mapping

**`.checkpoints/`:**
- Purpose: Training checkpoints (intermediate saves)
- Generated: Yes
- Committed: No

**`docker/`:**
- Purpose: Dockerfile + shell scripts for containerized execution
- Generated: No
- Committed: Yes
- Note: All scripts are idempotent, use `set -euo pipefail`

---

*Structure analysis: 2026-03-25*
