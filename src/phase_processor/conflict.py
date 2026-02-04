"""
相位冲突检测和解决模块

功能:
- 检测相位间的绿灯车道冲突
- 使用贪心算法解决冲突,保留互斥的相位集合
"""

import random
from typing import List, Tuple, Optional
from logging import Logger

from .models import PhaseInfo


def detect_conflict(phase_a: PhaseInfo, phase_b: PhaseInfo) -> bool:
    """
    检测两个相位是否冲突 (绿灯车道重叠)

    Args:
        phase_a: 相位 A
        phase_b: 相位 B

    Returns:
        True 如果两个相位的绿灯车道有重叠, False 否则
    """
    return len(phase_a.green_lanes & phase_b.green_lanes) > 0


def detect_all_conflicts(phases: List[PhaseInfo]) -> List[Tuple[int, int]]:
    """
    检测所有冲突的相位对

    Args:
        phases: 相位列表

    Returns:
        冲突的相位索引对列表
    """
    conflicts = []

    for i, phase_a in enumerate(phases):
        for j, phase_b in enumerate(phases[i + 1:], start=i + 1):
            if detect_conflict(phase_a, phase_b):
                conflicts.append((i, j))

    return conflicts


def resolve_conflicts(
    phases: List[PhaseInfo],
    logger: Optional[Logger] = None
) -> List[PhaseInfo]:
    """
    使用贪心算法解决相位冲突,保留互斥的相位集合

    算法:
    - 依次处理每个相位
    - 检查当前相位是否与已保留的相位冲突
    - 如果冲突,根据规则决定保留哪个:
      1. 保留绿灯车道数多的
      2. 相等时随机保留 (random.random() > 0.5)

    Args:
        phases: 相位列表
        logger: 日志对象

    Returns:
        互斥的相位列表
    """
    if not phases:
        return []

    # 第一个相位直接保留
    resolved = [phases[0]]

    # 处理剩余相位
    for current_phase in phases[1:]:
        # 检查当前相位是否与已保留的相位冲突
        conflict_found = False

        for i, existing_phase in enumerate(resolved):
            if detect_conflict(current_phase, existing_phase):
                conflict_found = True

                # 决定保留哪个相位
                current_green_count = len(current_phase.green_lanes)
                existing_green_count = len(existing_phase.green_lanes)

                if current_green_count > existing_green_count:
                    # 当前相位绿灯更多,替换已保留的相位
                    if logger:
                        logger.info(
                            f"冲突解决: 保留 phase_{current_phase.phase_index} "
                            f"({current_green_count} 绿灯车道), "
                            f"移除 phase_{existing_phase.phase_index} "
                            f"({existing_green_count} 绿灯车道), "
                            f"原因=more_green_lanes"
                        )
                    resolved[i] = current_phase
                    break  # 替换后继续检查下一个相位

                elif current_green_count == existing_green_count:
                    # 绿灯数相等,随机保留
                    if random.random() > 0.5:
                        # 保留当前相位
                        if logger:
                            logger.info(
                                f"冲突解决: 保留 phase_{current_phase.phase_index} "
                                f"({current_green_count} 绿灯车道), "
                                f"移除 phase_{existing_phase.phase_index} "
                                f"({existing_green_count} 绿灯车道), "
                                f"原因=random_kept_new"
                            )
                        resolved[i] = current_phase
                        break
                    else:
                        # 保留已存在的相位
                        if logger:
                            logger.info(
                                f"冲突解决: 保留 phase_{existing_phase.phase_index} "
                                f"({existing_green_count} 绿灯车道), "
                                f"移除 phase_{current_phase.phase_index} "
                                f"({current_green_count} 绿灯车道), "
                                f"原因=random_kept_existing"
                            )
                        break

                else:
                    # 已保留的相位绿灯更多,保留已有的
                    if logger:
                        logger.info(
                            f"冲突解决: 保留 phase_{existing_phase.phase_index} "
                            f"({existing_green_count} 绿灯车道), "
                            f"移除 phase_{current_phase.phase_index} "
                            f"({current_green_count} 绿灯车道), "
                            f"原因=more_green_lanes"
                        )
                    break

        # 如果当前相位与所有已保留的相位都不冲突,添加到结果中
        if not conflict_found:
            resolved.append(current_phase)

    return resolved
