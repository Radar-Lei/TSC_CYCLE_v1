# External Integrations

**Analysis Date:** 2026-02-18

## APIs & External Services

**LLM Inference API:**
- LM Studio (OpenAI-compatible local server)
  - Endpoint: `http://localhost:1234/v1`
  - SDK/Client: `openai` Python package
  - Auth: No API key required (local)
  - Usage: Benchmark inference (`benchmark/llm_client.py`)
  - Features: Structured output (JSON Schema), exponential backoff retry

**HuggingFace Hub:**
- Dataset downloading
  - Used datasets: `unsloth/OpenMathReasoning-mini`, `open-r1/DAPO-Math-17k-Processed`
  - SDK: `datasets` library
  - File: `qwen3_(4b)_grpo.py`

**ModelScope Hub:**
- Model downloading (alternative to HuggingFace for China region)
  - SDK: `modelscope.snapshot_download`
  - Usage: Download Qwen3-4B-Base model
  - File: `src/sft/train.py` → `ensure_model()`

## Data Storage

**Databases:**
- None (file-based storage only)

**File Storage:**
- Local filesystem
  - Training data: `outputs/data/`, `outputs/sft/`, `outputs/grpo/`
  - Model checkpoints: `outputs/sft/model/`, `outputs/grpo/model/`
  - SUMO state files: `outputs/states/**/*.xml`
  - Simulation environments: `sumo_simulation/environments/`

**Caching:**
- Unsloth compiled cache: `unsloth_compiled_cache/`
  - Contains precompiled trainers (GRPO, SFT, DPO, etc.)
  - Lock files: `unsloth_compiled_cache/.locks/`

## Authentication & Identity

**Auth Provider:**
- None (local development)

**API Authentication:**
- LM Studio: No auth required (localhost)
- HuggingFace: Optional token for push_to_hub operations
- ModelScope: Uses snapshot_download (no explicit auth in code)

## Monitoring & Observability

**Error Tracking:**
- None detected

**Logs:**
- `loguru` for structured logging
  - Usage: `benchmark/llm_client.py`, benchmark modules
- Console output for training scripts
- File logs: `phase_processing.log` (at project root)

**Training Monitoring:**
- `report_to: "none"` in config (Weights & Biases disabled)
- Can be enabled by setting `report_to: "wandb"` in `config/config.json`

## CI/CD & Deployment

**Hosting:**
- Docker containers
  - Base image: `unsloth/unsloth:dgxspark-latest`
  - Working directory: `/home/samuel/SCU_TSC` (in container)

**CI Pipeline:**
- None detected (no `.github/workflows/` or CI configs)

**Deployment Scripts:**
- `docker/Dockerfile` - Container image definition
- `docker/run.sh` - Container entry point
- Training pipeline scripts:
  - `docker/sft_train.sh` - SFT training
  - `docker/grpo_train.sh` - GRPO training
  - `docker/grpo_pipeline.sh` - Full GRPO pipeline
  - `docker/convert_gguf.sh` - GGUF model conversion

## Environment Configuration

**Required env vars:**
- `SUMO_HOME` - SUMO installation path
  - Default: `/usr/share/sumo`
  - Used by: `sumo_simulation/sumo_simulator.py`
- `CUDA_VISIBLE_DEVICES` - GPU selection (implicit)

**Secrets location:**
- No secrets files detected
- HuggingFace/ModelScope tokens passed as function arguments when needed

## Webhooks & Callbacks

**Incoming:**
- None

**Outgoing:**
- None

## Traffic Simulation Integration

**SUMO (Simulation of Urban Mobility):**
- Purpose: Traffic signal timing optimization reward calculation
- Integration: TraCI Python API
- Key files:
  - `sumo_simulation/sumo_simulator.py` - Main simulator class
  - `src/grpo/rewards.py` - SUMO-based reward functions
  - `src/data_generator/**/*.py` - Traffic data collection
- Capabilities:
  - State save/load for counterfactual evaluation
  - Multi-phase simulation with metrics collection
  - Parallel simulation support (random ports 10000-60000)
- Scenarios:
  - `arterial4x4_10` - 4x4 arterial grid
  - `chengdu` - Real-world Chengdu intersection

## Model Export Formats

**Supported Export Formats:**
- Merged 16-bit: `save_pretrained_merged(save_method="merged_16bit")`
- Merged 4-bit: `save_pretrained_merged(save_method="merged_4bit")`
- LoRA adapters: `save_pretrained()`
- GGUF/llama.cpp: `save_pretrained_gguf()`
  - Quantization methods: `q8_0`, `q4_k_m`, `q5_k_m`, `f16`

---

*Integration audit: 2026-02-18*
