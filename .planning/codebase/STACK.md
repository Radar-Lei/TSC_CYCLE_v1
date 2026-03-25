# Technology Stack

**Analysis Date:** 2026-03-25

## Languages

**Primary:**
- Python 3 - All source code across training, data generation, benchmarking, and simulation

**Secondary:**
- Bash - Shell scripts for pipeline orchestration in `docker/` (15+ scripts)
- XML - SUMO network and configuration files in `sumo_simulation/environments/`

## Runtime

**Environment:**
- NVIDIA DGX Spark (production development machine)
- Docker container based on `unsloth/unsloth:dgxspark-latest`
- CUDA GPU acceleration required for training and inference

**Package Manager:**
- pip (no requirements.txt, pyproject.toml, or setup.py - dependencies managed in Dockerfile)
- No lockfile present

## Frameworks

**Core ML:**
- Unsloth (`unsloth`) - Primary training framework for LoRA fine-tuning. Used in `src/sft/train.py`, `src/grpo/train.py`, `src/export_gguf.py`, `src/merge_lora.py`
- Hugging Face Transformers (`transformers==5.2.0`) - Model loading, tokenizers, fallback training. Explicitly pinned in `docker/Dockerfile` line 30
- TRL (`trl`) - SFTTrainer and GRPOTrainer for SFT and GRPO training. Used in `src/sft/train.py`, `src/grpo/train.py`
- PEFT (`peft`) - LoRA adapter management. Used as fallback in `src/sft/train.py`, and for merging in `src/merge_lora.py`, `src/export_gguf.py`
- PyTorch (`torch`) - Underlying tensor framework, BF16 training

**Data:**
- Hugging Face Datasets (`datasets`) - Dataset loading and processing in training scripts

**Simulation:**
- SUMO (Simulation of Urban Mobility) - Traffic simulation engine, installed via `apt` (PPA `sumo/stable`)
- TraCI (`traci`) - Python interface to SUMO, used in `src/grpo/rewards.py` and `sumo_simulation/sumo_simulator.py`

**Inference:**
- llama-cpp-python (`llama_cpp`) - GGUF model inference with CUDA. Used in `src/test_gguf.py`
- OpenAI Python SDK (`openai`) - LM Studio API client for benchmarking. Used in `benchmark/llm_client.py`

**Testing:**
- pytest - Test runner, configured via `conftest.py`

**Logging:**
- loguru - Used in benchmark modules (`benchmark/llm_client.py`, `benchmark/simulation.py`, `benchmark/run_benchmark.py`)
- Python `logging` stdlib - Used in `src/utils/logging_config.py` for phase_processor

**Build/Dev:**
- Docker - Containerized training and deployment (`docker/Dockerfile`)

## Key Dependencies

**Critical:**
- `unsloth` - Core training acceleration library; entire SFT/GRPO pipeline depends on `FastLanguageModel`
- `trl` - Provides `SFTTrainer`, `SFTConfig`, `GRPOTrainer`, `GRPOConfig` for the two-stage training pipeline
- `transformers>=5.2.0` - Required for GLM-4 model support (`glm4_moe_lite` model type)
- `traci` - SUMO simulation control for GRPO reward computation and benchmarking
- `torch` - BF16 precision training, GPU memory management

**Infrastructure:**
- `openai` - OpenAI-compatible API client for LM Studio inference in benchmarks (`benchmark/llm_client.py`)
- `llama-cpp-python` (with CUDA) - Local GGUF model inference (`src/test_gguf.py`)
- `modelscope` - Model download from Chinese model hub, used in `src/sft/train.py` line 37
- `scikit-learn` - Installed in Dockerfile, likely used for data analysis
- `safetensors` - LoRA weight verification in reference script `qwen3_(4b)_grpo.py`
- `peft` - LoRA adapter loading/merging in `src/merge_lora.py` and `src/export_gguf.py`
- `loguru` - Structured logging in benchmark subsystem
- `numpy` - Data filtering (quantile computation) in training scripts
- `pandas` - Dataset manipulation in reference training script

## Models

**Base Models (configured in `config/config.json`):**
- `Qwen/Qwen3-4B-Base` - Primary base model for SFT training (model_id for download)
- Local path: `model/Qwen3-4B-Base`

**Model Pipeline:**
1. SFT: Base model -> LoRA fine-tuned model (`outputs/sft/model`)
2. GRPO: SFT model -> GRPO-trained model (`outputs/grpo/model`)
3. Export: Merged model -> GGUF quantized (`outputs/sft/merged/model-Q4_K_M.gguf`)

**Training Config:**
- LoRA rank: 16 (SFT), 8 (GRPO)
- Max sequence length: 2048
- Optimizer: AdamW 8-bit
- Precision: BF16
- Epochs: 2 (SFT), 1 (GRPO)

## Configuration

**Environment:**
- `SUMO_HOME=/usr/share/sumo` - Set in Dockerfile and auto-detected in simulation code
- `TZ=Asia/Shanghai` - Timezone in Docker container
- No `.env` files detected

**Build:**
- `docker/Dockerfile` - Main container build definition
- `config/config.json` - Central training/simulation/paths configuration
- `docker/entrypoint.sh` - Container entry point

## Platform Requirements

**Development:**
- NVIDIA GPU with CUDA support (DGX Spark target)
- Docker with GPU passthrough (`nvidia-docker` / `--gpus`)
- SUMO traffic simulator (auto-installed in Docker)
- ~16GB+ GPU memory (Qwen3-4B with LoRA)

**Production/Inference:**
- LM Studio running locally on `http://localhost:1234/v1` for benchmark inference
- Or llama-cpp-python with CUDA for GGUF inference
- SUMO required for simulation-based evaluation

---

*Stack analysis: 2026-03-25*
