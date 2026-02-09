# Coding Conventions

**Analysis Date:** 2026-02-09

## Naming Patterns

**Files:**
- Snake case is used for Python source files.
- Examples: `cycle_detector.py`, `logging_config.py`, `process_phases.py`.

**Functions:**
- Snake case is used for function names.
- Examples: `setup_logging`, `filter_invalid_phases`, `validate_traffic_light`.

**Variables:**
- Snake case is used for variables and parameters.
- Examples: `log_file`, `current_phase`, `sim_time`.

**Types:**
- PascalCase is used for class names.
- Examples: `CycleDetector`, `PhaseInfo`, `TLInfo`.

## Code Style

**Formatting:**
- Standard Python (PEP 8) style is followed.
- Use of docstrings for classes and functions is consistent.
- `dataclasses` are used for data-only structures in `src/phase_processor/models.py`.

**Linting:**
- Not explicitly detected (no `.flake8` or `pyproject.toml` found in root), but code follows consistent PEP 8 style.

## Import Organization

**Order:**
1. Standard library imports (e.g., `import logging`, `import sys`).
2. Third-party library imports (e.g., `import traci`, `import argparse`).
3. Local application imports (e.g., `from .models import PhaseInfo`).

**Path Aliases:**
- Not detected. Absolute or relative package imports are used.

## Error Handling

**Patterns:**
- Try-except blocks are used for optional dependencies (e.g., `traci` in `cycle_detector.py`).
- Logging is used extensively to report errors and warnings instead of just raising exceptions.
- Custom logic for handling missing configuration (e.g., defaulting `first_green_phase` to 0).

## Logging

**Framework:**
- Standard Python `logging` module.
- Centralized configuration in `src/utils/logging_config.py`.

**Patterns:**
- Loggers are typically named after the module or a specific component (e.g., `"phase_processor"`).
- Both console and file handlers are configured.
- Log levels (INFO, DEBUG, WARNING, ERROR) are used appropriately.

## Comments

**When to Comment:**
- Module-level docstrings provide an overview of functionality.
- Function and class docstrings follow a structured format (Args, Returns, Examples).
- Inline comments explain complex logic, such as phase detection logic in `CycleDetector`.

**JSDoc/TSDoc:**
- Not applicable (Python project). Standard Python docstrings are used.

## Function Design

**Size:**
- Functions are generally small and focused on a single responsibility.
- Example: `filter_invalid_phases` in `src/phase_processor/validator.py`.

**Parameters:**
- Typed parameters are used (Type Hints).
- Optional parameters with default values (e.g., `logger: Optional[Logger] = None`).

**Return Values:**
- Explicit return types are specified.
- Boolean returns for validation functions.

## Module Design

**Exports:**
- Modules use `__init__.py` to organize exports (though many were found empty or standard).
- Specific functions and classes are imported where needed.

**Barrel Files:**
- `src/phase_processor/__init__.py` and others exist but their content was not fully audited.

---

*Convention analysis: 2026-02-09*
