"""
Benchmark configuration module.

Provides configuration loading and validation for LLM Traffic Signal Cycle Benchmark.
"""

from dataclasses import dataclass, field
from pathlib import Path
import json
from typing import Any


@dataclass
class BenchmarkConfig:
    """Configuration for benchmark runs.

    Attributes:
        cycle_duration: Cycle duration in seconds (default: 60)
        warmup_seconds: Warmup period before benchmarking in seconds (default: 300)
        simulation_seconds: Total simulation duration in seconds (default: 3600)
        step_length: Simulation step length in seconds (default: 1.0)
        environments_dir: Directory containing SUMO environment scenarios
        output_dir: Directory for benchmark results
        log_level: Logging level ('info' or 'debug')
        llm_timeout_seconds: Timeout for LLM API calls in seconds (default: 300)
        llm_api_base_url: Base URL for LLM API (default: LM Studio localhost:1234)
        llm_max_retries: Maximum number of retry attempts for LLM API calls (default: 2)
        llm_retry_base_delay: Base delay in seconds for exponential backoff (default: 1.0)
    """
    cycle_duration: int = 60
    warmup_seconds: int = 300
    simulation_seconds: int = 3600
    step_length: float = 1.0
    environments_dir: str = "sumo_simulation/environments"
    output_dir: str = "benchmark/results"
    log_level: str = "info"
    llm_timeout_seconds: int = 300
    llm_api_base_url: str = "http://localhost:1234/v1"
    llm_max_retries: int = 2
    llm_retry_base_delay: float = 1.0

    def validate(self) -> None:
        """Validate configuration constraints.

        Raises:
            ValueError: If any configuration constraint is violated
        """
        if self.cycle_duration <= 0:
            raise ValueError(f"cycle_duration must be positive, got {self.cycle_duration}")

        if self.warmup_seconds < 0:
            raise ValueError(f"warmup_seconds must be non-negative, got {self.warmup_seconds}")

        if self.simulation_seconds <= self.warmup_seconds:
            raise ValueError(
                f"simulation_seconds ({self.simulation_seconds}) must be greater than "
                f"warmup_seconds ({self.warmup_seconds})"
            )

        if self.step_length <= 0:
            raise ValueError(f"step_length must be positive, got {self.step_length}")

        if self.log_level not in ("info", "debug"):
            raise ValueError(f"log_level must be 'info' or 'debug', got '{self.log_level}'")

        if self.llm_timeout_seconds <= 0:
            raise ValueError(
                f"llm_timeout_seconds must be positive, got {self.llm_timeout_seconds}"
            )

        if not self.llm_api_base_url:
            raise ValueError("llm_api_base_url must not be empty")

        if self.llm_max_retries < 0:
            raise ValueError(
                f"llm_max_retries must be non-negative, got {self.llm_max_retries}"
            )

        if self.llm_retry_base_delay <= 0:
            raise ValueError(
                f"llm_retry_base_delay must be positive, got {self.llm_retry_base_delay}"
            )


def load_config(path: str | Path) -> BenchmarkConfig:
    """Load benchmark configuration from a JSON file.

    Args:
        path: Path to the JSON configuration file

    Returns:
        BenchmarkConfig instance with loaded values, or default config if file not found

    The JSON file should have the following structure:
        {
            "simulation": {
                "cycle_duration": 60,
                "warmup_seconds": 300,
                "simulation_seconds": 3600,
                "step_length": 1.0
            },
            "paths": {
                "environments_dir": "sumo_simulation/environments",
                "output_dir": "benchmark/results"
            },
            "logging": {
                "level": "info"
            },
            "llm": {
                "timeout_seconds": 300,
                "api_base_url": "http://localhost:1234/v1",
                "max_retries": 2,
                "retry_base_delay": 1.0
            }
        }
    """
    config_path = Path(path)

    if not config_path.exists():
        # Return default config if file not found
        return BenchmarkConfig()

    with open(config_path, "r", encoding="utf-8") as f:
        data: dict[str, Any] = json.load(f)

    # Parse nested JSON structure
    simulation = data.get("simulation", {})
    paths = data.get("paths", {})
    logging_config = data.get("logging", {})
    llm_config = data.get("llm", {})

    config = BenchmarkConfig(
        cycle_duration=simulation.get("cycle_duration", 60),
        warmup_seconds=simulation.get("warmup_seconds", 300),
        simulation_seconds=simulation.get("simulation_seconds", 3600),
        step_length=simulation.get("step_length", 1.0),
        environments_dir=paths.get("environments_dir", "sumo_simulation/environments"),
        output_dir=paths.get("output_dir", "benchmark/results"),
        log_level=logging_config.get("level", "info"),
        llm_timeout_seconds=llm_config.get("timeout_seconds", 300),
        llm_api_base_url=llm_config.get("api_base_url", "http://localhost:1234/v1"),
        llm_max_retries=llm_config.get("max_retries", 2),
        llm_retry_base_delay=llm_config.get("retry_base_delay", 1.0),
    )

    config.validate()
    return config
