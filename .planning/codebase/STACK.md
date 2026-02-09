# Technology Stack

**Analysis Date:** 2026-02-09

## Languages

**Primary:**
- Python 3.10+ - Used for the entire core logic, including traffic simulation control, data generation, and LLM training.

**Secondary:**
- Shell (Bash) - Used for project setup, running simulations, and Docker entrypoint scripts in `docker/`.
- XML - Used for SUMO network and route configurations, and simulation state saving.

## Runtime

**Environment:**
- Linux (Ubuntu/Debian) - Primary development and deployment environment as seen in `docker/Dockerfile`.
- NVIDIA GPU - Required for LLM training and inference via `unsloth` and `torch`.

**Package Manager:**
- pip - Used for installing Python dependencies.
- apt - Used for system-level dependencies (SUMO, X11 utilities).

## Frameworks

**Core:**
- SUMO (Simulation of Urban MObility) - The traffic simulation engine.
- TraCI (Traffic Control Interface) - Python interface for real-time SUMO control, heavily used in `sumo_simulation/sumo_simulator.py`.
- Unsloth - Optimized LLM fine-tuning framework used for Qwen3 models in `qwen3_(4b)_grpo.py`.

**Testing:**
- Not detected (No standard test framework like pytest or jest found in root).

**Build/Dev:**
- Docker - Used for environment containerization (`docker/Dockerfile`).

## Key Dependencies

**Critical:**
- `unsloth` - Used for memory-efficient LLM training.
- `traci` - Essential for interacting with the traffic simulation.
- `torch` (PyTorch) - Deep learning framework.
- `transformers` (Hugging Face) - For model loading and tokenization.
- `trl` (Transformer Reinforcement Learning) - Used for SFT and GRPO training.

**Infrastructure:**
- `vllm` - Used for fast inference during GRPO training.
- `pandas` & `numpy` - Data manipulation for training sets.
- `modelscope` - Alternative model/dataset hub mentioned in Dockerfile.

## Configuration

**Environment:**
- Configured via `config/config.json` for training hyperparameters and simulation settings.
- `SUMO_HOME` environment variable is critical for finding SUMO binaries and tools.

**Build:**
- `docker/Dockerfile` - Defines the environment.
- `package.json` - Not detected (Python-centric project).

## Platform Requirements

**Development:**
- Linux with NVIDIA Drivers and CUDA toolkit.
- SUMO installed and `SUMO_HOME` set.

**Production:**
- Docker container based on `unsloth/unsloth:dgxspark-latest`.

---

*Stack analysis: 2026-02-09*
