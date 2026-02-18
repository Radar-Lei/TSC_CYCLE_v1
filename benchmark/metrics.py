"""
Traffic metrics collection module for benchmark runs.

Provides per-second sampling of queue, throughput, and delay metrics
during simulation execution.
Also provides LLM and traffic metrics summary calculations.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    import traci


@dataclass
class CycleTrafficMetrics:
    """Cycle traffic metrics data.

    Attributes:
        passed_vehicles: Number of vehicles that passed through the intersection
        avg_queue_vehicles: Average queue length during the cycle
        total_delay: Total delay in vehicle-seconds
        samples: Per-second queue vehicle count samples
    """
    passed_vehicles: int
    avg_queue_vehicles: float
    total_delay: float
    samples: list[int]


class TrafficMetricsCollector:
    """Traffic metrics collector - samples metrics during simulation execution.

    Collects queue length, passed vehicles, and delay metrics by sampling
    at each simulation step during a timing plan execution.
    """

    def __init__(self, conn: "traci.Connection", tl_id: str):
        """Initialize the collector.

        Args:
            conn: TraCI connection
            tl_id: Target intersection ID
        """
        self._conn = conn
        self._tl_id = tl_id
        self._controlled_lanes: list[str] = []
        self._vehicles_before: set[str] = set()
        self._queue_samples: list[int] = []
        self._total_delay: float = 0.0

    def start_cycle(self) -> None:
        """Start cycle: record initial vehicle set, clear sampling data."""
        # Get controlled lanes
        self._controlled_lanes = self._get_controlled_lanes()
        # Record initial vehicles
        self._vehicles_before = self._get_current_vehicles()
        # Clear samples
        self._queue_samples = []
        self._total_delay = 0.0

    def sample(self) -> None:
        """Sample per simulation second: record queue count and delay."""
        # 1. Sample queue vehicle count
        queue_count = 0
        for lane in self._controlled_lanes:
            try:
                queue_count += self._conn.lane.getLastStepHaltingNumber(lane)
            except Exception:
                pass
        self._queue_samples.append(queue_count)

        # 2. Accumulate delay (using getWaitingTime)
        for lane in self._controlled_lanes:
            try:
                vehicle_ids = self._conn.lane.getLastStepVehicleIDs(lane)
                for vid in vehicle_ids:
                    self._total_delay += self._conn.vehicle.getWaitingTime(vid)
            except Exception:
                pass

    def finish_cycle(self) -> CycleTrafficMetrics:
        """Finish cycle: calculate and return metrics."""
        # Calculate passed vehicles
        vehicles_after = self._get_current_vehicles()
        passed = len(self._vehicles_before - vehicles_after)

        # Calculate average queue
        avg_queue = (
            sum(self._queue_samples) / len(self._queue_samples)
            if self._queue_samples else 0.0
        )

        return CycleTrafficMetrics(
            passed_vehicles=passed,
            avg_queue_vehicles=avg_queue,
            total_delay=self._total_delay,
            samples=self._queue_samples.copy(),
        )

    def _get_controlled_lanes(self) -> list[str]:
        """Get controlled lanes list."""
        lanes = set()
        try:
            controlled_links = self._conn.trafficlight.getControlledLinks(self._tl_id)
            for link_group in controlled_links:
                for link in link_group:
                    if link and link[0]:
                        lanes.add(str(link[0]))
        except Exception:
            pass
        return list(lanes)

    def _get_current_vehicles(self) -> set[str]:
        """Get all vehicle IDs on current controlled lanes."""
        vehicles = set()
        for lane in self._controlled_lanes:
            try:
                vehicles.update(self._conn.lane.getLastStepVehicleIDs(lane))
            except Exception:
                pass
        return vehicles


@dataclass
class LLMMetricsSummary:
    """LLM metrics summary.

    Attributes:
        format_success_rate: JSON format success rate
        constraint_satisfaction_rate: Constraint satisfaction rate
        phase_order_correct_rate: Phase order correct rate
        response_time_avg: Average response time in seconds
        response_time_max: Maximum response time in seconds
        response_time_min: Minimum response time in seconds
        response_time_std: Response time standard deviation
        total_cycles: Total number of cycles
        format_success_count: Number of format successes
        constraint_satisfied_count: Number of constraint satisfactions
    """
    format_success_rate: float
    constraint_satisfaction_rate: float
    phase_order_correct_rate: float
    response_time_avg: float
    response_time_max: float
    response_time_min: float
    response_time_std: float
    total_cycles: int
    format_success_count: int
    constraint_satisfied_count: int

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON output."""
        return {
            "format_success_rate": self.format_success_rate,
            "constraint_satisfaction_rate": self.constraint_satisfaction_rate,
            "phase_order_correct_rate": self.phase_order_correct_rate,
            "response_time": {
                "avg": self.response_time_avg,
                "max": self.response_time_max,
                "min": self.response_time_min,
                "std": self.response_time_std,
            },
            "counts": {
                "total_cycles": self.total_cycles,
                "format_success": self.format_success_count,
                "constraint_satisfied": self.constraint_satisfied_count,
            },
        }


@dataclass
class TrafficMetricsSummary:
    """Traffic metrics summary.

    Attributes:
        passed_vehicles_avg: Average passed vehicles per cycle
        passed_vehicles_max: Maximum passed vehicles
        passed_vehicles_min: Minimum passed vehicles
        passed_vehicles_std: Standard deviation of passed vehicles
        queue_vehicles_avg: Average queue vehicles per cycle
        queue_vehicles_max: Maximum queue vehicles
        queue_vehicles_min: Minimum queue vehicles
        queue_vehicles_std: Standard deviation of queue vehicles
        total_delay_avg: Average total delay per cycle
        total_delay_max: Maximum total delay
        total_delay_min: Minimum total delay
        total_delay_std: Standard deviation of total delay
    """
    passed_vehicles_avg: float
    passed_vehicles_max: int
    passed_vehicles_min: int
    passed_vehicles_std: float
    queue_vehicles_avg: float
    queue_vehicles_max: int
    queue_vehicles_min: int
    queue_vehicles_std: float
    total_delay_avg: float
    total_delay_max: float
    total_delay_min: float
    total_delay_std: float

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON output."""
        return {
            "passed_vehicles": {
                "avg": self.passed_vehicles_avg,
                "max": self.passed_vehicles_max,
                "min": self.passed_vehicles_min,
                "std": self.passed_vehicles_std,
            },
            "queue_vehicles": {
                "avg": self.queue_vehicles_avg,
                "max": self.queue_vehicles_max,
                "min": self.queue_vehicles_min,
                "std": self.queue_vehicles_std,
            },
            "total_delay": {
                "avg": self.total_delay_avg,
                "max": self.total_delay_max,
                "min": self.total_delay_min,
                "std": self.total_delay_std,
            },
        }


@dataclass
class WeightedMetricsSummary:
    """Weighted metrics summary using cycle duration as weight.

    Attributes:
        queue_vehicles_avg: Average queue vehicles (weighted by cycle duration)
        total_delay_avg: Average total delay (weighted by cycle duration)
        throughput: Vehicles per second (weighted by cycle duration)
        total_cycles: Total number of cycles
        total_duration: Total duration in seconds
    """
    queue_vehicles_avg: float
    total_delay_avg: float
    throughput: float  # vehicles per second
    total_cycles: int
    total_duration: float  # seconds

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON output."""
        return {
            "queue_vehicles_avg": self.queue_vehicles_avg,
            "total_delay_avg": self.total_delay_avg,
            "throughput": self.throughput,
            "total_cycles": self.total_cycles,
            "total_duration": self.total_duration,
        }


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
    if not values or not weights:
        return 0.0

    filtered = [(v, w) for v, w in zip(values, weights) if w > 0]
    if not filtered:
        return 0.0

    total_weight = sum(w for _, w in filtered)
    if total_weight == 0:
        return 0.0

    return sum(v * w for v, w in filtered) / total_weight


def calculate_throughput(passed_vehicles: int, cycle_duration: float) -> float:
    """Calculate throughput (vehicles per second) for a single cycle.

    Args:
        passed_vehicles: Number of vehicles that passed through
        cycle_duration: Duration of the cycle in seconds

    Returns:
        Vehicles per second, or 0.0 if duration is 0
    """
    if cycle_duration <= 0:
        return 0.0
    return passed_vehicles / cycle_duration


def calculate_weighted_metrics(results: List[dict]) -> WeightedMetricsSummary:
    """Calculate weighted metrics from cycle results.

    Each metric is weighted by cycle duration (inferred from samples length).
    Throughput is calculated per-cycle then weighted by duration.

    Args:
        results: List of dictionaries containing cycle metrics with keys:
                 - queue_vehicles: Average queue vehicles in the cycle
                 - total_delay: Total delay in vehicle-seconds
                 - passed_vehicles: Number of vehicles that passed through
                 - samples: Per-second queue samples (length = cycle duration)

    Returns:
        WeightedMetricsSummary with weighted averages
    """
    if not results:
        return WeightedMetricsSummary(
            queue_vehicles_avg=0.0,
            total_delay_avg=0.0,
            throughput=0.0,
            total_cycles=0,
            total_duration=0.0,
        )

    # Extract values and calculate durations from samples
    queue_values = []
    delay_values = []
    throughput_values = []
    durations = []

    for r in results:
        # Get cycle duration from samples length (1 sample per second)
        samples = r.get("samples", [])
        duration = float(len(samples)) if samples else 0.0

        if duration > 0:
            queue_values.append(float(r.get("queue_vehicles", 0)))
            delay_values.append(float(r.get("total_delay", 0.0)))

            # Calculate per-cycle throughput
            passed = r.get("passed_vehicles", 0)
            throughput_values.append(calculate_throughput(passed, duration))

            durations.append(duration)

    if not durations:
        return WeightedMetricsSummary(
            queue_vehicles_avg=0.0,
            total_delay_avg=0.0,
            throughput=0.0,
            total_cycles=len(results),
            total_duration=0.0,
        )

    # Calculate weighted averages
    weighted_queue = calculate_weighted_average(queue_values, durations)
    weighted_delay = calculate_weighted_average(delay_values, durations)
    weighted_throughput = calculate_weighted_average(throughput_values, durations)

    return WeightedMetricsSummary(
        queue_vehicles_avg=weighted_queue,
        total_delay_avg=weighted_delay,
        throughput=weighted_throughput,
        total_cycles=len(results),
        total_duration=sum(durations),
    )


def calculate_llm_metrics(results: List["CycleResult"]) -> LLMMetricsSummary:
    """Calculate LLM metrics summary.

    Args:
        results: List of CycleResult objects

    Returns:
        LLMMetricsSummary containing all LLM metrics
    """
    if not results:
        return LLMMetricsSummary(
            format_success_rate=0.0,
            constraint_satisfaction_rate=0.0,
            phase_order_correct_rate=0.0,
            response_time_avg=0.0,
            response_time_max=0.0,
            response_time_min=0.0,
            response_time_std=0.0,
            total_cycles=0,
            format_success_count=0,
            constraint_satisfied_count=0,
        )

    total = len(results)

    # Calculate counts
    format_success_count = sum(1 for r in results if r.format_success)
    constraint_satisfied_count = sum(1 for r in results if r.constraint_satisfied)

    # Note: phase_order_correct is the same as format_success
    # because parse_llm_timing validates phase order during parsing
    phase_order_correct_count = format_success_count

    # Collect response times (exclude None)
    response_times = [r.llm_response_time for r in results if r.llm_response_time is not None]

    # Calculate response time statistics
    if response_times:
        response_time_avg = statistics.mean(response_times)
        response_time_max = max(response_times)
        response_time_min = min(response_times)
        response_time_std = statistics.stdev(response_times) if len(response_times) > 1 else 0.0
    else:
        response_time_avg = response_time_max = response_time_min = response_time_std = 0.0

    return LLMMetricsSummary(
        format_success_rate=format_success_count / total if total > 0 else 0.0,
        constraint_satisfaction_rate=constraint_satisfied_count / total if total > 0 else 0.0,
        phase_order_correct_rate=phase_order_correct_count / total if total > 0 else 0.0,
        response_time_avg=response_time_avg,
        response_time_max=response_time_max,
        response_time_min=response_time_min,
        response_time_std=response_time_std,
        total_cycles=total,
        format_success_count=format_success_count,
        constraint_satisfied_count=constraint_satisfied_count,
    )


def calculate_traffic_metrics(results: List["CycleResult"]) -> TrafficMetricsSummary:
    """Calculate traffic metrics summary.

    Args:
        results: List of CycleResult objects

    Returns:
        TrafficMetricsSummary containing all traffic metrics
    """
    if not results:
        return TrafficMetricsSummary(
            passed_vehicles_avg=0.0,
            passed_vehicles_max=0,
            passed_vehicles_min=0,
            passed_vehicles_std=0.0,
            queue_vehicles_avg=0.0,
            queue_vehicles_max=0,
            queue_vehicles_min=0,
            queue_vehicles_std=0.0,
            total_delay_avg=0.0,
            total_delay_max=0.0,
            total_delay_min=0.0,
            total_delay_std=0.0,
        )

    passed = [r.passed_vehicles for r in results]
    queue = [r.queue_vehicles for r in results]
    delay = [r.total_delay for r in results]

    return TrafficMetricsSummary(
        passed_vehicles_avg=statistics.mean(passed),
        passed_vehicles_max=max(passed),
        passed_vehicles_min=min(passed),
        passed_vehicles_std=statistics.stdev(passed) if len(passed) > 1 else 0.0,
        queue_vehicles_avg=statistics.mean(queue),
        queue_vehicles_max=max(queue),
        queue_vehicles_min=min(queue),
        queue_vehicles_std=statistics.stdev(queue) if len(queue) > 1 else 0.0,
        total_delay_avg=statistics.mean(delay),
        total_delay_max=max(delay),
        total_delay_min=min(delay),
        total_delay_std=statistics.stdev(delay) if len(delay) > 1 else 0.0,
    )
