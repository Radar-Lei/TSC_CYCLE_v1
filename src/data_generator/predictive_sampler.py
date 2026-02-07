"""
预测采样器

在周期开始时进行预测性采样，计算预测排队数和饱和度。

核心逻辑:
1. 在周期开始时保存 SUMO 状态
2. 收集初始排队（各相位控制车道的瞬时排队）
3. 推进一个完整周期，统计各相位期间的排队累积
4. 恢复到周期开始状态
5. 计算预测排队 = 初始 + 累积 + 波动
6. 计算饱和度 = 预测排队 / capacity
"""

import os
import sys
import tempfile
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

# 设置 SUMO 环境
if 'SUMO_HOME' not in os.environ:
    possible_paths = [
        "/usr/share/sumo",
        "/usr/local/share/sumo",
        "/usr/lib/sumo",
        "/Library/Frameworks/EclipseSUMO.framework/Versions/1.25.0/EclipseSUMO/share/sumo",
        "/opt/homebrew/opt/sumo/share/sumo",
        "/usr/local/opt/sumo/share/sumo",
        "/Users/leida/Cline/sumo/share/sumo",
        "/Users/leida/Cline/sumo"
    ]
    for path in possible_paths:
        if os.path.exists(path):
            os.environ['SUMO_HOME'] = path
            break

if 'SUMO_HOME' in os.environ:
    tools = os.path.join(os.environ['SUMO_HOME'], 'tools')
    if tools not in sys.path:
        sys.path.append(tools)

try:
    import traci
    TRACI_AVAILABLE = True
except ImportError:
    TRACI_AVAILABLE = False

from src.data_generator.noise import add_gaussian_noise, calculate_saturation
from src.data_generator.traffic_collector import estimate_capacity


@dataclass
class PhasePrediction:
    """单个相位的预测结果"""
    phase_id: int
    initial_queue: float      # 周期开始时的初始排队
    accumulated_queue: float  # 周期推进期间的累积排队
    pred_queue: float         # 预测排队 = 初始 + 累积 + 波动
    capacity: int             # 相位容量
    pred_saturation: float    # 预测饱和度


@dataclass
class CyclePredictionResult:
    """周期预测采样结果"""
    state_file: str                         # 状态快照路径
    sim_time: float                         # 采样时间
    tl_id: str                              # 信号灯 ID
    predictions: Dict[int, PhasePrediction] # 各相位预测结果


class PredictiveSampler:
    """
    预测采样器 - 周期级别的数据采样

    在周期开始时：
    1. 保存 SUMO 状态
    2. 收集初始排队
    3. 推进周期获取累积数据
    4. 恢复状态
    5. 返回预测结果

    Attributes:
        state_dir: 状态文件保存目录
        noise_std_ratio: 噪声标准差比例
    """

    def __init__(
        self,
        state_dir: str,
        noise_std_ratio: float = 0.1,
        compress: bool = True
    ):
        """
        初始化预测采样器。

        Args:
            state_dir: 状态文件保存目录
            noise_std_ratio: 高斯噪声标准差占真实值的比例，默认 0.1 (10%)
            compress: 是否压缩状态文件
        """
        self.state_dir = state_dir
        self.noise_std_ratio = noise_std_ratio
        self.compress = compress

        # 确保目录存在
        os.makedirs(self.state_dir, exist_ok=True)

    def sample_at_cycle_start(
        self,
        simulator,
        tl_id: str,
        phase_config: Dict[str, Any],
        sim_time: float,
        base_date: str = "2026-01-01"
    ) -> Optional[CyclePredictionResult]:
        """
        在周期开始时进行预测采样。

        Args:
            simulator: SUMO 仿真器实例
            tl_id: 信号灯 ID
            phase_config: 相位配置（来自 phase_config.json）
            sim_time: 当前仿真时间
            base_date: 基准日期

        Returns:
            CyclePredictionResult 包含状态文件和各相位预测结果，
            采样失败返回 None
        """
        if not TRACI_AVAILABLE:
            return None

        try:
            # 1. 获取相位信息
            phases = phase_config.get('traffic_lights', {}).get(tl_id, [])
            if not phases:
                return None

            # 2. 保存当前状态（周期开始时刻）
            state_file = self._save_state(tl_id, sim_time, base_date)

            # 3. 收集初始排队（各相位控制车道的瞬时排队）
            initial_queues = self._collect_initial_queues(tl_id, phases)

            # 4. 获取周期时长并推进一个完整周期，收集累积数据
            cycle_duration = self._get_cycle_duration(tl_id)
            accumulated_queues = self._simulate_cycle_and_collect(
                tl_id, phases, cycle_duration
            )

            # 5. 恢复到周期开始状态
            self._restore_state(state_file)

            # 6. 计算预测结果
            predictions = self._calculate_predictions(
                phases, initial_queues, accumulated_queues
            )

            return CyclePredictionResult(
                state_file=state_file,
                sim_time=sim_time,
                tl_id=tl_id,
                predictions=predictions
            )

        except Exception as e:
            print(f"[PredictiveSampler] 采样失败 tl_id={tl_id}: {e}")
            return None

    def _save_state(self, tl_id: str, sim_time: float, date: str) -> str:
        """保存仿真状态。"""
        # 生成文件名
        hours = int(sim_time // 3600)
        minutes = int((sim_time % 3600) // 60)
        seconds = int(sim_time % 60)
        time_str = f"{hours:02d}-{minutes:02d}-{seconds:02d}"

        ext = ".xml.gz" if self.compress else ".xml"
        filename = f"state_{date}_T{time_str}_{tl_id}{ext}"
        filepath = os.path.join(self.state_dir, filename)

        # 保存状态
        traci.simulation.saveState(filepath)
        return os.path.abspath(filepath)

    def _restore_state(self, state_file: str):
        """恢复仿真状态。"""
        traci.simulation.loadState(state_file)

    def _collect_initial_queues(
        self,
        tl_id: str,
        phases: List[Dict[str, Any]]
    ) -> Dict[int, float]:
        """
        收集各相位控制车道的初始排队数。

        这是"周期开始时瞬时排队分配到各相位"的实现。

        Args:
            tl_id: 信号灯 ID
            phases: 相位配置列表

        Returns:
            {phase_index: queue_count}
        """
        initial_queues = {}

        for phase in phases:
            phase_index = phase['phase_index']
            green_lanes = phase.get('green_lanes', [])

            total_queue = 0
            for lane_id in green_lanes:
                try:
                    halting = traci.lane.getLastStepHaltingNumber(lane_id)
                    total_queue += halting
                except Exception:
                    continue

            initial_queues[phase_index] = float(total_queue)

        return initial_queues

    def _get_cycle_duration(self, tl_id: str) -> int:
        """获取周期总时长。"""
        try:
            programs = traci.trafficlight.getAllProgramLogics(tl_id)
            if not programs:
                return 120  # 默认 120 秒

            total_duration = sum(phase.duration for phase in programs[0].phases)
            return int(total_duration)

        except Exception:
            return 120

    def _simulate_cycle_and_collect(
        self,
        tl_id: str,
        phases: List[Dict[str, Any]],
        cycle_duration: int
    ) -> Dict[int, float]:
        """
        推进一个完整周期，收集各相位期间的排队累积。

        Args:
            tl_id: 信号灯 ID
            phases: 相位配置列表
            cycle_duration: 周期时长（秒）

        Returns:
            {phase_index: accumulated_queue}

        Note:
            累积排队 = 周期结束时的排队 - 周期开始时的排队
            这代表了周期期间新增的排队车辆
        """
        # 记录开始时的排队
        start_queues = self._collect_initial_queues(tl_id, phases)

        # 推进一个完整周期
        for _ in range(cycle_duration):
            traci.simulationStep()

        # 记录结束时的排队
        end_queues = self._collect_initial_queues(tl_id, phases)

        # 计算累积（结束 - 开始，可能为负表示车辆离开）
        accumulated = {}
        for phase_index in start_queues:
            start_q = start_queues.get(phase_index, 0)
            end_q = end_queues.get(phase_index, 0)
            # 累积排队取非负值（负值意味着车辆通行，这是好事）
            # 但对于预测，我们关心的是"如果不放行，会累积多少"
            # 因此这里保留原始差值
            accumulated[phase_index] = max(0, end_q - start_q)

        return accumulated

    def _calculate_predictions(
        self,
        phases: List[Dict[str, Any]],
        initial_queues: Dict[int, float],
        accumulated_queues: Dict[int, float]
    ) -> Dict[int, PhasePrediction]:
        """
        计算各相位的预测结果。

        预测排队 = 初始排队 + 累积排队 + 高斯波动

        Args:
            phases: 相位配置列表
            initial_queues: 初始排队 {phase_index: queue}
            accumulated_queues: 累积排队 {phase_index: queue}

        Returns:
            {phase_index: PhasePrediction}
        """
        predictions = {}

        for phase in phases:
            phase_index = phase['phase_index']
            green_lanes = phase.get('green_lanes', [])

            # 获取初始和累积排队
            initial_q = initial_queues.get(phase_index, 0.0)
            accumulated_q = accumulated_queues.get(phase_index, 0.0)

            # 计算原始预测排队
            raw_pred_queue = initial_q + accumulated_q

            # 添加高斯波动
            pred_queue = add_gaussian_noise(
                raw_pred_queue,
                std_ratio=self.noise_std_ratio,
                min_val=0.0
            )

            # 计算容量和饱和度
            capacity = estimate_capacity(green_lanes)
            pred_saturation = calculate_saturation(pred_queue, capacity)

            predictions[phase_index] = PhasePrediction(
                phase_id=phase_index,
                initial_queue=initial_q,
                accumulated_queue=accumulated_q,
                pred_queue=pred_queue,
                capacity=capacity,
                pred_saturation=pred_saturation
            )

        return predictions
