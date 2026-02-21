# Architecture

**Analysis Date:** 2026-02-21

## Pattern Overview

**Overall:** Reinforcement Learning from Human Feedback (RLHF) specialized for Traffic Signal Control (TSC) using LLMs. Specifically, it implements a pipeline from simulation-based data generation to Supervised Fine-Tuning (SFT) and Group Relative Policy Optimization (GRPO).

**Key Characteristics:**
- **Simulation-Centric:** Uses SUMO (Simulation of Urban MObility) as the ground truth environment for data collection and testing.
- **Agentic Control:** Traffic lights are controlled by an LLM agent that receives traffic state (queue, saturation) and outputs timing plans.
- **Distributed Data Generation:** Implements a "Flat Task Pool" model for parallel simulation of multiple intersections across different scenarios.

## Layers

**Environment Layer:**
- Purpose: Real-time traffic simulation and state observation.
- Location: `sumo_simulation/environments/`
- Contains: SUMO configuration files (`.sumocfg`, `.net.xml`, `.rou.xml`).
- Used by: Data Generator, Benchmark Runner.

**Data Generation Layer:**
- Purpose: Collects traffic states, builds prompts, and generates training samples (SFT/GRPO data).
- Location: `src/data_generator/`
- Contains: `traffic_collector.py`, `prompt_builder.py`, `day_simulator.py`.
- Depends on: SUMO (via Traci), Environment Layer.
- Used by: Training Layer.

**Training Layer (SFT/GRPO):**
- Purpose: Fine-tunes the LLM to learn optimal traffic signal control policies.
- Location: `src/sft/`, `src/grpo/`
- Contains: `train.py`, `rewards.py` (for GRPO).
- Depends on: Data Generation Layer (samples).
- Used by: Benchmark Layer.

**Benchmark Layer:**
- Purpose: Evaluates the performance of different models (baseline vs. LLM) in controlled scenarios.
- Location: `benchmark/`
- Contains: `run_benchmark.py`, `llm_client.py`, `metrics.py`.
- Depends on: Environment Layer, Trained Models.

## Data Flow

**Training Pipeline:**

1. **Simulate**: Parallel workers run SUMO simulations via `src/scripts/generate_training_data.py`.
2. **Collect**: `src/data_generator/traffic_collector.py` captures queue lengths and lane saturation.
3. **Format**: `src/data_generator/prompt_builder.py` creates prompt-response pairs in JSONL format.
4. **Train**: `src/sft/train.py` or `src/grpo/train.py` processes JSONL data to update model weights.

**Inference/Evaluation Flow:**

1. **Observe**: `benchmark/run_benchmark.py` extracts current traffic state from running SUMO.
2. **Predict**: State is sent to LLM (via `llm_client.py`) which returns a `CyclePlan`.
3. **Act**: `benchmark/timing_parser.py` extracts durations and applies them back to SUMO.
4. **Measure**: `benchmark/metrics.py` calculates delay, throughput, and queue metrics.

**State Management:**
- Handled via `src/data_generator/state_manager.py` for training data and `benchmark/simulation.py` for runtime evaluation.

## Key Abstractions

**PhaseWaitData:**
- Purpose: Represents the traffic state of a single signal phase.
- Examples: `src/data_generator/models.py`, `benchmark/prompt_builder.py`.

**TimingPlan:**
- Purpose: The decision output from the LLM, containing phase durations.
- Examples: `benchmark/timing_parser.py`.

**CycleResult:**
- Purpose: Container for performance metrics of a single traffic cycle.
- Examples: `benchmark/run_benchmark.py`.

## Entry Points

**Benchmark Runner:**
- Location: `benchmark/run_benchmark.py`
- Triggers: Manual CLI execution.
- Responsibilities: Orchestrates full evaluation of LLM models against traffic scenarios.

**Data Generator CLI:**
- Location: `src/scripts/generate_training_data.py`
- Triggers: Pre-training data collection phase.
- Responsibilities: Discovers scenarios, spawns multiprocess workers, merges final JSONL datasets.

## Error Handling

**Strategy:** Fail-fast for data generation; Fallback-to-baseline for benchmarking.

**Patterns:**
- **Simulation Recovery**: If an LLM returns invalid JSON during benchmark, the system falls back to the default timing defined in the `.net.xml` file (`benchmark/run_benchmark.py`).
- **Data Validation**: `src/phase_processor/validator.py` ensures signal logic and phase sequences are physically valid before being used in training or evaluation.

## Cross-Cutting Concerns

**Logging:** Uses `loguru` configured via `benchmark/logger.py` and `src/utils/logging_config.py`.
**Metrics Capture:** Standardized via `benchmark/metrics.py` for both training rewards and evaluation results.
**Conflict Resolution:** Traffic light logic conflict detection in `src/phase_processor/conflict.py` and `benchmark/tl_filter.py`.

---

*Architecture analysis: 2026-02-21*
