"""
Main entry point for running LLM Traffic Signal Cycle Benchmark.

Provides command-line interface for running benchmark tests with
configurable scenarios, models, and logging options.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Optional

from loguru import logger

from TSC_CYCLE.benchmark.config import BenchmarkConfig, load_config
from TSC_CYCLE.benchmark.simulation import (
    BenchmarkSimulation,
    discover_scenarios,
    get_sumocfg_path,
)
from TSC_CYCLE.benchmark.output import (
    RunOutput,
    create_run_dir,
    write_cycle_json,
    write_summary_csv,
    write_final_json,
    write_summary_csv_extended,
)
from TSC_CYCLE.benchmark.logger import setup_logging
from TSC_CYCLE.benchmark.llm_client import LLMClient, LLMResponse
from TSC_CYCLE.benchmark.prompt_builder import BenchmarkPromptBuilder, PhaseWaitData
from TSC_CYCLE.benchmark.timing_parser import parse_llm_timing, TimingPlan
from TSC_CYCLE.benchmark.default_timing import (
    load_default_timing,
    get_net_xml_path,
    DefaultTiming,
)
from TSC_CYCLE.benchmark.metrics import (
    CycleTrafficMetrics,
    calculate_llm_metrics,
    calculate_traffic_metrics,
    calculate_weighted_metrics,
)
from TSC_CYCLE.benchmark.tl_filter import filter_valid_traffic_lights


@dataclass
class CycleResult:
    """Data class for collecting per-cycle benchmark results.

    Attributes:
        cycle_index: Zero-based cycle index
        scenario: Name of the scenario being run
        tl_id: Traffic light ID (intersection ID)
        sim_time: Current simulation time in seconds
        passed_vehicles: Number of vehicles that passed through (real value from metrics)
        queue_vehicles: Number of vehicles in queue (rounded avg_queue_vehicles)
        total_delay: Total delay in vehicle-seconds (real value from metrics)
        llm_response_time: Time for LLM to respond in seconds
        format_success: Whether LLM output was valid
        constraint_satisfied: Whether timing constraints were met
    """
    cycle_index: int
    scenario: str
    tl_id: str
    sim_time: float
    passed_vehicles: int = 0
    queue_vehicles: int = 0
    total_delay: float = 0.0
    llm_response_time: float | None = None
    format_success: bool = True
    constraint_satisfied: bool = True

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON/CSV output."""
        return {
            "scenario": self.scenario,
            "tl_id": self.tl_id,
            "cycle_index": self.cycle_index,
            "sim_time": self.sim_time,
            "passed_vehicles": self.passed_vehicles,
            "queue_vehicles": self.queue_vehicles,
            "total_delay": self.total_delay,
            "llm_response_time": self.llm_response_time,
            "format_success": self.format_success,
            "constraint_satisfied": self.constraint_satisfied,
        }


def collect_phase_data(
    sim: BenchmarkSimulation,
    tl_id: str,
    min_green: int = 20,
    max_green: int = 60,
) -> List[PhaseWaitData]:
    """Collect current traffic state for prompt building.

    Gathers queue and saturation data for each phase of the traffic light.

    Args:
        sim: Running BenchmarkSimulation instance
        tl_id: Traffic light ID
        min_green: Minimum green time (default 20s)
        max_green: Maximum green time (default 60s)

    Returns:
        List of PhaseWaitData for each phase
    """
    conn = sim.conn
    phase_waits: List[PhaseWaitData] = []

    try:
        # Get controlled links for this traffic light
        controlled_links = conn.trafficlight.getControlledLinks(tl_id)

        # Get current phase count from the traffic light
        tl_logic = conn.trafficlight.getAllProgramLogics(tl_id)
        if tl_logic:
            # Get phases from the first program (usually the active one)
            phases = tl_logic[0].phases
            num_phases = len(phases)
        else:
            # Default to 4 phases if we can't determine
            num_phases = 4

        # Collect data for each phase
        # Only consider "green" phases (even indices typically)
        green_phase_indices = [i for i in range(num_phases) if i % 2 == 0]

        for phase_id in green_phase_indices:
            # Get lanes for this phase
            lanes = set()
            try:
                # Get all lanes controlled by this traffic light
                for link_group in controlled_links:
                    for link in link_group:
                        if link and link[0]:
                            lanes.add(str(link[0]))
            except Exception:
                pass

            # Count vehicles on these lanes
            queue_vehicles = 0
            for lane_id in lanes:
                try:
                    queue_vehicles += int(conn.lane.getLastStepHaltingNumber(lane_id))
                except Exception:
                    pass

            # Estimate capacity based on lane count
            # Assume each lane can hold about 15 vehicles
            capacity = max(len(lanes) * 15, 15)

            # Calculate saturation
            pred_saturation = queue_vehicles / capacity if capacity > 0 else 0.0

            phase_waits.append(PhaseWaitData(
                phase_id=len(phase_waits),  # LLM-friendly连续编号
                sumo_phase_index=phase_id,  # 保留原始SUMO相位索引
                pred_saturation=round(pred_saturation, 3),
                min_green=min_green,
                max_green=max_green,
                capacity=capacity,
            ))

    except Exception as e:
        logger.warning("Error collecting phase data for {}: {}", tl_id, e)
        # Return default data if collection fails
        # 使用偶数索引作为默认绿灯相位 (0, 2, 4, 6)
        for i in range(4):
            phase_waits.append(PhaseWaitData(
                phase_id=i,  # LLM-friendly连续编号
                sumo_phase_index=i * 2,  # 默认绿灯相位索引
                pred_saturation=0.5,
                min_green=min_green,
                max_green=max_green,
                capacity=30,
            ))

    return phase_waits


def convert_default_to_timing_plan(default_timing: DefaultTiming) -> TimingPlan:
    """Convert DefaultTiming to TimingPlan for apply_timing_plan.

    Args:
        default_timing: DefaultTiming from .net.xml

    Returns:
        TimingPlan that can be applied to simulation
    """
    from TSC_CYCLE.benchmark.timing_parser import PhaseTiming

    return TimingPlan(
        phases=[
            PhaseTiming(
                phase_id=p.phase_id,
                sumo_phase_index=p.sumo_phase_index,
                final=p.duration
            )
            for p in default_timing.phases
        ]
    )


def run_single_tl_benchmark(
    config: BenchmarkConfig,
    sumocfg_path: Path,
    net_xml_path: Path | None,
    scenario_name: str,
    tl_id: str,
    llm_client: Optional[LLMClient],
    prompt_builder: Optional[BenchmarkPromptBuilder],
    model_name: str,
    use_llm: bool,
    structured_output: bool,
    response_format: dict[str, Any] | None,
    gui: bool,
    run_output: RunOutput,
) -> tuple[list[CycleResult], list[dict[str, Any]], int]:
    """Run benchmark for a single traffic light (intersection).

    Each intersection runs its own complete simulation independently.

    Args:
        config: Benchmark configuration
        sumocfg_path: Path to .sumocfg file
        net_xml_path: Path to .net.xml file (for default timing)
        scenario_name: Name of the scenario
        tl_id: Traffic light ID to evaluate
        llm_client: LLM client instance (or None for baseline)
        prompt_builder: Prompt builder instance
        model_name: Model name for logging
        use_llm: Whether to use LLM for timing decisions
        structured_output: Whether to use structured output
        response_format: JSON Schema for structured output
        gui: Whether to show SUMO GUI
        run_output: Output directory handler

    Returns:
        Tuple of (cycle_results, cycle_data_list, total_cycles)
    """
    # Create simulation for this intersection
    sim = BenchmarkSimulation(config, sumocfg_path, gui=gui)

    try:
        # Start simulation (includes warmup)
        sim.start()

        # Load default timing as fallback for this intersection
        default_timing: Optional[DefaultTiming] = None
        if net_xml_path:
            default_timing = load_default_timing(net_xml_path, tl_id)
            if default_timing:
                logger.debug(
                    "Loaded default timing for {}: {} phases, {}s total",
                    tl_id,
                    len(default_timing.phases),
                    default_timing.get_total_duration()
                )

        # Run cycle by cycle with LLM integration
        tl_results: list[CycleResult] = []
        tl_cycle_data: list[dict[str, Any]] = []
        tl_cycles = 0

        while not sim.is_done:
            cycle_start_time = sim.sim_time

            # Initialize cycle metrics
            llm_response_time: Optional[float] = None
            format_success = True
            constraint_satisfied = True
            timing_plan: Optional[TimingPlan] = None
            cycle_metrics: Optional[CycleTrafficMetrics] = None

            if use_llm and llm_client and prompt_builder:
                # Collect traffic state for this cycle
                phase_waits = collect_phase_data(sim, tl_id)
                expected_phases = len(phase_waits)

                # Build prompt
                prompt = prompt_builder.build_prompt(
                    tl_id=tl_id,
                    sim_time=sim.sim_time,
                    phase_waits=phase_waits,
                )

                # Call LLM with structured output if configured
                logger.debug("Calling LLM for {} cycle {}...", tl_id, sim.cycle_index)
                llm_response = llm_client.call_with_system(
                    system_prompt=prompt_builder.get_system_prompt(),
                    user_prompt=prompt,
                    response_format=response_format if structured_output else None
                )
                llm_response_time = llm_response.response_time

                # Determine if we should expect raw JSON (structured output succeeded)
                expect_raw_json = (
                    structured_output
                    and llm_response.success
                    and llm_response.used_structured_output
                    and not llm_response.structured_output_failed
                )

                if llm_response.success:
                    # Parse LLM output
                    parse_result = parse_llm_timing(
                        llm_output=llm_response.content,
                        expected_phases=expected_phases,
                        min_green=20,
                        max_green=60,
                        phase_waits=phase_waits,
                        expect_raw_json=expect_raw_json,
                    )

                    if parse_result.success:
                        timing_plan = parse_result.plan
                        logger.debug(
                            "LLM timing plan accepted for {}: {} phases",
                            tl_id,
                            len(timing_plan.phases)
                        )
                    else:
                        format_success = False
                        logger.warning(
                            "LLM output parse failed for {}: {}",
                            tl_id,
                            parse_result.error
                        )
                else:
                    format_success = False
                    logger.warning(
                        "LLM call failed for {}: {}",
                        tl_id,
                        llm_response.error
                    )

                # Use default timing if LLM failed
                if timing_plan is None and default_timing:
                    timing_plan = convert_default_to_timing_plan(default_timing)

            # Apply timing plan if available
            if timing_plan:
                try:
                    cycle_metrics = sim.apply_timing_plan(tl_id, timing_plan)
                    constraint_satisfied = True
                except Exception as e:
                    constraint_satisfied = False
                    logger.error("Failed to apply timing plan for {}: {}", tl_id, e)
            else:
                # No timing plan, run default cycle (no metrics collected)
                cycle_state = sim.run_cycle()

            # Get current simulation time after cycle
            cycle_end_time = sim.sim_time

            # Collect cycle result with real metrics
            result = CycleResult(
                cycle_index=sim.cycle_index - 1,  # Already incremented
                scenario=scenario_name,
                tl_id=tl_id,
                sim_time=cycle_end_time,
                passed_vehicles=cycle_metrics.passed_vehicles if cycle_metrics else 0,
                queue_vehicles=int(round(cycle_metrics.avg_queue_vehicles)) if cycle_metrics else 0,
                total_delay=cycle_metrics.total_delay if cycle_metrics else 0.0,
                llm_response_time=llm_response_time,
                format_success=format_success,
                constraint_satisfied=constraint_satisfied,
            )
            tl_results.append(result)

            # Write cycle JSON
            cycle_data: dict[str, Any] = {
                "scenario": scenario_name,
                "tl_id": tl_id,
                "cycle_index": result.cycle_index,
                "sim_time": result.sim_time,
                "cycle_start_time": cycle_start_time,
                "is_warmup_complete": True,
                "is_done": sim.is_done,
                "traffic_metrics": {
                    "passed_vehicles": result.passed_vehicles,
                    "queue_vehicles": result.queue_vehicles,
                    "avg_queue_vehicles": cycle_metrics.avg_queue_vehicles if cycle_metrics else 0.0,
                    "total_delay": result.total_delay,
                    "samples": cycle_metrics.samples if cycle_metrics else [],
                },
                "llm_metrics": {
                    "response_time": llm_response_time,
                    "format_success": format_success,
                    "constraint_satisfied": constraint_satisfied,
                },
            }
            write_cycle_json(run_output, result.cycle_index, cycle_data)
            tl_cycle_data.append(cycle_data)

            tl_cycles += 1

        return tl_results, tl_cycle_data, tl_cycles

    finally:
        sim.close()


def run_benchmark(
    config: BenchmarkConfig,
    scenario: str | None = None,
    model_name: str = "baseline",
    use_llm: bool = True,
    structured_output: bool = False,
    response_format: dict[str, Any] | None = None,
    gui: bool = False,
    single_tl: str | None = None,
) -> dict[str, Any]:
    """Run benchmark tests with the given configuration.

    Evaluates all valid traffic lights (intersections) in each scenario.
    Each intersection runs its own independent simulation.

    Args:
        config: Benchmark configuration
        scenario: Optional scenario name. If None, runs all discovered scenarios.
        model_name: Model name for output directory (default: "baseline")
        use_llm: Whether to use LLM for timing decisions (default: True)
        structured_output: Whether to use structured output (default: False)
        response_format: JSON Schema for structured output (default: None)
        gui: Whether to show SUMO GUI (default: False)
        single_tl: Optional single traffic light ID to evaluate (for debugging)

    Returns:
        Dictionary containing:
        - scenarios_run: Number of scenarios executed
        - total_cycles: Total number of cycles across all scenarios and intersections
        - output_dir: Path to output directory
        - results: List of cycle results
        - valid_tl_count: Number of valid traffic lights evaluated
    """
    # Setup logging to terminal only initially
    setup_logging(level=config.log_level)

    # Create output directory
    run_output = create_run_dir(config.output_dir, model_name)
    logger.info("Created output directory: {}", run_output.run_dir)

    # Setup logging to file as well
    setup_logging(level=config.log_level, log_file=run_output.log_path())

    # Initialize LLM client and prompt builder if using LLM
    llm_client: Optional[LLMClient] = None
    prompt_builder: Optional[BenchmarkPromptBuilder] = None

    if use_llm:
        llm_client = LLMClient(
            api_base_url=config.llm_api_base_url,
            timeout_seconds=config.llm_timeout_seconds,
            max_retries=config.llm_max_retries,
            retry_base_delay=config.llm_retry_base_delay,
            model=model_name,
        )
        prompt_builder = BenchmarkPromptBuilder()
        logger.info("LLM client initialized: {} (model={}, structured_output={})",
                    config.llm_api_base_url, model_name, structured_output)

    # Discover scenarios
    if scenario:
        scenarios = [scenario]
        logger.info("Running single scenario: {}", scenario)
    else:
        scenarios = discover_scenarios(config.environments_dir)
        logger.info("Discovered {} scenarios: {}", len(scenarios), scenarios)

    if not scenarios:
        logger.error("No scenarios found in {}", config.environments_dir)
        return {
            "scenarios_run": 0,
            "total_cycles": 0,
            "output_dir": str(run_output.run_dir),
            "results": [],
            "error": "No scenarios found",
        }

    all_results: list[CycleResult] = []
    all_cycle_data: list[dict[str, Any]] = []
    scenarios_run = 0
    total_cycles = 0
    total_valid_tl = 0

    for scenario_name in scenarios:
        logger.info("=" * 60)
        logger.info("Starting scenario: {}", scenario_name)

        # Get sumocfg path
        sumocfg_path = get_sumocfg_path(config.environments_dir, scenario_name)
        if sumocfg_path is None:
            logger.error("No .sumocfg file found for scenario: {}", scenario_name)
            continue

        logger.info("Using sumocfg: {}", sumocfg_path)

        # Get net.xml path for filtering and default timing
        net_xml_path = get_net_xml_path(sumocfg_path)

        # Filter valid traffic lights
        if net_xml_path:
            valid_tl_ids = filter_valid_traffic_lights(str(net_xml_path))
            logger.info("Found {} valid traffic lights in {}", len(valid_tl_ids), scenario_name)
        else:
            logger.error("No net.xml found for scenario: {}", scenario_name)
            continue

        # If single_tl specified, only evaluate that one
        if single_tl:
            if single_tl in valid_tl_ids:
                valid_tl_ids = [single_tl]
                logger.info("Evaluating single traffic light: {}", single_tl)
            else:
                logger.error("Traffic light {} not found in valid list", single_tl)
                continue

        total_valid_tl += len(valid_tl_ids)
        scenarios_run += 1

        # Run benchmark for each valid traffic light
        for tl_idx, tl_id in enumerate(valid_tl_ids, 1):
            logger.info("-" * 40)
            logger.info("Evaluating intersection {}/{}: {}",
                       tl_idx, len(valid_tl_ids), tl_id)

            tl_results, tl_cycle_data, tl_cycles = run_single_tl_benchmark(
                config=config,
                sumocfg_path=sumocfg_path,
                net_xml_path=net_xml_path,
                scenario_name=scenario_name,
                tl_id=tl_id,
                llm_client=llm_client,
                prompt_builder=prompt_builder,
                model_name=model_name,
                use_llm=use_llm,
                structured_output=structured_output,
                response_format=response_format,
                gui=gui,
                run_output=run_output,
            )

            all_results.extend(tl_results)
            all_cycle_data.extend(tl_cycle_data)
            total_cycles += tl_cycles

            logger.info("Intersection {} complete: {} cycles", tl_id, tl_cycles)

        logger.info("Scenario {} complete: {} intersections, {} total cycles",
                   scenario_name, len(valid_tl_ids), total_cycles)

    # Write summary CSV (per-cycle data with tl_id)
    if all_results:
        csv_rows = [r.to_dict() for r in all_results]
        csv_path = write_summary_csv(run_output, csv_rows)
        logger.info("Wrote summary CSV: {}", csv_path)

    # Calculate metrics summary (averaged across all intersections)
    llm_summary = calculate_llm_metrics(all_results)
    traffic_summary = calculate_traffic_metrics(all_results)

    # Calculate weighted metrics summary (with throughput)
    # Convert CycleResult objects to dict format expected by calculate_weighted_metrics
    weighted_input = [
        {
            "queue_vehicles": r.queue_vehicles,
            "total_delay": r.total_delay,
            "passed_vehicles": r.passed_vehicles,
            "samples": cycle_data.get("traffic_metrics", {}).get("samples", []),
        }
        for r, cycle_data in zip(all_results, all_cycle_data)
    ]
    weighted_summary = calculate_weighted_metrics(weighted_input)

    # Prepare config dict for final JSON
    config_dict = {
        "cycle_duration": config.cycle_duration,
        "warmup_seconds": config.warmup_seconds,
        "simulation_seconds": config.simulation_seconds,
        "step_length": config.step_length,
        "llm_api_base_url": config.llm_api_base_url,
    }

    # Prepare scenario string
    scenario_str = ",".join(scenarios) if len(scenarios) > 1 else (scenarios[0] if scenarios else "")

    # Write final JSON
    json_path = write_final_json(
        run_output=run_output,
        config=config_dict,
        model_name=model_name,
        scenario=scenario_str,
        cycle_data_list=all_cycle_data,
        llm_summary=llm_summary.to_dict(),
        traffic_summary=traffic_summary.to_dict(),
    )
    logger.info("Wrote final JSON: {}", json_path)

    # Write summary CSV extended (one row per model, averaged metrics)
    csv_extended_path = write_summary_csv_extended(
        run_output=run_output,
        llm_summary=llm_summary.to_dict(),
        traffic_summary=traffic_summary.to_dict(),
        model_name=model_name,
        scenario=scenario_str,
        weighted_summary=weighted_summary.to_dict(),
    )
    logger.info("Wrote summary CSV extended: {}", csv_extended_path)

    summary = {
        "scenarios_run": scenarios_run,
        "total_cycles": total_cycles,
        "valid_tl_count": total_valid_tl,
        "output_dir": str(run_output.run_dir),
        "results": [r.to_dict() for r in all_results],
        "llm_summary": llm_summary.to_dict(),
        "traffic_summary": traffic_summary.to_dict(),
    }

    logger.info("=" * 60)
    logger.info("Benchmark complete!")
    logger.info("Scenarios run: {}", scenarios_run)
    logger.info("Valid intersections evaluated: {}", total_valid_tl)
    logger.info("Total cycles: {}", total_cycles)
    logger.info("Output directory: {}", run_output.run_dir)

    return summary


def main() -> None:
    """Main entry point with command-line argument parsing."""
    parser = argparse.ArgumentParser(
        description="Run LLM Traffic Signal Cycle Benchmark",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--config",
        type=str,
        default="benchmark/config/config.json",
        help="Path to configuration file",
    )
    parser.add_argument(
        "--scenario",
        type=str,
        default=None,
        help="Scenario name to run (runs all if not specified)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="baseline",
        help="Model name for output directory",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        choices=["info", "debug"],
        default="info",
        help="Log level",
    )
    parser.add_argument(
        "--single-tl",
        type=str,
        default=None,
        help="Evaluate only this traffic light ID (for debugging)",
    )

    args = parser.parse_args()

    try:
        # Load configuration
        config = load_config(args.config)

        # Override log level from command line if specified
        if args.log_level:
            config.log_level = args.log_level

        logger.info("Loaded configuration from: {}", args.config)
        logger.info("Configuration: cycle_duration={}s, warmup={}s, simulation={}s",
                    config.cycle_duration, config.warmup_seconds, config.simulation_seconds)

        # Run benchmark
        summary = run_benchmark(
            config=config,
            scenario=args.scenario,
            model_name=args.model,
            single_tl=args.single_tl,
        )

        # Print summary to stdout
        print("\n" + "=" * 60)
        print("BENCHMARK SUMMARY")
        print("=" * 60)
        print(f"Scenarios run: {summary['scenarios_run']}")
        print(f"Valid intersections: {summary.get('valid_tl_count', 'N/A')}")
        print(f"Total cycles: {summary['total_cycles']}")
        print(f"Output directory: {summary['output_dir']}")

        if "error" in summary:
            print(f"Error: {summary['error']}")
            sys.exit(1)

    except Exception as e:
        logger.error("Benchmark failed: {}", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
