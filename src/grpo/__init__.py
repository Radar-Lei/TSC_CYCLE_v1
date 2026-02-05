"""GRPO (Group Relative Policy Optimization) 模块

包含奖励函数和训练组件:
- format_reward: 格式奖励函数(完全匹配、部分匹配、相位有效性)
- reward_combiner: 奖励组合器(按权重合并格式和仿真奖励)
- sumo_evaluator: SUMO 仿真评估器
- simulation_reward: 仿真奖励函数
"""

from src.grpo.format_reward import (
    match_format_exactly,
    match_format_approximately,
    check_phase_validity,
    extract_json_from_completion,
)

from src.grpo.reward_combiner import (
    combine_rewards,
    combine_simulation_metrics,
    normalize_reward,
    RewardConfig,
)

from .sumo_evaluator import SUMOEvaluator, EvaluationResult, evaluate_single

__all__ = [
    # Format rewards
    "match_format_exactly",
    "match_format_approximately",
    "check_phase_validity",
    "extract_json_from_completion",
    # Reward combiners
    "combine_rewards",
    "combine_simulation_metrics",
    "normalize_reward",
    "RewardConfig",
    # SUMO evaluator
    "SUMOEvaluator",
    "EvaluationResult",
    "evaluate_single",
]
