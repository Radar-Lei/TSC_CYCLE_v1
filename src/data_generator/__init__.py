"""
数据生成模块

提供训练数据生成的核心组件:
- 数据模型定义 (TrainingSample, Prediction, PhaseWait)
- 自适应采样器 (AdaptiveSampler)
- 状态快照管理器 (StateManager)
"""

from .models import TrainingSample, Prediction, PhaseWait
from .sampler import AdaptiveSampler, calculate_queue_change_rate
from .state_manager import StateManager

__all__ = [
    'TrainingSample',
    'Prediction',
    'PhaseWait',
    'AdaptiveSampler',
    'calculate_queue_change_rate',
    'StateManager',
]
