"""
Output directory management module for LLM Traffic Signal Cycle Benchmark.

Provides RunOutput dataclass and functions for managing benchmark output directories,
writing cycle results to JSON, and generating summary CSV files.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from datetime import datetime
import json
import csv
from typing import Any


@dataclass
class RunOutput:
    """Container for benchmark run output paths and metadata.

    Attributes:
        run_dir: Path to the run output directory
        run_id: Run identifier in format {model_name}_{timestamp}
        model_name: Name of the model being benchmarked
        timestamp: Timestamp string in format YYYY-MM-DD_HH-MM-SS
    """
    run_dir: Path
    run_id: str
    model_name: str
    timestamp: str

    def cycle_json_path(self, cycle_index: int) -> Path:
        """Get path to cycle JSON file.

        Args:
            cycle_index: Zero-based cycle index

        Returns:
            Path to the cycle JSON file (e.g., cycle_0000.json)
        """
        return self.run_dir / f"cycle_{cycle_index:04d}.json"

    def summary_csv_path(self) -> Path:
        """Get path to summary CSV file.

        Returns:
            Path to the summary CSV file
        """
        return self.run_dir / "summary.csv"

    def log_path(self) -> Path:
        """Get path to log file.

        Returns:
            Path to the log file
        """
        return self.run_dir / "run.log"


def create_run_dir(
    output_dir: str | Path,
    model_name: str,
    timestamp: str | None = None
) -> RunOutput:
    """Create output directory structure for a benchmark run.

    Creates a directory named {model_name}_{timestamp} under the specified
    output directory. The directory is created if it doesn't exist.

    Args:
        output_dir: Base output directory path
        model_name: Name of the model being benchmarked
        timestamp: Optional timestamp string (format: YYYY-MM-DD_HH-MM-SS).
                   If not provided, current time is used.

    Returns:
        RunOutput instance with paths to the created directory structure

    Example:
        >>> run_output = create_run_dir("benchmark/results", "qwen3-4b")
        >>> print(run_output.run_dir)
        benchmark/results/qwen3-4b_2026-02-15_18-30-00
    """
    output_path = Path(output_dir)

    if timestamp is None:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    # Sanitize model name for use in directory name
    safe_model_name = model_name.replace("/", "_").replace("\\", "_")

    run_id = f"{safe_model_name}_{timestamp}"
    run_dir = output_path / run_id

    # Create directory structure
    run_dir.mkdir(parents=True, exist_ok=True)

    return RunOutput(
        run_dir=run_dir,
        run_id=run_id,
        model_name=safe_model_name,
        timestamp=timestamp
    )


def write_cycle_json(
    run_output: RunOutput,
    cycle_index: int,
    data: dict[str, Any]
) -> Path:
    """Write cycle result to JSON file.

    Args:
        run_output: RunOutput instance from create_run_dir()
        cycle_index: Zero-based cycle index
        data: Dictionary containing cycle result data

    Returns:
        Path to the written JSON file

    Example:
        >>> write_cycle_json(run_output, 0, {
        ...     "cycle": 0,
        ...     "duration": 60,
        ...     "phase_timings": {"phase_1": 30, "phase_2": 30}
        ... })
    """
    json_path = run_output.cycle_json_path(cycle_index)

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return json_path


def write_summary_csv(
    run_output: RunOutput,
    rows: list[dict[str, Any]]
) -> Path:
    """Write summary data to CSV file.

    Args:
        run_output: RunOutput instance from create_run_dir()
        rows: List of dictionaries containing summary data.
              All dictionaries should have the same keys.

    Returns:
        Path to the written CSV file

    Example:
        >>> write_summary_csv(run_output, [
        ...     {"cycle": 0, "avg_delay": 12.5, "queue_length": 10},
        ...     {"cycle": 1, "avg_delay": 11.8, "queue_length": 8}
        ... ])
    """
    csv_path = run_output.summary_csv_path()

    if not rows:
        # Create empty file if no data
        csv_path.touch()
        return csv_path

    # Get fieldnames from first row
    fieldnames = list(rows[0].keys())

    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    return csv_path


def write_final_json(
    run_output: RunOutput,
    config: dict[str, Any],
    model_name: str,
    scenario: str,
    cycle_data_list: list[dict[str, Any]],
    llm_summary: dict[str, Any],
    traffic_summary: dict[str, Any],
) -> Path:
    """Write complete final result JSON file.

    File naming: {model_name}_{timestamp}.json (using run_output.run_id)

    JSON structure:
    {
        "metadata": {
            "model_name": "...",
            "scenario": "...",
            "timestamp": "...",
            "config": {...}
        },
        "cycles": [...],  // Per-cycle detailed data
        "summary": {
            "llm": {...},
            "traffic": {...}
        }
    }

    Args:
        run_output: RunOutput instance from create_run_dir()
        config: Configuration dictionary
        model_name: Name of the model being benchmarked
        scenario: Scenario name(s) being run
        cycle_data_list: List of per-cycle data dictionaries
        llm_summary: LLM metrics summary dictionary
        traffic_summary: Traffic metrics summary dictionary

    Returns:
        Path to the written JSON file
    """
    # Use run_id as filename (run_id format is {model_name}_{timestamp})
    json_path = run_output.run_dir / f"{run_output.run_id}.json"

    final_data = {
        "metadata": {
            "model_name": model_name,
            "scenario": scenario,
            "timestamp": datetime.now().isoformat(),
            "config": config,
        },
        "cycles": cycle_data_list,
        "summary": {
            "llm": llm_summary,
            "traffic": traffic_summary,
        },
    }

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(final_data, f, ensure_ascii=False, indent=2)

    return json_path


def write_summary_csv_extended(
    run_output: RunOutput,
    llm_summary: dict[str, Any],
    traffic_summary: dict[str, Any],
    model_name: str,
    scenario: str,
    weighted_summary: dict[str, Any] | None = None,
) -> Path:
    """Write summary statistics CSV table (for Excel comparison).

    File naming: {model_name}_{timestamp}.csv (using run_output.run_id)

    CSV columns:
    - model_name, scenario
    - format_success_rate, constraint_satisfaction_rate, phase_order_correct_rate
    - response_time_avg, response_time_max, response_time_min, response_time_std
    - passed_vehicles_avg, passed_vehicles_max, passed_vehicles_min, passed_vehicles_std
    - queue_vehicles_avg, queue_vehicles_max, queue_vehicles_min, queue_vehicles_std
    - total_delay_avg, total_delay_max, total_delay_min, total_delay_std
    - throughput (vehicles per second, weighted by cycle duration)

    Args:
        run_output: RunOutput instance from create_run_dir()
        llm_summary: LLM metrics summary dictionary
        traffic_summary: Traffic metrics summary dictionary
        model_name: Name of the model being benchmarked
        scenario: Scenario name(s) being run
        weighted_summary: Optional weighted metrics summary dictionary with throughput.
                          If not provided, throughput will be 0.

    Returns:
        Path to the written CSV file
    """
    # Use run_id as filename (run_id format is {model_name}_{timestamp})
    csv_path = run_output.run_dir / f"{run_output.run_id}.csv"

    # Get throughput from weighted summary if available
    throughput = 0.0
    if weighted_summary is not None:
        throughput = weighted_summary.get("throughput", 0.0)

    row = {
        "model_name": model_name,
        "scenario": scenario,
        # LLM metrics
        "format_success_rate": llm_summary.get("format_success_rate", 0),
        "constraint_satisfaction_rate": llm_summary.get("constraint_satisfaction_rate", 0),
        "phase_order_correct_rate": llm_summary.get("phase_order_correct_rate", 0),
        "response_time_avg": llm_summary.get("response_time", {}).get("avg", 0),
        "response_time_max": llm_summary.get("response_time", {}).get("max", 0),
        "response_time_min": llm_summary.get("response_time", {}).get("min", 0),
        "response_time_std": llm_summary.get("response_time", {}).get("std", 0),
        # Traffic metrics
        "passed_vehicles_avg": traffic_summary.get("passed_vehicles", {}).get("avg", 0),
        "passed_vehicles_max": traffic_summary.get("passed_vehicles", {}).get("max", 0),
        "passed_vehicles_min": traffic_summary.get("passed_vehicles", {}).get("min", 0),
        "passed_vehicles_std": traffic_summary.get("passed_vehicles", {}).get("std", 0),
        "queue_vehicles_avg": traffic_summary.get("queue_vehicles", {}).get("avg", 0),
        "queue_vehicles_max": traffic_summary.get("queue_vehicles", {}).get("max", 0),
        "queue_vehicles_min": traffic_summary.get("queue_vehicles", {}).get("min", 0),
        "queue_vehicles_std": traffic_summary.get("queue_vehicles", {}).get("std", 0),
        "total_delay_avg": traffic_summary.get("total_delay", {}).get("avg", 0),
        "total_delay_max": traffic_summary.get("total_delay", {}).get("max", 0),
        "total_delay_min": traffic_summary.get("total_delay", {}).get("min", 0),
        "total_delay_std": traffic_summary.get("total_delay", {}).get("std", 0),
        # Weighted metrics
        "throughput": throughput,
    }

    fieldnames = list(row.keys())

    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow(row)

    return csv_path
