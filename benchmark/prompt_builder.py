"""
Benchmark Prompt 构建器

构建符合 sample_prompt_result.md 格式的 LLM 输入 Prompt。

与 src/data_generator/prompt_builder.py 的区别:
- 独立实现,不导入 TSC_CYCLE/src/ 下的任何模块
- 使用原始交通数据计算 pred_saturation (不添加高斯噪声)
- 用于 benchmark 场景,便于公平对比不同 LLM

主要功能:
- BenchmarkPromptBuilder: 构建完整的 LLM 输入 prompt
- PhaseWaitData: 相位等待数据的数据类
- format_timestamp: 将仿真时间转换为时间戳字符串
"""

import json
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import List


# 系统 Prompt (角色定义) - 与 src/data_generator/prompt_builder.py 保持一致
SYSTEM_PROMPT = (
    "你是交通信号配时优化专家。\n"
    "请认真分析预测得到的下个周期各个相位的交通状态，给出下个周期的配时方案，并给出你的推理过程。\n"
    "将推理过程放在 <start_working_out> 和 <end_working_out> 之间。\n"
    "然后，将你的最终方案放在 <SOLUTION> 和 </SOLUTION> 之间。"
)


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
2) 每相位约束:final 必须满足 prediction.phase_waits[*].min_green <= final <= prediction.phase_waits[*].max_green。
3) final 必须为整数秒。

提示(非硬约束):
- capacity 仅供参考,最终决策以 pred_saturation 为主。

输出格式:
1) JSON 顶层必须是数组(list);数组长度必须等于 prediction.phase_waits 的长度。
2) 数组元素必须为对象:{"phase_id": <int>, "final": <int>};不允许输出其它字段。
""".strip()


@dataclass
class PhaseWaitData:
    """相位等待数据

    用于构建 LLM 输入 prompt 的相位数据结构。

    Attributes:
        phase_id: LLM 友好的连续编号 (0, 1, 2, ...)
        sumo_phase_index: SUMO 实际相位索引 (可能是 0, 2, 4, 6)
        pred_saturation: 预测饱和度 (排队车辆数 / 容量)
        min_green: 最小绿灯时间 (秒)
        max_green: 最大绿灯时间 (秒)
        capacity: 相位容量 (车辆容纳数)
    """
    phase_id: int
    sumo_phase_index: int
    pred_saturation: float
    min_green: int
    max_green: int
    capacity: int

    def to_dict(self) -> dict:
        """转换为字典格式

        只输出 phase_id 给 LLM，不暴露 sumo_phase_index。

        Returns:
            包含 phase_id 和交通数据的字典
        """
        return {
            "phase_id": self.phase_id,
            "pred_saturation": self.pred_saturation,
            "min_green": self.min_green,
            "max_green": self.max_green,
            "capacity": self.capacity,
        }


def format_timestamp(sim_time: float, base_date: str = "2026-01-01") -> str:
    """将仿真时间转换为时间戳字符串

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


class BenchmarkPromptBuilder:
    """Benchmark Prompt 构建器

    构建符合 sample_prompt_result.md 格式的 LLM 输入 prompt。
    用于 benchmark 场景,便于公平对比不同 LLM 的效果。

    与 src/data_generator/prompt_builder.PromptBuilder 的区别:
    - 独立实现,不导入 TSC_CYCLE/src/ 下的任何模块
    - 使用原始交通数据计算 pred_saturation (不添加高斯噪声)
    - 接收 PhaseWaitData 列表作为输入,而不是 Prediction 对象
    """

    # 类常量
    SYSTEM_PROMPT = SYSTEM_PROMPT
    TASK_TEMPLATE = TASK_TEMPLATE

    def build_prompt(
        self,
        tl_id: str,
        sim_time: float,
        phase_waits: List[PhaseWaitData],
        base_date: str = "2026-01-01"
    ) -> str:
        """构建完整的 LLM 输入 prompt

        Prompt 格式:
        1. JSON 输入块: 【cycle_predict_input_json】{...}【/cycle_predict_input_json】
        2. 任务描述、字段说明、硬约束、输出要求

        Args:
            tl_id: 信号灯 ID (用于日志记录,不包含在 prompt 中)
            sim_time: 仿真时间 (秒)
            phase_waits: PhaseWaitData 列表
            base_date: 仿真的基准日期 (格式: YYYY-MM-DD)

        Returns:
            完整的 LLM 输入 prompt 字符串

        Example:
            >>> builder = BenchmarkPromptBuilder()
            >>> phase_waits = [
            ...     PhaseWaitData(phase_id=0, pred_saturation=0.5, min_green=20, max_green=40, capacity=30),
            ...     PhaseWaitData(phase_id=1, pred_saturation=0.8, min_green=15, max_green=30, capacity=25),
            ... ]
            >>> prompt = builder.build_prompt('test_tl', 300.0, phase_waits)
            >>> '【cycle_predict_input_json】' in prompt
            True
        """
        # 生成时间戳
        timestamp = format_timestamp(sim_time, base_date)

        # 构建 prediction JSON
        prediction_dict = {
            "prediction": {
                "as_of": timestamp,
                "phase_waits": [pw.to_dict() for pw in phase_waits]
            }
        }

        # 格式化 JSON (ensure_ascii=False 支持中文, indent=2 格式化)
        prediction_json = json.dumps(
            prediction_dict,
            ensure_ascii=False,
            indent=2
        )

        # 构建完整 prompt
        prompt_parts = [
            f"【cycle_predict_input_json】{prediction_json}【/cycle_predict_input_json】",
            self.TASK_TEMPLATE
        ]

        return "\n".join(prompt_parts)

    def get_system_prompt(self) -> str:
        """获取系统 prompt

        Returns:
            系统 prompt 字符串
        """
        return self.SYSTEM_PROMPT
