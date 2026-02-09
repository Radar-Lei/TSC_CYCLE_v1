# Codebase Concerns

**Analysis Date:** 2026-02-09

## Tech Debt

**Missing Dependencies:**
- Issue: Multiple references to `intersection_state_recorder` are commented out because the module is missing. This breaks state tracking and metric recording features.
- Files: `sumo_simulation/sumo_simulator.py` (lines 146, 544, 1215)
- Impact: Core functionality for recording intersection states is unavailable.
- Fix approach: Implement the missing `intersection_state_recorder` module or restore the file if it was accidentally deleted.

**Hardcoded Environment Paths:**
- Issue: SUMO installation paths are hardcoded in multiple search lists.
- Files: `src/data_generator/day_simulator.py` (lines 35-44), `sumo_simulation/sumo_simulator.py` (lines 21-30, 324-333)
- Impact: Brittle configuration; simulation fails if SUMO is installed in a non-standard location or on a different user's machine (e.g., `/Users/leida/...`).
- Fix approach: Move path configuration to a `.env` file or use a standardized config file.

**Large File Complexity:**
- Issue: `sumo_simulation/sumo_simulator.py` exceeds 2100 lines and handles too many responsibilities (simulation control, metrics, GRPO data generation, file management).
- Files: `sumo_simulation/sumo_simulator.py`
- Impact: Hard to maintain, test, and understand. High risk of side effects when modifying.
- Fix approach: Refactor `SUMOSimulator` into smaller components (e.g., `MetricsCollector`, `GRPODataGenerator`, `SumoProcessManager`).

## Performance Bottlenecks

**Frequent Disk I/O for State Management:**
- Issue: Counterfactual reasoning and GRPO evaluation involve saving and loading simulation states using `traci.simulation.saveState` and `traci.simulation.loadState`. These operations write/read XML files to disk.
- Files: `sumo_simulation/sumo_simulator.py` (lines 517, 525, 1438, 1457), `src/data_generator/day_simulator.py`
- Cause: TraCI's state management is file-based by default.
- Improvement path: Use in-memory state management if supported by the SUMO version, or use a RAM disk for temporary `.xml` state files.

**Synchronous Metrics Collection:**
- Issue: Metrics are collected and written to CSV within the main simulation loop.
- Files: `sumo_simulation/sumo_simulator.py` (lines 1831-1837)
- Cause: CSV writing and complex metrics calculations (`get_intersection_metrics`) happen every 10 simulation steps.
- Improvement path: Move metrics processing and file I/O to a separate background thread or process.

## Fragile Areas

**Port Management for Parallel Simulations:**
- Issue: `DaySimulator` uses `socket.bind(('', 0))` to find a free port, but there is a potential race condition between finding the port and `traci.start` actually binding it.
- Files: `src/data_generator/day_simulator.py` (lines 190-194)
- Why fragile: High-concurrency simulations might still encounter port collisions.
- Safe modification: Implement a retry mechanism with backoff for `traci.start` when port binding fails.

**Path Manipulation:**
- Issue: Dynamic `sys.path` manipulation using `sys.path.insert(0, ...)` and `sys.path.append(...)`.
- Files: `src/data_generator/day_simulator.py` (lines 30-31, 52-53), `sumo_simulation/sumo_simulator.py` (lines 41, 53)
- Why fragile: Can cause unexpected import behavior and makes the code sensitive to the execution directory.
- Safe modification: Use a proper package structure and install the project in editable mode (`pip install -e .`).

## Test Coverage Gaps

**Untested Reward Functions:**
- What's not tested: Complex reward functions for GRPO (`match_format_exactly`, `check_answer`, `check_numbers`) rely on regex and float conversions that are prone to edge cases.
- Files: `qwen3_(4b)_grpo.py` (lines 272-391)
- Risk: Subtle bugs in reward calculation can lead to model divergence or incorrect training.
- Priority: High

**Simulation Recovery:**
- What's not tested: Logic for recovering from `traci` connection losses.
- Files: `src/data_generator/day_simulator.py` (lines 260-261, 370-394)
- Risk: Large data generation runs may fail silently or crash without saving progress.
- Priority: Medium

---

*Concerns audit: 2026-02-09*
