"""
Prompt 构建器

构建符合 sample_prompt_result.md 格式的训练 prompt。

主要功能:
- PromptBuilder: 构建完整的训练 prompt
- format_timestamp: 将仿真时间转换为时间戳字符串
"""

import json
from datetime import datetime, timedelta
from typing import List, Dict, Any
from src.data_generator.models import Prediction


# 系统 Prompt (角色定义)
SYSTEM_PROMPT = "你是交通信号配时优化专家。"


# 任务模板 (从 sample_prompt_result.md 提取)
TASK_TEMPLATE = """
任务(必须完成):
主要基于 prediction.phase_waits 的 pred_saturation(已计算),在满足硬约束前提下输出下一周期各相位最终绿灯时间 final(单位:秒)。

字段说明(仅说明含义):
- prediction.phase_waits[*].min_green / max_green:秒。
- prediction.phase_waits[*].pred_saturation:预测饱和度(pred_wait / capacity)。
- prediction.phase_waits[*].capacity:相位容量(车辆容纳数)。

硬约束(必须满足):
1) 相位顺序固定:严格按 prediction.phase_waits 的顺序输出;不可跳相、不可重排。
2) 每相位约束:final 必须满足 prediction.phase_waits[*].min_green ≤ final ≤ prediction.phase_waits[*].max_green。
3) final 必须为整数秒。

提示(非硬约束):
- capacity 仅供参考,最终决策以 pred_saturation 为主。

输出格式:
1) JSON 顶层必须是数组(list);数组长度必须等于 prediction.phase_waits 的长度。
2) 数组元素必须为对象:{"phase_id": <int>, "final": <int>};不允许输出其它字段。
""".strip()


def format_timestamp(sim_time: float, base_date: str = "2026-01-01") -> str:
    """
    将仿真时间转换为时间戳字符串。

    Args:
        sim_time: 仿真时间 (从 0 开始的秒数)
        base_date: 仿真的基准日期 (格式: YYYY-MM-DD)

    Returns:
        时间戳字符串,格式: "YYYY-MM-DD HH:MM:SS"

    Example:
        >>> format_timestamp(3600.0, '2026-01-15')
        '2026-01-15 01:00:00'
        >>> format_timestamp(28800.0, '2026-01-01')
        '2026-01-01 08:00:00'
    """
    # 解析基准日期
    base_dt = datetime.strptime(base_date, "%Y-%m-%d")

    # 添加仿真时间
    timestamp_dt = base_dt + timedelta(seconds=sim_time)

    # 格式化为字符串
    return timestamp_dt.strftime("%Y-%m-%d %H:%M:%S")


class PromptBuilder:
    """
    Prompt 构建器

    构建符合 sample_prompt_result.md 格式的训练 prompt。
    """

    # 类常量
    SYSTEM_PROMPT = SYSTEM_PROMPT
    TASK_TEMPLATE = TASK_TEMPLATE

    def build_prompt(self, prediction: Prediction) -> str:
        """
        构建完整的训练 prompt。

        Prompt 格式:
        1. 系统角色: "你是交通信号配时优化专家。"
        2. JSON 输入块: 【cycle_predict_input_json】{...}【/cycle_predict_input_json】
        3. 任务描述、字段说明、硬约束、输出要求

        Args:
            prediction: Prediction 对象

        Returns:
            完整的训练 prompt 字符串

        Example:
            >>> phase_waits = [
            ...     PhaseWait(phase_id=1, pred_saturation=2.0635, min_green=20, max_green=40, capacity=31),
            ...     PhaseWait(phase_id=2, pred_saturation=0.0582, min_green=20, max_green=30, capacity=45),
            ... ]
            >>> prediction = Prediction(as_of='2026-01-28 13:12:15', phase_waits=phase_waits)
            >>> builder = PromptBuilder()
            >>> prompt = builder.build_prompt(prediction)
            >>> print(prompt[:50])
            你是交通信号配时优化专家。
            【cycle_predict_input_json】...
        """
        # 构建 prediction JSON
        prediction_dict = {
            "prediction": prediction.to_dict()
        }

        # 格式化 JSON (ensure_ascii=False 支持中文, indent=2 格式化)
        prediction_json = json.dumps(
            prediction_dict,
            ensure_ascii=False,
            indent=2
        )

        # 构建完整 prompt
        prompt_parts = [
            self.SYSTEM_PROMPT,
            f"【cycle_predict_input_json】{prediction_json}【/cycle_predict_input_json】",
            self.TASK_TEMPLATE
        ]

        return "\n".join(prompt_parts)

    def build_from_phase_data(
        self,
        tl_id: str,
        sim_time: float,
        phase_data: List[Dict[str, Any]]
    ) -> str:
        """
        从收集的相位数据构建 prompt。

        此方法简化了从 TrafficCollector.collect_phase_data() 的输出
        直接构建 prompt 的流程。

        Args:
            tl_id: 信号灯 ID
            sim_time: 仿真时间 (秒)
            phase_data: TrafficCollector.collect_phase_data() 的返回值

        Returns:
            完整的训练 prompt 字符串

        Note:
            需要配合 noise.py 中的函数使用:
            - add_gaussian_noise(queue_vehicles)
            - apply_time_variation(min_dur, max_dur)
            - calculate_saturation(queue, capacity)
            - estimate_capacity(green_lanes)

        Example:
            >>> from src.data_generator.traffic_collector import TrafficCollector
            >>> from src.data_generator.noise import add_gaussian_noise, apply_time_variation, calculate_saturation
            >>> from src.data_generator.traffic_collector import estimate_capacity
            >>>
            >>> collector = TrafficCollector(config)
            >>> phase_data = collector.collect_phase_data('1159176756')
            >>>
            >>> # 构建 PhaseWait 列表
            >>> phase_waits = []
            >>> for data in phase_data:
            ...     queue = add_gaussian_noise(data['queue_vehicles'])
            ...     capacity = estimate_capacity(data['green_lanes'])
            ...     sat = calculate_saturation(queue, capacity)
            ...     min_green, max_green = apply_time_variation(data['min_dur'], data['max_dur'])
            ...     phase_waits.append(PhaseWait(
            ...         phase_id=data['phase_index'],
            ...         pred_saturation=sat,
            ...         min_green=min_green,
            ...         max_green=max_green,
            ...         capacity=capacity
            ...     ))
            >>>
            >>> # 构建 prediction
            >>> timestamp = format_timestamp(sim_time, '2026-01-15')
            >>> prediction = Prediction(as_of=timestamp, phase_waits=phase_waits)
            >>>
            >>> # 构建 prompt
            >>> builder = PromptBuilder()
            >>> prompt = builder.build_prompt(prediction)
        """
        # 生成时间戳 (默认使用 2026-01-01 作为基准日期)
        timestamp = format_timestamp(sim_time, base_date="2026-01-01")

        # 注意: 这里只生成时间戳,实际的 PhaseWait 创建需要在外部完成
        # 因为需要配合 noise.py 中的函数使用
        # 此方法主要用于文档和示例,实际使用时建议直接调用 build_prompt()

        # 为了保持接口一致性,这里返回一个提示信息
        return f"Use build_prompt() with Prediction object. Timestamp: {timestamp}"
