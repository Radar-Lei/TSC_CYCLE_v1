# Testing Patterns

**Analysis Date:** 2026-02-21

## Test Framework

**Runner:**
- `pytest`
- Configuration: `conftest.py` in the root directory manages `sys.path` for module imports.

**Assertion Library:**
- Python standard `assert` statements.

**Run Commands:**
```bash
pytest                 # Run all tests
pytest benchmark/tests # Run benchmark specific tests
```

## Test File Organization

**Location:**
- Separate directory: `benchmark/tests/`.

**Naming:**
- `test_*.py` pattern (e.g., `test_weighted_stats.py`).

**Structure:**
```
TSC_CYCLE/
├── conftest.py
└── benchmark/
    └── tests/
        ├── __init__.py
        └── test_weighted_stats.py
```

## Test Structure

**Suite Organization:**
```python
class TestWeightedAverage:
    """Tests for the weighted average calculation."""

    def test_weighted_average_basic(self) -> None:
        """Basic weighted average calculation."""
        values = [10.0, 20.0, 30.0]
        weights = [1.0, 2.0, 3.0]
        result = calculate_weighted_average(values, weights)
        expected = (10 * 1 + 20 * 2 + 30 * 3) / (1 + 2 + 3)
        assert abs(result - expected) < 0.001
```

**Patterns:**
- **Arrange-Act-Assert**: Clear separation between input definition, function call, and result verification.
- **Parametrization**: Not explicitly seen in samples, but class-based grouping is used to organize related test cases.

## Mocking

**Framework:**
- `pytest` (standard mocking utilities or `unittest.mock` as needed).

**Patterns:**
- Testing logic involves simulating dictionaries that mimic `CycleResult` objects to test metric calculations without running a full SUMO simulation (see `test_calculate_weighted_metrics_single_cycle` in `benchmark/tests/test_weighted_stats.py`).

**What to Mock:**
- External simulation state (SUMO/TraCI) when testing downstream metric aggregation.

**What NOT to Mock:**
- Pure mathematical functions and dataclass serializations.

## Fixtures and Factories

**Test Data:**
- Local mocking: `mock_result = {"queue_vehicles": 10, ...}` defined directly within test methods.

**Location:**
- Within individual test modules or classes.

## Coverage

**Requirements:**
- None enforced (no `.coveragerc` or explicit coverage thresholds detected in configuration).

**View Coverage:**
```bash
pytest --cov=src --cov=benchmark
```

## Test Types

**Unit Tests:**
- Focused on specific logic like weighted averages, throughput calculations, and metrics aggregation.

**Integration Tests:**
- `TestEndToEndIntegration` class in `test_weighted_stats.py` checks CSV output generation and file presence using `tempfile`.

## Common Patterns

**Async Testing:**
- Not applicable (codebase appears synchronous based on current exploration).

**Error Testing:**
- Boundary condition checks for zero values or empty lists (e.g., `test_weighted_average_empty`, `test_throughput_zero_duration`).

---

*Testing analysis: 2026-02-21*
