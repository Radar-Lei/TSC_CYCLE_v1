# Technology Stack

**Analysis Date:** 2026-02-09

## Languages

**Primary:**
- Python 3.10+ - Used for the entire codebase including data generation, traffic simulation, and model training.

**Secondary:**
- XML - Used for SUMO configuration files (`.sumocfg`, `.net.xml`, `.rou.xml`) and simulation state snapshots.
- JSON/JSONL - Used for configuration (`config/config.json`) and training data storage (`outputs/sft/train.jsonl`).

## Runtime

**Environment:**
- Python 3.10 (via `.venv`)
- Ubuntu-based Docker environment (`docker/Dockerfile` base: `unsloth/unsloth:dgxspark-latest`)

**Package Manager:**
- pip - Used for installing dependencies like `traci`, `modelscope`, `scikit-learn`, `unsloth`.
- Lockfile: missing (dependencies are managed via `Dockerfile` and manual installs).

## Frameworks

**Core:**
- Unsloth - Used for efficient LLM fine-tuning (LoRA/QLoRA).
- SUMO (Simulation of Urban MObility) - Traffic simulation engine used for data generation.

**Testing:**
- Not detected (No standard test framework like pytest/unittest found).

**Build/Dev:**
- Docker - Used for containerized development and execution environment.

## Key Dependencies

**Critical:**
- `unsloth` - core for model loading and efficient training in `src/sft/model_loader.py`.
- `traci` - Python interface for SUMO simulation control, used in `src/data_generator/traffic_collector.py` and `src/data_generator/predictive_sampler.py`.
- `transformers` - underlying library for LLM operations (implied by Unsloth/SFT).

**Infrastructure:**
- `modelscope` - used for model downloading/hosting (detected in `docker/Dockerfile`).
- `scikit-learn` - used for potential data processing (detected in `docker/Dockerfile`).

## Configuration

**Environment:**
- `.env` file - stores API keys (e.g., `ZHIPUAI_API_KEY` for GLM-4.7) and environment paths.
- `SUMO_HOME` - environment variable required for SUMO tools and `traci`.

**Build:**
- `config/config.json` - Central configuration for training parameters and file paths.
- `docker/Dockerfile` - Defines the system-level environment and software stack.

## Platform Requirements

**Development:**
- Linux (Ubuntu recommended) with NVIDIA GPU (required for Unsloth/LLM training).
- SUMO installed and `SUMO_HOME` path configured.

**Production:**
- NVIDIA GPU environment with CUDA support (for SFT training).
- SUMO simulation environment.

---

*Stack analysis: 2026-02-09*
