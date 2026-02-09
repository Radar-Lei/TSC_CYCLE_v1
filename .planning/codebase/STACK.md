# Technology Stack

**Analysis Date:** 2026-02-09

## Languages

**Primary:**
- Python 3.x - Core logic for data generation, model training, and simulation control.

**Secondary:**
- Bash - Orchestration scripts for Docker and execution pipelines.

## Runtime

**Environment:**
- Python 3.x
- Docker - Used to encapsulate the environment, including SUMO and NVIDIA GPU support.

**Package Manager:**
- pip (implicit in Docker/scripts)
- Lockfile: missing (no `requirements.txt` or `poetry.lock` found in root, but scripts use `pip` or pre-built images).

## Frameworks

**Core:**
- Unsloth - Fast LLM fine-tuning (specifically for Qwen3-4B).
- Hugging Face Transformers - Model architecture and weights management.
- PyTorch - Deep learning backend.
- SUMO (Simulation of Urban MObility) - Traffic simulation engine.

**Testing:**
- Not explicitly detected (no dedicated test suite, though validation logic exists in `src/sft/trainer.py`).

**Build/Dev:**
- Docker - Environment isolation.
- TraCI (Traffic Control Interface) - Python API for SUMO.

## Key Dependencies

**Critical:**
- `unsloth` - Performance-optimized LLM training.
- `traci` - Real-time interaction with SUMO simulation.
- `torch` - GPU-accelerated tensor computations.
- `trl` - Transformer Reinforcement Learning library for SFT and GRPO.

**Infrastructure:**
- `datasets` - Hugging Face dataset management.
- `xml.etree.ElementTree` - Parsing SUMO configuration and net files.

## Configuration

**Environment:**
- Configured via `config/config.json`.
- Environment variables: `SUMO_HOME`, `HF_HOME`, `MODELSCOPE_CACHE`, `UNSLOTH_USE_MODELSCOPE`.

**Build:**
- `docker/Dockerfile`: Environment setup.
- `config/config.json`: Training and simulation parameters.

## Platform Requirements

**Development:**
- Linux (based on scripts and paths).
- NVIDIA GPU with CUDA support (required for LLM training).
- SUMO installation (`SUMO_HOME`).

**Production:**
- Deployment target: GPU-enabled Docker containers.

---

*Stack analysis: 2026-02-09*
