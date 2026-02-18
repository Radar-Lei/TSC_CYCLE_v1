"""
Unit tests for weighted statistics calculation.

Tests the weighted average formula and throughput calculation logic.
"""

import pytest
from TSC_CYCLE.benchmark.metrics import (
    calculate_weighted_average,
    calculate_throughput,
    calculate_weighted_metrics,
    WeightedMetricsSummary,
)


class TestWeightedAverage:
    """Tests for the weighted average calculation."""

    def test_weighted_average_basic(self) -> None:
        """Basic weighted average calculation.

        Input: values=[10, 20, 30], weights=[1, 2, 3]
        Expected: (10*1 + 20*2 + 30*3) / (1+2+3) = 23.33...
        """
        values = [10.0, 20.0, 30.0]
        weights = [1.0, 2.0, 3.0]
        result = calculate_weighted_average(values, weights)
        expected = (10 * 1 + 20 * 2 + 30 * 3) / (1 + 2 + 3)
        assert abs(result - expected) < 0.001

    def test_weighted_average_zero_weight_skip(self) -> None:
        """Zero weight should be skipped in calculation.

        Input: values=[10, 20, 30], weights=[1, 0, 3]
        Expected: (10*1 + 30*3) / (1+3) = 25.0
        """
        values = [10.0, 20.0, 30.0]
        weights = [1.0, 0.0, 3.0]
        result = calculate_weighted_average(values, weights)
        expected = (10 * 1 + 30 * 3) / (1 + 3)
        assert abs(result - expected) < 0.001

    def test_weighted_average_empty(self) -> None:
        """Empty input should return 0."""
        result = calculate_weighted_average([], [])
        assert result == 0.0

    def test_weighted_average_all_zero_weights(self) -> None:
        """All zero weights should return 0."""
        values = [10.0, 20.0, 30.0]
        weights = [0.0, 0.0, 0.0]
        result = calculate_weighted_average(values, weights)
        assert result == 0.0

    def test_weighted_average_single_value(self) -> None:
        """Single value with weight 1 should return the value."""
        values = [42.0]
        weights = [1.0]
        result = calculate_weighted_average(values, weights)
        assert result == 42.0


class TestThroughputCalculation:
    """Tests for throughput calculation."""

    def test_throughput_calculation(self) -> None:
        """Basic throughput calculation.

        Input: passed_vehicles=60, cycle_duration=120
        Expected: 60/120 = 0.5 vehicles/second
        """
        passed_vehicles = 60
        cycle_duration = 120
        result = calculate_throughput(passed_vehicles, cycle_duration)
        expected = 60 / 120
        assert abs(result - expected) < 0.001

    def test_throughput_zero_duration(self) -> None:
        """Zero duration should return 0 (avoid division by zero)."""
        passed_vehicles = 60
        cycle_duration = 0
        result = calculate_throughput(passed_vehicles, cycle_duration)
        assert result == 0.0

    def test_throughput_weighted_average(self) -> None:
        """Throughput weighted average across multiple cycles.

        Scenario: Two cycles
        - Cycle 1: passed=60, duration=120, throughput=0.5
        - Cycle 2: passed=30, duration=60, throughput=0.5
        Expected: (0.5*120 + 0.5*60) / (120+60) = 0.5
        """
        # Throughput for each cycle
        throughput_1 = calculate_throughput(60, 120)  # 0.5
        throughput_2 = calculate_throughput(30, 60)   # 0.5

        # Weighted average by duration
        durations = [120.0, 60.0]
        throughputs = [throughput_1, throughput_2]
        weighted_avg = calculate_weighted_average(throughputs, durations)

        expected = 0.5
        assert abs(weighted_avg - expected) < 0.001

    def test_throughput_different_rates(self) -> None:
        """Throughput with different rates across cycles.

        Scenario: Two cycles with different throughput rates
        - Cycle 1: passed=60, duration=120, throughput=0.5
        - Cycle 2: passed=90, duration=60, throughput=1.5
        Expected: (0.5*120 + 1.5*60) / (120+60) = (60 + 90) / 180 = 0.833...
        """
        throughput_1 = calculate_throughput(60, 120)  # 0.5
        throughput_2 = calculate_throughput(90, 60)   # 1.5

        durations = [120.0, 60.0]
        throughputs = [throughput_1, throughput_2]
        weighted_avg = calculate_weighted_average(throughputs, durations)

        expected = (60 + 90) / 180
        assert abs(weighted_avg - expected) < 0.001


class TestWeightedMetricsSummary:
    """Tests for WeightedMetricsSummary dataclass."""

    def test_weighted_metrics_summary_creation(self) -> None:
        """Test creating a WeightedMetricsSummary instance."""
        summary = WeightedMetricsSummary(
            queue_vehicles_avg=10.5,
            total_delay_avg=150.0,
            throughput=0.75,
            total_cycles=5,
            total_duration=300.0,
        )
        assert summary.queue_vehicles_avg == 10.5
        assert summary.total_delay_avg == 150.0
        assert summary.throughput == 0.75
        assert summary.total_cycles == 5
        assert summary.total_duration == 300.0

    def test_weighted_metrics_summary_to_dict(self) -> None:
        """Test to_dict method for JSON output."""
        summary = WeightedMetricsSummary(
            queue_vehicles_avg=10.5,
            total_delay_avg=150.0,
            throughput=0.75,
            total_cycles=5,
            total_duration=300.0,
        )
        d = summary.to_dict()
        assert d["queue_vehicles_avg"] == 10.5
        assert d["total_delay_avg"] == 150.0
        assert d["throughput"] == 0.75
        assert d["total_cycles"] == 5
        assert d["total_duration"] == 300.0


class TestCalculateWeightedMetrics:
    """Tests for calculate_weighted_metrics function with CycleResult-like data."""

    def test_calculate_weighted_metrics_empty(self) -> None:
        """Empty results should return zeros."""
        summary = calculate_weighted_metrics([])
        assert summary.queue_vehicles_avg == 0.0
        assert summary.total_delay_avg == 0.0
        assert summary.throughput == 0.0
        assert summary.total_cycles == 0
        assert summary.total_duration == 0.0

    def test_calculate_weighted_metrics_single_cycle(self) -> None:
        """Single cycle should return that cycle's values."""
        # Create a mock cycle result with metrics
        mock_result = {
            "queue_vehicles": 10,
            "total_delay": 100.0,
            "passed_vehicles": 30,
            "samples": [0] * 60,  # 60 samples = 60 seconds
        }
        results = [mock_result]

        summary = calculate_weighted_metrics(results)
        assert summary.queue_vehicles_avg == 10.0
        assert summary.total_delay_avg == 100.0
        assert abs(summary.throughput - 0.5) < 0.001  # 30/60
        assert summary.total_cycles == 1
        assert summary.total_duration == 60.0

    def test_calculate_weighted_metrics_multiple_cycles(self) -> None:
        """Multiple cycles should be weighted by duration."""
        mock_results = [
            {
                "queue_vehicles": 10,
                "total_delay": 100.0,
                "passed_vehicles": 60,
                "samples": [0] * 120,  # 120 seconds
            },
            {
                "queue_vehicles": 20,
                "total_delay": 200.0,
                "passed_vehicles": 30,
                "samples": [0] * 60,   # 60 seconds
            },
        ]

        summary = calculate_weighted_metrics(mock_results)

        # Weighted average queue: (10*120 + 20*60) / 180 = 13.33
        expected_queue = (10 * 120 + 20 * 60) / 180
        assert abs(summary.queue_vehicles_avg - expected_queue) < 0.01

        # Weighted average delay: (100*120 + 200*60) / 180 = 133.33
        expected_delay = (100 * 120 + 200 * 60) / 180
        assert abs(summary.total_delay_avg - expected_delay) < 0.01

        # Throughput: (0.5*120 + 0.5*60) / 180 = 0.5
        # (60/120=0.5, 30/60=0.5)
        assert abs(summary.throughput - 0.5) < 0.001

        assert summary.total_cycles == 2
        assert summary.total_duration == 180.0
