# Coding Conventions

**Analysis Date:** 2026-02-09

## Naming Patterns

**Files:**
- snake_case: `rou_month_generator.py`, `phase_processor/models.py`, `utils/logging_config.py`

**Functions:**
- snake_case: `process_traffic_lights()`, `setup_logging()`, `calculate_queue_change_rate()`

**Variables:**
- snake_case: `net_file`, `logger`, `current_queue_state`

**Types:**
- PascalCase (Classes/Dataclasses): `PhaseInfo`, `TLInfo`, `SUMOSimulator`, `AdaptiveSampler`, `TrainingSample`

## Code Style

**Formatting:**
- PEP 8 compliant: 4-space indentation, consistent spacing around operators.
- Line length: Generally follows 80-120 character limits.

**Linting:**
- No explicit configuration file (like `.eslintrc` or `pyproject.toml`) detected.
- Type hints are used extensively across the codebase for parameters and return values.

## Import Organization

**Order:**
1. Standard library imports (e.g., `os`, `sys`, `json`, `xml.etree.ElementTree`)
2. Third-party library imports (e.g., `traci`, `random`)
3. Local module imports (e.g., `from .models import PhaseInfo`)

**Path Aliases:**
- No path aliases (like `@/`) detected. Uses relative imports within packages (e.g., `from .models import ...`) and absolute-style imports from `src`.

## Error Handling

**Patterns:**
- Extensive use of `try...except` blocks, particularly around `traci` (SUMO interface) and file I/O operations.
- Validation functions return booleans or filtered lists rather than raising exceptions in many cases (e.g., `src/phase_processor/validator.py`).
- Logging of errors with stack traces in CLI entry points.

## Logging

**Framework:** `logging` (Python standard library)

**Patterns:**
- Centralized configuration in `src/utils/logging_config.py`.
- Logs to both console and file (`phase_processing.log`).
- Usage of named loggers (e.g., `logger = logging.getLogger("phase_processor")`).

## Comments

**When to Comment:**
- High-level module descriptions at the top of files.
- Complex logic explanations (e.g., conflict resolution greedy algorithm in `src/phase_processor/conflict.py`).
- Parameter and return value documentation for most functions.

**JSDoc/TSDoc:**
- Uses Python-style docstrings (triple quotes) with sections for `Args` and `Returns`.
- Language: Primarily **Simplified Chinese** for descriptions.

## Function Design

**Size:** Functions are generally small and focused on a single responsibility. Large processes are broken down into steps (e.g., `process_traffic_lights` in `processor.py`).

**Parameters:** Uses type hinting. Optional parameters often default to `None`.

**Return Values:** Consistent use of `Optional` and `List`/`Dict` type hints. Use of `@dataclass` for complex return structures (e.g., `ProcessingResult`).

## Module Design

**Exports:** Relies on standard Python module exports. `__init__.py` files are present in most directories to define packages.

**Barrel Files:** `__init__.py` files are mostly empty, but some scripts explicitly add `src` to `sys.path` to enable cross-package imports.

---

*Convention analysis: 2026-02-09*
