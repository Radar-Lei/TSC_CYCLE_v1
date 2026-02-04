"""数据模型定义"""
from dataclasses import dataclass, field
from typing import Set, List, Dict, Tuple


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
