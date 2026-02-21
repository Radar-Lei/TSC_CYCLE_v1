"""
交叉口过滤器

从 SUMO 网络文件中过滤出有效的交叉口，用于 benchmark 评估。

过滤逻辑与 src/phase_processor 保持一致:
1. 解析 .net.xml 文件，提取所有 tlLogic 和相位信息
2. 过滤无效相位 (state 中没有 G 或 g 的相位)
3. 解决冲突 (绿灯车道重叠的相位)
4. 验证路口有效性 (必须有 >= 2 个有效相位)

主要功能:
- filter_valid_traffic_lights: 返回有效交叉口 ID 列表
- parse_net_file: 解析 SUMO 网络文件
"""

import random
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Set, Tuple


@dataclass
class PhaseInfo:
    """相位信息"""
    phase_index: int
    state: str
    duration: float
    green_lanes: Set[str] = field(default_factory=set)
    min_dur: float = 0.0
    max_dur: float = 0.0


@dataclass
class TLInfo:
    """信号灯信息"""
    tl_id: str
    phases: List[PhaseInfo] = field(default_factory=list)
    link_map: Dict[int, Tuple[str, str]] = field(default_factory=dict)


def parse_net_file(net_file: str) -> Dict[str, TLInfo]:
    """解析 SUMO 网络文件，提取信号灯和相位信息

    Args:
        net_file: SUMO 网络文件路径 (.net.xml)

    Returns:
        {tl_id: TLInfo} 字典
    """
    tree = ET.parse(net_file)
    root = tree.getroot()

    # 第一步: 解析所有 connection 元素，建立 {tl_id: {linkIndex: (from_lane, to_lane)}}
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

    # 第二步: 解析所有 tlLogic 元素及其 phase
    result: Dict[str, TLInfo] = {}

    for tl_logic in root.findall('.//tlLogic'):
        tl_id = tl_logic.get('id')

        if tl_id not in tl_link_maps:
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

    return result


def filter_invalid_phases(phases: List[PhaseInfo]) -> List[PhaseInfo]:
    """过滤无效相位 (state 中不包含任何绿灯信号的相位)

    Args:
        phases: 相位列表

    Returns:
        有效相位列表
    """
    valid_phases = []

    for phase in phases:
        # 检查 state 是否包含 'G' 或 'g' (绿灯信号)
        has_green = 'G' in phase.state or 'g' in phase.state

        if has_green:
            valid_phases.append(phase)

    return valid_phases


def detect_conflict(phase_a: PhaseInfo, phase_b: PhaseInfo) -> bool:
    """检测两个相位是否冲突 (绿灯车道重叠)

    Args:
        phase_a: 相位 A
        phase_b: 相位 B

    Returns:
        True 如果两个相位的绿灯车道有重叠，False 否则
    """
    return len(phase_a.green_lanes & phase_b.green_lanes) > 0


def resolve_conflicts(
    phases: List[PhaseInfo],
    seed: int = 42
) -> List[PhaseInfo]:
    """使用贪心算法解决相位冲突，保留互斥的相位集合

    算法:
    - 依次处理每个相位
    - 检查当前相位是否与已保留的相位冲突
    - 如果冲突，根据规则决定保留哪个:
      1. 保留绿灯车道数多的
      2. 相等时随机保留 (使用固定种子保证可复现)

    Args:
        phases: 相位列表
        seed: 随机种子 (保证结果可复现)

    Returns:
        互斥的相位列表
    """
    if not phases:
        return []

    # 设置随机种子保证可复现
    rng = random.Random(seed)

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
                    # 当前相位绿灯更多，替换已保留的相位
                    resolved[i] = current_phase
                    break

                elif current_green_count == existing_green_count:
                    # 绿灯数相等，随机保留
                    if rng.random() > 0.5:
                        resolved[i] = current_phase
                        break

                else:
                    # 已保留的相位绿灯更多，保留已有的
                    break

        # 如果当前相位与所有已保留的相位都不冲突，添加到结果中
        if not conflict_found:
            resolved.append(current_phase)

    return resolved


def validate_traffic_light(tl_id: str, phases: List[PhaseInfo]) -> bool:
    """验证路口是否有足够的互斥相位

    Args:
        tl_id: 路口 ID
        phases: 相位列表

    Returns:
        True 如果相位数量 >= 2，False 否则
    """
    return len(phases) >= 2


def filter_valid_traffic_lights(
    net_file: str,
    seed: int = 42
) -> List[str]:
    """过滤出有效的交叉口 ID 列表

    过滤流程:
    1. 解析网络文件
    2. 过滤无效相位
    3. 解决冲突
    4. 验证路口有效性

    Args:
        net_file: SUMO 网络文件路径 (.net.xml)
        seed: 随机种子 (用于冲突解决)

    Returns:
        有效交叉口 ID 列表
    """
    net_path = Path(net_file)
    if not net_path.exists():
        raise FileNotFoundError(f"Network file not found: {net_file}")

    # 1. 解析网络文件
    traffic_lights_raw = parse_net_file(str(net_path))

    # 2. 处理每个信号灯
    valid_tl_ids = []

    for tl_id, tl_info in traffic_lights_raw.items():
        # 2a. 过滤无效相位
        valid_phases = filter_invalid_phases(tl_info.phases)

        if not valid_phases:
            continue

        # 2b. 解决冲突
        resolved_phases = resolve_conflicts(valid_phases, seed=seed)

        # 2c. 验证路口有效性
        if validate_traffic_light(tl_id, resolved_phases):
            valid_tl_ids.append(tl_id)

    return valid_tl_ids


def get_tl_phase_info(net_file: str, seed: int = 42) -> Dict[str, List[PhaseInfo]]:
    """获取有效交叉口的相位信息

    Args:
        net_file: SUMO 网络文件路径 (.net.xml)
        seed: 随机种子

    Returns:
        {tl_id: [PhaseInfo]} 字典，只包含有效交叉口
    """
    net_path = Path(net_file)
    if not net_path.exists():
        raise FileNotFoundError(f"Network file not found: {net_file}")

    # 解析网络文件
    traffic_lights_raw = parse_net_file(str(net_path))

    # 处理每个信号灯
    valid_tl_phases: Dict[str, List[PhaseInfo]] = {}

    for tl_id, tl_info in traffic_lights_raw.items():
        # 过滤无效相位
        valid_phases = filter_invalid_phases(tl_info.phases)

        if not valid_phases:
            continue

        # 解决冲突
        resolved_phases = resolve_conflicts(valid_phases, seed=seed)

        # 验证路口有效性
        if validate_traffic_light(tl_id, resolved_phases):
            valid_tl_phases[tl_id] = resolved_phases

    return valid_tl_phases
