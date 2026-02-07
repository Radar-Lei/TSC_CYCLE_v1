"""
训练数据模型定义

定义用于 GRPO 训练的数据结构:
- PhaseWait: 单个相位的配时和预测信息
- Prediction: 某一时刻的交通预测信息
- TrainingSample: 完整的训练样本 (prompt + prediction + state_file)
"""

from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any


@dataclass
class PhaseWait:
    """
    相位配时和预测信息

    Attributes:
        phase_id: 相位ID (对应 phase_config.json 中的 phase_index)
        pred_saturation: 预测饱和度 (排队车辆数 / capacity)
        min_green: 最小绿灯时间 (秒), 范围 5-120
        max_green: 最大绿灯时间 (秒), 范围 5-120
        capacity: 相位容量 (车辆容纳数), 默认 30
    """
    phase_id: int
    pred_saturation: float
    min_green: int
    max_green: int
    capacity: int = 30

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PhaseWait':
        """从字典创建实例"""
        return cls(**data)


@dataclass
class Prediction:
    """
    某一时刻的交通预测信息

    Attributes:
        as_of: 预测时间戳, 格式 "YYYY-MM-DD HH:MM:SS"
        phase_waits: 各相位的配时和预测信息列表
    """
    as_of: str
    phase_waits: List[PhaseWait] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'as_of': self.as_of,
            'phase_waits': [pw.to_dict() for pw in self.phase_waits]
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Prediction':
        """从字典创建实例"""
        phase_waits = [PhaseWait.from_dict(pw) for pw in data.get('phase_waits', [])]
        return cls(as_of=data['as_of'], phase_waits=phase_waits)


@dataclass
class TrainingSample:
    """
    完整的训练样本

    Attributes:
        prompt: 完整的训练 prompt 文本
        prediction: 交通预测信息
        state_file: SUMO 仿真状态快照路径 (用于 GRPO reward 计算)
        metadata: 元数据 (tl_id, sim_time, date 等)
    """
    prompt: str
    prediction: Prediction
    state_file: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典 (用于 JSON 序列化)"""
        return {
            'prompt': self.prompt,
            'prediction': self.prediction.to_dict(),
            'state_file': self.state_file,
            'metadata': self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TrainingSample':
        """从字典创建实例"""
        prediction = Prediction.from_dict(data['prediction'])
        return cls(
            prompt=data['prompt'],
            prediction=prediction,
            state_file=data['state_file'],
            metadata=data.get('metadata', {})
        )
