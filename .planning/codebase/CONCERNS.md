# Codebase Concerns

**Analysis Date:** 2026-02-09

## Tech Debt

**Predictive Sampling Performance:**
- Issue: `PredictiveSampler` saves and restores SUMO state for every cycle to calculate ground truth queue accumulation. This involves heavy disk I/O and process state manipulation.
- Files: `src/data_generator/predictive_sampler.py`, `src/data_generator/day_simulator.py`
- Impact: Significantly slows down training data generation, especially for large networks or high worker counts.
- Fix approach: Implement a more efficient way to track future queue accumulation without full state rollbacks, or optimize the snapshot storage (e.g., in-memory if supported by TraCI/SUMO).

**Dynamic Phase Configuration Dependency:**
- Issue: `CycleDetector` and `PredictiveSampler` heavily depend on a pre-generated `phase_config.json`. If Phase 1 (processing) fails or is skipped, the generator fails.
- Files: `src/data_generator/cycle_detector.py`, `src/data_generator/traffic_collector.py`
- Impact: Tight coupling between pipeline stages makes it difficult to run simulations on arbitrary SUMO networks without a specific preprocessing step.
- Fix approach: Allow optional auto-discovery of phases from the network file if config is missing, or provide more robust defaults.

## Known Bugs

**State File Leakage:**
- Issue: While `StateManager` has `cleanup_old_states`, it is not explicitly called during the main data generation loop in `generate_training_data.py`.
- Files: `src/data_generator/state_manager.py`, `src/scripts/generate_training_data.py`
- Impact: Long-running data generation tasks can fill up disk space with `.xml.gz` state files in `outputs/states`.
- Fix approach: Add an explicit cleanup call at the end of `DaySimulator.run()` or as a post-task step in the main script.

**Cycle Detection Edge Case:**
- Issue: `CycleDetector.update` might miss a cycle if the simulation step size is larger than the shortest phase duration, as it relies on detecting a transition to the `first_green_phase`.
- Files: `src/data_generator/cycle_detector.py`
- Impact: Inconsistent sampling intervals for very high-speed simulations.
- Fix approach: Use TraCI to check the remaining duration of the current phase or monitor cumulative phase transitions.

## Security Considerations

**Hardcoded Paths:**
- Risk: `DaySimulator` contains several hardcoded absolute paths for `SUMO_HOME` belonging to specific users.
- Files: `src/data_generator/day_simulator.py`
- Impact: Potential information disclosure of local system structure and breakage on different environments.
- Fix approach: Use environment variables or a portable configuration file for tool paths.

**Shell Injection Risk:**
- Risk: Use of `os.system` or `subprocess.run` with unsanitized inputs in some script areas (though most use `traci`).
- Files: `docker/run.sh`, `src/scripts/generate_training_data.py`
- Current mitigation: Basic variable quoting.
- Recommendations: Always use list-based arguments for subprocess calls and avoid `shell=True`.

## Performance Bottlenecks

**ProcessPoolExecutor Fail-Fast:**
- Problem: The `generate_training_data.py` script uses a fail-fast approach where any single worker failure terminates the entire job.
- Files: `src/scripts/generate_training_data.py`
- Cause: `sys.exit(1)` is called inside the result processing loop.
- Improvement path: Implement a retry mechanism or log failures and continue with other tasks, only failing if the success rate drops below a threshold.

**XML Parsing Overhead:**
- Problem: Parsing large `.net.xml` and `.rou.xml` files repeatedly.
- Files: `src/phase_processor/parser.py`, `src/data_generator/day_simulator.py`
- Cause: Repeated use of `xml.etree.ElementTree`.
- Improvement path: Use `lxml` for faster parsing or cache parsed results when multiple simulations share the same network.

## Fragile Areas

**Conflict Resolution Strategy:**
- Files: `src/phase_processor/conflict.py`
- Why fragile: Uses a greedy algorithm that might discard useful phases simply because they conflict with earlier ones in the list.
- Safe modification: Implement a more comprehensive maximal independent set algorithm for phase selection.
- Test coverage: Low coverage for complex intersection topologies.

**Capacity Estimation:**
- Files: `src/data_generator/traffic_collector.py`
- Why fragile: Uses a very simple heuristic (`len(green_lanes) * 15`) which doesn't account for lane length, speed limits, or vehicle types.
- Safe modification: Integrate more metadata from the SUMO network file (lane length) into the estimation.

---

*Concerns audit: 2026-02-09*
