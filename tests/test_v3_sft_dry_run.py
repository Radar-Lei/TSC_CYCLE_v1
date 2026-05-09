from __future__ import annotations


REQUIREMENTS = ["SFT-04", "SFT-06"]


def _passing_report(**overrides):
    report = {
        "sample_count": 500,
        "ood_hard_constraint_pass_rate": 0.95,
        "grad_gate": {"ok": True, "steps": 200, "grad_norm_p99": 2.999, "loss_finite": True},
        "adapter_path": "runs/v3.0-9B-20260509T000000Z/dry_run/adapter",
        "checkpoint_path": "runs/v3.0-9B-20260509T000000Z/dry_run/checkpoint-200",
    }
    report.update(overrides)
    return report


def test_sft_04_d07_dry_run_gate_passes_at_exact_500_samples_and_095_rate() -> None:
    from tsc_cycle.v3_gates.sft_dry_run_v3 import evaluate_dry_run_gate  # noqa: PLC0415

    result = evaluate_dry_run_gate(_passing_report(ood_hard_constraint_pass_rate=0.95))

    assert result["ok"] is True
    assert result["full_run_allowed"] is True
    assert result["gates"]["sample_count"]["ok"] is True
    assert result["gates"]["ood_hard_constraint_pass_rate"]["ok"] is True
    assert result["requirements_covered"] == REQUIREMENTS


def test_sft_04_d07_dry_run_gate_fails_closed_below_500_samples() -> None:
    from tsc_cycle.v3_gates.sft_dry_run_v3 import evaluate_dry_run_gate  # noqa: PLC0415

    result = evaluate_dry_run_gate(_passing_report(sample_count=499, ood_hard_constraint_pass_rate=0.99))

    assert result["ok"] is False
    assert result["full_run_allowed"] is False
    assert any(item["gate"] == "sample_count" for item in result["fatal_failures"])


def test_sft_04_d07_dry_run_gate_uses_strict_095_boundary() -> None:
    from tsc_cycle.v3_gates.sft_dry_run_v3 import evaluate_dry_run_gate  # noqa: PLC0415

    passing = evaluate_dry_run_gate(_passing_report(ood_hard_constraint_pass_rate=0.95))
    failing = evaluate_dry_run_gate(_passing_report(ood_hard_constraint_pass_rate=0.949999))

    assert passing["ok"] is True
    assert passing["full_run_allowed"] is True
    assert failing["ok"] is False
    assert failing["full_run_allowed"] is False
    assert any(item["gate"] == "ood_hard_constraint_pass_rate" for item in failing["fatal_failures"])


def test_sft_04_d07_adapter_or_checkpoint_existence_alone_cannot_false_green() -> None:
    from tsc_cycle.v3_gates.sft_dry_run_v3 import evaluate_dry_run_gate  # noqa: PLC0415

    result = evaluate_dry_run_gate(
        {
            "adapter_path": "runs/v3.0-9B-20260509T000000Z/dry_run/adapter",
            "checkpoint_path": "runs/v3.0-9B-20260509T000000Z/dry_run/checkpoint-200",
        }
    )

    assert result["ok"] is False
    assert result["full_run_allowed"] is False
    assert {item["gate"] for item in result["fatal_failures"]} >= {
        "sample_count",
        "ood_hard_constraint_pass_rate",
        "grad_gate",
    }


def test_sft_04_d07_dry_run_gate_counts_generation_time_in_one_hour_budget() -> None:
    from tsc_cycle.v3_gates.sft_dry_run_v3 import evaluate_dry_run_gate  # noqa: PLC0415

    result = evaluate_dry_run_gate(_passing_report(elapsed_seconds=3500, wall_clock_generation_seconds=101))

    assert result["ok"] is False
    assert result["full_run_allowed"] is False
    assert any(item["gate"] == "elapsed_seconds" for item in result["fatal_failures"])


def test_sft_04_d07_raw_solution_lint_rejects_non_integer_outputs() -> None:
    from tsc_cycle.v3_gates.sft_dry_run_v3 import parse_solution_block_raw  # noqa: PLC0415
    from tsc_cycle.constraint_lint import validate  # noqa: PLC0415

    raw = parse_solution_block_raw('<start_working_out>x<end_working_out><SOLUTION>{"1": 20.9}</SOLUTION>')
    lint = validate(
        {"prediction": {"phase_waits": [{"phase_id": 1, "min_green": 20, "max_green": 45}]}},
        raw,
    )

    assert raw == {"1": 20.9}
    assert lint.ok is False
    assert any(item["kind"] == "not_integer" for item in lint.violations)
