# Technology Stack

**Analysis Date:** 2026-02-09

## Languages

**Primary:**
- Python 3.10+ - Core logic, data generation, and model training scripts. Used in `qwen3_(4b)_grpo.py`, `rou_month_generator.py`, and all files in `src/`.

**Secondary:**
- Bash - Infrastructure scripts for Docker and execution (`docker/run.sh`, `docker/data.sh`).
- XML - SUMO configuration and route files (`.rou.xml`).
- JSON - Configuration management (`config/config.json`).

## Runtime

**Environment:**
- Linux (Dockerized) - Ubuntu-based with NVIDIA CUDA support.
- SUMO (Simulation of Urban MObility) - Traffic simulation engine.

**Package Manager:**
- pip - Python package manager (Lockfile: missing).
- apt - System package manager in Docker.

## Frameworks

**Core:**
- Unsloth - Lightweight and fast LLM fine-tuning framework (used for Qwen3 training).
- PyTorch - Deep learning foundation for model training.
- TraCI (Traffic Control Interface) - Python API for controlling and retrieving data from SUMO.

**Testing:**
- Not detected - No dedicated testing framework (e.g., pytest) found in root or src.

**Build/Dev:**
- Docker - Containerization of the simulation and training environment.

## Key Dependencies

**Critical:**
- `unsloth` - Primary framework for fine-tuning `Qwen3-4B-Base`.
- `traci` - Essential for real-time interaction with the SUMO simulation.
- `sumo` - The simulation engine itself.
- `transformers` & `trl` - Hugging Face libraries for LLM training (SFT, GRPO).

**Infrastructure:**
- `vllm` - Fast inference engine for LLMs.
- `datasets` - For loading and processing training data (e.g., OpenMathReasoning).
- `torch` - Backend for tensor computations.

## Configuration

**Environment:**
- Managed via `config/config.json`.
- Environment variables in Docker: `SUMO_HOME`, `DEBIAN_FRONTEND`, `TZ`.

**Build:**
- `docker/Dockerfile` - Defines the full system environment.

## Platform Requirements

**Development:**
- NVIDIA GPU with CUDA support (required for Unsloth/vLLM).
- SUMO installed on the host or run via Docker.

**Production:**
- High-performance GPU environment (e.g., DGX) as indicated by the Docker base image `unsloth/unsloth:dgxspark-latest`.

---

*Stack analysis: 2026-02-09*
