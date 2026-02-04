"""
自适应采样器

根据交通状态变化率动态调整采样频率:
- 变化率高 (>50%): 立即采样
- 变化率中等 (>30%): 缩短采样间隔
- 变化率低: 使用基础采样间隔

重要: prev_queue_state 在每次 record_sample() 时更新,
      should_sample() 使用它计算变化率
"""

from typing import Dict, Optional


def calculate_queue_change_rate(prev: Dict[str, int], curr: Dict[str, int]) -> float:
    """
    计算排队车辆变化率

    Args:
        prev: 上次的排队状态 {lane_id: queue_count}
        curr: 当前的排队状态 {lane_id: queue_count}

    Returns:
        变化率 [0, ∞), 空 prev 返回 1.0 表示完全变化
    """
    if not prev:
        return 1.0

    # 计算总变化量: sum(|curr[k] - prev.get(k, 0)| for k in curr)
    total_change = sum(abs(curr.get(k, 0) - prev.get(k, 0)) for k in set(curr) | set(prev))

    # 计算基准值: sum(prev.values())
    total_prev = max(sum(prev.values()), 1)

    return total_change / total_prev


class AdaptiveSampler:
    """
    自适应采样器

    根据交通状态变化率动态决定采样时机。

    Attributes:
        base_interval: 基础采样间隔 (秒), 用于低变化率场景
        min_interval: 最小采样间隔 (秒), 用于中等变化率场景
        change_threshold_high: 高变化阈值, 超过立即采样
        change_threshold_medium: 中变化阈值, 超过则使用 min_interval
        last_sample_time: 上次采样的仿真时间
        prev_queue_state: 上次采样时的排队状态 (用于计算变化率)
    """

    def __init__(
        self,
        base_interval: float = 300,
        min_interval: float = 60,
        change_threshold_high: float = 0.5,
        change_threshold_medium: float = 0.3
    ):
        """
        初始化自适应采样器

        Args:
            base_interval: 基础采样间隔 (秒), 默认 300
            min_interval: 最小采样间隔 (秒), 默认 60
            change_threshold_high: 高变化阈值, 默认 0.5
            change_threshold_medium: 中变化阈值, 默认 0.3
        """
        self.base_interval = base_interval
        self.min_interval = min_interval
        self.change_threshold_high = change_threshold_high
        self.change_threshold_medium = change_threshold_medium

        # 状态属性
        self.last_sample_time: Optional[float] = None
        self.prev_queue_state: Dict[str, int] = {}

    def should_sample(
        self,
        current_time: float,
        current_queue_state: Dict[str, int]
    ) -> bool:
        """
        判断是否应该采样

        Args:
            current_time: 当前仿真时间 (秒)
            current_queue_state: 当前排队状态 {lane_id: queue_count}

        Returns:
            True 表示应该采样, False 表示跳过
        """
        # 首次采样
        if self.last_sample_time is None:
            return True

        # 计算距上次采样的时间
        time_since_last = current_time - self.last_sample_time

        # 使用 prev_queue_state 计算变化率
        change_rate = calculate_queue_change_rate(
            self.prev_queue_state,
            current_queue_state
        )

        # 高变化率: 立即采样
        if change_rate > self.change_threshold_high:
            return True

        # 中等变化率: 如果距上次 >= min_interval, 采样
        if change_rate > self.change_threshold_medium:
            return time_since_last >= self.min_interval

        # 低变化率: 如果距上次 >= base_interval, 采样
        return time_since_last >= self.base_interval

    def record_sample(
        self,
        current_time: float,
        current_queue_state: Dict[str, int]
    ):
        """
        记录采样,更新状态

        Args:
            current_time: 当前仿真时间 (秒)
            current_queue_state: 当前排队状态 {lane_id: queue_count}
        """
        self.last_sample_time = current_time
        # 重要: 必须 copy, 避免外部修改影响
        self.prev_queue_state = current_queue_state.copy()

    def reset(self):
        """重置采样器状态"""
        self.last_sample_time = None
        self.prev_queue_state = {}
