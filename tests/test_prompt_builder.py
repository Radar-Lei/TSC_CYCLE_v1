import json

from tsc_cycle.prompt_builder import (
    TAG_SOLUTION_CLOSE,
    TAG_SOLUTION_OPEN,
    TAG_THINK_CLOSE,
    TAG_THINK_OPEN,
    build_assistant_prefill,
    build_full_assistant,
    build_user_prompt,
    parse_assistant_output,
)

EX_INPUT = {
    "prediction": {
        "as_of": "2026-04-27 00:02:27",
        "phase_waits": [
            {"phase_id": 1, "pred_wait": 0.4, "pred_saturation": 0.0083,
             "min_green": 50, "max_green": 80, "capacity": 48},
            {"phase_id": 2, "pred_wait": 1.0, "pred_saturation": 0.025,
             "min_green": 20, "max_green": 45, "capacity": 40},
        ],
    }
}


def test_user_prompt_contains_required_blocks():
    p = build_user_prompt(EX_INPUT)
    assert "你是交通信号配时优化专家。" in p
    assert "【cycle_predict_input_json】" in p and "【/cycle_predict_input_json】" in p
    assert "硬约束（必须满足）" in p
    assert "<start_working_out>" in p and "</end_working_out>" in p
    assert "<SOLUTION>" in p and "</SOLUTION>" in p


def test_user_prompt_embeds_input_json():
    p = build_user_prompt(EX_INPUT)
    # The framed JSON should be parseable when extracted
    a = p.index("【cycle_predict_input_json】") + len("【cycle_predict_input_json】")
    b = p.index("【/cycle_predict_input_json】", a)
    parsed = json.loads(p[a:b])
    assert parsed == EX_INPUT


def test_assistant_prefill():
    assert build_assistant_prefill() == TAG_THINK_OPEN


def test_full_assistant_roundtrip():
    txt = build_full_assistant("reasoning text", {"1": 60, "2": 30})
    assert txt.startswith(TAG_THINK_OPEN)
    assert TAG_THINK_CLOSE in txt
    assert TAG_SOLUTION_OPEN in txt and TAG_SOLUTION_CLOSE in txt
    reasoning, solution = parse_assistant_output(txt)
    assert reasoning == "reasoning text"
    assert solution == {"1": 60, "2": 30}


def test_parse_with_prefill_only():
    # Output as model would emit: prefilled <start_working_out> NOT in text, only the new close
    body = "step-by-step</end_working_out><SOLUTION>{\"1\":60}</SOLUTION>"
    r, s = parse_assistant_output(body)
    assert r == "step-by-step"
    assert s == {"1": 60}


def test_parse_missing_solution_returns_none():
    body = TAG_THINK_OPEN + "thinking" + TAG_THINK_CLOSE
    r, s = parse_assistant_output(body)
    assert s is None


def test_parse_int_coercion():
    body = TAG_THINK_OPEN + "x" + TAG_THINK_CLOSE + TAG_SOLUTION_OPEN + '{"1": 60.0}' + TAG_SOLUTION_CLOSE
    _, s = parse_assistant_output(body)
    assert s == {"1": 60}


# --- Phase 07-01 new tests (D-02 / D-03 / D-04 / D-07 / D-08) ---

def test_constants_match_protocol():
    # D-02: lock the four protocol literals
    assert TAG_THINK_OPEN == "<start_working_out>"
    assert TAG_THINK_CLOSE == "</end_working_out>"
    assert TAG_SOLUTION_OPEN == "<SOLUTION>"
    assert TAG_SOLUTION_CLOSE == "</SOLUTION>"


def test_parse_rejects_malformed_close_tag():
    body = (
        "<start_working_out>x<end_working_out>"
        "<SOLUTION>{\"1\":60}</SOLUTION>"
    )
    r, s = parse_assistant_output(body)
    assert r == ""
    assert s is None


def test_parse_malformed_close_in_prefill_form():
    body = "step-by-step<end_working_out><SOLUTION>{\"1\":60}</SOLUTION>"
    r, s = parse_assistant_output(body)
    assert r == ""
    assert s is None


def test_parse_rejects_when_both_close_tags_present():
    body = (
        "<start_working_out>x<end_working_out>y</end_working_out>"
        "<SOLUTION>{\"1\":60}</SOLUTION>"
    )
    r, s = parse_assistant_output(body)
    assert r == ""
    assert s is None


def test_user_prompt_uses_slash_close_tag():
    p = build_user_prompt(EX_INPUT)
    assert "</end_working_out>" in p
    assert "<end_working_out>" not in p


def test_full_assistant_uses_slash_close_tag():
    txt = build_full_assistant("r", {"1": 60})
    assert "</end_working_out>" in txt
    assert "<end_working_out>" not in txt
