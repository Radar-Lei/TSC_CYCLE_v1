from __future__ import annotations

import copy

from tsc_cycle.constraint_lint import validate
from tsc_cycle.prompt_builder import parse_assistant_output

GOOD_OUTPUT = "<start_working_out>各相位均在上下限内，按饱和度分配。</end_working_out><SOLUTION>{\"1\":30,\"2\":40}</SOLUTION>"
GOOD_INPUT = {
    "prediction": {
        "phase_waits": [
            {"phase_id": 1, "min_green": 10, "max_green": 60, "pred_wait": 12, "pred_saturation": 0.3, "capacity": 40},
            {"phase_id": 2, "min_green": 15, "max_green": 70, "pred_wait": 20, "pred_saturation": 0.5, "capacity": 40},
        ]
    }
}


def _contract():
    from tsc_cycle.v4_gates.phase9_smoke import evaluate_pretrain_smoke_report  # noqa: PLC0415

    return evaluate_pretrain_smoke_report


def _good_report() -> dict:
    return {
        "phase8_gate": {"ok": True, "next_phase_allowed": True, "requirements_covered": ["DATA4B-01", "DATA4B-02", "DATA4B-03", "DATA4B-04", "DATA4B-05"]},
        "tokenizer_leakage": {
            "native_think_text_count": 0,
            "native_think_token_id_count": 0,
            "native_think_token_ids": [151667, 151668],
            "checked_untruncated_ids": True,
        },
        "sample_format": {
            "examples_checked": 2,
            "raw_text_protocol": True,
            "malformed_close_tag_count": 0,
            "native_think_text_count": 0,
            "contains_start_working_out": True,
            "contains_end_working_out_close": True,
            "contains_solution_tags": True,
            "packing": False,
            "chat_template_used": False,
        },
        "minimal_train_step": {
            "ran": True,
            "global_step": 1,
            "loss": 1.234,
            "finite_loss": True,
            "adapter_path": "runs/v4.0-4B-20260510T010203Z/smoke/adapter",
            "checkpoint_path": "runs/v4.0-4B-20260510T010203Z/smoke/checkpoint-1",
            "saved": True,
        },
        "generated_outputs": [
            {
                "sample_id": "smoke-1",
                "input": GOOD_INPUT,
                "text": GOOD_OUTPUT,
            }
        ],
    }


def _assert_blocks(mutator, expected_gate: str) -> None:
    report = _good_report()
    mutator(report)
    payload = _contract()(report)
    assert payload["ok"] is False
    assert payload["next_phase_allowed"] is False
    assert any(failure["gate"] == expected_gate for failure in payload["fatal_failures"])


def test_parse_and_lint_fixture_is_representative() -> None:
    reasoning, solution = parse_assistant_output(GOOD_OUTPUT)
    assert reasoning.startswith("各相位")
    assert solution == {"1": 30, "2": 40}
    assert validate(GOOD_INPUT, solution).ok is True


def test_evaluate_pretrain_smoke_report_passes_only_for_complete_green_report() -> None:
    payload = _contract()(_good_report())

    assert payload["ok"] is True
    assert payload["next_phase_allowed"] is True
    assert payload["requirements_covered"] == ["SFT4B-02"]
    assert payload["gates"]["phase8_handoff"]["ok"] is True
    assert payload["gates"]["tokenizer_leakage"]["ok"] is True
    assert payload["gates"]["sample_format"]["ok"] is True
    assert payload["gates"]["minimal_train_step"]["ok"] is True
    assert payload["gates"]["solution_parse_and_lint"]["ok"] is True


def test_smoke_gate_fails_closed_without_phase8_handoff() -> None:
    _assert_blocks(lambda report: report.__setitem__("phase8_gate", {"ok": True, "next_phase_allowed": False}), "phase8_handoff")


def test_smoke_gate_blocks_native_think_text_and_token_ids() -> None:
    _assert_blocks(lambda report: report["tokenizer_leakage"].__setitem__("native_think_text_count", 1), "tokenizer_leakage")
    _assert_blocks(lambda report: report["tokenizer_leakage"].__setitem__("native_think_token_id_count", 1), "tokenizer_leakage")


def test_smoke_gate_blocks_bad_sample_protocol_variants() -> None:
    _assert_blocks(lambda report: report["sample_format"].__setitem__("malformed_close_tag_count", 1), "sample_format")
    _assert_blocks(lambda report: report["sample_format"].__setitem__("native_think_text_count", 1), "sample_format")
    _assert_blocks(lambda report: report["sample_format"].__setitem__("packing", True), "sample_format")
    _assert_blocks(lambda report: report["sample_format"].__setitem__("chat_template_used", True), "sample_format")


def test_smoke_gate_requires_real_minimal_train_step_and_saved_adapter() -> None:
    _assert_blocks(lambda report: report["minimal_train_step"].__setitem__("global_step", 0), "minimal_train_step")
    _assert_blocks(lambda report: report["minimal_train_step"].__setitem__("loss", float("nan")), "minimal_train_step")
    _assert_blocks(lambda report: report["minimal_train_step"].__setitem__("saved", False), "minimal_train_step")
    _assert_blocks(lambda report: report["minimal_train_step"].__setitem__("adapter_path", "runs/v3.0-9B-20260510/smoke/adapter"), "minimal_train_step")


def test_smoke_gate_blocks_unparseable_solution_and_lint_violations() -> None:
    bad_parse = copy.deepcopy(_good_report())
    bad_parse["generated_outputs"][0]["text"] = "<start_working_out>x<end_working_out><SOLUTION>{bad}</SOLUTION>"
    payload = _contract()(bad_parse)
    assert payload["ok"] is False
    assert any(failure["gate"] == "solution_parse_and_lint" and "parse" in failure["reason"] for failure in payload["fatal_failures"])

    lint_bad = copy.deepcopy(_good_report())
    lint_bad["generated_outputs"][0]["text"] = "<start_working_out>x</end_working_out><SOLUTION>{\"1\":5,\"2\":40}</SOLUTION>"
    payload = _contract()(lint_bad)
    assert payload["ok"] is False
    assert any(failure["gate"] == "solution_parse_and_lint" and "lint" in failure["reason"] for failure in payload["fatal_failures"])


def test_smoke_gate_rejects_native_tags_inside_generated_outputs() -> None:
    native = copy.deepcopy(_good_report())
    native["generated_outputs"][0]["text"] = "<think>bad</think><SOLUTION>{\"1\":30,\"2\":40}</SOLUTION>"
    payload = _contract()(native)
    assert payload["ok"] is False
    assert any(failure["gate"] == "solution_parse_and_lint" for failure in payload["fatal_failures"])
