"""
Batch test configuration module for LLM Traffic Signal Cycle Benchmark.

Provides BatchConfig, ModelConfig dataclasses and configuration loading for multi-model batch testing.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
from typing import Any


@dataclass
class ModelConfig:
    """Configuration for a single model in batch testing.

    Attributes:
        name: Model name/identifier
        structured_output: Whether to use structured output (JSON Schema) for this model.
                          Defaults to True for non-custom models.
    """
    name: str
    structured_output: bool = True  # Default to True for non-custom models

    def validate(self) -> None:
        """Validate model configuration.

        Raises:
            ValueError: If model name is empty
        """
        if not self.name or not self.name.strip():
            raise ValueError("model name must be a non-empty string")


@dataclass
class BatchConfig:
    """Configuration for batch benchmark runs.

    Note: Simulation parameters (cycle_duration, warmup_seconds, simulation_seconds)
    are loaded from the main benchmark config (config.py), not duplicated here.
    BatchConfig only specifies which models to test and LLM API endpoint.

    Attributes:
        models: List of ModelConfig objects specifying models and their settings
        scenario: Optional scenario name (if None, uses default from benchmark config)
        llm_api_base_url: Base URL for LLM API
        benchmark_config_path: Optional path to benchmark config (default: benchmark/config.json)
        cycle_plan_schema: Optional JSON Schema for structured output
    """
    models: list[ModelConfig]
    scenario: str | None
    llm_api_base_url: str
    benchmark_config_path: str | None = None
    cycle_plan_schema: dict[str, Any] | None = None

    @property
    def model_names(self) -> list[str]:
        """Get list of model names for backward compatibility."""
        return [m.name for m in self.models]

    def validate(self) -> None:
        """Validate configuration constraints.

        Raises:
            ValueError: If any configuration constraint is violated
        """
        if not self.models:
            raise ValueError("models list must not be empty")

        for model in self.models:
            model.validate()

        if not self.llm_api_base_url:
            raise ValueError("llm_api_base_url must not be empty")


def load_batch_config(path: str | Path) -> BatchConfig:
    """Load batch test configuration from a JSON file.

    Supports both old format (list of strings) and new format (list of objects).

    Old format (backward compatible):
        {"models": ["model1", "model2"], ...}

    New format:
        {"models": [{"name": "model1", "structured_output": true}, ...], ...}

    Args:
        path: Path to the JSON configuration file

    Returns:
        BatchConfig instance with loaded values

    Raises:
        FileNotFoundError: If config file does not exist

    The JSON file should have the following structure (new format):
        {
            "models": [
                {"name": "qwen3-4b", "structured_output": true},
                {"name": "deepsignal_cycleplan@f16", "structured_output": false}
            ],
            "scenario": null,
            "llm_api_base_url": "http://localhost:1234/v1",
            "benchmark_config_path": null,
            "cycle_plan_schema": {...}
        }

    Simulation parameters (cycle_duration, warmup_seconds, simulation_seconds)
    are loaded from the benchmark config, not duplicated here.
    """
    config_path = Path(path)

    if not config_path.exists():
        raise FileNotFoundError(f"Batch config file not found: {path}")

    with open(config_path, "r", encoding="utf-8") as f:
        data: dict[str, Any] = json.load(f)

    # Parse models with backward compatibility
    models_raw = data.get("models", [])
    models: list[ModelConfig] = []

    for m in models_raw:
        if isinstance(m, str):
            # Old format: string -> default structured_output=True
            models.append(ModelConfig(name=m, structured_output=True))
        elif isinstance(m, dict):
            # New format: object
            models.append(ModelConfig(
                name=m.get("name", ""),
                structured_output=m.get("structured_output", True)
            ))
        else:
            raise ValueError(f"Invalid model config format: {m}")

    config = BatchConfig(
        models=models,
        scenario=data.get("scenario"),
        llm_api_base_url=data.get("llm_api_base_url", "http://localhost:1234/v1"),
        benchmark_config_path=data.get("benchmark_config_path"),
        cycle_plan_schema=data.get("cycle_plan_schema"),
    )

    config.validate()
    return config
