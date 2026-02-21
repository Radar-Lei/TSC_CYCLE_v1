"""
默认配时加载模块

从 SUMO .net.xml 文件中读取默认配时方案作为 fallback。

主要功能:
- load_default_timing: 从 .net.xml 读取 tlLogic 配时
- get_net_xml_path: 从 .sumocfg 提取 .net.xml 路径
- DefaultTiming: 默认配时数据类
"""

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from loguru import logger


@dataclass
class PhaseDefault:
    """相位默认配时

    表示单个相位的默认配时信息。

    Attributes:
        phase_id: LLM 友好的连续编号 (0, 1, 2, ...)
        sumo_phase_index: SUMO 实际相位索引 (可能是 0, 2, 4, 6)
        duration: 持续时间 (秒)
    """
    phase_id: int
    sumo_phase_index: int
    duration: int

    def to_dict(self) -> dict:
        """转换为字典格式"""
        return {
            "phase_id": self.phase_id,
            "sumo_phase_index": self.sumo_phase_index,
            "duration": self.duration
        }


@dataclass
class DefaultTiming:
    """默认配时方案

    包含从 .net.xml 读取的默认配时信息。

    Attributes:
        tl_id: 信号灯 ID
        phases: PhaseDefault 列表 (仅包含绿灯相位)
    """
    tl_id: str
    phases: List[PhaseDefault]

    def to_dict(self) -> dict:
        """转换为字典格式"""
        return {
            "tl_id": self.tl_id,
            "phases": [p.to_dict() for p in self.phases]
        }

    def get_total_duration(self) -> int:
        """获取总周期时长"""
        return sum(p.duration for p in self.phases)


def get_net_xml_path(sumocfg_path: str | Path) -> Optional[Path]:
    """从 .sumocfg 文件提取 .net.xml 路径

    解析 .sumocfg 文件，找到 net-file 的 value 属性，
    并返回相对于 sumocfg 文件所在目录的完整路径。

    Args:
        sumocfg_path: .sumocfg 文件路径

    Returns:
        .net.xml 文件的完整路径，如果无法解析则返回 None

    Example:
        >>> path = get_net_xml_path('environments/chengdu/chengdu.sumocfg')
        >>> path.name
        'chengdu.net.xml'
    """
    sumocfg_path = Path(sumocfg_path).resolve()

    if not sumocfg_path.exists():
        logger.warning("sumocfg file not found: {}", sumocfg_path)
        return None

    try:
        tree = ET.parse(sumocfg_path)
        root = tree.getroot()

        # 查找 net-file 元素
        # 结构: <input><net-file value="..."/></input>
        for input_elem in root.findall(".//input"):
            net_file_elem = input_elem.find("net-file")
            if net_file_elem is not None:
                net_file_value = net_file_elem.get("value")
                if net_file_value:
                    # 构建完整路径
                    net_xml_path = sumocfg_path.parent / net_file_value
                    if net_xml_path.exists():
                        return net_xml_path
                    else:
                        logger.warning(
                            "net.xml file not found at: {}",
                            net_xml_path
                        )
                        return None

        logger.warning("No net-file found in sumocfg: {}", sumocfg_path)
        return None

    except ET.ParseError as e:
        logger.error("Failed to parse sumocfg: {}", e)
        return None


def load_default_timing(
    net_xml_path: str | Path,
    tl_id: str,
    min_phase_duration: int = 10
) -> Optional[DefaultTiming]:
    """从 SUMO .net.xml 文件加载默认配时

    解析 .net.xml 文件中的 tlLogic 元素，提取相位配时。
    默认只包含绿灯相位 (duration >= min_phase_duration)，跳过黄灯过渡相位。

    Args:
        net_xml_path: .net.xml 文件路径
        tl_id: 信号灯 ID
        min_phase_duration: 最小相位持续时间阈值 (默认 10 秒)
                           用于过滤黄灯过渡相位 (通常 3-6 秒)

    Returns:
        DefaultTiming 包含配时信息，如果找不到则返回 None

    Example:
        >>> timing = load_default_timing('chengdu.net.xml', '1159176756')
        >>> timing.tl_id
        '1159176756'
        >>> len(timing.phases)
        2  # 只有绿灯相位 (20s 和 30s)，跳过黄灯 (5s)
    """
    net_xml_path = Path(net_xml_path).resolve()

    if not net_xml_path.exists():
        logger.warning("net.xml file not found: {}", net_xml_path)
        return None

    try:
        tree = ET.parse(net_xml_path)
        root = tree.getroot()

        # 查找 tlLogic 元素
        # 结构: <tlLogic id="..." type="static" programID="0" offset="0">
        #          <phase duration="..." state="..."/>
        #       </tlLogic>
        for tl_logic in root.findall(".//tlLogic"):
            if tl_logic.get("id") == tl_id:
                phases: List[PhaseDefault] = []
                phase_elements = tl_logic.findall("phase")

                for idx, phase_elem in enumerate(phase_elements):
                    duration_str = phase_elem.get("duration")
                    state = phase_elem.get("state", "")

                    if duration_str:
                        duration = int(duration_str)

                        # 过滤掉过渡相位 (黄灯通常 3-6 秒)
                        # 只保留较长的绿灯相位
                        if duration >= min_phase_duration:
                            phases.append(PhaseDefault(
                                phase_id=len(phases),  # LLM-friendly连续编号
                                sumo_phase_index=idx,  # 保留原始SUMO相位索引
                                duration=duration
                            ))

                if phases:
                    timing = DefaultTiming(tl_id=tl_id, phases=phases)
                    phase_indices = [p.sumo_phase_index for p in phases]
                    logger.info(
                        "Loaded default timing for {}: {} green phases (SUMO indices: {}), total {}s",
                        tl_id,
                        len(phases),
                        phase_indices,
                        timing.get_total_duration()
                    )
                    return timing
                else:
                    logger.warning(
                        "No green phases found for tl_id {} (all phases < {}s)",
                        tl_id,
                        min_phase_duration
                    )
                    return None

        logger.warning("tlLogic not found for tl_id: {}", tl_id)
        return None

    except ET.ParseError as e:
        logger.error("Failed to parse net.xml: {}", e)
        return None
    except ValueError as e:
        logger.error("Failed to parse phase duration: {}", e)
        return None


def discover_traffic_lights(net_xml_path: str | Path) -> List[str]:
    """发现 .net.xml 文件中的所有信号灯 ID

    扫描 .net.xml 文件，返回所有 tlLogic 元素的 id 属性列表。

    Args:
        net_xml_path: .net.xml 文件路径

    Returns:
        信号灯 ID 列表

    Example:
        >>> tl_ids = discover_traffic_lights('chengdu.net.xml')
        >>> len(tl_ids) > 0
        True
    """
    net_xml_path = Path(net_xml_path).resolve()

    if not net_xml_path.exists():
        logger.warning("net.xml file not found: {}", net_xml_path)
        return []

    try:
        tree = ET.parse(net_xml_path)
        root = tree.getroot()

        tl_ids: List[str] = []
        for tl_logic in root.findall(".//tlLogic"):
            tl_id = tl_logic.get("id")
            if tl_id:
                tl_ids.append(tl_id)

        logger.debug("Found {} traffic lights in {}", len(tl_ids), net_xml_path)
        return tl_ids

    except ET.ParseError as e:
        logger.error("Failed to parse net.xml: {}", e)
        return []
