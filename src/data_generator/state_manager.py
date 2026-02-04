"""
SUMO 仿真状态快照管理器

管理 SUMO 仿真状态快照的保存和加载:
- 生成规范的状态文件名 (包含日期、时间、信号灯ID)
- 支持压缩存储 (.xml.gz)
- 自动创建存储目录
"""

import os
from typing import Optional


class StateManager:
    """
    SUMO 仿真状态快照管理器

    用于保存和加载 SUMO 仿真状态,支持 GRPO 训练阶段从特定时刻恢复仿真。

    Attributes:
        state_dir: 状态文件存储目录
        compress: 是否使用 .xml.gz 压缩
    """

    def __init__(self, state_dir: str, compress: bool = True):
        """
        初始化状态管理器

        Args:
            state_dir: 状态文件存储目录
            compress: 是否使用 .xml.gz 压缩, 默认 True
        """
        self.state_dir = state_dir
        self.compress = compress

        # 自动创建目录
        os.makedirs(self.state_dir, exist_ok=True)

    def generate_state_filename(
        self,
        tl_id: str,
        sim_time: float,
        date: str
    ) -> str:
        """
        生成状态文件名

        格式: state_{date}_T{HH-MM-SS}_{tl_id}.xml.gz
        例如: state_2026-01-01_T08-30-00_1159176756.xml.gz

        Args:
            tl_id: 信号灯 ID
            sim_time: 仿真时间 (秒)
            date: 日期字符串 (YYYY-MM-DD)

        Returns:
            状态文件名 (不含路径)
        """
        # 将仿真时间转换为 HH-MM-SS 格式
        hours = int(sim_time // 3600)
        minutes = int((sim_time % 3600) // 60)
        seconds = int(sim_time % 60)
        time_str = f"{hours:02d}-{minutes:02d}-{seconds:02d}"

        # 生成文件名
        ext = ".xml.gz" if self.compress else ".xml"
        filename = f"state_{date}_T{time_str}_{tl_id}{ext}"

        return filename

    def save_state(
        self,
        simulator,
        tl_id: str,
        sim_time: float,
        date: str
    ) -> str:
        """
        保存仿真状态

        Args:
            simulator: SUMO 仿真器实例
            tl_id: 信号灯 ID
            sim_time: 仿真时间 (秒)
            date: 日期字符串 (YYYY-MM-DD)

        Returns:
            完整的状态文件路径 (绝对路径)
        """
        filename = self.generate_state_filename(tl_id, sim_time, date)
        filepath = os.path.join(self.state_dir, filename)

        # 调用仿真器的状态保存方法
        # 注意: 实际实现需要根据 SUMOSimulator 接口调整
        if hasattr(simulator, 'save_simulation_state_to_file'):
            simulator.save_simulation_state_to_file(filepath)
        elif hasattr(simulator, 'save_simulation_state'):
            simulator.save_simulation_state(filepath)
        else:
            # 如果使用 traci 直接调用
            import traci
            traci.simulation.saveState(filepath)

        return os.path.abspath(filepath)

    def load_state(
        self,
        simulator,
        filepath: str
    ) -> bool:
        """
        加载仿真状态

        Args:
            simulator: SUMO 仿真器实例
            filepath: 状态文件路径

        Returns:
            是否加载成功
        """
        if not os.path.exists(filepath):
            return False

        try:
            # 调用仿真器的状态加载方法
            if hasattr(simulator, 'restore_simulation_state'):
                simulator.restore_simulation_state(filepath)
            else:
                # 如果使用 traci 直接调用
                import traci
                traci.simulation.loadState(filepath)
            return True
        except Exception:
            return False

    def cleanup_old_states(self, max_age_days: int = 7):
        """
        清理超过指定天数的状态文件

        Args:
            max_age_days: 最大保留天数, 默认 7 天
        """
        import time

        max_age_seconds = max_age_days * 86400
        current_time = time.time()

        for filename in os.listdir(self.state_dir):
            filepath = os.path.join(self.state_dir, filename)
            if os.path.isfile(filepath):
                file_age = current_time - os.path.getmtime(filepath)
                if file_age > max_age_seconds:
                    os.remove(filepath)

    def get_state_count(self) -> int:
        """
        获取状态文件数量

        Returns:
            状态文件数量
        """
        count = 0
        for filename in os.listdir(self.state_dir):
            filepath = os.path.join(self.state_dir, filename)
            if os.path.isfile(filepath) and (
                filename.endswith('.xml') or filename.endswith('.xml.gz')
            ):
                count += 1
        return count
