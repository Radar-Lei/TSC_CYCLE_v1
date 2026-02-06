"""
数据生成模块

提供训练数据生成的核心组件:
- 数据模型定义 (TrainingSample, Prediction, PhaseWait)
- 周期检测器 (CycleDetector)
- 预测采样器 (PredictiveSampler)
- 自适应采样器 (AdaptiveSampler, 保留兼容)
- 状态快照管理器 (StateManager)
"""

from .models import TrainingSample, Prediction, PhaseWait
from .cycle_detector import CycleDetector
from .predictive_sampler import PredictiveSampler, PhasePrediction, CyclePredictionResult
from .sampler import AdaptiveSampler, calculate_queue_change_rate
from .state_manager import StateManager

__all__ = [
    'TrainingSample',
    'Prediction',
    'PhaseWait',
    'CycleDetector',
    'PredictiveSampler',
    'PhasePrediction',
    'CyclePredictionResult',
    'AdaptiveSampler',
    'calculate_queue_change_rate',
    'StateManager',
]

