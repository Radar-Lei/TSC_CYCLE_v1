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
    # Output as model would emit: prefilled <start_working_out> NOT in text, only the close
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
