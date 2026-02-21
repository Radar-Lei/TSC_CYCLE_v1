# Codebase Concerns

**Analysis Date:** 2026-02-21

## Tech Debt

**Monolithic Simulator:**
- Issue: `sumo_simulation/sumo_simulator.py` is excessively large (2127 lines), handling simulation lifecycle, state extraction, and environment control.
- Files: `sumo_simulation/sumo_simulator.py`
- Impact: Difficult to maintain, high risk of regression when modifying core simulation logic, and hard to unit test.
- Fix approach: Decompose the simulator into smaller classes: `SimulationManager` (lifecycle), `StateExtractor` (observation logic), and `ActionExecutor` (applying LLM decisions to SUMO).

**Environment-Specific Configuration:**
- Issue: Hardcoded Docker host URLs and local API endpoints in configuration files.
- Files: `benchmark/config/batch_config.json`, `docker/grpo_pipeline.sh`
- Impact: Prevents seamless "out of the box" execution in different environments (e.g., CI/CD or different dev machines).
- Fix approach: Move environment-specific values to `.env` files or use environment variables with sensible defaults.

**Greedy Phase Filtering:**
- Issue: `benchmark/tl_filter.py` uses a greedy approach to resolve traffic light phase conflicts.
- Files: `benchmark/tl_filter.py`
- Impact: May lead to suboptimal phase sets for complex intersections, affecting the quality of the benchmark results.
- Fix approach: Implement a more robust conflict resolution algorithm (e.g., maximum clique detection) to ensure the optimal set of non-conflicting phases is selected.

## Known Issues

**Qwen3 Tokenizer Conflict:**
- Issue: Native `<think>`/`</think>` tokens in Qwen3-4B-Base cause semantic conflicts during SFT.
- Files: Multi-file impact: `src/scripts/generate_sft_data.py`, `src/grpo/rewards.py`, `MEMORY.md`
- Symptoms: Model outputs random characters or fails to learn reasoning boundaries.
- Trigger: Using default chat templates with custom reasoning tags.
- Workaround: Use mapped tags like `<start_working_out>` and `<end_working_out>` as documented in `MEMORY.md`.

**SFT Training Insufficiency:**
- Issue: 1 epoch of SFT training is documented as insufficient for convergence.
- Files: `config/config.json`, `src/sft/train.py`
- Symptoms: Poor model performance on downstream tasks.
- Workaround: Set `num_train_epochs` to at least 2 in `config/config.json`.

## Security Considerations

**Docker Socket/Network Exposure:**
- Risk: Development scripts use `host.docker.internal` and expose ports that could be vulnerable if the host machine is on an untrusted network.
- Files: `docker/run.sh`, `benchmark/config/batch_config.json`
- Current mitigation: None explicitly found.
- Recommendations: Use dedicated Docker networks and avoid exposing the full host network to containers.

**Shell Injection in Scripts:**
- Risk: Some shell scripts pass variables directly to commands without sanitization.
- Files: `docker/*.sh`
- Current mitigation: Basic variable quoting.
- Recommendations: Use `shellcheck` to audit scripts and ensure all inputs are sanitized.

## Performance Bottlenecks

**Large-Scale Scenario Simulation:**
- Problem: Scenarios like `chengdu` (46 traffic lights) or massive batch runs (`arterial4x4_1000`) take significant time to simulate and evaluate.
- Files: `sumo_simulation/sumo_simulator.py`, `benchmark/run_benchmark.py`
- Cause: Synchronous simulation steps and potential overhead in TraCI communication.
- Improvement path: Implement parallel scenario execution in the benchmark runner and optimize state extraction to only pull necessary data from SUMO.

## Fragile Areas

**Phase Mapping Logic:**
- Files: `src/phase_processor/` (inferred), `benchmark/tl_filter.py`
- Why fragile: Relies heavily on the exact string representation of SUMO `state` (e.g., 'G', 'g', 'y'). Any change in how the network files are generated or how SUMO represents states will break the mapping.
- Safe modification: Encapsulate state parsing in a dedicated utility with exhaustive unit tests covering various junction types.
- Test coverage: Mostly covered by `benchmark/tests/`.

**LLM Output Parsing:**
- Files: `benchmark/timing_parser.py`, `src/utils/`
- Why fragile: Expects specific JSON or tag formats from LLM responses which can be non-deterministic.
- Safe modification: Use structured output (JSON schema) where supported or implement robust regex-based extraction with fallbacks.

## Scaling Limits

**Context Window Pressure:**
- Current capacity: Prompting 46 traffic lights simultaneously in `chengdu`.
- Limit: As the number of lanes and historical traffic data increases, the prompt size may exceed the effective context window of smaller models (like Qwen3-4B).
- Scaling path: Implement spatial partitioning (only prompt for nearby intersections) or hierarchical coordination.

## Test Coverage Gaps

**Core Simulation Logic:**
- What's not tested: The state transition logic and rewards calculation in `sumo_simulation/` and `src/grpo/rewards.py` have limited unit test coverage.
- Files: `sumo_simulation/sumo_simulator.py`, `src/grpo/rewards.py`
- Risk: Subtle bugs in traffic metrics (waiting time, queue length) could lead to incorrect training signals.
- Priority: High

---

*Concerns audit: 2026-02-21*
