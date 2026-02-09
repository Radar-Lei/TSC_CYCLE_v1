"""
单天仿真 Worker

负责运行单个 SUMO 仿真实例,生成一天的训练数据。
改进: 在每个信号周期开始时刻采样，计算预测饱和度。

主要功能:
- DaySimulator: 单天仿真任务类
- simulate_day: 多进程入口函数
- create_temp_sumocfg: 创建临时 SUMO 配置文件

采样策略:
- 检测周期边界（phase 从其他相位切换到第一个绿灯相位）
- 第一个绿灯相位 index 从 phase_config 动态获取
- 在周期开始时保存 SUMO 状态
- 计算预测排队 = 初始排队 + 周期累积 + 波动
- 计算预测饱和度 = 预测排队 / capacity
"""

import os
import sys
import tempfile
import xml.etree.ElementTree as ET
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
import random
import socket

# 导入 SUMO 模拟器
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

# 设置 SUMO 环境
if 'SUMO_HOME' not in os.environ:
    possible_paths = [
        "/usr/share/sumo",
        "/usr/local/share/sumo",
        "/usr/lib/sumo",
        "/Library/Frameworks/EclipseSUMO.framework/Versions/1.25.0/EclipseSUMO/share/sumo",
        "/opt/homebrew/opt/sumo/share/sumo",
        "/usr/local/opt/sumo/share/sumo",
        "/Users/leida/Cline/sumo/share/sumo",
        "/Users/leida/Cline/sumo"
    ]
    for path in possible_paths:
        if os.path.exists(path):
            os.environ['SUMO_HOME'] = path
            break

if 'SUMO_HOME' in os.environ:
    tools = os.path.join(os.environ['SUMO_HOME'], 'tools')
    if tools not in sys.path:
        sys.path.append(tools)

try:
    import traci
    TRACI_AVAILABLE = True
except ImportError:
    TRACI_AVAILABLE = False

from sumo_simulation.sumo_simulator import SUMOSimulator
from src.data_generator.cycle_detector import CycleDetector
from src.data_generator.predictive_sampler import PredictiveSampler
from src.data_generator.traffic_collector import TrafficCollector, estimate_capacity, load_phase_config
from src.data_generator.prompt_builder import PromptBuilder, format_timestamp
from src.data_generator.noise import apply_time_variation
from src.data_generator.models import PhaseWait, Prediction, TrainingSample


def create_temp_sumocfg(
    template_path: str,
    rou_file: str,
    end_time: Optional[int] = None
) -> str:
    """
    创建临时 SUMO 配置文件

    Args:
        template_path: 模板 sumocfg 文件路径
        rou_file: 流量文件路径 (绝对路径)
        end_time: 仿真结束时间 (秒), None 时保留模板原始值

    Returns:
        临时配置文件路径
    """
    # 读取模板配置
    tree = ET.parse(template_path)
    root = tree.getroot()

    # 移除 GUI 设置文件引用(无头模式不需要)
    gui_settings_elem = root.find('gui-settings-file')
    if gui_settings_elem is not None:
        root.remove(gui_settings_elem)

    # 修改 input 元素
    input_elem = root.find('input')
    if input_elem is None:
        input_elem = ET.SubElement(root, 'input')

    # 修改 net-file - 转换为绝对路径
    net_elem = input_elem.find('net-file')
    if net_elem is not None:
        net_file = net_elem.get('value')
        # 如果是相对路径，基于模板文件目录解析为绝对路径
        if not os.path.isabs(net_file):
            template_dir = os.path.dirname(os.path.abspath(template_path))
            net_file = os.path.join(template_dir, net_file)
        net_elem.set('value', os.path.abspath(net_file))

    # 修改 route-files
    route_elem = input_elem.find('route-files')
    if route_elem is None:
        route_elem = ET.SubElement(input_elem, 'route-files')

    route_elem.set('value', rou_file)

    # 修改 end 时间（仅在显式指定时覆盖，否则保留模板原始值）
    time_elem = root.find('time')
    if time_elem is None:
        time_elem = ET.SubElement(root, 'time')

    end_elem = time_elem.find('end')
    if end_time is not None:
        if end_elem is None:
            end_elem = ET.SubElement(time_elem, 'end')
        end_elem.set('value', str(end_time))

    # 写入临时文件
    fd, temp_path = tempfile.mkstemp(suffix='.sumocfg', prefix='sumo_temp_')
    os.close(fd)

    tree.write(temp_path, encoding='utf-8', xml_declaration=True)

    return temp_path


class DaySimulator:
    """
    单天仿真任务类

    管理一天的 SUMO 仿真,收集训练数据。
    """

    def __init__(
        self,
        day_index: int,
        rou_file: str,
        config: Dict[str, Any]
    ):
        """
        初始化单天仿真器

        Args:
            day_index: 日期索引 (用于端口分配, 避免并行冲突)
            rou_file: 流量文件路径 (绝对路径)
            config: 配置字典
        """
        self.day_index = day_index
        self.rou_file = os.path.abspath(rou_file)
        self.config = config

        # 配置参数
        self.sumocfg = config['sumocfg']
        self.phase_config_path = config['phase_config_path']
        self.output_dir = config['output_dir']
        self.state_dir = config['state_dir']
        self.warmup_steps = config.get('warmup_steps', 300)
        self.sim_end = self._parse_sim_end()
        self.base_date = config.get('base_date', '2026-01-01')
        # 可选: 只处理指定的交叉口子集 (用于交叉口级别并行)
        self.target_tl_ids = set(config.get('target_tl_ids', []))

        # 仅当 config 中没有提供 base_date 时，才从 rou_file 文件名提取日期
        # 这样可以支持交叉口并行模式中使用的临时文件名
        if 'base_date' not in config:
            rou_basename = os.path.basename(self.rou_file)
            if '_2026-' in rou_basename:
                date_part = rou_basename.split('_2026-')[1].split('.rou.xml')[0]
                self.base_date = f'2026-{date_part}'

        # 初始化组件
        self.samples: List[TrainingSample] = []
        self.simulator: Optional[SUMOSimulator] = None
        self.temp_cfg_path: Optional[str] = None

        # 端口分配 (使用 OS 分配空闲端口避免并行冲突)
        self.port = self._find_free_port()

    @staticmethod
    def _find_free_port() -> int:
        """让操作系统分配一个确保可用的空闲端口"""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('', 0))
            return s.getsockname()[1]

    def _parse_sim_end(self) -> int:
        """从 sumocfg 文件解析仿真结束时间，解析失败则回退到 3600"""
        try:
            tree = ET.parse(self.sumocfg)
            end_elem = tree.find('time/end')
            if end_elem is not None:
                return int(float(end_elem.get('value', '3600')))
        except Exception:
            pass
        return 3600

    def run(self) -> Dict[str, Any]:
        """
        运行单天仿真

        Returns:
            结果字典
        """
        try:
            # 1. 创建临时配置文件（保留 sumocfg 原始仿真时间）
            self.temp_cfg_path = create_temp_sumocfg(
                self.sumocfg,
                self.rou_file
            )

            # 2. 初始化 SUMO 仿真器
            self.simulator = SUMOSimulator(
                config_file=self.temp_cfg_path,
                junctions_file=None,  # 数据生成不需要路口数据文件
                gui=False,
                verbose=False,
                port=self.port
            )

            # 3. 加载相位配置
            phase_config = load_phase_config(self.phase_config_path)

            # 4. 初始化组件
            collector = TrafficCollector(phase_config)
            prompt_builder = PromptBuilder()
            predictive_sampler = PredictiveSampler(
                state_dir=self.state_dir,
                noise_std_ratio=0.1,
                compress=False
            )

            # 获取所有信号灯 ID
            all_tl_ids = collector.get_all_tl_ids()
            
            # 如果指定了 target_tl_ids，只处理子集
            if self.target_tl_ids:
                tl_ids = [tl_id for tl_id in all_tl_ids if tl_id in self.target_tl_ids]
            else:
                tl_ids = all_tl_ids

            # 为每个信号灯创建周期检测器
            cycle_detectors = {tl_id: CycleDetector(tl_id, phase_config) for tl_id in tl_ids}

            # 5. 启动仿真
            self.simulator.start_simulation()

            # 6. 预热阶段
            current_step = 0
            while current_step < self.warmup_steps:
                if not self.simulator.step():
                    raise RuntimeError(f"Simulation connection lost at step {current_step}")
                # 更新周期检测器状态（预热期间不采样）
                for tl_id in tl_ids:
                    current_phase = collector.get_current_phase(tl_id)
                    if current_phase >= 0:
                        cycle_detectors[tl_id].update(current_phase, float(current_step))
                current_step += 1

            # 7. 正式采样阶段 - 周期边界采样
            while current_step < self.sim_end:
                if not self.simulator.step():
                    # 仿真结束或连接断开
                    break
                sim_time = float(current_step)

                # 对每个信号灯检查周期边界
                for tl_id in tl_ids:
                    # a. 获取当前相位
                    current_phase = collector.get_current_phase(tl_id)
                    if current_phase < 0:
                        continue

                    # b. 检查是否是新周期开始
                    is_new_cycle = cycle_detectors[tl_id].update(current_phase, sim_time)
                    if not is_new_cycle:
                        continue

                    # c. 周期开始 - 进行预测采样
                    result = predictive_sampler.sample_at_cycle_start(
                        simulator=self.simulator,
                        tl_id=tl_id,
                        phase_config=phase_config,
                        sim_time=sim_time,
                        base_date=self.base_date
                    )

                    if result is None:
                        continue

                    # d. 构建 PhaseWait 列表（使用预测饱和度）
                    phases = phase_config['traffic_lights'].get(tl_id, [])
                    phase_waits = []
                    for phase in phases:
                        phase_idx = phase['phase_index']
                        pred = result.predictions.get(phase_idx)
                        if pred is None:
                            continue

                        # 应用时间波动
                        min_green, max_green = apply_time_variation(
                            phase['min_dur'],
                            phase['max_dur']
                        )

                        phase_waits.append(PhaseWait(
                            phase_id=phase_idx,
                            pred_saturation=pred.pred_saturation,
                            min_green=min_green,
                            max_green=max_green,
                            capacity=pred.capacity
                        ))

                    if not phase_waits:
                        continue

                    # e. 构建 Prediction 和 prompt
                    timestamp = format_timestamp(sim_time, self.base_date)
                    prediction = Prediction(as_of=timestamp, phase_waits=phase_waits)
                    prompt = prompt_builder.build_prompt(prediction)

                    # f. 创建 TrainingSample
                    sample = TrainingSample(
                        prompt=prompt,
                        prediction=prediction,
                        state_file=result.state_file,
                        metadata={
                            'tl_id': tl_id,
                            'sim_time': sim_time,
                            'date': self.base_date,
                            'cycle_count': cycle_detectors[tl_id].cycle_count
                        }
                    )
                    self.samples.append(sample)

                current_step += 1

            # 8. 关闭仿真
            self.simulator.close()

            # 9. 清理临时文件
            if self.temp_cfg_path and os.path.exists(self.temp_cfg_path):
                os.remove(self.temp_cfg_path)

            # 10. 返回结果
            # 如果是交叉口级别并行，返回 metadata 包含 tl_id
            metadata = {}
            if self.target_tl_ids and len(self.target_tl_ids) == 1:
                metadata['tl_id'] = list(self.target_tl_ids)[0]

            return {
                "day_index": self.day_index,
                "date": self.base_date,
                "samples": [s.to_dict() for s in self.samples],
                "status": "success",
                "error": None,
                "sample_count": len(self.samples),
                "metadata": metadata
            }

        except Exception as e:
            # 异常处理
            error_msg = f"Day {self.day_index} failed: {str(e)}"

            # 确保清理资源
            if self.simulator:
                try:
                    self.simulator.close()
                except Exception:
                    pass

            if self.temp_cfg_path and os.path.exists(self.temp_cfg_path):
                try:
                    os.remove(self.temp_cfg_path)
                except Exception:
                    pass

            return {
                "day_index": self.day_index,
                "date": self.base_date,
                "samples": [],
                "status": "error",
                "error": error_msg,
                "sample_count": 0
            }


def simulate_day(args: tuple) -> Dict[str, Any]:
    """
    多进程入口函数

    Args:
        args: (day_index, rou_file, config) 元组

    Returns:
        仿真结果字典
    """
    day_index, rou_file, config = args

    simulator = DaySimulator(day_index, rou_file, config)
    result = simulator.run()

    return result
