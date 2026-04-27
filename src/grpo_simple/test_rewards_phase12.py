import math

from src.grpo_simple import rewards


def setup_module():
    rewards._config = {
        "saturation_target_score": 5.0,
        "saturation_exact_hit_bonus": 0.4,
        "saturation_off_by_one_bonus": 0.15,
        "saturation_near_miss_penalty": 0.35,
        "clip_sensitive_bonus": 0.25,
        "clip_sensitive_penalty": 0.2,
        "invalid_completion_score": 0.0,
    }


def _phase(pred_saturation, min_green=10, max_green=50, phase_id=1):
    return {
        "phase_id": phase_id,
        "pred_saturation": pred_saturation,
        "min_green": min_green,
        "max_green": max_green,
    }


def _actual(final, phase_id=1):
    return {"phase_id": phase_id, "final": final}


def test_phase_saturation_score_has_threshold_aligned_ordering():
    config = rewards._ensure_config()
    expected = _phase(0.8)

    exact = rewards._phase_saturation_score(expected, _actual(40), config)
    near = rewards._phase_saturation_score(expected, _actual(41), config)
    edge_pass = rewards._phase_saturation_score(expected, _actual(44), config)
    near_miss = rewards._phase_saturation_score(expected, _actual(45), config)
    farther = rewards._phase_saturation_score(expected, _actual(48), config)
    far = rewards._phase_saturation_score(expected, _actual(50), config)

    assert exact > near > edge_pass > near_miss
    assert farther == 0.0
    assert far == 0.0


def test_clip_sensitive_cases_reward_boundary_hits_more_than_misses():
    config = rewards._ensure_config()

    low_clip = _phase(0.2, min_green=10, max_green=40)
    low_hit = rewards._phase_saturation_score(low_clip, _actual(10), config)
    low_miss = rewards._phase_saturation_score(low_clip, _actual(14), config)
    assert low_hit > low_miss

    high_clip = _phase(1.2, min_green=10, max_green=40)
    high_hit = rewards._phase_saturation_score(high_clip, _actual(40), config)
    high_miss = rewards._phase_saturation_score(high_clip, _actual(34), config)
    assert high_hit > high_miss


def test_saturation_reward_returns_invalid_score_for_bad_outputs():
    rewards._config["invalid_completion_score"] = -0.25
    prompts = [[{"role": "user", "content": '{"phase_waits": [{"phase_id": 1, "pred_saturation": 0.8, "min_green": 10, "max_green": 50}]}' }]]
    completions = [[{"content": "bad completion"}]]

    scores = rewards.saturation_proportional_reward(prompts, completions)
    assert scores == [-0.25]

    rewards._config["invalid_completion_score"] = 0.0
