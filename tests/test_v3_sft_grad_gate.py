from __future__ import annotations

import math


REQUIREMENTS = ["SFT-06"]


def _rows(count: int, *, grad_norm: float = 1.0, loss: float = 0.25) -> list[dict]:
    return [{"step": step + 1, "grad_norm": grad_norm, "loss": loss} for step in range(count)]


def test_sft_06_d07_grad_gate_passes_with_200_finite_steps_and_p99_below_3() -> None:
    from tsc_cycle.student.sft_v3 import evaluate_grad_gate  # noqa: PLC0415

    result = evaluate_grad_gate(_rows(200, grad_norm=2.999), gate_steps=200)

    assert result["ok"] is True
    assert result["steps_evaluated"] == 200
    assert result["grad_norm_p99"] < 3.0
    assert result["loss_finite"] is True
    assert result["requirements_covered"] == REQUIREMENTS


def test_sft_06_d07_grad_gate_fails_when_fewer_than_200_steps_are_available() -> None:
    from tsc_cycle.student.sft_v3 import evaluate_grad_gate  # noqa: PLC0415

    result = evaluate_grad_gate(_rows(199, grad_norm=1.0), gate_steps=200)

    assert result["ok"] is False
    assert any(item["gate"] == "min_steps" for item in result["fatal_failures"])


def test_sft_06_d07_grad_gate_fails_on_nan_or_inf_loss() -> None:
    from tsc_cycle.student.sft_v3 import evaluate_grad_gate  # noqa: PLC0415

    nan_result = evaluate_grad_gate([*_rows(199), {"step": 200, "grad_norm": 1.0, "loss": math.nan}], gate_steps=200)
    inf_result = evaluate_grad_gate([*_rows(199), {"step": 200, "grad_norm": 1.0, "loss": math.inf}], gate_steps=200)

    assert nan_result["ok"] is False
    assert inf_result["ok"] is False
    assert any(item["gate"] == "loss_finite" for item in nan_result["fatal_failures"])
    assert any(item["gate"] == "loss_finite" for item in inf_result["fatal_failures"])


def test_sft_06_d07_grad_gate_uses_strict_3_0_p99_boundary() -> None:
    from tsc_cycle.student.sft_v3 import evaluate_grad_gate  # noqa: PLC0415

    passing = evaluate_grad_gate(_rows(200, grad_norm=2.999), gate_steps=200)
    failing = evaluate_grad_gate(_rows(200, grad_norm=3.0), gate_steps=200)

    assert passing["ok"] is True
    assert passing["grad_norm_p99"] < 3.0
    assert failing["ok"] is False
    assert failing["grad_norm_p99"] >= 3.0
    assert any(item["gate"] == "grad_norm_p99" for item in failing["fatal_failures"])
