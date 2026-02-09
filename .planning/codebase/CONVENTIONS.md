# Coding Conventions

**Analysis Date:** 2026-02-09

## Naming Patterns

**Files:**
- Snake case (`snake_case.py`): e.g., `src/sft/model_loader.py`, `src/data_generator/day_simulator.py`.
- Scripts follow the same pattern: `src/scripts/train_sft.py`.

**Functions:**
- Snake case: e.g., `setup_logging()`, `prepare_dataset()`, `validate_model_output()`.

**Variables:**
- Snake case for local variables and arguments: `output_dir`, `train_dataset`, `is_valid`.
- UPPER_SNAKE_CASE for constants: `SYSTEM_PROMPT` in `src/sft/chat_template.py`, `THINK_PATTERN` in `src/sft/format_validator.py`.

**Types:**
- PascalCase for classes and Dataclasses: `TrainingArgs`, `SFTTrainerWrapper` in `src/sft/trainer.py`, `PhaseWait`, `TrainingSample` in `src/data_generator/models.py`.

## Code Style

**Formatting:**
- PEP 8 compliant style observed.
- Indentation: 4 spaces.
- Line length: Generally kept within 80-120 characters.

**Linting:**
- Not explicitly configured via config files like `.flake8` or `ruff.toml` in the root, but the code shows consistent quality.

## Import Organization

**Order:**
1. Standard library imports: `import os`, `import sys`, `import json`.
2. Third-party imports: `import torch`, `from datasets import Dataset`, `from trl import SFTTrainer`.
3. Local/Internal imports: `from .format_validator import validate_format`.

**Path Aliases:**
- Use of `sys.path.insert(0, str(project_root))` in data generation scripts to handle absolute imports from the project root.

## Error Handling

**Patterns:**
- Try-except blocks for risky operations (JSON parsing, SUMO simulation): e.g., `src/sft/format_validator.py` uses `try...except json.JSONDecodeError`.
- Meaningful error messages in `raise` statements: e.g., `raise ValueError(f"Data format error: missing 'messages' field...")`.
- Validation functions return tuples `(is_valid, errors_list)` for complex validation logic.

## Logging

**Framework:** `logging` (Python standard library).

**Patterns:**
- Centralized setup in `src/utils/logging_config.py`.
- Per-script logging configuration in `src/scripts/train_sft.py` using `logging.StreamHandler` and `logging.FileHandler`.
- Log format: `%(asctime)s - %(name)s - %(levelname)s - %(message)s`.

## Comments

**When to Comment:**
- Module-level docstrings describing the purpose of the file.
- Complex logic explanations (e.g., SUMO environment setup in `src/data_generator/day_simulator.py`).
- Step-by-step comments in main execution blocks.

**JSDoc/TSDoc:**
- Google-style or ReST-style docstrings for functions:
  ```python
  """Description.

  Args:
      name: Type - Description

  Returns:
      Type - Description
  """
  ```

## Function Design

**Size:** Functions are modular and focused on a single responsibility (e.g., `extract_think_content`, `validate_json_structure`).

**Parameters:** Use of type hints for clarity: `def validate_format(output_text: str) -> tuple[bool, list[str]]:`.

**Return Values:** Consistent use of return types, including tuples for multi-value returns.

## Module Design

**Exports:** Classes and functions intended for use are defined at the top level.

**Barrel Files:** `__init__.py` files are present in most directories to treat them as packages.

---

*Convention analysis: 2026-02-09*
