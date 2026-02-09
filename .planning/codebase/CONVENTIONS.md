# Coding Conventions

**Analysis Date:** 2026-02-09

## Naming Patterns

**Files:**
- Snake case: `cycle_detector.py`, `process_phases.py`

**Functions:**
- Snake case: `process_traffic_lights`, `setup_logging`, `get_nested`

**Variables:**
- Snake case: `tl_id`, `current_phase`, `is_new_cycle`

**Types:**
- CamelCase for classes: `CycleDetector`, `ProcessingResult`, `PhaseInfo`
- Type aliases or hints: `Optional[int]`, `Dict[str, List[PhaseInfo]]`

## Code Style

**Formatting:**
- PEP 8 compliant (implied by indentation and naming)
- Use of 4 spaces for indentation

**Linting:**
- Not explicitly detected in config files, but code follows consistent PEP 8 patterns.

## Import Organization

**Order:**
1. Standard library: `import json`, `import argparse`, `import logging`
2. Third-party libraries: `import traci`, `from pathlib import Path`
3. Local modules: `from .models import PhaseInfo`, `from .parser import parse_net_file`

**Path Aliases:**
- Relative imports within packages: `from .models import ...`

## Error Handling

**Patterns:**
- `try-except` blocks with specific exception catching: `except (KeyError, IndexError, TypeError) as e`
- Fallback values with logging: `logger.warning(...)` then setting a default value
- Availability checks: `try: import traci ... except ImportError: TRACI_AVAILABLE = False`

## Logging

**Framework:** `logging` (Standard library)

**Patterns:**
- Per-module loggers: `logger = logging.getLogger(__name__)`
- Centralized setup in scripts: `setup_logging(output_dir)` configuring both `StreamHandler` and `FileHandler`
- Information levels: `info` for progress, `warning` for missing config or non-critical errors.

## Comments

**When to Comment:**
- Module level docstrings explaining purpose and core logic
- Class and function docstrings using a structured format
- Inline comments for complex logic blocks (e.g., `# 1. 解析网络文件`)

**JSDoc/TSDoc:**
- Python Docstrings (Google/NumPy style variant in Simplified Chinese)
- Sections: `Attributes`, `Args`, `Returns`, `Example`

## Function Design

**Size:**
- Modular and focused. Scripts like `train_sft.py` break logic into `load_config`, `setup_logging`, etc.

**Parameters:**
- Use of type hints for all parameters
- Optional parameters with default values: `logger: Optional[Logger] = None`

**Return Values:**
- Explicit return type hints
- Use of `dataclass` for complex return structures: `ProcessingResult`

## Module Design

**Exports:**
- Controlled via `__init__.py` in packages (`src/data_generator`, `src/phase_processor`)

**Barrel Files:**
- `__init__.py` files used to organize package exports.

---

*Convention analysis: 2026-02-09*
