# Coding Conventions

**Analysis Date:** 2026-02-09

## Naming Patterns

**Files:**
- Lowercase with underscores (snake_case): `cycle_detector.py`, `day_simulator.py`, `traffic_collector.py`.
- Scripts are also snake_case: `generate_training_data.py`, `process_phases.py`.

**Functions:**
- Snake case: `filter_invalid_phases`, `estimate_capacity`, `build_prompt`.

**Variables:**
- Snake case: `total_queue`, `valid_phases`, `tl_id`.

**Types:**
- Pascal case for classes: `CycleDetector`, `DaySimulator`, `TrafficCollector`, `PromptBuilder`.
- Dataclasses: `PhaseWait`, `Prediction`, `TrainingSample`, `PhaseInfo`.

## Code Style

**Formatting:**
- Follows standard Python (PEP 8) style.
- Uses 4 spaces for indentation.
- Includes docstrings for most classes and functions.

**Linting:**
- Not explicitly configured in the repository (no `.eslintrc` or similar found), but code follows consistent patterns.

## Import Organization

**Order:**
1. Standard library imports: `os`, `sys`, `json`, `datetime`.
2. Third-party imports: `traci`, `numpy` (if used), `xml.etree.ElementTree`.
3. Local module imports: `from .models import PhaseInfo`, `from src.data_generator.models import PhaseWait`.

**Path Aliases:**
- Not detected. Absolute paths are often used via `sys.path.insert(0, str(project_root))`.

## Error Handling

**Patterns:**
- Uses `try...except` blocks for external service calls (especially TraCI):
```python
try:
    halting_count = traci.lane.getLastStepHaltingNumber(lane_id)
    total_queue += halting_count
except Exception:
    return 0
```
- Return default values (like `0`, `[]`, or `None`) upon failure.
- Fail-fast pattern in main scripts: `sys.exit(1)` on critical errors.

## Logging

**Framework:** Standard `logging` module.

**Patterns:**
- Configured in `src/utils/logging_config.py`.
- Custom logger named "phase_processor".
- Logs to both console and file (`phase_processing.log`).
- Common usage: `logger.info("message")`, `logger.warning("message")`.

## Comments

**When to Comment:**
- Module-level docstrings explaining the purpose of the file.
- Class and function docstrings explaining arguments and return values.
- Inline comments for complex logic (e.g., Cycle detection boundaries).

**JSDoc/TSDoc:**
- Not applicable (Python). Uses standard Python docstrings (Google or Sphinx style).

## Function Design

**Size:** Functions are generally concise and focused on a single responsibility.

**Parameters:** Clear naming, often with type hints: `tl_id: str, phases: List[PhaseInfo]`.

**Return Values:** Explicit return types via type hints: `-> List[PhaseInfo]`.

## Module Design

**Exports:** Classes and functions are exported directly.

**Barrel Files:** `__init__.py` files are present in most directories to mark them as packages, sometimes empty, sometimes importing key members.

---

*Convention analysis: 2026-02-09*
