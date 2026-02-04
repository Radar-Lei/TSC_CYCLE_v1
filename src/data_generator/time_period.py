"""
时段识别模块

根据仿真时间识别交通时段 (早高峰/晚高峰/平峰)。

时段定义:
- 早高峰: 07:00 - 09:00 (25200 - 32400 秒)
- 晚高峰: 17:00 - 19:00 (61200 - 68400 秒)
- 平峰: 其他时间
"""

from enum import Enum
from typing import List, Dict


class TimePeriod(Enum):
    """
    交通时段枚举

    用于标识训练数据的时段类别,支持时段分布统计和平衡采样。
    """
    MORNING_PEAK = "morning_peak"  # 早高峰 (07:00-09:00)
    EVENING_PEAK = "evening_peak"  # 晚高峰 (17:00-19:00)
    OFF_PEAK = "off_peak"          # 平峰


def identify_time_period(sim_time: float) -> TimePeriod:
    """
    根据仿真时间识别交通时段。

    Args:
        sim_time: 仿真时间 (从 0 开始的秒数, 0 = 00:00:00)

    Returns:
        对应的 TimePeriod 枚举值

    时段定义:
        - 早高峰: 07:00 - 09:00 (25200 - 32400 秒)
        - 晚高峰: 17:00 - 19:00 (61200 - 68400 秒)
        - 平峰: 其他时间

    Example:
        >>> identify_time_period(28800)  # 08:00
        TimePeriod.MORNING_PEAK
        >>> identify_time_period(64800)  # 18:00
        TimePeriod.EVENING_PEAK
        >>> identify_time_period(43200)  # 12:00
        TimePeriod.OFF_PEAK
    """
    # 早高峰: 07:00 - 09:00
    if 25200 <= sim_time < 32400:
        return TimePeriod.MORNING_PEAK

    # 晚高峰: 17:00 - 19:00
    if 61200 <= sim_time < 68400:
        return TimePeriod.EVENING_PEAK

    # 平峰: 其他时间
    return TimePeriod.OFF_PEAK


def get_time_period_stats(samples: List[dict]) -> dict:
    """
    统计各时段的样本数量。

    Args:
        samples: 样本列表,每个样本需包含 'time_period' 字段

    Returns:
        各时段样本数量,格式: {"morning_peak": 1234, "evening_peak": 1156, "off_peak": 7610}

    Example:
        >>> samples = [
        ...     {'time_period': 'morning_peak'},
        ...     {'time_period': 'morning_peak'},
        ...     {'time_period': 'evening_peak'},
        ...     {'time_period': 'off_peak'},
        ... ]
        >>> stats = get_time_period_stats(samples)
        >>> print(stats)
        {'morning_peak': 2, 'evening_peak': 1, 'off_peak': 1}
    """
    # 初始化计数器
    stats = {
        "morning_peak": 0,
        "evening_peak": 0,
        "off_peak": 0
    }

    # 统计各时段样本数
    for sample in samples:
        period = sample.get('time_period')
        if period in stats:
            stats[period] += 1

    return stats


def sim_time_to_hours(sim_time: float) -> float:
    """
    将仿真时间转换为小时数。

    Args:
        sim_time: 仿真时间 (从 0 开始的秒数)

    Returns:
        小时数 (0-24)

    Example:
        >>> sim_time_to_hours(0)
        0.0
        >>> sim_time_to_hours(3600)
        1.0
        >>> sim_time_to_hours(28800)
        8.0
    """
    return sim_time / 3600.0
