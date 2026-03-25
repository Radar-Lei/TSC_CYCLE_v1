# Testing Patterns

**Analysis Date:** 2026-03-25

## Test Framework

**Runner:**
- pytest (version not pinned in config; no `pyproject.toml` or `pytest.ini` detected)
- Config: `conftest.py` at project root

**Assertion Library:**
- Built-in `assert` statements (pytest-native)
- No third-party assertion libraries

**Run Commands:**
```bash
pytest                                    # Run all tests
pytest benchmark/tests/                   # Run benchmark tests only
pytest -v                                 # Verbose output
python src/grpo/test_rewards.py           # Run reward tests (standalone script)
python src/sft/test_inference.py [N]      # Run SFT inference test with N samples
python src/test_gguf.py [N]              # Run GGUF inference test with N samples
python src/test_lmstudio.py [N]          # Run LM Studio inference test with N samples
```

## Test File Organization

**Location:** Mixed pattern - pytest tests in `benchmark/tests/`, standalone test scripts in `src/`.

**Two distinct test categories:**

### 1. Pytest Unit Tests (automated, CI-ready)

**Location:** `benchmark/tests/`
**Files:**
- `benchmark/tests/__init__.py`
- `benchmark/tests/test_weighted_stats.py` (the only pytest-style test file)

**Naming:** `test_*.py` files, `Test*` classes, `test_*` methods

### 2. Standalone Test Scripts (manual, require GPU/SUMO/API)

**Location:** Scattered in `src/`
**Files:**
- `src/grpo/test_rewards.py` - Tests reward functions (requires config + baseline data)
- `src/sft/test_inference.py` - Tests SFT model inference (requires GPU + trained model)
- `src/test_gguf.py` - Tests GGUF model inference (requires llama-cpp-python + GGUF model)
- `src/test_lmstudio.py` - Tests LM Studio API inference (requires running LM Studio server)

These are **NOT** collected by pytest. They are run directly with `python script.py`.

## conftest.py Configuration

**File:** `conftest.py` (project root)

```python
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
```

Purpose: Adds parent directory to `sys.path` so tests can import `TSC_CYCLE.*` modules.

## Test Structure (Pytest)

**Suite Organization in `benchmark/tests/test_weighted_stats.py`:**

```python
class TestWeightedAverage:
    """Tests for the weighted average calculation."""

    def test_weighted_average_basic(self) -> None:
        """Basic weighted average calculation.

        Input: values=[10, 20, 30], weights=[1, 2, 3]
        Expected: (10*1 + 20*2 + 30*3) / (1+2+3) = 23.33...
        """
        values = [10.0, 20.0, 30.0]
        weights = [1.0, 2.0, 3.0]
        result = calculate_weighted_average(values, weights)
        expected = (10 * 1 + 20 * 2 + 30 * 3) / (1 + 2 + 3)
        assert abs(result - expected) < 0.001
```

**Patterns:**
- Group related tests in classes: `TestWeightedAverage`, `TestThroughputCalculation`, `TestBoundaryConditions`
- Each test method has descriptive docstring with Input/Expected format
- Return type annotation `-> None` on all test methods
- No setup/teardown fixtures; each test is self-contained
- Tolerance-based float comparison: `assert abs(result - expected) < 0.001`

**Test categories in the file:**
- `TestWeightedAverage` - Pure function unit tests (5 tests)
- `TestThroughputCalculation` - Pure function unit tests (4 tests)
- `TestWeightedMetricsSummary` - Dataclass creation/serialization (2 tests)
- `TestCalculateWeightedMetrics` - Integration with mock data (3 tests)
- `TestBoundaryConditions` - Edge cases (6 tests)
- `TestEndToEndIntegration` - File I/O integration (2 tests)

## Mocking

**Framework:** No mocking framework (no `unittest.mock`, no `pytest-mock` detected)

**Pattern:** Tests use plain dictionaries as mock data instead of mock objects:

```python
mock_result = {
    "queue_vehicles": 10,
    "total_delay": 100.0,
    "passed_vehicles": 30,
    "samples": [0] * 60,  # 60 samples = 60 seconds
}
results = [mock_result]
summary = calculate_weighted_metrics(results)
```

**What to mock:**
- Cycle results as plain `dict` with known values
- Use `tempfile.TemporaryDirectory()` for file I/O tests

**What NOT to mock:**
- SUMO/TraCI (tested via standalone scripts with real SUMO)
- LLM API (tested via standalone scripts with real API server)
- GPU model inference (tested via standalone scripts)

## Standalone Test Script Patterns

### Reward Function Tests (`src/grpo/test_rewards.py`)

**Pattern:** Script with hardcoded test data + optional SUMO validation mode.

```python
# Hardcoded test completions
test_completions = [
    [{"content": "reasoning...<end_working_out><SOLUTION>[...]</SOLUTION>"}],
    [{"content": "missing tags"}],
]

# Functions tested directly
scores = match_format_exactly(test_completions)
scores = match_format_approximately(test_completions)
scores = check_constraints(test_prompts, test_completions)
scores = think_length_reward(test_completions)
```

**CLI:** `python src/grpo/test_rewards.py --config config/config.json [--sumo-validate] [--sample-size N]`

### Inference Tests (`src/sft/test_inference.py`, `src/test_gguf.py`, `src/test_lmstudio.py`)

**Pattern:** Random sampling from training data, generate output, check format tags.

```python
# Random sample from training data
indices = sorted(random.sample(range(total), num))

# Generate and check format
generated_text = ...  # model output
print(f"  '<end_working_out>' appears: {generated_text.count('<end_working_out>')}")
print(f"  '<SOLUTION>' appears: {generated_text.count('<SOLUTION>')}")
```

**CLI:** `python src/test_*.py [NUM_SAMPLES]` (default 3)

## Fixtures and Factories

**Test Data:** Inline dictionary literals (no fixtures directory, no factory functions).

```python
mock_results = [
    {
        "queue_vehicles": 10,
        "total_delay": 100.0,
        "passed_vehicles": 60,
        "samples": [0] * 120,
    },
]
```

**Location:** All test data defined inline within test methods or at module level.

## Coverage

**Requirements:** None enforced. No coverage configuration detected.
**Coverage tool:** Not configured (no `pytest-cov` or `.coveragerc`).

**Current state:**
- `benchmark/metrics.py` has thorough unit tests (20+ test cases)
- `benchmark/output.py` and `benchmark/report.py` have integration tests
- `src/grpo/rewards.py` has manual test script (not pytest)
- Most of `src/` has **no automated tests** - only manual inference scripts

## Test Types

**Unit Tests:**
- Scope: Pure functions in `benchmark/metrics.py`
- Approach: Class-based grouping, inline mock data, tolerance-based assertions
- File: `benchmark/tests/test_weighted_stats.py`

**Integration Tests:**
- Scope: End-to-end file I/O in `TestEndToEndIntegration`
- Approach: `tempfile.TemporaryDirectory()` for isolated file operations
- File: `benchmark/tests/test_weighted_stats.py` (last 2 test classes)

**Manual Smoke Tests:**
- Scope: Model inference, SUMO simulation, API connectivity
- Approach: Standalone scripts with `if __name__ == "__main__"` entry
- Files: `src/sft/test_inference.py`, `src/test_gguf.py`, `src/test_lmstudio.py`, `src/grpo/test_rewards.py`

**E2E Tests:**
- Not implemented as automated tests
- `benchmark/run_benchmark.py` serves as manual end-to-end validation

## Common Patterns

**Float Comparison:**
```python
assert abs(result - expected) < 0.001
```

**Edge Case Testing:**
```python
def test_weighted_average_empty(self) -> None:
    """Empty input should return 0."""
    result = calculate_weighted_average([], [])
    assert result == 0.0

def test_weighted_average_all_zero_weights(self) -> None:
    """All zero weights should return 0."""
    result = calculate_weighted_average([10.0, 20.0], [0.0, 0.0])
    assert result == 0.0
```

**Temporary File Testing:**
```python
import tempfile
with tempfile.TemporaryDirectory() as tmpdir:
    run_output = create_run_dir(tmpdir, "test-model", "2026-02-18_12-00-00")
    csv_path = write_summary_csv_extended(run_output=run_output, ...)
    assert csv_path.exists()
    with open(csv_path, "r") as f:
        content = f.read()
        assert "throughput" in content
```

**File Content Verification (non-import approach):**
```python
def test_report_columns_constant(self) -> None:
    """Test that COMPARISON_COLUMNS in report.py includes throughput."""
    report_path = __file__.replace("tests/test_weighted_stats.py", "report.py")
    with open(report_path, "r") as f:
        content = f.read()
    assert '"throughput"' in content
```

## Where to Add New Tests

**New pytest unit tests:**
- Add to `benchmark/tests/test_{module_name}.py`
- Follow class-based grouping pattern: `class Test{Feature}:`
- Import from `TSC_CYCLE.benchmark.{module}`

**New standalone test scripts:**
- Add to `src/{subpackage}/test_{feature}.py`
- Use `if __name__ == "__main__": main()` pattern
- Accept `--config` argument for config path

**Test gaps (no automated tests):**
- `src/phase_processor/` - parser, validator, conflict resolver
- `src/data_generator/` - noise functions, cycle detector, day simulator
- `benchmark/simulation.py` - SUMO simulation control
- `benchmark/llm_client.py` - API client (needs mocking)
- `benchmark/timing_parser.py` - LLM output parsing

---

*Testing analysis: 2026-03-25*
