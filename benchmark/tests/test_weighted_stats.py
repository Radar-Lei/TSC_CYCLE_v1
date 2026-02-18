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


class TestBoundaryConditions:
    """Tests for boundary conditions and edge cases."""

    def test_single_cycle_edge_case(self) -> None:
        """Single cycle should work correctly."""
        mock_result = {
            "queue_vehicles": 15,
            "total_delay": 200.0,
            "passed_vehicles": 45,
            "samples": [5, 10, 15, 20, 25],  # 5 samples = 5 seconds
        }
        results = [mock_result]

        summary = calculate_weighted_metrics(results)
        assert summary.queue_vehicles_avg == 15.0
        assert summary.total_delay_avg == 200.0
        assert abs(summary.throughput - 9.0) < 0.001  # 45/5 = 9.0
        assert summary.total_cycles == 1
        assert summary.total_duration == 5.0

    def test_all_cycles_same_duration(self) -> None:
        """When all cycles have same duration, weighted = simple average."""
        mock_results = [
            {
                "queue_vehicles": 10,
                "total_delay": 100.0,
                "passed_vehicles": 30,
                "samples": [0] * 60,  # 60 seconds
            },
            {
                "queue_vehicles": 20,
                "total_delay": 200.0,
                "passed_vehicles": 60,
                "samples": [0] * 60,   # 60 seconds
            },
            {
                "queue_vehicles": 30,
                "total_delay": 300.0,
                "passed_vehicles": 90,
                "samples": [0] * 60,   # 60 seconds
            },
        ]

        summary = calculate_weighted_metrics(mock_results)

        # With equal weights, should equal simple average
        assert abs(summary.queue_vehicles_avg - 20.0) < 0.001  # (10+20+30)/3
        assert abs(summary.total_delay_avg - 200.0) < 0.001  # (100+200+300)/3
        # Throughput: (0.5 + 1.0 + 1.5) / 3 = 1.0
        assert abs(summary.throughput - 1.0) < 0.001

    def test_cycles_with_very_different_durations(self) -> None:
        """Cycles with very different durations should weight correctly."""
        mock_results = [
            {
                "queue_vehicles": 10,
                "total_delay": 100.0,
                "passed_vehicles": 600,
                "samples": [0] * 600,  # 600 seconds (10 min)
            },
            {
                "queue_vehicles": 100,
                "total_delay": 1000.0,
                "passed_vehicles": 5,
                "samples": [0] * 5,   # 5 seconds
            },
        ]

        summary = calculate_weighted_metrics(mock_results)

        # Long cycle dominates: (10*600 + 100*5) / 605 = 10.74
        expected_queue = (10 * 600 + 100 * 5) / 605
        assert abs(summary.queue_vehicles_avg - expected_queue) < 0.01

        # Delay: (100*600 + 1000*5) / 605 = 107.44
        expected_delay = (100 * 600 + 1000 * 5) / 605
        assert abs(summary.total_delay_avg - expected_delay) < 0.1

        # Throughput: (1.0*600 + 1.0*5) / 605 = 1.0
        # (600/600=1.0, 5/5=1.0)
        assert abs(summary.throughput - 1.0) < 0.001

    def test_cycle_with_zero_samples(self) -> None:
        """Cycle with no samples should be skipped."""
        mock_results = [
            {
                "queue_vehicles": 10,
                "total_delay": 100.0,
                "passed_vehicles": 30,
                "samples": [0] * 60,  # 60 seconds
            },
            {
                "queue_vehicles": 20,
                "total_delay": 200.0,
                "passed_vehicles": 40,
                "samples": [],  # 0 seconds - should be skipped
            },
            {
                "queue_vehicles": 30,
                "total_delay": 300.0,
                "passed_vehicles": 60,
                "samples": [0] * 120,  # 120 seconds
            },
        ]

        summary = calculate_weighted_metrics(mock_results)

        # Only first and third cycles counted
        # Total duration: 60 + 120 = 180
        # Queue: (10*60 + 30*120) / 180 = 23.33
        expected_queue = (10 * 60 + 30 * 120) / 180
        assert abs(summary.queue_vehicles_avg - expected_queue) < 0.01

        # But total_cycles counts all input results
        assert summary.total_cycles == 3
        assert summary.total_duration == 180.0

    def test_all_cycles_zero_samples(self) -> None:
        """All cycles with no samples should return zeros."""
        mock_results = [
            {"queue_vehicles": 10, "total_delay": 100.0, "passed_vehicles": 30, "samples": []},
            {"queue_vehicles": 20, "total_delay": 200.0, "passed_vehicles": 40, "samples": []},
        ]

        summary = calculate_weighted_metrics(mock_results)
        assert summary.queue_vehicles_avg == 0.0
        assert summary.total_delay_avg == 0.0
        assert summary.throughput == 0.0
        assert summary.total_cycles == 2
        assert summary.total_duration == 0.0


class TestEndToEndIntegration:
    """End-to-end integration tests for the weighted statistics pipeline."""

    def test_output_integration(self) -> None:
        """Test that weighted_summary can be used with write_summary_csv_extended."""
        from TSC_CYCLE.benchmark.output import write_summary_csv_extended, create_run_dir
        import tempfile
        import os

        # Create mock weighted summary
        weighted_summary = WeightedMetricsSummary(
            queue_vehicles_avg=15.5,
            total_delay_avg=150.0,
            throughput=0.75,
            total_cycles=10,
            total_duration=600.0,
        )

        # Create temporary directory
        with tempfile.TemporaryDirectory() as tmpdir:
            run_output = create_run_dir(tmpdir, "test-model", "2026-02-18_12-00-00")

            # Write CSV with weighted summary
            csv_path = write_summary_csv_extended(
                run_output=run_output,
                llm_summary={
                    "format_success_rate": 0.9,
                    "constraint_satisfaction_rate": 0.8,
                    "phase_order_correct_rate": 0.9,
                    "response_time": {"avg": 1.5, "max": 3.0, "min": 0.5, "std": 0.5},
                },
                traffic_summary={
                    "passed_vehicles": {"avg": 50, "max": 100, "min": 10, "std": 20},
                    "queue_vehicles": {"avg": 15, "max": 30, "min": 5, "std": 5},
                    "total_delay": {"avg": 150, "max": 300, "min": 50, "std": 50},
                },
                model_name="test-model",
                scenario="test-scenario",
                weighted_summary=weighted_summary.to_dict(),
            )

            # Verify CSV was created and contains throughput
            assert csv_path.exists()
            with open(csv_path, "r") as f:
                content = f.read()
                assert "throughput" in content
                assert "0.75" in content

    def test_report_columns_constant(self) -> None:
        """Test that COMPARISON_COLUMNS in report.py includes throughput.

        Note: We read the file directly to avoid import dependencies in test env.
        """
        import re

        # Read report.py and check COMPARISON_COLUMNS definition
        report_path = __file__.replace("tests/test_weighted_stats.py", "report.py")
        with open(report_path, "r") as f:
            content = f.read()

        # Check that throughput is in COMPARISON_COLUMNS
        assert '"throughput"' in content
        # Verify it's in the COMPARISON_COLUMNS list
        columns_match = re.search(r'COMPARISON_COLUMNS\s*=\s*\[(.*?)\]', content, re.DOTALL)
        assert columns_match is not None
        columns_content = columns_match.group(1)
        assert '"throughput"' in columns_content

