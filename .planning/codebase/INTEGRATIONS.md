# External Integrations

**Analysis Date:** 2026-03-25

## APIs & Services

**LM Studio (OpenAI-compatible API):**
- Purpose: Local LLM inference for benchmarking fine-tuned models
- SDK/Client: `openai` Python package, wrapped in `benchmark/llm_client.py` (`LLMClient` class)
- Default endpoint: `http://localhost:1234/v1`
- Auth: None required (`api_key="not-needed"`)
- Configuration: `benchmark/config.py` (`BenchmarkConfig.llm_api_base_url`, `llm_timeout_seconds`, `llm_max_retries`, `llm_retry_base_delay`)
- Features: Structured output (JSON Schema) with automatic fallback, exponential backoff retry, system+user prompt support

**ModelScope:**
- Purpose: Download base models from Chinese model hub when not available locally
- SDK/Client: `modelscope.snapshot_download()`
- Used in: `src/sft/train.py` line 37 (`ensure_model()` function)
- Triggered: Only when local model path doesn't exist
- No auth configuration detected (public model downloads)

**Hugging Face Hub:**
- Purpose: Download training datasets (OpenMathReasoning, DAPO-Math)
- SDK/Client: `datasets.load_dataset()`
- Used in: `qwen3_(4b)_grpo.py` (reference script) for pre-training data
- Datasets: `unsloth/OpenMathReasoning-mini`, `open-r1/DAPO-Math-17k-Processed`
- Note: These are used in the reference script only; production training uses locally generated data

## Simulation Engine

**SUMO (Simulation of Urban Mobility):**
- Purpose: Traffic simulation for GRPO reward computation and benchmark evaluation
- Interface: TraCI (Traffic Control Interface) via `traci` Python package
- Integration points:
  - `src/grpo/rewards.py` - GRPO reward function runs SUMO simulations in `ProcessPoolExecutor` workers
  - `sumo_simulation/sumo_simulator.py` - Full-featured simulator class for data generation
  - `benchmark/simulation.py` - Benchmark simulation control with cycle-based operation
- Environment variable: `SUMO_HOME` (default: `/usr/share/sumo`)
- Scenarios:
  - `sumo_simulation/environments/arterial4x4_*` - 1400+ arterial grid scenarios with pre-generated route files
  - `sumo_simulation/environments/chengdu/` - Real-world Chengdu intersection scenario
- Connection: TCP socket with random port assignment (port range 10000-60000 in reward functions)
- Timeout: Configurable per `config/config.json` `training.grpo.reward.sumo_timeout_seconds` (default 60s)

## Data Storage

**Databases:**
- None - All data is file-based (JSON, JSONL)

**File Storage:**
- Local filesystem only
- Training data: `outputs/data/`, `outputs/sft/`, `outputs/grpo/` (JSONL format)
- Model checkpoints: `outputs/sft/model/`, `outputs/grpo/model/`
- GGUF exports: `outputs/sft/merged/`
- Benchmark results: `benchmark/results/`
- SUMO state files: `sumo_simulation/environments/`
- Baseline metrics: `outputs/grpo/baseline.json`

**Caching:**
- None

## Authentication & Identity

**Auth Provider:**
- Not applicable - This is a local ML training/evaluation pipeline
- LM Studio API requires no authentication
- ModelScope uses anonymous/public downloads

## Monitoring & Observability

**Error Tracking:**
- None - Errors are logged and raised as exceptions

**Logs:**
- `loguru` for benchmark subsystem (`benchmark/llm_client.py`, `benchmark/simulation.py`, `benchmark/run_benchmark.py`)
- Python `logging` stdlib for phase processor (`src/utils/logging_config.py` -> `phase_processing.log`)
- Print statements for training progress in `src/sft/train.py`, `src/grpo/train.py`
- TRL training metrics logged via trainer (configured with `report_to: "none"` - no external tracking)

## CI/CD & Deployment

**Hosting:**
- Local DGX Spark machine
- Docker container for reproducible training environment

**CI Pipeline:**
- None detected (no `.github/workflows/`, `.gitlab-ci.yml`, etc.)

**Deployment Scripts:**
- `docker/sft_train.sh` - Run SFT training in container
- `docker/grpo_train.sh` - Run GRPO training in container
- `docker/grpo_pipeline.sh` - Full GRPO pipeline (baseline + data + filter + train)
- `docker/convert_gguf.sh` - Export model to GGUF format
- `docker/deploy_lmstudio.sh` - Deploy GGUF model to LM Studio
- `docker/data.sh` - Generate training data
- `docker/run.sh` - General container run script
- `docker/sft_test.sh`, `docker/sft_test_lmstudio.sh` - Inference testing

## Webhooks & Callbacks

**Incoming:**
- None

**Outgoing:**
- None

## Environment Configuration

**Required env vars:**
- `SUMO_HOME` - SUMO installation path (auto-set in Docker to `/usr/share/sumo`, auto-detected on host)

**Optional env vars:**
- None detected (no `.env` files, all config via `config/config.json`)

**Key config file:**
- `config/config.json` - Central configuration for all training parameters, paths, reward weights, and simulation settings

---

*Integration audit: 2026-03-25*
