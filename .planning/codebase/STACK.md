# Technology Stack

**Analysis Date:** 2026-02-18

## Languages

**Primary:**
- Python 3.13 - Main development language for ML training, simulation, and data processing
  - Source files: `src/**/*.py`, `qwen3_(4b)_grpo.py`, `sumo_simulation/sumo_simulator.py`
  - Benchmark: `benchmark/**/*.py`

**Secondary:**
- Shell Script - Docker container orchestration and training pipelines
  - Location: `docker/*.sh`

## Runtime

**Environment:**
- Docker Container (unsloth/unsloth:dgxspark-latest)
- Virtual environment: `.venv/` (Python 3.13)

**Package Manager:**
- pip (installed packages in `.venv/lib/python3.13/site-packages/`)
- No lockfile detected (requirements.txt not present in root)

## Frameworks

**Core ML/Training:**
- Unsloth - Fast LLM fine-tuning framework
  - Source: `unsloth/unsloth:dgxspark-latest` Docker image
  - Usage: SFT and GRPO training (`src/sft/train.py`, `src/grpo/train.py`)
- TRL (Transformer Reinforcement Learning) - GRPO and SFT trainers
  - Classes: `SFTTrainer`, `SFTConfig`, `GRPOTrainer`, `GRPOConfig`
  - Files: `src/sft/train.py`, `src/grpo/train.py`, `qwen3_(4b)_grpo.py`
- PyTorch - Deep learning backend
  - Usage: Model training, tensor operations
- vLLM - Fast inference (optional, disabled via `fast_inference=False` in config)

**Traffic Simulation:**
- SUMO (Simulation of Urban Mobility) - Traffic simulation platform
  - Python API: TraCI (`import traci`)
  - Files: `sumo_simulation/sumo_simulator.py`, `src/data_generator/**/*.py`, `src/grpo/rewards.py`
  - Environment: `SUMO_HOME=/usr/share/sumo`

**Testing:**
- Not detected (no pytest/unittest configs found)

**Build/Dev:**
- Docker - Container-based development and deployment
  - Dockerfile: `docker/Dockerfile`
  - Scripts: `docker/*.sh`

## Key Dependencies

**Critical:**
- `unsloth` - LoRA fine-tuning with gradient checkpointing
  - Configuration: `config/config.json` → `training.sft.model`, `training.grpo.model`
- `trl` - SFTTrainer, GRPOTrainer for training loops
- `transformers` - Model loading, tokenization, TextStreamer
- `torch` - GPU computation, CUDA support
- `traci` - SUMO traffic control interface
- `datasets` (HuggingFace) - Dataset loading and processing
- `modelscope` - Model downloading from ModelScope Hub
- `openai` - OpenAI-compatible API client (for benchmark)
- `loguru` - Structured logging

**Infrastructure:**
- `scikit-learn` - ML utilities
- `pandas`, `numpy` - Data manipulation
- `safetensors` - Model weight serialization

## Configuration

**Environment:**
- JSON-based configuration: `config/config.json`
  - Training params: `training.sft.*`, `training.grpo.*`
  - Paths: `paths.*` (data_dir, sft_output, grpo_output, etc.)
  - Simulation: `simulation.*` (parallel_workers, warmup_steps, etc.)
- Custom chat template for Qwen3 models
- No `.env` files detected (secrets likely managed via Docker)

**Build:**
- `docker/Dockerfile` - Docker image definition
- Docker scripts: `docker/*.sh` for training pipelines

## Platform Requirements

**Development:**
- Docker with NVIDIA GPU support (CUDA)
- SUMO traffic simulation installed
- At least 16GB GPU memory (configured `gpu_memory_utilization=0.9`)

**Production:**
- Docker container deployment
- GPU inference capability (vLLM optional)
- SUMO environment for real-time simulation rewards

---

*Stack analysis: 2026-02-18*
