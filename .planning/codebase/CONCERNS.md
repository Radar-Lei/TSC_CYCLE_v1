# Codebase Concerns

**Analysis Date:** 2026-02-09

## Tech Debt

**Hardcoded Environment Paths:**
- Issue: `SUMO_HOME` discovery relies on a list of hardcoded paths including user-specific local paths.
- Files: `src/data_generator/day_simulator.py`, `src/data_generator/predictive_sampler.py`
- Impact: Poor portability and environment-specific failures in CI/CD or other developers' machines.
- Fix approach: Rely strictly on environment variables or a centralized configuration file; remove user-specific paths like `/Users/leida/Cline/...`.

**Simple SFT Label Heuristic:**
- Issue: The "ground truth" for SFT training is calculated using a simple linear interpolation of saturation between min/max green times, rather than a true optimizer or expert demonstration.
- Files: `src/scripts/generate_training_data.py` (`convert_to_sft_format`)
- Impact: The model may learn sub-optimal behavior or simply mimic a basic rule-based controller instead of providing "expert" optimization.
- Fix approach: Replace heuristic with results from a more sophisticated traditional optimizer (e.g., Webster's formula or max-pressure) or reinforcement learning agent.

## Known Bugs

**Fail-Fast Execution Exit:**
- Issue: Any single worker failure in the multi-process data generation script triggers a `sys.exit(1)`, cancelling all other ongoing simulations.
- Files: `src/scripts/generate_training_data.py`
- Trigger: A single SUMO crash or TraCI connection timeout in one of many parallel tasks.
- Workaround: Manually restart the generation and hope for no transient failures.

## Security Considerations

**Unvalidated Path Joins:**
- Risk: While primarily a research tool, there are several instances of `os.path.join` with user-provided or config-provided strings without thorough validation.
- Files: `src/scripts/generate_training_data.py`, `src/data_generator/day_simulator.py`
- Current mitigation: None explicitly beyond basic Python error handling.
- Recommendations: Add path normalization and validation to ensure files are written only to intended directories.

## Performance Bottlenecks

**Predictive Sampling Overhead:**
- Problem: The "Look-ahead" strategy runs a full cycle simulation for every single sample point.
- Files: `src/data_generator/predictive_sampler.py` (`_simulate_cycle_and_collect`)
- Cause: Calling `traci.simulationStep()` in a loop inside a worker.
- Improvement path: Optimize cycle duration or implement a more efficient traffic model for prediction (e.g., flow-based instead of microsimulation).

**State Save/Load Latency:**
- Problem: Frequent use of `saveState` and `loadState` is slow for large network files.
- Files: `src/data_generator/predictive_sampler.py`
- Cause: SUMO state files are XML-based and can be large.
- Improvement path: Use binary state files if supported by the SUMO version, or minimize the frequency of state snapshots.

## Fragile Areas

**TraCI Port Allocation:**
- Files: `src/data_generator/day_simulator.py` (`_find_free_port`)
- Why fragile: While it attempts to find a free port, there is a race condition between finding the port and SUMO actually binding to it.
- Safe modification: Use the `sumo` command's ability to pick its own port or implement a retry mechanism.
- Test coverage: Gaps in parallel execution stress tests.

**Phase Configuration Dependency:**
- Files: `src/phase_processor/processor.py`, `src/data_generator/traffic_collector.py`
- Why fragile: If the `.net.xml` file changes its phase indices or logic, the JSON-based `phase_config` might become out of sync, leading to incorrect sampling or crashes.
- Safe modification: Add a validation step that compares the loaded `phase_config` against the active SUMO junction logic at runtime.

## Scaling Limits

**Memory Consumption in Parallel Workers:**
- Current capacity: Dependent on host RAM. Each SUMO instance + Python worker can consume 500MB-2GB+.
- Limit: On a 32GB machine, running more than 12-16 parallel workers may lead to OOM or heavy swapping.
- Scaling path: Move to a distributed task queue (e.g., Celery/Redis) across multiple nodes.

## Missing Critical Features

**Validation of SFT Output Format:**
- Problem: The trainer doesn't strictly enforce that the model output is valid JSON within the `assistant` message during the training loop.
- Blocks: Prevents early detection of model "drifting" from the required output schema.

**Automated Evaluation Pipeline:**
- Problem: No automated script to run the trained model back in the simulation to measure actual traffic metrics (delay, throughput).
- Blocks: Hard to quantify improvement over baseline.

## Test Coverage Gaps

**Unit Tests for Core Logic:**
- What's not tested: `PredictiveSampler`, `CycleDetector`, and `PhaseProcessor` lack unit tests.
- Files: `src/data_generator/*.py`, `src/phase_processor/*.py`
- Risk: Changes to core algorithms could introduce regressions in data quality without notice.
- Priority: High

---

*Concerns audit: 2026-02-09*
