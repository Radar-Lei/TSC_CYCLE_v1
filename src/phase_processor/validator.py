"""
相位验证模块

功能:
- 过滤无效相位 (无绿灯信号的相位)
- 验证路口是否有足够的互斥相位
"""

from typing import List, Optional
from logging import Logger

from .models import PhaseInfo


def filter_invalid_phases(
    phases: List[PhaseInfo],
    logger: Optional[Logger] = None
) -> List[PhaseInfo]:
    """
    过滤无效相位 (state 中不包含任何绿灯信号的相位)

    Args:
        phases: 相位列表
        logger: 日志对象

    Returns:
        有效相位列表
    """
    valid_phases = []

    for phase in phases:
        # 检查 state 是否包含 'G' 或 'g' (绿灯信号)
        has_green = 'G' in phase.state or 'g' in phase.state

        if has_green:
            valid_phases.append(phase)
        else:
            # 记录无效相位
            if logger:
                logger.info(
                    f"过滤无效相位: phase_index={phase.phase_index}, "
                    f"state={phase.state}"
                )

    return valid_phases


def validate_traffic_light(
    tl_id: str,
    phases: List[PhaseInfo],
    logger: Optional[Logger] = None
) -> bool:
    """
    验证路口是否有足够的互斥相位

    Args:
        tl_id: 路口 ID
        phases: 相位列表
        logger: 日志对象

    Returns:
        True 如果相位数量 >= 2, False 否则
    """
    if len(phases) < 2:
        if logger:
            logger.warning(
                f"路口 {tl_id} 相位不足: 需要至少 2 个,实际 {len(phases)} 个"
            )
        return False

    return True
