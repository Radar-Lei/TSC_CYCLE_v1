# Coding Conventions

**Analysis Date:** 2026-02-09

## Naming Patterns

**Files:**
- Snake case: `rou_month_generator.py`, `cycle_detector.py`, `format_validator.py`.

**Functions:**
- Snake case: `extract_think_content`, `validate_format`, `setup_logging`.
- Private functions use leading underscore: `_local_tag`, `_parse_float`.

**Variables:**
- Snake case: `output_text`, `think_content`, `json_match`.

**Types:**
- Pascal Case for Classes: `TemplateVehicle`.
- Extensive use of Type Hints: `Optional[str]`, `list[str]`, `tuple[bool, list[str]]`.

## Code Style

**Formatting:**
- Follows PEP 8 standards. No explicit configuration file (like `.flake8` or `pyproject.toml` with black/ruff settings) was found, but the code is consistently formatted.

**Linting:**
- Not explicitly configured via config files in the root.

## Import Organization

**Order:**
1. Standard Library: `import re`, `import json`, `import argparse`.
2. Third-party Library: (None detected in sampled files, but expected if using PyTorch/Transformers).
3. Local Modules: `from src.utils.logging_config import setup_logging`.

**Path Aliases:**
- None detected. Relative and absolute imports from `src` are used.

## Error Handling

**Patterns:**
- Uses `try...except` blocks for parsing and validation: `try: return json.loads(match.group(0)) except json.JSONDecodeError: return None`.
- Explicitly raises `ValueError` for invalid input data or structure: `raise ValueError(f"profile 必须是长度为 24 的数组：{profile_path}")`.

## Logging

**Framework:**
- Standard Python `logging` module.

**Patterns:**
- Centralized configuration in `src/utils/logging_config.py`.
- Custom `setup_logging` function provides both `StreamHandler` (console) and `FileHandler` (default: `phase_processing.log`).
- Logs include timestamp, logger name, level, and message.

## Comments

**When to Comment:**
- Comments are used to describe complex regex patterns or specific logic steps.
- Chinese is used for descriptive comments.

**JSDoc/TSDoc:**
- Uses Google-style docstrings (in Chinese) for function descriptions, arguments, and return values.

## Function Design

**Size:**
- Functions are generally small and focused (e.g., `extract_json_array`, `_parse_float`).

**Parameters:**
- Uses descriptive parameter names with type hints.

**Return Values:**
- Uses type hints for return values, including tuples for multi-value returns: `tuple[bool, list[str]]`.

## Module Design

**Exports:**
- Standard Python modules using `__init__.py` for package structure.

**Barrel Files:**
- `__init__.py` files are present in `src/data_generator/`, `src/sft/`, and `src/utils/`.

---

*Convention analysis: 2026-02-09*
