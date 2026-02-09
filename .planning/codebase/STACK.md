# Technology Stack

**Analysis Date:** 2026-02-09

## Languages

**Primary:**
- Python 3.10+ - Core logic for simulation control, data processing, and model training.

**Secondary:**
- Bash - Automation scripts for Docker orchestration and pipeline execution.
- XML - Configuration files for SUMO (networks, routes, and phase definitions).
- JSON - Configuration settings and output data format.

## Runtime

**Environment:**
- Linux (Dockerized) - Primary execution environment.
- CUDA - GPU acceleration for LLM training and inference.
- SUMO (Simulation of Urban MObility) - Traffic simulation engine.

**Package Manager:**
- Pip (inside Docker)
- Lockfile: missing (managed via Dockerfile instructions)

## Frameworks

**Core:**
- Unsloth - Optimized training of Large Language Models (Qwen3).
- TraCI (Traffic Control Interface) - Python API to connect and control SUMO simulation.

**Testing:**
- Not detected (manual execution via scripts)

**Build/Dev:**
- Docker - Containerization of the entire environment.

## Key Dependencies

**Critical:**
- `unsloth` - Used for memory-efficient LLM training (GRPO).
- `traci` - Essential for real-time traffic simulation interaction.
- `torch` - Backend for deep learning.
- `sumo` - The underlying traffic simulator.

**Infrastructure:**
- `modelscope` - Used for model downloading/hosting.
- `scikit-learn` - General utility functions (e.g., noise/normalization).
- `multiprocessing` / `concurrent.futures` - Used for parallel simulation workers.

## Configuration

**Environment:**
- `SUMO_HOME` - Points to the SUMO installation directory.
- `DEBIAN_FRONTEND=noninteractive` - Set during build for automated installations.
- `TZ=Asia/Shanghai` - Timezone configuration.

**Build:**
- `docker/Dockerfile`: Defines the environment, including SUMO PPA and Python packages.
- `config/config.json`: Central configuration for training parameters (LoRA, SFT) and simulation settings (parallel workers, duration).

## Platform Requirements

**Development:**
- Linux with Docker installed.
- NVIDIA GPU with CUDA support (required by Unsloth/Torch).
- Sufficient Shared Memory (`--shm-size=32GB` recommended).

**Production:**
- Deployment target: GPU-enabled Linux servers (DGX or similar recommended given `unsloth/unsloth:dgxspark-latest` base image).

---

*Stack analysis: 2026-02-09*
