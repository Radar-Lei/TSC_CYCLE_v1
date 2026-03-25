# Coding Conventions

**Analysis Date:** 2026-03-25

## Language

**Primary:** Python 3.10+ (uses `X | Y` union syntax, `list[str]` built-in generics)

## Naming Patterns

**Files:**
- Use `snake_case.py` for all modules: `prompt_builder.py`, `traffic_collector.py`, `logging_config.py`
- Test files prefixed with `test_`: `test_weighted_stats.py`, `test_rewards.py`, `test_gguf.py`
- `__init__.py` in every package, typically minimal (docstring + `__all__`)

**Functions:**
- `snake_case` throughout: `calculate_weighted_average()`, `match_format_exactly()`, `load_config()`
- Private methods prefixed with underscore: `_get_controlled_lanes()`, `_call_regular()`, `_run_sumo_evaluation()`
- Entry-point functions named `main()` with `if __name__ == "__main__": main()` guard

**Classes:**
- `PascalCase`: `PhaseWait`, `PromptBuilder`, `TrafficMetricsCollector`, `BenchmarkSimulation`
- Dataclasses used extensively for data containers: `CycleTrafficMetrics`, `LLMResponse`, `BenchmarkConfig`
- Naming pattern: `{Domain}{Noun}` for data, `{Domain}{Verb}er` for actors (e.g., `TrafficMetricsCollector`)

**Variables:**
- `snake_case`: `total_delay`, `phase_waits`, `controlled_lanes`
- Module-level private state prefixed with underscore: `_config`, `_baseline`, `_sumo_pool`
- Constants as `UPPER_SNAKE_CASE`: `SYSTEM_PROMPT`, `TASK_TEMPLATE`, `COMPARISON_COLUMNS`

**Type Hints:**
- Used consistently on function signatures: `def calculate_weighted_average(values: List[float], weights: List[float]) -> float:`
- Mix of `typing.List`/`typing.Dict` (older code in `src/`) and built-in `list`/`dict` (newer code in `benchmark/`)
- `from __future__ import annotations` used in `benchmark/` modules for forward references

## Code Style

**No Linter/Formatter Configured:**
- No `.flake8`, `ruff.toml`, `pyproject.toml`, `.prettierrc`, or similar config files detected
- Code style is manually maintained, generally consistent

**Indentation:**
- 4 spaces (standard Python)

**String Quotes:**
- Double quotes `"` for strings throughout (consistent)
- f-strings used for interpolation: `f"[模型] 本地模型已存在: {model_path}"`

**Line Length:**
- No enforced limit; lines occasionally exceed 100 chars in docstrings and long expressions
- Long function calls broken across lines with trailing comma style

**Docstrings:**
- Google-style docstrings with `Args:`, `Returns:`, `Raises:`, `Attributes:`, `Example:` sections
- Module-level docstrings on every file describing purpose
- Chinese used in docstrings for `src/` modules; English used in `benchmark/` modules
- Class docstrings document `Attributes:` for dataclasses

**Example from `benchmark/metrics.py`:**
```python
def calculate_weighted_average(values: List[float], weights: List[float]) -> float:
    """Calculate weighted average, skipping zero weights.

    Formula: weighted_avg = sum(value_i * weight_i) / sum(weight_i)
    Zero weights are skipped in the calculation.

    Args:
        values: List of values to average
        weights: List of weights (same length as values)

    Returns:
        Weighted average, or 0.0 if all weights are zero or empty input
    """
```

## Bilingual Codebase

**English used in:**
- `benchmark/` module: all docstrings, comments, variable names, class names
- Log messages via `loguru` in benchmark: `logger.info("Starting SUMO simulation: {}", ...)`

**Chinese used in:**
- `src/` module: docstrings, inline comments, `print()` status messages
- Console output: `print(f"[模型] 加载 SFT 模型 (基础模型 + LoRA adapter)")`
- Status prefix pattern: `[模型]`, `[数据]`, `[训练]`, `[保存]`, `[配置]`

**Prescription:** Follow the existing language convention per module. Use English for `benchmark/`, Chinese for `src/`.

## Import Organization

**Order observed across codebase:**
1. Standard library (`import json`, `import os`, `import sys`, `from pathlib import Path`)
2. Third-party packages (`import torch`, `from datasets import Dataset`, `import openai`)
3. Local project imports (`from src.grpo.rewards import ...`, `from .models import PhaseInfo`)

**No import sorting tool** configured. Imports are manually organized.

**Path Aliases:**
- No path aliases or `importlib` tricks
- `conftest.py` adds parent directory to `sys.path` for test imports
- Some scripts use `sys.path.insert(0, ...)` for ad-hoc path resolution (e.g., `src/grpo/test_rewards.py`)

**Import style:**
- Prefer `from module import specific_name` over `import module`
- `TYPE_CHECKING` guard used in `benchmark/` for heavy imports: `if TYPE_CHECKING: import traci`

## Data Modeling

**Dataclasses are the primary data modeling tool:**
```python
from dataclasses import dataclass, field

@dataclass
class PhaseWait:
    phase_id: int
    pred_saturation: float
    min_green: int
    max_green: int
    capacity: int = 30

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PhaseWait':
        return cls(**data)
```

**Conventions for dataclasses:**
- Always define `to_dict()` for JSON serialization
- Define `from_dict()` classmethod for deserialization
- Use `field(default_factory=...)` for mutable defaults
- Document attributes in class docstring `Attributes:` section

## Configuration Pattern

**Central JSON config:** `config/config.json`
- Nested structure: `training.sft`, `training.grpo`, `simulation`, `paths`
- All scripts accept `--config` CLI argument defaulting to `config/config.json`
- Config loaded with `json.load()`, no schema validation in `src/` (but validated in `benchmark/config.py`)

**Example pattern:**
```python
def load_config(config_path: str) -> dict:
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    return config
```

## Error Handling

**Pattern 1 - Bare except (in SUMO interaction code):**
```python
try:
    queue_count += self._conn.lane.getLastStepHaltingNumber(lane)
except Exception:
    pass
```
Used in `benchmark/metrics.py`, `benchmark/simulation.py` for resilience against TraCI errors.

**Pattern 2 - Explicit error types (in API client code):**
```python
except openai.APITimeoutError as e:
    last_error = f"API timeout after {self.timeout_seconds}s: {str(e)}"
except openai.APIConnectionError as e:
    last_error = f"API connection error: {str(e)}"
```
Used in `benchmark/llm_client.py` with exponential backoff retry.

**Pattern 3 - Fail-fast with RuntimeError:**
```python
if not os.path.isdir(model_path):
    raise RuntimeError(f"SFT 模型不存在: {model_path}")
```
Used in training scripts for precondition checks.

**Prescription:**
- Use bare `except Exception: pass` only for SUMO/TraCI calls where individual lane errors are non-fatal
- Use typed exceptions for API calls with retry logic
- Use `RuntimeError` or `ValueError` for precondition failures with descriptive messages

## Logging

**Two logging systems in use:**

1. **`loguru`** in `benchmark/` module:
   - Setup: `benchmark/logger.py` using `setup_logging(level, log_file)`
   - Usage: `from loguru import logger; logger.info("message {}", var)`
   - Format: `{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}`

2. **`logging` (stdlib)** in `src/utils/logging_config.py`:
   - Setup: `setup_logging(log_file, level)` returning named logger
   - Usage: `logger.info(f"message {var}")`

3. **`print()`** in training scripts (`src/sft/`, `src/grpo/`, `src/scripts/`):
   - Pattern: `print(f"[TAG] message")` with Chinese tags
   - Tags: `[模型]`, `[数据]`, `[训练]`, `[保存]`, `[配置]`, `[完成]`

**Prescription:** Use `loguru` for new `benchmark/` code. Use `print("[TAG] ...")` for training/script code.

## Function Design

**Size:** Functions are moderate size (20-80 lines typical). Long functions exist in reward computation (`sumo_simulation_reward` ~220 lines) and simulation control.

**Parameters:** Prefer explicit parameters over `**kwargs`. Training config passed as `dict` from JSON. Dataclasses used for structured parameters.

**Return Values:**
- Use dataclasses for multi-field returns: `CycleTrafficMetrics`, `LLMResponse`, `ProcessingResult`
- Use `list[float]` for reward functions (trl interface)
- Use `Optional[str]` or `X | None` for nullable returns

## Module Design

**Exports:**
- `__init__.py` files are minimal, containing only docstrings and empty `__all__`
- No barrel file pattern; import directly from specific modules

**Script entry points:**
- All runnable scripts use `if __name__ == "__main__": main()` pattern
- CLI via `argparse` with `--config` as standard argument
- Default config path: `"config/config.json"`

---

*Convention analysis: 2026-03-25*
