"""
Batch benchmark runner for LLM Traffic Signal Cycle Benchmark.

Provides command-line interface for running multiple model benchmarks sequentially
and generating comparison reports.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

from loguru import logger

from TSC_CYCLE.benchmark.batch_config import BatchConfig, ModelConfig, load_batch_config
from TSC_CYCLE.benchmark.config import BenchmarkConfig, load_config
from TSC_CYCLE.benchmark.run_benchmark import run_benchmark
from TSC_CYCLE.benchmark.report import generate_comparison_report, print_terminal_summary
from TSC_CYCLE.benchmark.logger import setup_logging


def run_batch(config_path: str, log_level: str = "info", gui: bool = False) -> dict[str, Any]:
    """Run batch benchmarks for multiple models.

    Loads batch configuration, runs benchmarks for each model sequentially,
    and generates a comparison report at the end.

    Args:
        config_path: Path to the batch configuration JSON file
        log_level: Logging level (info/debug)
        gui: Whether to show SUMO GUI (default: False)

    Returns:
        Dictionary containing:
        - models_run: Number of models successfully benchmarked
        - results_dir: Path to the results directory
        - comparison_file: Path to the comparison report
        - model_summaries: List of per-model summaries
        - error: Error message if any model failed (only first error)

    Raises:
        ValueError: If batch configuration is invalid
        RuntimeError: If any model benchmark fails (stops on first failure)
    """
    # Setup logging
    setup_logging(level=log_level)

    # Load batch configuration
    batch_config = load_batch_config(config_path)

    if not batch_config.models:
        raise ValueError(
            f"No models specified in batch configuration: {config_path}\n"
            "Please add models to the 'models' list in the configuration file."
        )

    # Load base benchmark configuration
    # Determine config path: use batch_config.benchmark_config_path if specified,
    # otherwise look for config.json relative to batch config
    batch_config_path = Path(config_path)
    if batch_config.benchmark_config_path:
        benchmark_config_path = Path(batch_config.benchmark_config_path)
    else:
        benchmark_config_path = batch_config_path.parent / "config.json"
    if not benchmark_config_path.exists():
        benchmark_config_path = Path("TSC_CYCLE/benchmark/config/config.json")

    benchmark_config = load_config(str(benchmark_config_path))
    logger.info("Loaded benchmark config: cycle_duration={}s, warmup={}s, simulation={}s",
                benchmark_config.cycle_duration, benchmark_config.warmup_seconds, benchmark_config.simulation_seconds)

    # Override LLM API URL from batch config
    benchmark_config.llm_api_base_url = batch_config.llm_api_base_url

    # Get or create results base directory
    results_dir = Path(benchmark_config.output_dir)
    results_dir.mkdir(parents=True, exist_ok=True)

    total_models = len(batch_config.models)
    scenario = batch_config.scenario

    model_summaries: list[dict[str, Any]] = []
    models_run = 0

    # Print batch header
    print("\n" + "=" * 60)
    print(f"BATCH BENCHMARK: {total_models} models", end="")
    if scenario:
        print(f", scenario={scenario}")
    else:
        print()
    print("=" * 60)

    # Run each model sequentially
    for i, model_config in enumerate(batch_config.models, start=1):
        model_name = model_config.name
        print(f"\n[{i}/{total_models}] Running model: {model_name}...")
        print(f"    Structured output: {model_config.structured_output}")

        try:
            # Run benchmark for this model
            summary = run_benchmark(
                config=benchmark_config,
                scenario=scenario,
                model_name=model_name,
                use_llm=True,
                structured_output=model_config.structured_output,
                response_format=batch_config.cycle_plan_schema if model_config.structured_output else None,
                gui=gui,
            )

            # Check for errors
            if "error" in summary and summary["error"]:
                raise RuntimeError(f"Benchmark failed for {model_name}: {summary['error']}")

            # Extract key metrics for display
            total_cycles = summary.get("total_cycles", 0)
            valid_tl_count = summary.get("valid_tl_count", 1)
            llm_summary = summary.get("llm_summary", {})
            format_success_rate = llm_summary.get("format_success_rate", 0) * 100

            print(f"[{i}/{total_models}] Complete: {valid_tl_count} intersections, {total_cycles} cycles, format_success={format_success_rate:.1f}%")

            model_summaries.append({
                "model_name": model_name,
                "structured_output": model_config.structured_output,
                "total_cycles": total_cycles,
                "valid_tl_count": valid_tl_count,
                "format_success_rate": format_success_rate,
                "output_dir": summary.get("output_dir", ""),
            })
            models_run += 1

        except Exception as e:
            # Stop on first error and raise
            error_msg = f"Model {model_name} failed: {e}"
            logger.error(error_msg)
            print(f"\n[ERROR] {error_msg}")
            raise RuntimeError(error_msg) from e

    # All models complete - generate comparison report
    print("\n" + "=" * 60)
    print("ALL MODELS COMPLETE")
    print("=" * 60)

    # Generate comparison report
    comparison_file = generate_comparison_report(results_dir)
    logger.info(f"Generated comparison report: {comparison_file}")

    # Print terminal summary
    print_terminal_summary(results_dir)

    return {
        "models_run": models_run,
        "results_dir": str(results_dir),
        "comparison_file": str(comparison_file),
        "model_summaries": model_summaries,
    }


def main() -> None:
    """Main entry point with command-line argument parsing."""
    parser = argparse.ArgumentParser(
        description="Run batch LLM Traffic Signal Cycle Benchmark for multiple models",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--config",
        type=str,
        default="TSC_CYCLE/benchmark/config/batch_config.json",
        help="Path to batch configuration file",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        choices=["info", "debug"],
        default="info",
        help="Log level",
    )
    parser.add_argument(
        "--gui",
        action="store_true",
        help="Show SUMO GUI (also enabled by SUMO_GUI=1 env var)",
    )

    args = parser.parse_args()

    # Check GUI mode from CLI flag or environment variable
    gui = args.gui or os.environ.get("SUMO_GUI", "0") == "1"

    try:
        logger.info("Starting batch benchmark with config: {}", args.config)
        if gui:
            logger.info("SUMO GUI mode enabled")

        result = run_batch(
            config_path=args.config,
            log_level=args.log_level,
            gui=gui,
        )

        # Print final summary
        print("\n" + "=" * 60)
        print("BATCH BENCHMARK COMPLETE")
        print("=" * 60)
        print(f"Models run: {result['models_run']}")
        print(f"Results directory: {result['results_dir']}")
        print(f"Comparison report: {result['comparison_file']}")

    except ValueError as e:
        logger.error("Configuration error: {}", e)
        print(f"\n[CONFIG ERROR] {e}")
        sys.exit(1)
    except RuntimeError as e:
        logger.error("Benchmark failed: {}", e)
        print(f"\n[RUNTIME ERROR] {e}")
        sys.exit(1)
    except Exception as e:
        logger.error("Unexpected error: {}", e)
        print(f"\n[ERROR] {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
