"""XML 解析器模块"""
import xml.etree.ElementTree as ET
from typing import Dict
from .models import PhaseInfo, TLInfo
from ..utils.logging_config import setup_logging

logger = setup_logging()


def parse_net_file(net_file: str) -> Dict[str, TLInfo]:
    """解析 SUMO 网络文件,提取信号灯和相位信息

    Args:
        net_file: SUMO 网络文件路径 (.net.xml)

    Returns:
        {tl_id: TLInfo} 字典
    """
    logger.info(f"开始解析网络文件: {net_file}")

    tree = ET.parse(net_file)
    root = tree.getroot()

    # 第一步: 解析所有 connection 元素,建立 {tl_id: {linkIndex: (from_lane, to_lane)}}
    tl_link_maps: Dict[str, Dict[int, tuple]] = {}

    for conn in root.findall('.//connection[@tl]'):
        tl_id = conn.get('tl')
        link_index = int(conn.get('linkIndex'))
        from_edge = conn.get('from')
        to_edge = conn.get('to')
        from_lane_idx = conn.get('fromLane')
        to_lane_idx = conn.get('toLane')

        # 构造车道 ID
        from_lane = f"{from_edge}_{from_lane_idx}"
        to_lane = f"{to_edge}_{to_lane_idx}"

        if tl_id not in tl_link_maps:
            tl_link_maps[tl_id] = {}
        tl_link_maps[tl_id][link_index] = (from_lane, to_lane)

    logger.info(f"解析到 {len(tl_link_maps)} 个信号灯的连接映射")

    # 第二步: 解析所有 tlLogic 元素及其 phase
    result: Dict[str, TLInfo] = {}

    for tl_logic in root.findall('.//tlLogic'):
        tl_id = tl_logic.get('id')

        if tl_id not in tl_link_maps:
            logger.warning(f"信号灯 {tl_id} 没有找到对应的连接映射,跳过")
            continue

        link_map = tl_link_maps[tl_id]
        phases = []

        for phase_idx, phase_elem in enumerate(tl_logic.findall('phase')):
            state = phase_elem.get('state')
            duration = float(phase_elem.get('duration'))
            min_dur = float(phase_elem.get('minDur', '0'))
            max_dur = float(phase_elem.get('maxDur', '0'))

            # 提取绿灯车道
            green_lanes = set()
            for i, signal in enumerate(state):
                if signal in ('G', 'g'):  # 'G' 优先绿灯, 'g' 非优先绿灯
                    if i in link_map:
                        from_lane, to_lane = link_map[i]
                        green_lanes.add(from_lane)
                    else:
                        logger.debug(f"信号灯 {tl_id} 相位 {phase_idx}: linkIndex {i} 未找到对应车道")

            phase_info = PhaseInfo(
                phase_index=phase_idx,
                state=state,
                duration=duration,
                green_lanes=green_lanes,
                min_dur=min_dur,
                max_dur=max_dur
            )
            phases.append(phase_info)

        tl_info = TLInfo(
            tl_id=tl_id,
            phases=phases,
            link_map=link_map
        )
        result[tl_id] = tl_info

        logger.debug(f"信号灯 {tl_id}: {len(phases)} 个相位")

    logger.info(f"解析完成,共 {len(result)} 个信号灯")
    return result
