# Testing Patterns

**Analysis Date:** 2026-02-09

## Test Framework

**Runner:**
- Not explicitly configured (e.g., no `pytest` or `unittest` files found).

**Assertion Library:**
- Standard Python `assert` or framework-specific assertions (if added).

**Run Commands:**
```bash
# Not detected. Suggested for future:
pytest                 # Run all tests
```

## Test File Organization

**Location:**
- No dedicated `tests/` directory found in the root.

**Naming:**
- Not detected.

**Structure:**
- Code is modular, facilitating unit testing of components in `src/phase_processor/` and `src/data_generator/`.

## Test Structure

**Suite Organization:**
- No test suites currently implemented.

**Patterns:**
- Examples in docstrings (doctest style) are used for some classes:
```python
>>> # 假设第一个绿灯相位 index 是 2
>>> detector = CycleDetector('tl_1', phase_config)
>>> detector.update(2, 0.0)   # 首次调用
False
>>> detector.update(2, 90.0)  # phase 5 -> 2 (新周期!)
True
```

## Mocking

**Framework:**
- Not explicitly used, but dependency injection (passing `logger`, `phase_config`) is practiced, which facilitates mocking.

**Patterns:**
- Checking for dependency availability: `TRACI_AVAILABLE = False` if `traci` cannot be imported, allowing code to run without the simulator.

## Fixtures and Factories

**Test Data:**
- Sample data and results are present in `data/` and `outputs/` directories, which can be used as integration test fixtures.

**Location:**
- `data/`: SUMO network files (`.net.xml`), phase configurations (`.json`)
- `outputs/`: Training logs and generated datasets

## Coverage

**Requirements:**
- None enforced.

## Test Types

**Unit Tests:**
- Modular structure in `src/` allows for testing individual logic components like `conflict.py` or `validator.py`.

**Integration Tests:**
- Scripts in `src/scripts/` (e.g., `generate_training_data.py`, `process_phases.py`) serve as entry points for end-to-end processing pipelines.

**E2E Tests:**
- SUMO simulation runs (`day_simulator.py`) act as functional/integration tests for the traffic signal control logic.

## Common Patterns

**Async Testing:**
- Not detected.

**Error Testing:**
- Handled via `try-except` blocks and logging in the main code.

---

*Testing analysis: 2026-02-09*
