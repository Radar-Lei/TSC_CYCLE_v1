# Codebase Concerns

**Analysis Date:** 2026-02-09

## Tech Debt

**Hardcoded Environment Paths:**
- Issue: Multiple files contain hardcoded lists of possible `SUMO_HOME` paths, including user-specific paths like `/Users/leida/Cline/sumo`.
- Files: `sumo_simulation/sumo_simulator.py`, `src/data_generator/day_simulator.py`, `src/data_generator/traffic_collector.py`, `src/data_generator/predictive_sampler.py`
- Impact: Makes the codebase less portable and requires manual editing for new environments.
- Fix approach: Use a central configuration or environment variable exclusively, and provide a setup script to validate the environment.

**Simplified Capacity Estimation:**
- Issue: `estimate_capacity` uses a hardcoded multiplier of 15 vehicles per lane without considering lane length or road type.
- Files: `src/data_generator/traffic_collector.py`
- Impact: Inaccurate saturation calculations if lane lengths vary significantly across the network.
- Fix approach: Query lane length from SUMO via TraCI (`traci.lane.getLength`) and use it in the capacity formula.

**Circular Import Workarounds:**
- Issue: `SUMOSimulator` avoids top-level imports of recorders to prevent circular dependencies.
- Files: `sumo_simulation/sumo_simulator.py`
- Impact: Indicators of architectural tight coupling; makes code harder to trace and test.
- Fix approach: Refactor recorder interfaces to be injected or use an event/observer pattern.

## Known Bugs

**Port Allocation Race Condition:**
- Issue: `DaySimulator._find_free_port` finds an available port by binding to 0 and closing, but another process could grab that port before SUMO starts.
- Files: `src/data_generator/day_simulator.py`
- Impact: Flaky simulation starts in highly parallel environments.
- Fix approach: Let SUMO choose its own port or implement a retry mechanism with backoff for the TraCI connection.

## Security Considerations

**Unchecked Subprocess Execution:**
- Risk: While not directly exposed to user input, `SUMOSimulator` constructs command lines for SUMO.
- Files: `sumo_simulation/sumo_simulator.py`
- Current mitigation: Basic list-based argument construction.
- Recommendations: Ensure all paths passed to subprocess are sanitized or validated against expected patterns.

## Performance Bottlenecks

**Disk I/O for State Snapshots:**
- Problem: `PredictiveSampler` saves and restores simulation states to disk for every cycle prediction.
- Files: `src/data_generator/predictive_sampler.py`, `src/data_generator/day_simulator.py`
- Cause: TraCI state management is primarily file-based.
- Improvement path: Use a fast RAM-disk for temporary state files or explore if in-memory state snapshots (available in newer SUMO versions) can be utilized.

**Multiprocessing Memory Overhead:**
- Problem: Running multiple SUMO instances + Python workers in parallel can quickly exhaust system memory.
- Files: `src/scripts/generate_training_data.py`
- Cause: Each worker loads the full Python environment and a SUMO process.
- Improvement path: Monitor memory usage and dynamically adjust worker count, or optimize the state management to reduce overhead.

## Fragile Areas

**State Restoration Logic:**
- Files: `src/data_generator/predictive_sampler.py`
- Why fragile: The `_simulate_cycle_and_collect` method advances the global simulation clock and then `_restore_state` rolls it back. If any other component depends on a monotonic simulation clock during the sampling phase, it will break.
- Safe modification: Ensure `PredictiveSampler` operations are atomic and no other threads/components interact with the TraCI connection during the "look-ahead" phase.

## Scaling Limits

**State File Accumulation:**
- Current capacity: Limited by disk space.
- Limit: Generating 24-hour simulations with per-cycle snapshots for multiple intersections.
- Scaling path: Implement an explicit cleanup policy for state files once a training sample is successfully generated and verified.

## Dependencies at Risk

**Unsloth Compiled Cache:**
- Risk: The repository contains a large `unsloth_compiled_cache/` directory with Python files that look generated.
- Impact: Bloats repository size and might cause version mismatches if the environment changes.
- Migration plan: Add these to `.gitignore` and ensure they are generated during the setup/install phase.

## Missing Critical Features

**Unit and Integration Tests:**
- Problem: No automated testing suite (e.g., `pytest`, `unittest`) was detected in the codebase.
- Blocks: Prevents regression testing and makes refactoring (like fixing tech debt) risky.
- Priority: High.

---

*Concerns audit: 2026-02-09*
