# Codebase Concerns

**Analysis Date:** 2026-02-09

## Tech Debt

**Hardcoded Environment Paths:**
- Issue: `SUMO_HOME` discovery logic contains multiple hardcoded user-specific paths (e.g., `/Users/leida/...`) and is duplicated across multiple files.
- Files: `src/data_generator/day_simulator.py`, `src/data_generator/traffic_collector.py`, `src/data_generator/predictive_sampler.py`
- Impact: Makes the codebase difficult to port to new environments without editing source code.
- Fix approach: Centralize environment discovery in a utility module or rely strictly on environment variables/configuration.

**Redundant State Management:**
- Issue: Both `StateManager` and `PredictiveSampler` implement state saving/loading logic with slightly different naming conventions and implementations.
- Files: `src/data_generator/state_manager.py`, `src/data_generator/predictive_sampler.py`
- Impact: Maintenance overhead and potential inconsistency in how simulation snapshots are handled.
- Fix approach: Refactor `PredictiveSampler` to use `StateManager` for all state-related operations.

**Simplistic Capacity Estimation:**
- Issue: Traffic capacity is estimated using a fixed multiplier (15 vehicles per lane), which ignores lane length, speed limits, and vehicle types.
- Files: `src/data_generator/traffic_collector.py`
- Impact: Saturation calculations may be significantly inaccurate for short lanes or high-speed arterials.
- Fix approach: Use SUMO lane attributes (length, speed) to calculate a more realistic theoretical capacity.

## Known Bugs

**Incorrect SFT Final Time Calculation:**
- Symptoms: The "linear interpolation" logic in SFT conversion is simplified in a way that ignores the 0.5 threshold mentioned in comments.
- Files: `src/scripts/generate_training_data.py` (line 301)
- Trigger: During Phase 6 of data generation.
- Workaround: None; the current logic simply applies `min_green + (max_green - min_green) * pred_saturation`.

**Fragile Date Parsing:**
- Symptoms: `DaySimulator` assumes a specific filename format containing `_2026-` to extract the base date.
- Files: `src/data_generator/day_simulator.py` (line 177)
- Trigger: Running simulation with route files that don't follow the 2026 naming convention or when the year changes.
- Workaround: Pass `base_date` explicitly in the configuration.

## Performance Bottlenecks

**O(Cycle_Duration) Sampling:**
- Problem: For every sampling point (start of every cycle for every TL), the sampler runs a full cycle of look-ahead simulation.
- Files: `src/data_generator/predictive_sampler.py`
- Cause: `_simulate_cycle_and_collect` calls `traci.simulationStep()` for the duration of the cycle to "predict" accumulation. In a network with 100 TLs and 120s cycles, this is extremely heavy.
- Improvement path: Use mathematical flow models or historical accumulation data instead of per-sample look-ahead simulation.

**I/O Intensive State Snapshots:**
- Problem: Saving and loading XML state files to disk for every cycle start.
- Files: `src/data_generator/predictive_sampler.py`, `src/data_generator/state_manager.py`
- Cause: SUMO's `saveState` and `loadState` are slow and produce large files.
- Improvement path: Enable compression by default or use in-memory state if supported by the TraCI version.

## Fragile Areas

**Cycle Detection Logic:**
- Files: `src/data_generator/cycle_detector.py`
- Why fragile: Relies on detecting a transition to the first green phase. If the simulation uses actuated controllers where phases might be skipped or the order changes, cycle detection will break.
- Safe modification: Check for full phase sequence completion or use TraCI's program switching events.
- Test coverage: Gaps in handling non-standard phase sequences.

**Fail-Fast Multi-processing:**
- Files: `src/scripts/generate_training_data.py`
- Why fragile: If a single SUMO instance crashes or a single task fails among thousands, the entire generation process is terminated immediately.
- Safe modification: Implement a retry mechanism or log failures to a report while allowing other tasks to continue.

## Test Coverage Gaps

**Error Handling and Logging:**
- What's not tested: Most modules catch `Exception` and return empty structures (`[]`, `{}`) or `None` with minimal logging.
- Files: `src/data_generator/cycle_detector.py`, `src/data_generator/traffic_collector.py`, `src/phase_processor/conflict.py`
- Risk: Critical failures (like TraCI connection loss or malformed configs) are silenced, leading to empty datasets that cause training failures later.
- Priority: High

---

*Concerns audit: 2026-02-09*
