"""
主处理流程模块

整合解析、验证、冲突解决和时间配置生成功能,
提供完整的相位处理流程。
"""

import json
from dataclasses import dataclass
from typing import Dict, List, Optional
from logging import Logger

from .models import PhaseInfo
from .parser import parse_net_file
from .validator import filter_invalid_phases, validate_traffic_light
from .conflict import resolve_conflicts
from .time_config import generate_time_config


@dataclass
class ProcessingResult:
    """处理结果数据类"""
    total_tl: int               # 总信号灯数
    valid_tl: int               # 有效信号灯数 (至少 2 个互斥相位)
    skipped_tl: int             # 跳过的信号灯数
    total_phases: int           # 处理后总相位数
    filtered_phases: int        # 过滤掉的无效相位数
    conflict_resolutions: int   # 冲突解决次数
    traffic_lights: Dict[str, List[PhaseInfo]]  # 结果: {tl_id: [phases]}


def process_traffic_lights(
    net_file: str,
    logger: Optional[Logger] = None
) -> ProcessingResult:
    """
    处理 SUMO 网络文件中的所有信号灯和相位

    处理流程:
    1. 解析 XML 文件
    2. 过滤无效相位
    3. 解决冲突
    4. 验证路口有效性
    5. 生成时间配置

    Args:
        net_file: SUMO 网络文件路径 (.net.xml)
        logger: 日志对象

    Returns:
        ProcessingResult 包含处理统计和结果
    """
    if logger:
        logger.info("=" * 60)
        logger.info(f"开始处理 SUMO 网络文件: {net_file}")
        logger.info("=" * 60)

    # 1. 解析网络文件
    traffic_lights_raw = parse_net_file(net_file)
    total_tl = len(traffic_lights_raw)

    if logger:
        logger.info(f"解析完成,共 {total_tl} 个信号灯")

    # 统计变量
    filtered_phases_count = 0
    conflict_resolutions_count = 0
    valid_traffic_lights: Dict[str, List[PhaseInfo]] = {}

    # 2. 处理每个信号灯
    for tl_id, tl_info in traffic_lights_raw.items():
        if logger:
            logger.info(f"\n处理信号灯: {tl_id} (原始相位数: {len(tl_info.phases)})")

        original_phase_count = len(tl_info.phases)

        # 2a. 过滤无效相位
        valid_phases = filter_invalid_phases(tl_info.phases, logger)
        filtered_count = original_phase_count - len(valid_phases)
        filtered_phases_count += filtered_count

        if logger and filtered_count > 0:
            logger.info(f"  过滤了 {filtered_count} 个无效相位")

        if not valid_phases:
            if logger:
                logger.warning(f"  跳过信号灯 {tl_id}: 没有有效相位")
            continue

        # 2b. 解决冲突
        before_conflict = len(valid_phases)
        resolved_phases = resolve_conflicts(valid_phases, logger)
        after_conflict = len(resolved_phases)

        if before_conflict > after_conflict:
            conflict_resolutions_count += (before_conflict - after_conflict)
            if logger:
                logger.info(f"  冲突解决: {before_conflict} -> {after_conflict} 个相位")

        # 2c. 验证路口有效性
        is_valid = validate_traffic_light(tl_id, resolved_phases, logger)

        if not is_valid:
            if logger:
                logger.warning(f"  跳过信号灯 {tl_id}: 相位不足 ({len(resolved_phases)} < 2)")
            continue

        # 2d. 生成时间配置
        for phase in resolved_phases:
            min_dur, max_dur = generate_time_config(
                original_duration=phase.duration,
                original_min_dur=phase.min_dur,
                original_max_dur=phase.max_dur
            )
            phase.min_dur = min_dur
            phase.max_dur = max_dur

        # 记录有效信号灯
        valid_traffic_lights[tl_id] = resolved_phases

        if logger:
            logger.info(f"  ✓ 信号灯 {tl_id} 处理完成: {len(resolved_phases)} 个互斥相位")

    # 3. 计算统计结果
    valid_tl = len(valid_traffic_lights)
    skipped_tl = total_tl - valid_tl
    total_phases = sum(len(phases) for phases in valid_traffic_lights.values())

    result = ProcessingResult(
        total_tl=total_tl,
        valid_tl=valid_tl,
        skipped_tl=skipped_tl,
        total_phases=total_phases,
        filtered_phases=filtered_phases_count,
        conflict_resolutions=conflict_resolutions_count,
        traffic_lights=valid_traffic_lights
    )

    # 4. 输出最终摘要
    if logger:
        logger.info("\n" + "=" * 60)
        logger.info("处理完成摘要")
        logger.info("=" * 60)
        logger.info(f"总信号灯数: {total_tl}")
        logger.info(f"有效信号灯数: {valid_tl}")
        logger.info(f"跳过信号灯数: {skipped_tl}")
        logger.info(f"总相位数: {total_phases}")
        logger.info(f"过滤的无效相位数: {filtered_phases_count}")
        logger.info(f"冲突解决次数: {conflict_resolutions_count}")
        logger.info("=" * 60)

    return result


def save_result_to_json(
    result: ProcessingResult,
    output_file: str,
    source_file: str = "chengdu.net.xml"
) -> None:
    """
    将处理结果保存为 JSON 文件

    Args:
        result: ProcessingResult 对象
        output_file: 输出 JSON 文件路径
        source_file: 源文件名称 (用于 metadata)
    """
    # 构造 JSON 数据结构
    data = {
        "metadata": {
            "total_tl": result.total_tl,
            "valid_tl": result.valid_tl,
            "skipped_tl": result.skipped_tl,
            "total_phases": result.total_phases,
            "source_file": source_file
        },
        "traffic_lights": {}
    }

    # 转换 PhaseInfo 为可序列化的字典
    for tl_id, phases in result.traffic_lights.items():
        data["traffic_lights"][tl_id] = [
            {
                "phase_index": phase.phase_index,
                "state": phase.state,
                "green_lanes": sorted(list(phase.green_lanes)),  # 转换 set 为 list
                "min_dur": phase.min_dur,
                "max_dur": phase.max_dur
            }
            for phase in phases
        ]

    # 保存为格式化的 JSON
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
