# Technology Stack

**Analysis Date:** 2026-02-09

## Languages

**Primary:**
- Python 3 - Main development language for simulation control, data processing, and model training. Used across `src/`, `sumo_simulation/`, and scripts like `qwen3_(4b)_grpo.py`.

**Secondary:**
- XML - Used for SUMO configuration (`.sumocfg`), network definitions (`.net.xml`), and traffic route definitions (`.rou.xml`).

## Runtime

**Environment:**
- Linux (Ubuntu/Debian) - Detected via `possible_paths` in `sumo_simulation/sumo_simulator.py`.
- SUMO (Simulation of Urban MObility) - Traffic simulation suite used for generating traffic data and testing signal control strategies.

**Package Manager:**
- pip / uv - Used for managing Python dependencies like `unsloth`, `vllm`, and `traci`.
- Lockfile: missing (Not detected in root).

## Frameworks

**Core:**
- Unsloth - Used for 2-3x faster LLM fine-tuning with reduced VRAM usage. Specifically applied to Qwen3 models in `src/sft/model_loader.py` and `qwen3_(4b)_grpo.py`.
- TraCI (Traffic Control Interface) - Python API for SUMO to retrieve simulation state and control traffic lights in real-time.
- PyTorch - Underlying deep learning framework for model training.

**Testing:**
- Not detected (No standard test directories like `tests/` or `jest.config.js` found in root).

**Build/Dev:**
- SUMO tools - Used for network parsing and route generation (`rou_month_generator.py`).

## Key Dependencies

**Critical:**
- `unsloth` - Critical for efficient LLM training and 4-bit LoRA loading.
- `traci` - Critical for interaction with the SUMO simulation environment.
- `transformers` (v4.56.2) - Used for model and tokenizer management.
- `trl` (v0.22.2) - Used for SFT (Supervised Fine-Tuning) and potentially GRPO.

**Infrastructure:**
- `vllm` - Used for fast inference.
- `datasets` - Used for managing training data in `src/sft/trainer.py`.

## Configuration

**Environment:**
- `.env` file - Stores environment variables like `GLM_API_KEY` and `SUMO_HOME`.
- `SUMO_HOME` - Critical environment variable pointing to the SUMO installation directory.

**Build:**
- `config/config.json` - Central configuration for training parameters (SFT), simulation settings (workers, duration), and file paths.

## Platform Requirements

**Development:**
- NVIDIA GPU with CUDA support - Required for Unsloth and LLM training/inference (indicated by `bf16: true` and `optim: adamw_8bit` in `config.json`).
- SUMO installed on system - Required for running simulations.

**Production:**
- Not specified (Primarily a research/training codebase for Traffic Signal Control).

---

*Stack analysis: 2026-02-09*
