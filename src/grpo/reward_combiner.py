"""奖励组合器

按权重合并多个奖励函数的结果:
- 格式奖励 (20%)
- 仿真奖励 (80%)
"""

from dataclasses import dataclass
from typing import List


@dataclass
class RewardConfig:
    """奖励权重配置

    Attributes:
        format_weight: 格式奖励权重 (默认 20%)
        simulation_weight: 仿真奖励权重 (默认 80%)
        queue_weight: 排队长度权重 (默认 33%)
        throughput_weight: 通行量权重 (默认 33%)
        waiting_weight: 等待时间权重 (默认 34%)
    """
    format_weight: float = 0.2
    simulation_weight: float = 0.8
    # 仿真指标权重 (等权)
    queue_weight: float = 0.33
    throughput_weight: float = 0.33
    waiting_weight: float = 0.34


def normalize_reward(reward: float, min_val: float, max_val: float) -> float:
    """将奖励归一化到 [-1, 1] 范围

    Args:
        reward: 原始奖励值
        min_val: 最小值
        max_val: 最大值

    Returns:
        归一化后的奖励值
    """
    if max_val == min_val:
        return 0.0
    
    # 归一化到 [0, 1]
    normalized = (reward - min_val) / (max_val - min_val)
    
    # 映射到 [-1, 1]
    return 2 * normalized - 1


def combine_rewards(
    format_rewards: List[float],
    simulation_rewards: List[float],
    config: RewardConfig = None
) -> List[float]:
    """按权重合并格式奖励和仿真奖励

    Args:
        format_rewards: 格式奖励列表
        simulation_rewards: 仿真奖励列表
        config: 奖励权重配置 (默认使用 RewardConfig())

    Returns:
        合并后的奖励列表
    """
    if config is None:
        config = RewardConfig()
    
    assert len(format_rewards) == len(simulation_rewards), \
        f"Format and simulation rewards must have same length: {len(format_rewards)} vs {len(simulation_rewards)}"
    
    combined = []
    for fmt_r, sim_r in zip(format_rewards, simulation_rewards):
        total = config.format_weight * fmt_r + config.simulation_weight * sim_r
        combined.append(total)
    
    return combined


def combine_simulation_metrics(
    queue_scores: List[float],
    throughput_scores: List[float],
    waiting_scores: List[float],
    config: RewardConfig = None
) -> List[float]:
    """合并仿真指标 (排队长度、通行量、等待时间)

    Args:
        queue_scores: 排队长度奖励列表 (越小越好,已归一化)
        throughput_scores: 通行量奖励列表 (越大越好,已归一化)
        waiting_scores: 等待时间奖励列表 (越小越好,已归一化)
        config: 奖励权重配置 (默认使用 RewardConfig())

    Returns:
        合并后的仿真奖励列表
    """
    if config is None:
        config = RewardConfig()
    
    assert len(queue_scores) == len(throughput_scores) == len(waiting_scores), \
        "All metric lists must have same length"
    
    combined = []
    for q, t, w in zip(queue_scores, throughput_scores, waiting_scores):
        total = (
            config.queue_weight * q +
            config.throughput_weight * t +
            config.waiting_weight * w
        )
        combined.append(total)
    
    return combined


if __name__ == "__main__":
    # 自测试
    print("Testing reward_combiner...")

    # 测试 normalize_reward
    print("\n1. Testing normalize_reward...")
    norm = normalize_reward(5.0, 0.0, 10.0)
    assert abs(norm - 0.0) < 0.01, f"Expected 0.0, got {norm}"
    print(f"  ✓ Normalize 5 in [0, 10]: {norm}")

    norm = normalize_reward(0.0, 0.0, 10.0)
    assert abs(norm - (-1.0)) < 0.01, f"Expected -1.0, got {norm}"
    print(f"  ✓ Normalize 0 in [0, 10]: {norm}")

    norm = normalize_reward(10.0, 0.0, 10.0)
    assert abs(norm - 1.0) < 0.01, f"Expected 1.0, got {norm}"
    print(f"  ✓ Normalize 10 in [0, 10]: {norm}")

    # 测试 combine_rewards
    print("\n2. Testing combine_rewards...")
    config = RewardConfig()
    format_rewards = [3.0, 0.0, 1.5]
    simulation_rewards = [1.0, -0.5, 0.5]

    combined = combine_rewards(format_rewards, simulation_rewards, config)
    # 3.0 * 0.2 + 1.0 * 0.8 = 0.6 + 0.8 = 1.4
    assert abs(combined[0] - 1.4) < 0.01, f"Expected 1.4, got {combined[0]}"
    print(f"  ✓ Combine [3.0, 1.0]: {combined[0]}")

    # 0.0 * 0.2 + (-0.5) * 0.8 = 0.0 - 0.4 = -0.4
    assert abs(combined[1] - (-0.4)) < 0.01, f"Expected -0.4, got {combined[1]}"
    print(f"  ✓ Combine [0.0, -0.5]: {combined[1]}")

    # 1.5 * 0.2 + 0.5 * 0.8 = 0.3 + 0.4 = 0.7
    assert abs(combined[2] - 0.7) < 0.01, f"Expected 0.7, got {combined[2]}"
    print(f"  ✓ Combine [1.5, 0.5]: {combined[2]}")

    # 测试 combine_simulation_metrics
    print("\n3. Testing combine_simulation_metrics...")
    queue_scores = [0.5, -0.3, 0.8]
    throughput_scores = [0.7, 0.2, -0.1]
    waiting_scores = [-0.2, 0.5, 0.3]

    combined = combine_simulation_metrics(
        queue_scores, throughput_scores, waiting_scores, config
    )
    # 0.5*0.33 + 0.7*0.33 + (-0.2)*0.34 = 0.165 + 0.231 - 0.068 = 0.328
    expected = 0.5 * 0.33 + 0.7 * 0.33 + (-0.2) * 0.34
    assert abs(combined[0] - expected) < 0.01, f"Expected {expected}, got {combined[0]}"
    print(f"  ✓ Combine metrics [0.5, 0.7, -0.2]: {combined[0]:.3f}")

    # 测试自定义权重
    print("\n4. Testing custom weights...")
    custom_config = RewardConfig(
        format_weight=0.3,
        simulation_weight=0.7,
        queue_weight=0.5,
        throughput_weight=0.3,
        waiting_weight=0.2
    )
    format_rewards = [2.0]
    simulation_rewards = [1.0]
    combined = combine_rewards(format_rewards, simulation_rewards, custom_config)
    # 2.0 * 0.3 + 1.0 * 0.7 = 0.6 + 0.7 = 1.3
    assert abs(combined[0] - 1.3) < 0.01, f"Expected 1.3, got {combined[0]}"
    print(f"  ✓ Custom weights (30%/70%): {combined[0]}")

    print("\n✅ All reward_combiner tests passed!")
