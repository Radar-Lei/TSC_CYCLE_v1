"""
噪声和波动生成模块

提供为训练数据添加随机噪声和波动的功能:
- add_gaussian_noise: 为数值添加高斯噪声
- apply_time_variation: 为时间配置添加随机波动
- calculate_saturation: 计算饱和度
"""

import random
from typing import Tuple


def add_gaussian_noise(
    value: float,
    std_ratio: float = 0.1,
    min_val: float = 0.0
) -> float:
    """
    为真实值添加高斯噪声。

    用于增加训练数据多样性,模拟真实场景中的测量误差和变化。

    Args:
        value: 原始真实值
        std_ratio: 标准差占真实值的比例 (默认 10%)
        min_val: 最小值约束 (默认 0, 排队车辆不能为负)

    Returns:
        添加噪声后的值

    Example:
        >>> add_gaussian_noise(10.0, std_ratio=0.1)
        10.234  # 约在 10 ± 1 范围内
    """
    # 计算标准差: std = |value| * std_ratio
    std = abs(value) * std_ratio

    # 生成高斯噪声
    noise = random.gauss(0, std)

    # 添加噪声并应用最小值约束
    noisy_value = value + noise
    return max(noisy_value, min_val)


def apply_time_variation(
    min_dur: float,
    max_dur: float,
    variation_range: Tuple[int, int] = (2, 5)
) -> Tuple[int, int]:
    """
    在原始 minDur/maxDur 基础上添加随机波动。

    用于生成训练数据多样性,避免过拟合固定时间配置。

    Args:
        min_dur: 原始最小持续时间
        max_dur: 原始最大持续时间
        variation_range: 波动范围 (默认 2-5 秒)

    Returns:
        (new_min, new_max) 波动后的时间配置,均为整数秒

    边界约束:
        - new_min: 5-60 秒
        - new_max: 30-120 秒
        - new_min <= new_max

    Example:
        >>> apply_time_variation(20.0, 60.0)
        (18, 63)  # ±2-5 秒波动
    """
    # 生成随机波动量: ±2-5 秒
    delta_min = random.randint(*variation_range) * random.choice([-1, 1])
    delta_max = random.randint(*variation_range) * random.choice([-1, 1])

    # 应用波动
    new_min = min_dur + delta_min
    new_max = max_dur + delta_max

    # 边界验证
    # 最小绿灯时间: 5-60 秒
    new_min = max(5, min(new_min, 60))
    # 最大绿灯时间: 30-120 秒
    new_max = max(30, min(new_max, 120))

    # 确保 new_min <= new_max
    if new_min > new_max:
        # 如果违反,交换两者
        new_min, new_max = new_max, new_min

    # 返回整数秒
    return int(new_min), int(new_max)


def calculate_saturation(queue_vehicles: float, capacity: int) -> float:
    """
    计算饱和度。

    饱和度 = 排队车辆数 / 容量
    - 饱和度 < 1: 容量充足
    - 饱和度 = 1: 刚好满载
    - 饱和度 > 1: 超负荷,需要更多绿灯时间

    Args:
        queue_vehicles: 排队车辆数
        capacity: 相位容量 (车辆容纳数)

    Returns:
        饱和度,保留 4 位小数

    Example:
        >>> calculate_saturation(15.0, 30)
        0.5
        >>> calculate_saturation(64.0, 31)
        2.0645
    """
    if capacity == 0:
        return 0.0

    saturation = queue_vehicles / capacity
    return round(saturation, 4)
