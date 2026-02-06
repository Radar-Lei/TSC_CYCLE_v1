"""
单天仿真 Worker

负责运行单个 SUMO 仿真实例,生成一天的训练数据。

主要功能:
- DaySimulator: 单天仿真任务类
- simulate_day: 多进程入口函数
- create_temp_sumocfg: 创建临时 SUMO 配置文件
"""

import os
import tempfile
import xml.etree.ElementTree as ET
from typing import Dict, Any, List, Optional
from pathlib import Path

# 导入 SUMO 模拟器
import sys
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from sumo_simulation.sumo_simulator import SUMOSimulator
from src.data_generator.sampler import AdaptiveSampler
from src.data_generator.traffic_collector import TrafficCollector, estimate_capacity, load_phase_config
from src.data_generator.state_manager import StateManager
from src.data_generator.prompt_builder import PromptBuilder, format_timestamp
from src.data_generator.noise import add_gaussian_noise, apply_time_variation, calculate_saturation
from src.data_generator.models import PhaseWait, Prediction, TrainingSample
from src.data_generator.time_period import identify_time_period


def create_temp_sumocfg(
    template_path: str,
    rou_file: str,
    end_time: int = 86400
) -> str:
    """
    创建临时 SUMO 配置文件

    Args:
        template_path: 模板 sumocfg 文件路径
        rou_file: 流量文件路径 (绝对路径)
        end_time: 仿真结束时间 (秒), 默认 86400 (24小时)

    Returns:
        临时配置文件路径

    Example:
        >>> temp_cfg = create_temp_sumocfg(
        ...     'sumo_simulation/environments/chengdu/chengdu.sumocfg',
        ...     'sumo_simulation/environments/chengdu/chengdu_daily/chengdu.rou_2026-01-01.rou.xml',
        ...     end_time=3600
        ... )
        >>> print(temp_cfg)
        /tmp/sumo_temp_12345.sumocfg
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

    # 修改 end 时间
    time_elem = root.find('time')
    if time_elem is None:
        time_elem = ET.SubElement(root, 'time')

    end_elem = time_elem.find('end')
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

    Attributes:
        day_index: 日期索引 (用于端口分配)
        rou_file: 流量文件路径
        config: 配置字典
        samples: 收集的训练样本列表
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
            config: 配置字典,包含:
                - sumocfg: SUMO 配置文件路径
                - net_file: 网络文件路径
                - phase_config_path: Phase 1 输出的相位配置路径
                - output_dir: 训练数据输出目录
                - state_dir: 状态快照目录
                - warmup_steps: 预热步数 (默认 300)
                - sim_end: 仿真结束时间 (默认 86400)
                - base_date: 基准日期 (默认 "2026-01-01")
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
        self.sim_end = config.get('sim_end', 86400)
        self.base_date = config.get('base_date', '2026-01-01')

        # 从 rou_file 文件名提取日期
        # 例如: chengdu.rou_2026-01-15.rou.xml -> 2026-01-15
        rou_basename = os.path.basename(self.rou_file)
        if '_2026-' in rou_basename:
            date_part = rou_basename.split('_2026-')[1].split('.rou.xml')[0]
            self.base_date = f'2026-{date_part}'

        # 初始化组件
        self.samples: List[TrainingSample] = []
        self.simulator: Optional[SUMOSimulator] = None
        self.temp_cfg_path: Optional[str] = None

        # 端口分配 (避免并行冲突)
        self.port = 10000 + day_index

    def run(self) -> Dict[str, Any]:
        """
        运行单天仿真

        Returns:
            结果字典:
            {
                "day_index": int,
                "date": str,
                "samples": List[dict],
                "status": "success" | "error",
                "error": str | None,
                "sample_count": int
            }
        """
        try:
            # 1. 创建临时配置文件
            self.temp_cfg_path = create_temp_sumocfg(
                self.sumocfg,
                self.rou_file,
                end_time=self.sim_end
            )

            # 2. 初始化 SUMO 仿真器
            self.simulator = SUMOSimulator(
                config_file=self.temp_cfg_path,
                gui=False,
                verbose=False,
                port=self.port
            )

            # 3. 加载相位配置
            phase_config = load_phase_config(self.phase_config_path)

            # 4. 初始化组件
            sampler = AdaptiveSampler(
                base_interval=300,
                min_interval=60,
                change_threshold_high=0.5,
                change_threshold_medium=0.3
            )
            collector = TrafficCollector(phase_config)
            state_manager = StateManager(self.state_dir, compress=True)
            prompt_builder = PromptBuilder()

            # 获取所有信号灯 ID
            tl_ids = collector.get_all_tl_ids()

            # 5. 启动仿真
            self.simulator.start_simulation()

            # 6. 预热 (让车辆进入路网)
            for _ in range(self.warmup_steps):
                self.simulator.step()

            # 7. 仿真循环 (从 warmup_steps 到 sim_end)
            current_step = self.warmup_steps

            while current_step < self.sim_end:
                # 推进仿真
                self.simulator.step()
                sim_time = float(current_step)

                # 对每个信号灯收集数据
                for tl_id in tl_ids:
                    # a. 收集当前排队状态
                    phases = phase_config['traffic_lights'].get(tl_id, [])
                    current_queue_state = {
                        f"{tl_id}_phase_{phase['phase_index']}":
                            collector.get_queue_vehicles(tl_id, phase['phase_index'])
                        for phase in phases
                    }

                    # b. 检查是否采样
                    if not sampler.should_sample(sim_time, current_queue_state):
                        continue

                    # c. 采样流程
                    # i. 收集相位数据
                    phase_data = collector.collect_phase_data(tl_id)
                    if not phase_data:
                        continue

                    # ii. 应用噪声和波动生成 PhaseWait 列表
                    phase_waits = []
                    for data in phase_data:
                        queue = add_gaussian_noise(data['queue_vehicles'], std_ratio=0.1, min_val=0.0)
                        capacity = estimate_capacity(data['green_lanes'])
                        sat = calculate_saturation(queue, capacity)
                        min_green, max_green = apply_time_variation(
                            data['min_dur'],
                            data['max_dur']
                        )
                        phase_waits.append(PhaseWait(
                            phase_id=data['phase_index'],
                            pred_saturation=sat,
                            min_green=min_green,
                            max_green=max_green,
                            capacity=capacity
                        ))

                    # iii. 构建 Prediction 和 prompt
                    timestamp = format_timestamp(sim_time, self.base_date)
                    prediction = Prediction(as_of=timestamp, phase_waits=phase_waits)
                    prompt = prompt_builder.build_prompt(prediction)

                    # iv. 保存 SUMO 状态快照
                    state_file = state_manager.save_state(
                        self.simulator,
                        tl_id,
                        sim_time,
                        self.base_date
                    )

                    # v. 识别时段
                    time_period = identify_time_period(sim_time)

                    # vi. 创建 TrainingSample
                    sample = TrainingSample(
                        prompt=prompt,
                        prediction=prediction,
                        state_file=state_file,
                        metadata={
                            'tl_id': tl_id,
                            'sim_time': sim_time,
                            'date': self.base_date,
                            'time_period': time_period.value
                        }
                    )
                    self.samples.append(sample)

                    # vii. 记录采样
                    sampler.record_sample(sim_time, current_queue_state)

                current_step += 1

            # 8. 关闭仿真
            self.simulator.close()

            # 9. 清理临时文件
            if self.temp_cfg_path and os.path.exists(self.temp_cfg_path):
                os.remove(self.temp_cfg_path)

            # 10. 返回结果
            return {
                "day_index": self.day_index,
                "date": self.base_date,
                "samples": [s.to_dict() for s in self.samples],
                "status": "success",
                "error": None,
                "sample_count": len(self.samples)
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

    Example:
        >>> result = simulate_day((0, 'path/to/rou.xml', config_dict))
        >>> print(result['status'])
        success
    """
    day_index, rou_file, config = args

    simulator = DaySimulator(day_index, rou_file, config)
    result = simulator.run()

    return result
