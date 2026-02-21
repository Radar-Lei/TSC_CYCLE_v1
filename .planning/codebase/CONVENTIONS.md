# Coding Conventions

**Analysis Date:** 2026-02-21

## Naming Patterns

**Files:**
- `snake_case.py` (e.g., `processor.py`, `logging_config.py`, `test_weighted_stats.py`)

**Functions:**
- `snake_case` (e.g., `process_traffic_lights`, `setup_logging`, `calculate_weighted_average`)

**Variables:**
- `snake_case` for local variables.
- Prefix with `_` for private class members (e.g., `self._conn`, `self._tl_id` in `TrafficMetricsCollector`).

**Types:**
- `PascalCase` for classes and dataclasses (e.g., `PhaseInfo`, `ProcessingResult`, `WeightedMetricsSummary`).

## Code Style

**Formatting:**
- Standard PEP8 compliant style (observed 4-space indentation, consistent spacing).

**Linting:**
- Type hinting is strictly applied to function signatures (e.g., `net_file: str`, `logger: Optional[Logger] = None`).
- Use of `dataclass` for structured data models.

## Import Organization

**Order:**
1. Standard library imports (e.g., `import json`, `import sys`).
2. Third-party library imports (e.g., `import traci`, `import pytest`).
3. Local project imports (e.g., `from .models import PhaseInfo`, `from TSC_CYCLE.benchmark.metrics import ...`).

**Path Aliases:**
- The project root is added to `sys.path` in `conftest.py` to allow top-level imports: `from TSC_CYCLE.benchmark.metrics import ...`.

## Error Handling

**Patterns:**
- Graceful degradation in sampling loops: `try...except Exception: pass` is used when calls to external systems (like SUMO/TraCI) might fail during simulation steps (see `benchmark/metrics.py`).
- Logger-based error reporting in core logic (see `src/phase_processor/processor.py`).

## Logging

**Framework:**
- Python standard `logging` library.

**Patterns:**
- Centralized configuration in `src/utils/logging_config.py`.
- Dedicated logger names per module (e.g., `logging.getLogger("phase_processor")`).
- Dual output to both `sys.stdout` (Console) and file (`phase_processing.log`).

## Comments

**When to Comment:**
- Use docstrings for all classes and functions.
- Inline comments explain complex logic or formulas (e.g., weighted average calculation in `benchmark/metrics.py`).

**JSDoc/TSDoc:**
- Google/Numpy style docstrings.
- Multilingual: Chinese docstrings in `src/phase_processor` and English in `benchmark`.

## Function Design

**Size:**
- Small, focused functions typically under 50-100 lines. Larger processing pipelines are split into separate modules (validator, parser, conflict resolver).

**Parameters:**
- Explicit type hinting.
- Use of `Optional` for nullable parameters like loggers.

**Return Values:**
- Use of `dataclass` or `TypedDict` for returning multiple values (e.g., `ProcessingResult` in `processor.py`).

## Module Design

**Exports:**
- Standard Python module structure with `__init__.py`.
- Public functions intended for use across modules are clearly defined in their respective `.py` files.

**Barrel Files:**
- `src/phase_processor/__init__.py` and other `__init__.py` files are present but primary logic remains in specific modules.

---

*Convention analysis: 2026-02-21*
