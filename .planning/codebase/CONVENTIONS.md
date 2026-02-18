# Coding Conventions

**Analysis Date:** 2026-02-18

## Naming Patterns

**Files:**
- Python modules use `snake_case`: `prompt_builder.py`, `traffic_collector.py`, `train.py`
- Test files use `test_*.py` prefix: `test_rewards.py`, `test_inference.py`
- Scripts in `src/scripts/` use `snake_case`: `generate_sft_data.py`, `filter_grpo_data.py`

**Functions:**
- Use `snake_case`: `load_config()`, `setup_model()`, `calculate_solution()`
- Private helpers prefix with `_`: `_run_sumo_evaluation()`, `_get_controlled_lanes()`, `_ensure_sumo_home()`
- Factory/creation functions use `create_` or `setup_`: `setup_logging()`, `create_run_dir()`

**Variables:**
- Use `snake_case`: `phase_waits`, `pred_saturation`, `max_seq_length`
- Constants use UPPER_SNAKE_CASE at module level: `SYSTEM_PROMPT`, `TASK_TEMPLATE`
- Private module state prefix with `_`: `_config`, `_baseline`, `_sumo_pool`, `_print_counter`

**Types/Classes:**
- Use `PascalCase`: `PhaseWait`, `Prediction`, `TrainingSample`, `PromptBuilder`, `BenchmarkConfig`
- Dataclasses preferred for data structures
- Type hints required for public functions

## Code Style

**Formatting:**
- No explicit formatter detected (no `.prettierrc`, `.eslintrc`, `ruff.toml`, or `pyproject.toml`)
- Indentation: 4 spaces
- Max line length: ~100-120 characters (observed in source files)

**Linting:**
- No explicit linter configuration detected
- Code follows PEP 8 conventions naturally

**File Headers:**
- Python files use shebang and encoding declaration:
```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Module docstring here.

Detailed explanation of functionality.
"""
```

## Import Organization

**Order:**
1. `from __future__ import annotations` (if using modern type hints)
2. Standard library (alphabetical)
3. Third-party libraries
4. Local imports from `src/` or `TSC_CYCLE.`

**Pattern (from `benchmark/simulation.py`):**
```python
from __future__ import annotations

import math
import os
import socket
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from shutil import which
from typing import Any, TYPE_CHECKING

import traci
from loguru import logger

from TSC_CYCLE.benchmark.config import BenchmarkConfig
from TSC_CYCLE.benchmark.metrics import TrafficMetricsCollector, CycleTrafficMetrics

if TYPE_CHECKING:
    from TSC_CYCLE.benchmark.timing_parser import TimingPlan
```

**Path Aliases:**
- `src.` prefix for source imports: `from src.data_generator.models import Prediction`
- `TSC_CYCLE.` prefix for benchmark imports: `from TSC_CYCLE.benchmark.config import BenchmarkConfig`

**sys.path manipulation** (for scripts needing module access):
```python
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
```

## Error Handling

**Patterns:**
- Use assertions for internal invariants:
```python
assert pw['phase_id'] == sol['phase_id'], f"Phase ID mismatch"
assert pw['min_green'] <= sol['final'] <= pw['max_green'], f"Constraint violation"
```

- Raise descriptive exceptions with context:
```python
raise RuntimeError(
    f"SFT model not found: {model_path}\n"
    f"GRPO training requires SFT training first. Run ./docker/sft_train.sh"
)
```

- Try/except with specific exception types and fallback values:
```python
try:
    plan = json.loads(match.group(1))
except:
    scores.append(-2.0)
    continue
```

- LLM API error handling with retry logic:
```python
except openai.APITimeoutError as e:
    last_error = f"API timeout after {self.timeout_seconds}s: {str(e)}"
    logger.warning("LLM API timeout (attempt {}/{}): {}", attempt + 1, self.max_retries + 1, str(e))
```

- Configuration validation:
```python
required_weights = ["sumo_throughput_weight", "sumo_queue_weight", "sumo_delay_weight"]
missing = [w for w in required_weights if _config.get(w) is None]
if missing:
    raise ValueError(f"Missing required weights in config: {missing}")
```

## Logging

**Frameworks:**
1. Standard `logging` module in `src/utils/logging_config.py`
2. `loguru` for benchmark code (preferred for new code)

**Standard Logging Pattern:**
```python
from src.utils.logging_config import setup_logging
logger = setup_logging(log_file="phase_processing.log", level=logging.INFO)
logger.info("[数据加载] 原始样本数: %d, 过滤后: %d", original_count, filtered_count)
```

**Loguru Pattern (benchmark):**
```python
from loguru import logger

# Setup
logger.remove()
logger.add(sys.stdout, format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}", level=log_level)

# Usage
logger.info("Created output directory: {}", run_output.run_dir)
logger.warning("Error collecting phase data for {}: {}", tl_id, e)
logger.error("Benchmark failed: {}", e)
```

**Console Output (training scripts):**
- Use `print()` with Chinese labels for training progress:
```python
print(f"[配置] 加载配置文件: {args.config}")
print(f"[模型] SFT 模型已存在: {model_path}")
print("[开始训练] GRPO 训练...")
```

## Comments

**When to Comment:**
- Module-level docstrings explaining purpose and structure
- Function docstrings with Args, Returns, and Examples
- Inline comments for non-obvious logic

**Docstring Format (Google style with Chinese):**
```python
def format_timestamp(sim_time: float, base_date: str = "2026-01-01") -> str:
    """
    将仿真时间转换为时间戳字符串。

    Args:
        sim_time: 仿真时间 (从 0 开始的秒数)
        base_date: 仿真的基准日期 (格式: YYYY-MM-DD)

    Returns:
        时间戳字符串,格式: "YYYY-MM-DD HH:MM:SS"

    Example:
        >>> format_timestamp(3600.0, '2026-01-15')
        '2026-01-15 01:00:00'
    """
```

## Function Design

**Size:** Functions typically 20-50 lines; complex functions broken into helpers

**Parameters:**
- Use type hints for all parameters
- Group related parameters into dataclasses when >3-4 params
- Use default values for optional parameters
- Use `**kwargs` for TRL-compatible reward functions

**Return Values:**
- Return tuples for multiple values: `Tuple[Dataset, int]`
- Return `Optional[T]` for potentially missing values
- Use dataclasses for structured return types:
```python
@dataclass
class LLMResponse:
    content: str
    response_time: float
    success: bool
    error: Optional[str] = None
```

## Module Design

**Exports:** Use `__init__.py` to expose public interface:
```python
# src/data_generator/__init__.py
from .models import TrainingSample, Prediction, PhaseWait
from .cycle_detector import CycleDetector
from .prompt_builder import PromptBuilder
```

**Barrel Files:** Each subpackage has `__init__.py` that exports key classes

**Entry Points:**
- Training scripts: `src/sft/train.py`, `src/grpo/train.py`
- Benchmark: `benchmark/run_benchmark.py`
- Use `if __name__ == "__main__": main()` pattern
- Shell scripts in `docker/` wrap Python entry points

## Configuration

**Config File Pattern:**
- Single JSON config at `config/config.json`
- Nested structure by component: `training.sft`, `training.grpo`, `simulation`, `paths`
- Load with dedicated function:
```python
def load_config(config_path: str) -> dict:
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    return config
```

**Dataclass Configuration:**
```python
@dataclass
class BenchmarkConfig:
    cycle_duration: int = 60
    warmup_seconds: int = 300

    def validate(self) -> None:
        if self.cycle_duration <= 0:
            raise ValueError(f"cycle_duration must be positive")
```

## GRPO Reward Functions

**Interface (following TRL GRPOTrainer):**
```python
# All reward functions accept these signatures:
def reward_func(completions, **kwargs) -> List[float]:
    pass

def reward_func(prompts, completions, **kwargs) -> List[float]:
    pass
```

**Initialization Pattern:**
```python
# Module-level state (initialized once before training)
_config = None
_baseline = None
_sumo_pool = None

def init_rewards(config_path: str, baseline_path: str):
    """Initialize reward functions with config and baseline data."""
    global _config, _baseline
    # Load configuration...
```

---

*Convention analysis: 2026-02-18*
