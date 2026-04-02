import json

from src.grpo_simple.rewards import (
    calculate_target_green,
    check_constraints,
    init_rewards,
    match_format_exactly,
    saturation_proportional_reward,
)


def _build_prompt(phase_waits):
    payload = {"prediction": {"phase_waits": phase_waits}}
    return [
        {"role": "system", "content": "系统提示"},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False, indent=2)},
    ]


def _build_completion(solution):
    return [{
        "content": (
            "这是推理过程。"
            "<end_working_out>"
            f"<SOLUTION>{json.dumps(solution, ensure_ascii=False)}</SOLUTION>"
        )
    }]


def setup_module(module):
    init_rewards("config/config.json")


def test_simple_grpo_data_defaults_are_isolated():
    with open("config/config.json", "r", encoding="utf-8") as f:
        config = json.load(f)

    assert config["paths"]["grpo_simple_data_dir"] == "outputs/grpo_simple"


def test_calculate_target_green_uses_saturation_and_clipping():
    assert calculate_target_green(
        {"pred_saturation": 0.1, "min_green": 5, "max_green": 100}
    ) == 10
    assert calculate_target_green(
        {"pred_saturation": 0.1, "min_green": 20, "max_green": 100}
    ) == 20
    assert calculate_target_green(
        {"pred_saturation": 1.5, "min_green": 10, "max_green": 60}
    ) == 60


def test_saturation_reward_prefers_target_allocation():
    phase_waits = [
        {"phase_id": 0, "pred_saturation": 0.1, "min_green": 5, "max_green": 100},
        {"phase_id": 1, "pred_saturation": 0.8, "min_green": 10, "max_green": 100},
    ]
    prompt = _build_prompt(phase_waits)

    near_target = _build_completion(
        [{"phase_id": 0, "final": 10}, {"phase_id": 1, "final": 80}]
    )
    far_target = _build_completion(
        [{"phase_id": 0, "final": 90}, {"phase_id": 1, "final": 10}]
    )

    scores = saturation_proportional_reward(
        prompts=[prompt, prompt],
        completions=[near_target, far_target],
    )

    assert scores[0] > scores[1]


def test_saturation_reward_rejects_out_of_range_solution():
    phase_waits = [
        {"phase_id": 0, "pred_saturation": 0.5, "min_green": 10, "max_green": 60},
    ]
    prompt = _build_prompt(phase_waits)
    invalid_completion = _build_completion([{"phase_id": 0, "final": 80}])

    scores = saturation_proportional_reward(
        prompts=[prompt],
        completions=[invalid_completion],
    )

    assert scores == [0.0]


def test_constraint_and_format_reward_still_apply():
    phase_waits = [
        {"phase_id": 0, "pred_saturation": 0.5, "min_green": 10, "max_green": 60},
        {"phase_id": 1, "pred_saturation": 0.2, "min_green": 10, "max_green": 60},
    ]
    prompt = _build_prompt(phase_waits)
    valid_completion = _build_completion(
        [{"phase_id": 0, "final": 30}, {"phase_id": 1, "final": 12}]
    )
    wrong_order_completion = _build_completion(
        [{"phase_id": 1, "final": 30}, {"phase_id": 0, "final": 12}]
    )

    format_scores = match_format_exactly([valid_completion, wrong_order_completion])
    constraint_scores = check_constraints(
        prompts=[prompt, prompt],
        completions=[valid_completion, wrong_order_completion],
    )

    assert format_scores == [3.0, 3.0]
    assert constraint_scores[0] > constraint_scores[1]
