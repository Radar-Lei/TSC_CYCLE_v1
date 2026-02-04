"""
交通数据收集器

从 SUMO 仿真中收集交通数据,用于生成训练样本。

主要功能:
- TrafficCollector: 从 SUMO 收集各相位的排队车辆数据
- load_phase_config: 加载 Phase 1 输出的相位配置
- estimate_capacity: 估算相位容量
"""

import json
from typing import List, Dict, Any

try:
    import traci
    TRACI_AVAILABLE = True
except ImportError:
    TRACI_AVAILABLE = False


def load_phase_config(config_path: str) -> Dict[str, Any]:
    """
    从 JSON 文件加载 Phase 1 输出的相位配置。

    Args:
        config_path: phase_config.json 文件路径

    Returns:
        相位配置字典,包含:
        - metadata: 元数据 (total_tl, valid_tl, skipped_tl, ...)
        - traffic_lights: 各信号灯的相位配置

    Example:
        >>> config = load_phase_config('output/phase_config.json')
        >>> print(config['metadata']['valid_tl'])
        18
    """
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def estimate_capacity(green_lanes: List[str]) -> int:
    """
    基于绿灯车道数量估算相位容量。

    简单估算公式: 每条车道约能容纳 15 辆车

    Args:
        green_lanes: 绿灯车道列表

    Returns:
        估算容量,范围 15-60

    Example:
        >>> estimate_capacity(['lane1', 'lane2'])
        30
        >>> estimate_capacity(['lane1', 'lane2', 'lane3', 'lane4'])
        60
    """
    # 每条车道约 15 辆车
    capacity = len(green_lanes) * 15

    # 边界约束: 15-60
    capacity = max(15, min(capacity, 60))

    return capacity


class TrafficCollector:
    """
    交通数据收集器

    从 SUMO 仿真中收集交通数据,包括排队车辆数、车道信息等。

    Attributes:
        phase_config: Phase 1 输出的相位配置
        _tl_phases: 缓存的信号灯相位映射
    """

    def __init__(self, phase_config: Dict[str, Any]):
        """
        初始化收集器。

        Args:
            phase_config: Phase 1 输出的相位配置 (从 phase_config.json 加载)
        """
        self.phase_config = phase_config
        self._tl_phases = phase_config.get('traffic_lights', {})

    def get_queue_vehicles(self, tl_id: str, phase_index: int) -> int:
        """
        获取指定信号灯指定相位控制车道的排队车辆数。

        Args:
            tl_id: 信号灯 ID
            phase_index: 相位索引

        Returns:
            排队车辆总数 (该相位所有绿灯车道的停止车辆数之和)

        Note:
            - 需要 SUMO 仿真已启动并通过 traci 连接
            - 如果 traci 不可用或调用失败,返回默认值 0
        """
        if not TRACI_AVAILABLE:
            return 0

        # 获取该相位的绿灯车道
        if tl_id not in self._tl_phases:
            return 0

        # 查找对应的相位
        phase_info = None
        for phase in self._tl_phases[tl_id]:
            if phase['phase_index'] == phase_index:
                phase_info = phase
                break

        if phase_info is None:
            return 0

        green_lanes = phase_info.get('green_lanes', [])

        # 累加各车道的停止车辆数
        total_queue = 0
        try:
            for lane_id in green_lanes:
                # 使用 traci 获取车道上的停止车辆数
                halting_count = traci.lane.getLastStepHaltingNumber(lane_id)
                total_queue += halting_count
        except Exception:
            # traci 调用失败时返回默认值
            return 0

        return total_queue

    def collect_phase_data(self, tl_id: str) -> List[Dict[str, Any]]:
        """
        收集指定信号灯所有相位的数据。

        Args:
            tl_id: 信号灯 ID

        Returns:
            相位数据列表,每个元素包含:
            - phase_index: 相位索引
            - queue_vehicles: 排队车辆数 (从 traci 获取)
            - green_lanes: 绿灯车道列表
            - min_dur: 最小持续时间 (从 phase_config 读取)
            - max_dur: 最大持续时间 (从 phase_config 读取)

        Note:
            此格式可直接用于创建 PhaseWait 对象:
            - phase_id = phase_index
            - pred_saturation = calculate_saturation(add_gaussian_noise(queue_vehicles), capacity)
            - min_green, max_green = apply_time_variation(min_dur, max_dur)
            - capacity = estimate_capacity(green_lanes)

        Example:
            >>> collector = TrafficCollector(config)
            >>> data = collector.collect_phase_data('1159176756')
            >>> print(data[0])
            {
                'phase_index': 0,
                'queue_vehicles': 15,
                'green_lanes': ['-100289006#0_0', '-345684193#5_0'],
                'min_dur': 21.11922249864318,
                'max_dur': 76.31762830149657
            }
        """
        if tl_id not in self._tl_phases:
            return []

        phase_data = []
        for phase in self._tl_phases[tl_id]:
            phase_index = phase['phase_index']

            # 从 traci 获取排队车辆数
            queue_vehicles = self.get_queue_vehicles(tl_id, phase_index)

            # 构建相位数据
            data = {
                'phase_index': phase_index,
                'queue_vehicles': queue_vehicles,
                'green_lanes': phase['green_lanes'],
                'min_dur': phase['min_dur'],
                'max_dur': phase['max_dur']
            }
            phase_data.append(data)

        return phase_data

    def get_all_tl_ids(self) -> List[str]:
        """
        返回 phase_config 中所有信号灯 ID。

        Returns:
            信号灯 ID 列表

        Example:
            >>> collector = TrafficCollector(config)
            >>> tl_ids = collector.get_all_tl_ids()
            >>> print(tl_ids[:3])
            ['1159176756', '1492574988', '1492574990']
        """
        return list(self._tl_phases.keys())
