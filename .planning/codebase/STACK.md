# Technology Stack

**Analysis Date:** 2026-02-21

## Languages

**Primary:**
- Python 3.10+ - Core logic, training scripts, benchmark runner, and simulation control.

**Secondary:**
- C++ - Underlying implementation for `llama.cpp` used in model conversion and potentially optimized inference.
- Shell - Pipeline orchestration and deployment scripts in `docker/` and `benchmark/`.

## Runtime

**Environment:**
- Python 3.10+
- SUMO (Simulation of Urban MObility) - Traffic simulation engine.
- Docker - Used for containerized training and benchmarking environments.

**Package Manager:**
- Pip (via `.venv`)
- Lockfile: `llama.cpp` contains `poetry.lock`.

## Frameworks

**Core:**
- Unsloth - Optimized LoRA/QLoRA training for LLMs.
- TRL (Transformer Reinforcement Learning) - Used for GRPO (Group Relative Policy Optimization) training.
- PyTorch - Deep learning foundation.
- Hugging Face Transformers/Datasets - Model and data management.

**Testing:**
- pytest - Used for benchmark and reward function testing.

**Build/Dev:**
- CMake - Used for building `llama.cpp`.
- Docker - Environment standardization.

## Key Dependencies

**Critical:**
- `unsloth` - Fast LLM fine-tuning.
- `trl` - GRPO implementation for reinforcement learning.
- `traci` - Python link to SUMO simulation.
- `torch` - Neural network backend.

**Infrastructure:**
- `openai` - API client for LLM interaction (via LM Studio).
- `loguru` - Structured logging.
- `numpy` - Numerical computations (metrics, data filtering).

## Configuration

**Environment:**
- `SUMO_HOME` - Path to SUMO installation.
- `SUMO_GUI` - Toggle for visual simulation mode.
- `BENCHMARK_TRACI_RETRY_DELAY_S` - TraCI connection timeout settings.

**Build:**
- `config/config.json` - Training and path configuration.
- `benchmark/config/config.json` - Benchmark scenario settings.
- `benchmark/config/batch_config.json` - Model list for batch evaluation.

## Platform Requirements

**Development:**
- Linux (seen in OS Version: Linux 6.14.0-1015-nvidia)
- NVIDIA GPU (implied by `bf16`, `unsloth`, and `gpu_memory_utilization` configs)

**Production:**
- Local deployment (LM Studio/llama.cpp) or containerized execution.

---

*Stack analysis: 2026-02-21*
