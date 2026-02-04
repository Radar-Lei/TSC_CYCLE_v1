"""
时间配置生成模块

提供相位时间配置的生成和变化功能。
"""

import random
from typing import Tuple


def generate_time_config(
    original_duration: float,
    original_min_dur: float = 0.0,
    original_max_dur: float = 0.0
) -> Tuple[float, float]:
    """
    生成相位的 minDur 和 maxDur 时间配置。

    优先使用 SUMO 文件中提供的原始值,缺失值则随机生成。

    Args:
        original_duration: 原始相位持续时间 (未使用,保留用于未来扩展)
        original_min_dur: SUMO 文件中的 minDur 值 (0 表示缺失)
        original_max_dur: SUMO 文件中的 maxDur 值 (0 表示缺失)

    Returns:
        (min_dur, max_dur) 元组,值在 [5, 120] 范围内

    用户决策:
        - 优先从 SUMO 文件读取 minDur/maxDur
        - 缺失值处理: 在 5-120 秒之间随机生成
        - 边界验证: minDur >= 5, maxDur <= 120
    """
    # 处理 min_dur
    if original_min_dur > 0:
        min_dur = original_min_dur
    else:
        # 随机生成 min_dur (5-30 秒)
        min_dur = random.uniform(5, 30)

    # 处理 max_dur
    if original_max_dur > 0:
        max_dur = original_max_dur
    else:
        # 随机生成 max_dur (60-120 秒)
        max_dur = random.uniform(60, 120)

    # 边界验证
    min_dur = max(5.0, min(min_dur, 120.0))
    max_dur = max(5.0, min(max_dur, 120.0))

    # 确保 min_dur <= max_dur
    if min_dur > max_dur:
        min_dur, max_dur = max_dur, min_dur

    return min_dur, max_dur


def apply_time_variation(min_dur: float, max_dur: float) -> Tuple[float, float]:
    """
    在原始时间配置基础上应用随机波动。

    用于生成训练数据的多样性,避免过拟合固定时间配置。

    Args:
        min_dur: 原始最小持续时间
        max_dur: 原始最大持续时间

    Returns:
        波动后的 (min_dur, max_dur) 元组

    用户决策:
        - 在原始值基础上 ±2-5 秒随机波动
    """
    # 生成随机波动量: ±2-5 秒
    delta_min = random.randint(2, 5) * random.choice([-1, 1])
    delta_max = random.randint(2, 5) * random.choice([-1, 1])

    # 应用波动
    new_min_dur = min_dur + delta_min
    new_max_dur = max_dur + delta_max

    # 边界验证
    new_min_dur = max(5.0, min(new_min_dur, 120.0))
    new_max_dur = max(5.0, min(new_max_dur, 120.0))

    # 确保 min_dur <= max_dur (如果违反,交换)
    if new_min_dur > new_max_dur:
        new_min_dur, new_max_dur = new_max_dur, new_min_dur

    return new_min_dur, new_max_dur
