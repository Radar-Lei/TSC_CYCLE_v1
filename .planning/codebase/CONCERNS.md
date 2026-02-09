# Codebase Concerns

**Analysis Date:** 2026-02-09

## Tech Debt

**Hardcoded Paths in Environment Check:**
- Issue: Several files contain hardcoded paths for `SUMO_HOME` searching, including user-specific home directory paths.
- Files: `src/data_generator/day_simulator.py`, `src/data_generator/traffic_collector.py`, `src/data_generator/predictive_sampler.py`
- Impact: Makes the codebase less portable and tied to specific developer environments.
- Fix approach: Move path discovery to a central utility or rely exclusively on environment variables and system-standard locations.

**Duplicate Logic for Time Variation:**
- Issue: `apply_time_variation` function is duplicated in two different modules with slightly different implementations (return types and constraints).
- Files: `src/data_generator/noise.py`, `src/phase_processor/time_config.py`
- Impact: Inconsistent behavior and higher maintenance cost.
- Fix approach: Consolidate into a single utility module.

**Manual Path Manipulation:**
- Issue: Frequent use of `sys.path.insert(0, ...)` to handle imports instead of using proper package installation or relative imports.
- Files: `src/scripts/generate_training_data.py`, `src/data_generator/day_simulator.py`, `src/scripts/process_phases.py`, `qwen3_(4b)_grpo.py`
- Impact: Can lead to import conflicts and makes the codebase harder to use as a library.
- Fix approach: Use a standard `pyproject.toml` or `setup.py` and install the package in editable mode.

## Known Bugs

**None explicitly detected:**
- No critical runtime bugs were identified during static analysis, but the lack of unit tests makes the codebase fragile to regressions.

## Security Considerations

**Unsafe XML Parsing:**
- Risk: Usage of `xml.etree.ElementTree` is vulnerable to XML external entity (XXE) attacks if processing untrusted net.xml or rou.xml files.
- Files: `src/phase_processor/parser.py`, `src/data_generator/day_simulator.py`, `rou_month_generator.py`
- Current mitigation: None.
- Recommendations: Use `defusedxml` or ensure input files are strictly controlled and validated.

**Execution of Shell via `os.path.exists` for Path Search:**
- Risk: While not directly executing shells, the logic searches for `SUMO_HOME` in a list of paths which could be manipulated if the environment is compromised.
- Files: `src/data_generator/day_simulator.py`
- Current mitigation: Only checking for directory existence.
- Recommendations: Rely on a single well-defined environment variable or configuration file.

## Performance Bottlenecks

**Serial Phase Processing in Loop:**
- Problem: The phase processor iterates through traffic lights serially, which can be slow for very large network files.
- Files: `src/phase_processor/processor.py`
- Cause: Single-threaded loop over `traffic_lights_raw.items()`.
- Improvement path: Implement multiprocessing for individual traffic light processing.

**State Snapshot Disk I/O:**
- Problem: Frequent saving of SUMO state snapshots during predictive sampling.
- Files: `src/data_generator/predictive_sampler.py`, `src/data_generator/state_manager.py`
- Cause: `traci.simulation.saveState` writes to disk.
- Improvement path: Ensure `compress=True` is always used or use memory-mapped files if supported by SUMO version.

## Fragile Areas

**Cycle Boundary Detection:**
- Files: `src/data_generator/cycle_detector.py`
- Why fragile: Relies on detecting the transition to the *first* green phase. If a signal program has complex transitions or skips phases, the detector might miss cycle boundaries.
- Safe modification: Add more robust state machine logic that accounts for all possible phase transitions defined in the signal program.
- Test coverage: Zero.

**Phase Conflict Resolution (Greedy):**
- Files: `src/phase_processor/conflict.py`
- Why fragile: Uses a simple greedy algorithm (keep phase with more lanes) which might not be optimal for complex intersection topologies.
- Safe modification: Evaluate multiple resolution strategies or use a graph-based maximum independent set approach.
- Test coverage: Zero.

## Scaling Limits

**Training Data Generation Workers:**
- Current capacity: Limited by CPU cores and RAM (especially with multiple SUMO instances).
- Limit: `Pool(workers)` in `generate_training_data.py`. Large networks with high traffic density significantly increase memory usage per worker.
- Scaling path: Distribute tasks across multiple nodes or optimize SUMO memory footprint (e.g., using `sublane` model sparingly).

## Dependencies at Risk

**Unsloth / FastLanguageModel:**
- Risk: High dependency on specific versions of `unsloth` and `torch`, which are rapidly evolving.
- Impact: Breaking changes in these libraries can easily break the training script `qwen3_(4b)_grpo.py`.
- Migration plan: Pin versions in a requirements file and keep a local mirror of the base models.

## Missing Critical Features

**Unit and Integration Tests:**
- Problem: The codebase has virtually no automated tests (no `tests/` directory or `*.test.py` files found).
- Blocks: Safe refactoring and continuous integration.

**Comprehensive Error Recovery in Workers:**
- Problem: If a worker fails during simulation, it might leave temporary files or orphaned SUMO processes.
- Blocks: Robust long-running data generation tasks.

## Test Coverage Gaps

**Entire Codebase:**
- What's not tested: All modules.
- Files: `src/**/*.py`
- Risk: Regressions in core logic (conflict detection, saturation calculation, prompt building) will go unnoticed until manual verification.
- Priority: High.

---

*Concerns audit: 2026-02-09*
