# Testing Patterns

**Analysis Date:** 2026-02-09

## Test Framework

**Runner:**
- No formal test runner (like `pytest` or `unittest`) detected in the codebase.

**Assertion Library:**
- Uses standard Python `assert` statements occasionally for internal consistency checks.
- Relies on validation logic in modules like `src/phase_processor/validator.py`.

**Run Commands:**
```bash
python3 src/scripts/process_phases.py -i input.net.xml  # Manual verification of output
python3 rou_month_generator.py --validate             # Built-in validation flag
```

## Test File Organization

**Location:**
- No dedicated `tests/` directory found.
- Validation logic is co-located with source code (e.g., `src/phase_processor/validator.py`).

**Naming:**
- No `test_*.py` files detected.

**Structure:**
- Internal validation functions: `validate_traffic_light`, `filter_invalid_phases`.

## Test Structure

**Suite Organization:**
- Not applicable (no test suites).

**Patterns:**
- **Counterfactual Reasoning**: In `sumo_simulation/sumo_simulator.py`, the `step_with_state_reload` and `evaluate_action_for_grpo` methods use `saveState` and `loadState` to "test" different signal actions from the same simulation point. This serves as a form of simulation-based testing for logic.

## Mocking

**Framework:** No mocking framework (like `unittest.mock`) detected.

**Patterns:**
- Instead of mocking `traci` (the simulation interface), the code uses a "dry run" approach within the simulation itself by saving and restoring the state.

## Fixtures and Factories

**Test Data:**
- SUMO network files (`.net.xml`) and route files (`.rou.xml`) serve as the primary test data.
- Located in `sumo_simulation/arterial4x4/` and `environments/`.

**Location:**
- `sumo_simulation/arterial4x4/`
- `environments/`

## Coverage

**Requirements:** None enforced.

**View Coverage:** Not applicable.

## Test Types

**Unit Tests:**
- Performed implicitly via validation functions in `src/phase_processor/validator.py`.

**Integration Tests:**
- Script-based testing: CLI scripts like `process_phases.py` and `rou_month_generator.py` are used to verify that components work together.

**E2E Tests:**
- Full simulation runs using `sumo_simulation/sumo_simulator.py`.

## Common Patterns

**Async Testing:**
- The simulation is synchronous, controlled by `traci.simulationStep()`.

**Error Testing:**
- Handled via `try...except` blocks and logging in production code rather than dedicated failure test cases.

---

*Testing analysis: 2026-02-09*
