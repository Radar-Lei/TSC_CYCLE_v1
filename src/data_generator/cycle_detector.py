"""
信号周期检测器

检测信号灯周期边界，用于在周期开始时触发采样。

核心逻辑:
- 当 phase 从其他相位切换到第一个绿灯相位时，视为新周期开始
- 首次调用不触发周期开始（等待完整周期）
- 第一个绿灯相位 index 从 phase_config 动态获取（不再硬编码为 0）
"""

from typing import Optional, List, Dict, Any

try:
    import traci
    TRACI_AVAILABLE = True
except ImportError:
    TRACI_AVAILABLE = False


class CycleDetector:
    """
    信号周期检测器

    检测信号灯周期边界（第一个绿灯相位开始），用于触发周期级别的采样。
    第一个绿灯相位 index 从 phase_config 动态获取，支持任意相位序列。

    Attributes:
        tl_id: 信号灯 ID
        first_green_phase: 第一个绿灯相位的 phase_index（从 phase_config 获取）
        last_phase: 上一步的相位索引
        cycle_start_time: 当前周期开始时间
        cycle_count: 已检测到的周期数
    """

    def __init__(self, tl_id: str, phase_config: Dict[str, Any]):
        """
        初始化周期检测器。

        Args:
            tl_id: 信号灯 ID
            phase_config: 相位配置字典，包含 traffic_lights 字段
        """
        self.tl_id = tl_id
        self.last_phase: Optional[int] = None
        self.cycle_start_time: Optional[float] = None
        self.cycle_count: int = 0
        self._cycle_duration_cache: Optional[float] = None

        # 从 phase_config 动态获取第一个绿灯相位 index
        import logging
        logger = logging.getLogger(__name__)

        try:
            tl_phases = phase_config['traffic_lights'].get(tl_id, [])
            if tl_phases:
                self.first_green_phase = tl_phases[0]['phase_index']
            else:
                logger.warning(f"CycleDetector: tl_id '{tl_id}' not found in phase_config, using default first_green_phase=0")
                self.first_green_phase = 0
        except (KeyError, IndexError, TypeError) as e:
            logger.warning(f"CycleDetector: failed to get first_green_phase for '{tl_id}': {e}, using default 0")
            self.first_green_phase = 0

    def update(self, current_phase: int, sim_time: float) -> bool:
        """
        更新状态，检测是否是新周期开始。

        当 phase 从其他相位切换到第一个绿灯相位时，视为新周期开始。
        第一个绿灯相位 index 从构造函数传入的 phase_config 动态获取。

        Args:
            current_phase: 当前相位索引
            sim_time: 当前仿真时间（秒）

        Returns:
            True 表示是新周期开始，False 表示不是

        Example:
            >>> # 假设第一个绿灯相位 index 是 2
            >>> detector = CycleDetector('tl_1', phase_config)
            >>> detector.update(2, 0.0)   # 首次调用
            False
            >>> detector.update(4, 30.0)  # phase 2 -> 4
            False
            >>> detector.update(5, 60.0)  # phase 4 -> 5
            False
            >>> detector.update(2, 90.0)  # phase 5 -> 2 (新周期!)
            True
        """
        is_new_cycle = False

        # 检测周期边界: phase 从其他相位切换到第一个绿灯相位
        if (
            self.last_phase is not None
            and self.last_phase != self.first_green_phase
            and current_phase == self.first_green_phase
        ):
            is_new_cycle = True
            self.cycle_start_time = sim_time
            self.cycle_count += 1

        # 更新状态
        self.last_phase = current_phase
        return is_new_cycle

    def get_cycle_duration(self) -> float:
        """
        获取配置的周期总时长（所有相位 duration 之和）。

        从 traci 获取相位定义并累加各相位的 duration。
        结果会被缓存，避免重复查询。

        Returns:
            周期总时长（秒），获取失败返回 0.0

        Note:
            需要 SUMO 仿真已启动且 traci 连接可用
        """
        # 使用缓存
        if self._cycle_duration_cache is not None:
            return self._cycle_duration_cache

        if not TRACI_AVAILABLE:
            return 0.0

        try:
            # 获取信号灯程序定义
            programs = traci.trafficlight.getAllProgramLogics(self.tl_id)
            if not programs:
                return 0.0

            # 使用第一个程序（默认程序）
            phases = programs[0].phases

            # 累加所有相位的 duration
            total_duration = sum(phase.duration for phase in phases)

            # 缓存结果
            self._cycle_duration_cache = total_duration
            return total_duration

        except Exception:
            return 0.0

    def get_phase_durations(self) -> List[float]:
        """
        获取各相位的持续时间列表。

        Returns:
            各相位的 duration 列表，获取失败返回空列表
        """
        if not TRACI_AVAILABLE:
            return []

        try:
            programs = traci.trafficlight.getAllProgramLogics(self.tl_id)
            if not programs:
                return []

            phases = programs[0].phases
            return [phase.duration for phase in phases]

        except Exception:
            return []

    def get_num_phases(self) -> int:
        """
        获取相位总数。

        Returns:
            相位总数，获取失败返回 0
        """
        if not TRACI_AVAILABLE:
            return 0

        try:
            programs = traci.trafficlight.getAllProgramLogics(self.tl_id)
            if not programs:
                return 0

            return len(programs[0].phases)

        except Exception:
            return 0

    def reset(self):
        """重置检测器状态。"""
        self.last_phase = None
        self.cycle_start_time = None
        self.cycle_count = 0
        # 保留 duration 缓存，因为相位配置不变

    def __repr__(self) -> str:
        return (
            f"CycleDetector(tl_id='{self.tl_id}', "
            f"first_green_phase={self.first_green_phase}, "
            f"cycle_count={self.cycle_count}, "
            f"last_phase={self.last_phase})"
        )
