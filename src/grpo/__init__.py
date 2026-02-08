"""GRPO (Group Relative Policy Optimization) 模块

包含奖励函数和训练组件:
- format_reward: 格式奖励函数(完全匹配、部分匹配、相位有效性)
- reward_combiner: 奖励组合器(按权重合并格式和仿真奖励)
- sumo_evaluator: SUMO 仿真评估器
- simulation_reward: 仿真奖励函数
- trainer: GRPO 训练配置和训练器创建
- data_loader: 训练数据加载器
"""

from src.grpo.format_reward import (
    graded_format_reward,
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

from .simulation_reward import (
    compute_metric_reward,
    compute_simulation_reward,
    parallel_evaluate,
)

from .trainer import (
    GRPOConfig,
    load_sft_model,
    create_grpo_trainer,
    create_sampling_params,
)

from .data_loader import (
    load_training_data,
    prepare_grpo_dataset,
    get_system_prompt,
)

__all__ = [
    # Format rewards
    "graded_format_reward",
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
    # Simulation reward
    "compute_metric_reward",
    "compute_simulation_reward",
    "parallel_evaluate",
    # Trainer
    "GRPOConfig",
    "load_sft_model",
    "create_grpo_trainer",
    "create_sampling_params",
    # Data loader
    "load_training_data",
    "prepare_grpo_dataset",
    "get_system_prompt",
]
