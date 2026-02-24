import os
import sys
import json
import time
import datetime
import xml.etree.ElementTree as ET
from collections import defaultdict  # 用于自动初始化嵌套字典
from threading import Thread, Event  # 用于后台运行仿真
from typing import Any, Optional, Dict, List, Tuple  # 类型提示
import csv  # 用于保存指标到CSV文件
import subprocess  # 用于控制SUMO子进程输出
import contextlib  # 用于静默 traci.start 的输出
import io  # 用于静默 traci.start 的输出

# --- 1. 路径与环境配置 ---

# 配置 SUMO_HOME 环境变量（SUMO安装路径）
# 如果系统环境变量中没有设置SUMO_HOME，则尝试从常见安装位置查找
if 'SUMO_HOME' not in os.environ:
    # macOS 和 Linux 常见的 SUMO 安装路径列表
    possible_paths = [
        "/usr/share/sumo",  # Ubuntu/Debian (apt install sumo sumo-tools)
        "/usr/local/share/sumo",  # 本地编译安装
        "/usr/lib/sumo",  # 部分发行版可能使用的路径
        "/Library/Frameworks/EclipseSUMO.framework/Versions/1.25.0/EclipseSUMO/share/sumo",  # macOS框架安装
        "/opt/homebrew/opt/sumo/share/sumo",  # Homebrew（Apple Silicon）
        "/usr/local/opt/sumo/share/sumo",      # Homebrew（Intel Mac）
        "/Users/leida/Cline/sumo/share/sumo",  # 自定义安装位置
        "/Users/leida/Cline/sumo"
    ]
    # 遍历可能的路径，找到第一个存在的路径并设置为SUMO_HOME
    for path in possible_paths:
        if os.path.exists(path):
            os.environ['SUMO_HOME'] = path
            break

# 如果找到了SUMO_HOME，将其tools目录添加到Python路径
# tools目录包含traci等Python接口模块
if 'SUMO_HOME' in os.environ:
    tools = os.path.join(os.environ['SUMO_HOME'], 'tools')
    sys.path.append(tools)

# 导入 TraCI（Traffic Control Interface）
# TraCI 是 SUMO 的 Python 控制接口，用于实时控制仿真
try:
    import traci
except ImportError:
    sys.exit("错误: 无法导入 traci。请检查 SUMO 是否安装或运行 'pip install traci'")

# 将项目根目录加入 Python 路径，以便导入项目内的其他模块
current_dir = os.path.dirname(os.path.abspath(__file__))  # 当前文件所在目录
parent_dir = os.path.dirname(current_dir)                  # 父目录
sys.path.append(parent_dir)


# 【注意】删除了这里顶层的 intersection_state_recorder 导入，移到了函数内部
# 原因：避免循环导入问题（intersection_state_recorder 可能会导入本模块）

class SUMOSimulator:
    """
    SUMO交通仿真器核心类
    
    功能：
    1. 管理SUMO仿真生命周期（启动、运行、关闭）
    2. 提供交通数据采集接口（车辆数、速度、等待时间等）
    3. 支持信号灯控制（手动切换相位、压力优化）
    5. 历史数据管理与指标计算
    """
    
    def __init__(self, config_file=os.path.join(os.getcwd(), "sumo_sim/osm.sumocfg"),
                 junctions_file: Optional[str] = os.path.join(os.getcwd(), "sumo_sim/J54_data.json"),
                 gui: bool = True,
                 history_file: Optional[str] = None,
                 additional_options: Optional[List[str]] = None,
                 verbose: bool = True,
                 port: Optional[int] = None):
        """
        初始化SUMO仿真器
        
        参数:
            config_file (str): SUMO配置文件路径（.sumocfg）
            junctions_file (str): 路口数据文件路径（JSON格式）
            gui (bool): 是否使用图形界面（True=sumo-gui, False=sumo）
            history_file (str): 历史数据存储文件路径（可选）
            additional_options (List[str]): 额外的SUMO命令行参数（可选）
            verbose (bool): 是否输出启动/预热等冗余日志（默认 True）
            port (int): 指定 TraCI 连接端口（可选，用于并行场景避免冲突）
        """
        # 文件路径配置（转换为绝对路径）
        self.config_file = os.path.abspath(config_file)        # SUMO配置文件
        self.junctions_file = os.path.abspath(junctions_file) if junctions_file else None  # 路口数据文件（可选）
        self.gui = gui  # 是否使用图形界面
        self.verbose = bool(verbose)
        self.port = port  # 指定端口（可选）
        self._active_port = None  # 实际使用的端口（用于清理残留进程）
        self.additional_options = additional_options or []  # 额外的SUMO参数
        if not self.verbose:
            # 尽可能关闭 SUMO 控制台输出（尤其是 Step #... 与 duration log）
            quiet_flags = ["--no-step-log", "--duration-log.disable"]
            for f in quiet_flags:
                if f not in self.additional_options:
                    self.additional_options.append(f)
        
        # 仿真状态标志
        self.simulation_started = False  # 仿真是否已启动
        self.warmup_done = False         # 预热是否完成
        self.warmup_steps = 300          # 预热步数（300秒，让车辆进入路网）
        self.start_time = None           # 仿真开始时间（用于计算运行时长）
        
        # 车辆计数数据结构：{路口ID: {方向: [车辆数列表]}}
        # 使用defaultdict自动初始化嵌套字典
        self.vehicle_counts = defaultdict(lambda: defaultdict(list))
        self.timestamps = defaultdict(lambda: defaultdict(list))  # 对应的时间戳

        # 历史数据存储配置
        # 如果未指定history_file，则使用配置文件同目录下的traffic_history.json
        self.history_file = history_file or os.path.join(os.path.dirname(config_file), "traffic_history.json")
        
        # 历史数据结构：记录每个时刻的交通状态
        self.historical_data = {
            'timestamps': [],      # 时间戳列表
            'phase_queues': [],    # 各相位队列长度列表
            'phases': []           # 当前相位索引列表
        }
        self.load_historical_data()  # 从文件加载已有历史数据

        # 验证必需文件是否存在
        if not os.path.exists(self.config_file):
            raise FileNotFoundError(f"SUMO配置文件未找到: {self.config_file}")

        # 加载路口配置数据（包含路口ID、进口道、出口道等信息）
        # environments/ 下的场景通常没有 *_data.json，因此这里改为“可选加载”
        self.junctions_data = {}
        if self.junctions_file and os.path.exists(self.junctions_file):
            try:
                with open(self.junctions_file, 'r', encoding='utf-8') as f:
                    self.junctions_data = json.load(f)
            except Exception as e:
                print(f"Error loading junctions data: {str(e)}")
                self.junctions_data = {}  # 加载失败则使用空字典
        elif self.junctions_file:
            print(f"警告: 路口数据文件未找到，将跳过加载并使用空配置: {self.junctions_file}")

        # [修复] 延迟导入，防止循环引用
        # intersection_state_recorder 用于记录路口状态，这里将指标计算方法注入
        # TODO: intersection_state_recorder 模块不存在,暂时注释掉
        # from sumo_sim.intersection_state_recorder import intersection_state_recorder
        # intersection_state_recorder.set_metrics_supplier(self.get_intersection_metrics)

    def load_historical_data(self):
        """
        从文件加载历史交通数据
        
        功能：
        - 从 history_file 加载 JSON 格式的历史数据
        - 验证数据格式（必须包含 timestamps, phase_queues, phases）
        - 加载失败则初始化为空数据结构
        """
        try:
            # 如果历史文件存在，则读取
            if os.path.exists(self.history_file):
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    self.historical_data = json.load(f)
                # 验证数据完整性：必须包含三个关键字段
                if not all(key in self.historical_data for key in ['timestamps', 'phase_queues', 'phases']):
                    # 数据不完整，重新初始化
                    self.historical_data = {'timestamps': [], 'phase_queues': [], 'phases': []}
        except Exception:
            # 加载失败（文件损坏、格式错误等），初始化为空数据
            self.historical_data = {'timestamps': [], 'phase_queues': [], 'phases': []}

    def save_historical_data(self):
        """
        保存历史交通数据到文件
        
        功能：
        - 清理过期数据（超过24小时的数据）
        - 将当前历史数据保存为 JSON 格式
        - 自动处理保存失败的情况
        """
        try:
            # 最大保留时间：24小时（24 * 3600 秒）
            max_history = 24 * 3600
            current_time = datetime.datetime.now()
            
            # 删除过期数据（从头开始检查，直到遇到未过期的数据）
            while len(self.historical_data['timestamps']) > 0:
                # 将 ISO 格式字符串转换为 datetime 对象
                timestamp = datetime.datetime.fromisoformat(self.historical_data['timestamps'][0])
                # 如果数据已过期（超过24小时）
                if (current_time - timestamp).total_seconds() > max_history:
                    # 删除所有列表的第一个元素（保持数据同步）
                    for key in self.historical_data:
                        self.historical_data[key].pop(0)
                else:
                    break  # 遇到未过期数据，停止删除
            
            # 将数据保存为 JSON 文件
            # ensure_ascii=False：支持中文字符
            # indent=2：格式化输出，便于阅读
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self.historical_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存历史数据失败: {str(e)}")

    def collect_traffic_data(self, tl_id: str):
        """
        收集交通数据并保存到历史记录
        
        参数:
            tl_id (str): 交通信号灯ID（路口ID）
            
        功能：
        1. 获取当前时间戳
        2. 计算所有相位的压力值（队列长度）
        3. 获取当前信号灯相位
        4. 将数据追加到历史记录
        5. 每收集10次数据就保存一次到文件
        """
        try:
            # 记录当前时间
            current_time = datetime.datetime.now()
            
            # 计算所有相位的压力值（入口队列 - 出口队列）
            phase_queues = self.calculate_all_phases_pressure(tl_id)
            
            # 获取当前信号灯相位信息
            phase_info = self.get_current_phase(tl_id)
            current_phase = phase_info.get('phase_index', 0)  # 默认相位0

            # 将数据追加到历史记录（保持三个列表同步）
            self.historical_data['timestamps'].append(current_time.isoformat())  # ISO格式时间字符串
            self.historical_data['phase_queues'].append(phase_queues)           # 各相位压力值
            self.historical_data['phases'].append(current_phase)                 # 当前相位索引

            # 每收集10次数据就保存一次（减少文件I/O频率）
            if len(self.historical_data['timestamps']) % 10 == 0:
                self.save_historical_data()
        except Exception as e:
            print(f"收集交通数据失败: {str(e)}")

    def get_historical_data(self, tl_id: str, time_window: Optional[int] = None):
        """
        获取历史交通数据（支持时间窗口过滤）
        
        参数:
            tl_id (str): 交通信号灯ID（当前实现中未使用，预留用于多路口）
            time_window (Optional[int]): 时间窗口（秒），None=返回全部数据
            
        返回:
            dict: 包含 timestamps, phase_queues, phases 的字典
            
        示例：
            get_historical_data("J54", 300)  # 获取最近5分钟的数据
            get_historical_data("J54", None)  # 获取全部历史数据
        """
        # 如果没有指定时间窗口，返回全部历史数据
        if time_window is None:
            return self.historical_data
        
        # 计算起始时间（当前时间 - 时间窗口）
        current_time = datetime.datetime.now()
        start_time = current_time - datetime.timedelta(seconds=time_window)
        
        # 初始化过滤后的数据结构
        filtered_data = {'timestamps': [], 'phase_queues': [], 'phases': []}

        # 遍历所有历史数据，筛选出时间窗口内的数据
        for i, timestamp_str in enumerate(self.historical_data['timestamps']):
            timestamp = datetime.datetime.fromisoformat(timestamp_str)
            # 只保留时间窗口内的数据
            if timestamp >= start_time:
                filtered_data['timestamps'].append(timestamp_str)
                filtered_data['phase_queues'].append(self.historical_data['phase_queues'][i])
                filtered_data['phases'].append(self.historical_data['phases'][i])
        
        return filtered_data

    def is_connected(self):
        """
        检查是否已连接到SUMO仿真
        
        返回:
            bool: True=已连接, False=未连接
            
        用途：
        - 在执行TraCI命令前检查连接状态
        - 避免在未连接时调用TraCI导致错误
        """
        try:
            return traci.getConnection() is not None
        except:
            return False

    def start_simulation(self):
        """
        启动SUMO仿真并进行预热
        
        流程：
        1. 检查并关闭已有连接
        2. 查找sumo-gui可执行文件
        3. 构建启动命令
        4. 启动SUMO进程并建立TraCI连接
        5. 执行预热步骤（让车辆进入路网）
        
        返回:
            bool: True=启动成功, False=启动失败
        """
        try:
            # 如果仿真尚未启动
            if not self.simulation_started:
                # 步骤1：清理已有连接（如果存在）
                try:
                    if self.is_connected():
                        traci.close()  # 关闭旧连接
                except:
                    pass  # 忽略关闭失败的错误

                # 步骤2：查找 SUMO 可执行文件路径（根据 self.gui 选择 sumo-gui 或 sumo）
                # 按优先级顺序检查多个可能的位置
                want_gui = bool(self.gui)
                env_key = "SUMO_BINARY_GUI" if want_gui else "SUMO_BINARY"
                binary_name = "sumo-gui" if want_gui else "sumo"
                candidate_binaries = [
                    os.environ.get(env_key),  # 环境变量指定的路径（最高优先级）
                    os.path.join(os.environ['SUMO_HOME'], 'bin', binary_name) if 'SUMO_HOME' in os.environ else None,  # SUMO_HOME/bin
                    f"/usr/bin/{binary_name}",  # Ubuntu/Debian
                    f"/usr/local/bin/{binary_name}",  # 本地编译
                    f"/Library/Frameworks/EclipseSUMO.framework/Versions/1.25.0/EclipseSUMO/bin/{binary_name}",  # macOS框架安装
                    f"/opt/homebrew/bin/{binary_name}",  # Homebrew（Apple Silicon）
                    f"/usr/local/bin/{binary_name}",     # Homebrew（Intel Mac）
                    f"/Users/leida/Cline/sumo/bin/{binary_name}"  # 自定义安装位置
                ]

                # 遍历候选路径，找到第一个存在的可执行文件
                sumo_binary = None
                for path in candidate_binaries:
                    if path and os.path.exists(path):
                        sumo_binary = path
                        break

                # 如果所有路径都不存在，尝试使用系统PATH中的命令
                if sumo_binary is None:
                    if self.verbose:
                        print(f"警告: 未在常见路径找到 {binary_name}，尝试使用系统命令 '{binary_name}'")
                    sumo_binary = binary_name

                if self.verbose:
                    print(f"DEBUG: 使用的 SUMO 路径是: {sumo_binary}")

                # 步骤3：构建SUMO启动命令
                sumo_cmd = [
                    sumo_binary,                    # SUMO可执行文件路径
                    "-c", self.config_file,         # 配置文件路径
                    "--step-length", "1.0",         # 仿真步长（1秒/步）
                    "--no-warnings", "true",        # 禁用警告信息
                    # "--quit-on-end",              # 仿真结束后自动退出（已注释）
                ]

                # 仅在 GUI 模式下添加 --start 参数（无头模式不支持）
                if want_gui:
                    sumo_cmd.append("--start")
                
                # 添加额外的命令行参数
                if self.additional_options:
                    sumo_cmd.extend(self.additional_options)

                # 步骤4：启动SUMO进程并建立TraCI连接 (带重试机制)
                import random
                max_retries = 10 if self.port is None else 3  # 指定端口时减少重试次数
                
                for attempt in range(max_retries):
                    try:
                        # 如果指定了端口则使用，否则随机选择 (10000-60000)
                        if self.port is not None:
                            port = self.port
                        else:
                            port = random.randint(10000, 60000)
                        
                        # traci.start 会自动添加 --remote-port 参数，不需要手动添加
                        # 只需要传 port 参数即可
                        cmd_to_run = sumo_cmd

                        if self.verbose:
                            print(f"Starting SUMO with command: {' '.join(cmd_to_run)} on port {port} (Attempt {attempt+1}/{max_retries})")
                        
                        stdout = None if self.verbose else subprocess.DEVNULL
                        
                        if self.verbose:
                            traci.start(cmd_to_run, port=port, stdout=stdout)
                        else:
                            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                                traci.start(cmd_to_run, port=port, stdout=stdout, verbose=False)
                                
                        self.simulation_started = True
                        self._active_port = port  # 记录实际使用的端口
                        if self.verbose:
                            print(f"Successfully connected to SUMO on port {port}")
                        break
                    except Exception as e:
                        if attempt == max_retries - 1:
                            raise e
                        if self.verbose:
                            print(f"SUMO launch failed on port {port}, retrying... ({str(e)})")
                        # 如果是指定端口失败，等待更长时间让端口释放
                        wait_time = 1.0 if self.port is not None else random.random() * 0.5
                        time.sleep(wait_time)
                if self.verbose:
                    print("Successfully connected to SUMO")

                # 步骤5：执行预热阶段
                # 目的：让车辆进入路网，使交通流达到稳定状态
                if self.verbose:
                    print("Starting warmup phase...")
                for i in range(self.warmup_steps):  # 执行300步预热
                    # 检查连接是否仍然有效
                    if not self.is_connected():
                        raise Exception("SUMO connection lost during warmup")
                    
                    # 执行一步仿真
                    traci.simulationStep()
                    
                    # 每100步打印一次进度
                    if self.verbose and i % 100 == 0:
                        print(f"Warmup progress: {i}/{self.warmup_steps}")

                # 预热完成，标记状态并记录开始时间
                self.warmup_done = True
                self.start_time = time.time()  # 记录实际仿真开始时间
                if self.verbose:
                    print("Warmup completed. Starting real-time simulation.")
                return True  # 启动成功

        # 异常处理：启动失败时清理状态
        except Exception as e:
            print(f"Error starting simulation: {str(e)}")
            # 重置仿真状态标志
            self.simulation_started = False
            self.warmup_done = False
            # 尝试关闭可能的残留连接
            try:
                if self.is_connected():
                    traci.close()
            except:
                pass
            return False  # 启动失败

    def step(self):
        """
        执行一步仿真
        
        返回:
            bool: True=执行成功, False=执行失败
            
        用途：
        - 在主循环中调用，推进仿真时间
        - 每调用一次，仿真时间前进1秒（取决于step-length配置）
        """
        try:
            # 只有在仿真已启动且连接有效时才执行
            if self.simulation_started and self.is_connected():
                traci.simulationStep()  # 执行一步仿真
                return True
            # 连接已断开，标记状态（避免重复检查）
            if self.simulation_started:
                self.simulation_started = False
            return False
        except Exception as e:
            # 连接异常，只在首次断开时打印错误
            if self.simulation_started:
                if self.verbose:
                    print(f"Simulation step failed: {str(e)}")
                self.simulation_started = False
            return False

    def _get_current_total_waiting_time(self, tl_id: str) -> float:
        """
        计算指定路口所有受控车道的总等待时间
        
        参数:
            tl_id (str): 交通信号灯ID
            
        返回:
            float: 总等待时间（秒）
            
        用途：
        - 等待时间越低，相位效果越好
        """
        total_wait = 0.0
        try:
            # 获取该信号灯控制的所有车道
            controlled_lanes = traci.trafficlight.getControlledLanes(tl_id)
            # 使用set去重（因为一个车道可能被多个信号控制）
            for lane in set(controlled_lanes):
                # 累加每条车道的等待时间
                total_wait += traci.lane.getWaitingTime(lane)
        except traci.exceptions.TraCIException:
            pass  # 忽略TraCI异常（车道不存在等）
        return total_wait

    def step_with_state_reload(self, tl_id: str, chosen_action: int, simulation_duration: int = 10):
        # 步骤1：获取相位信息并验证
        phase_info = self.get_phase_info(tl_id)
        num_phases = phase_info.get('num_phases', 0)
        if num_phases == 0:
            return {}, 0.0  # 无相位信息，返回空结果
        
        # 生成所有可能的动作列表（相位索引：0, 1, 2, ...）
        all_possible_actions = list(range(num_phases))
        
        # 验证选择的动作是否有效
        if chosen_action not in all_possible_actions:
            chosen_action = 0  # 无效则默认为相位0

        # 步骤2：保存当前仿真状态（用于后续恢复）
        current_time = traci.simulation.getTime()
        state_file = f"temp_grpo_state_{tl_id}_{current_time}.xml"
        traci.simulation.saveState(state_file)  # 保存状态到临时文件

        # 步骤3：对每个可能的相位进行反事实推理
        counterfactual_outcomes = {}  # 存储每个相位的性能

        for phase_to_sim in all_possible_actions:
            # 恢复到保存的状态（每次模拟前都恢复）
            traci.simulation.loadState(state_file)
            # 设置要模拟的相位
            traci.trafficlight.setPhase(tl_id, phase_to_sim)

            # 模拟指定步数，累计等待时间
            accumulated_wait = 0.0
            for _ in range(simulation_duration):
                traci.simulationStep()  # 执行一步
                # 累加该步的总等待时间
                accumulated_wait += self._get_current_total_waiting_time(tl_id)

            # 记录该相位的性能（等待时间越低越好）
            counterfactual_outcomes[phase_to_sim] = accumulated_wait

        # 步骤4：恢复状态并实际执行选择的相位
        traci.simulation.loadState(state_file)
        traci.trafficlight.setPhase(tl_id, chosen_action)

        # [修复] 延迟导入，记录路口状态
        # TODO: intersection_state_recorder 模块不存在,暂时注释掉
        # from sumo_sim.intersection_state_recorder import intersection_state_recorder
        # intersection_state_recorder.enqueue_state(tl_id)

        # 实际执行选择的相位（推进仿真）
        for _ in range(simulation_duration):
            traci.simulationStep()

        # 获取选择相位的性能（用于奖励计算）
        reward_of_chosen_action = counterfactual_outcomes[chosen_action]

        # 步骤5：清理临时状态文件
        try:
            os.remove(state_file)
        except OSError:
            pass  # 删除失败不影响功能

        # 返回所有相位的性能和选择相位的奖励
        return counterfactual_outcomes, reward_of_chosen_action

    def get_junction_vehicle_counts(self, junction_id):
        """
        获取路口各方向的车辆计数和交通指标
        
        参数:
            junction_id (str): 路口ID
            
        返回:
            tuple: (traffic_data, historical_data)
                - traffic_data: dict, {方向: {指标: 值}}
                - historical_data: dict, 历史交通数据
                
        交通指标包括：
        - vehicle_count: 车辆数量
        - mean_speed: 平均速度（m/s）
        - halting_count: 停止车辆数
        - waiting_time: 平均等待时间（秒）
        """
        try:
            # 验证仿真状态
            if not self.simulation_started or not self.is_connected():
                return None, None

            # 记录采集时间
            current_time = datetime.datetime.now()
            
            # 初始化交通数据结构（每个方向的指标）
            traffic_data = defaultdict(lambda: {
                'vehicle_count': 0,    # 车辆数
                'mean_speed': 0,       # 平均速度
                'halting_count': 0,    # 停止车辆数
                'waiting_time': 0      # 平均等待时间
            })

            # 获取路口配置信息（包含进口道信息）
            junction_info = self.junctions_data.get(junction_id)
            if not junction_info:
                return None, None  # 路口配置不存在

            # 遍历每个方向（东、西、南、北等）
            for direction, lanes in junction_info["incoming_lanes"].items():
                total_speed = 0           # 累计速度
                total_waiting_time = 0    # 累计等待时间
                total_vehicles = 0        # 总车辆数

                # 遍历该方向的所有车道
                for lane in lanes:
                    lane_id = lane['lane_id']
                    try:
                        # 获取车道上的所有车辆ID
                        vehicle_ids = traci.lane.getLastStepVehicleIDs(lane_id)
                        # 累加车辆数
                        traffic_data[direction]['vehicle_count'] += len(vehicle_ids)
                        # 累加停止车辆数（速度<0.1m/s的车辆）
                        traffic_data[direction]['halting_count'] += traci.lane.getLastStepHaltingNumber(lane_id)

                        # 遍历每辆车，获取详细信息
                        for vehicle_id in vehicle_ids:
                            total_speed += traci.vehicle.getSpeed(vehicle_id)  # 累加速度
                            total_waiting_time += traci.vehicle.getAccumulatedWaitingTime(vehicle_id)  # 累加等待时间
                            total_vehicles += 1
                    except traci.exceptions.TraCIException:
                        continue  # 忽略TraCI异常（车道不存在等）

                # 计算平均值
                if total_vehicles > 0:
                    traffic_data[direction]['mean_speed'] = total_speed / total_vehicles
                    traffic_data[direction]['waiting_time'] = total_waiting_time / total_vehicles

                # 保存历史数据（保留最近20个数据点）
                self.vehicle_counts[junction_id][direction].append(traffic_data[direction]['vehicle_count'])
                self.timestamps[junction_id][direction].append(current_time)

                # 限制历史数据长度（超过20个则删除最旧的）
                if len(self.vehicle_counts[junction_id][direction]) > 20:
                    self.vehicle_counts[junction_id][direction].pop(0)
                    self.timestamps[junction_id][direction].pop(0)

            # 返回当前交通数据和历史数据
            return dict(traffic_data), self.get_historical_data(junction_id)
        except Exception as e:
            print(f"Error getting traffic data: {str(e)}")
            return None, None

    def get_current_phase(self, junction_id):
        """
        获取当前信号灯相位信息
        
        参数:
            junction_id (str): 路口ID（等同于信号灯ID）
            
        返回:
            dict: 相位信息
                - phase_index: 当前相位索引
                - phase_name: 相位名称
                - total_duration: 相位总时长（秒）
                - remaining_duration: 剩余时长（秒）
            None: 获取失败时返回
            
        用途：
        - 显示当前信号灯状态
        - 用于决策算法判断是否需要切换相位
        """
        try:
            tls_id = junction_id
            # 获取当前相位索引（0, 1, 2, ...）
            current_phase_index = traci.trafficlight.getPhase(tls_id)
            # 获取相位名称（自定义）
            phase_name = self.get_phase_name(tls_id, current_phase_index)
            # 获取相位总时长
            phase_duration = traci.trafficlight.getPhaseDuration(tls_id)
            # 计算剩余时长（下次切换时间 - 当前时间）
            remaining_duration = traci.trafficlight.getNextSwitch(tls_id) - traci.simulation.getTime()
            
            return {
                "phase_index": current_phase_index,
                "phase_name": phase_name,
                "total_duration": phase_duration,
                "remaining_duration": remaining_duration
            }
        except Exception:
            return None  # 获取失败（信号灯不存在等）

    def get_phase_name(self, tls_id, phase_index):
        """
        获取相位名称（可自定义为"东西直行"、"南北左转"等）
        
        参数:
            tls_id (str): 信号灯ID
            phase_index (int): 相位索引
            
        返回:
            str: 相位名称
        """
        return f"Phase {phase_index}"

    def get_simulation_time(self):
        """
        获取当前仿真时间（秒）
        
        返回:
            float: 仿真时间（从0开始计时）
            
        注意：
        - 这是仿真内部时间，不是真实世界时间
        - 预热阶段也会计入仿真时间
        """
        if self.is_connected():
            try:
                # traci.simulation.getTime() 返回当前仿真时间
                return traci.simulation.getTime()
            except Exception as e:
                print(f"获取仿真时间失败: {str(e)}")
                return 0
        return 0
    def get_phase_info(self, tl_id):
        """
        获取信号灯的完整相位信息
        
        参数:
            tl_id (str): 信号灯ID
            
        返回:
            dict: 相位配置信息
                - traffic_light_id: 信号灯ID
                - current_phase_index: 当前相位索引
                - num_phases: 相位总数
                - phase_durations: 各相位时长列表
                - phase_states: 各相位状态字符串列表
            {}: 获取失败时返回空字典
            
        相位状态字符串说明：
        - 'G': 绿灯（优先）
        - 'g': 绿灯（非优先）
        - 'y': 黄灯
        - 'r': 红灯
        - 'o': 关闭
        
        示例：
            "GGGrrrrGGGrrrr" 表示前3条连接绿灯，中间4条红灯，后面3条绿灯...
        """
        try:
            # 获取当前相位索引
            current_phase_index = traci.trafficlight.getPhase(tl_id)
            # 获取所有相位定义（从第一个程序逻辑中获取）
            phase_definitions = traci.trafficlight.getAllProgramLogics(tl_id)[0].phases
            
            return {
                'traffic_light_id': tl_id,
                'current_phase_index': current_phase_index,
                'num_phases': len(phase_definitions),  # 相位总数
                'phase_durations': [p.duration for p in phase_definitions],  # 各相位时长
                'phase_states': [p.state for p in phase_definitions]  # 各相位状态字符串
            }
        except Exception:
            return {}  # 获取失败

    def get_phase_controlled_lanes(self, tl_id, phase_index=None):
        """
        获取指定相位控制的车道（进口道和出口道）
        
        参数:
            tl_id (str): 信号灯ID
            phase_index (int, optional): 相位索引，None则使用当前相位
            
        返回:
            dict: 车道信息
                - phase_index: 相位索引
                - incoming_lanes: 进口道列表（绿灯放行的车道）
                - outgoing_lanes: 出口道列表（对应的下游车道）
            {}: 获取失败时返回空字典
            
        用途：
        - 计算相位压力（进口队列 vs 出口队列）
        - 判断相位的交通需求
        """
        try:
            # 如果未指定相位，使用当前相位
            if phase_index is None:
                phase_index = traci.trafficlight.getPhase(tl_id)
            
            # 获取所有相位定义
            phase_definitions = traci.trafficlight.getAllProgramLogics(tl_id)[0].phases
            if phase_index >= len(phase_definitions): 
                return {}  # 相位索引超出范围

            # 获取该相位的状态字符串（如"GGGrrrrGGGrrrr"）
            phase_state = phase_definitions[phase_index].state
            incoming_phase_lanes = []  # 进口道列表
            outgoing_phase_lanes = []  # 出口道列表
            
            # 获取信号灯控制的所有连接（from_lane -> to_lane）
            controlled_links = traci.trafficlight.getControlledLinks(tl_id)

            # 遍历相位状态字符串，找出绿灯放行的车道
            for i, state in enumerate(phase_state):
                if i < len(controlled_links):
                    # 如果是绿灯（'G' 或 'g'）
                    if state in ['G', 'g']:
                        # 获取该连接的起点和终点车道
                        from_lane, to_lane, _ = controlled_links[i][0]
                        incoming_phase_lanes.append(from_lane)  # 进口道
                        outgoing_phase_lanes.append(to_lane)    # 出口道

            return {
                'phase_index': phase_index,
                'incoming_lanes': list[Any](set[Any](incoming_phase_lanes)),  # 去重
                'outgoing_lanes': list[Any](set[Any](outgoing_phase_lanes))   # 去重
            }
        except Exception:
            return {}  # 获取失败

    def calculate_phase_pressure(self, tl_id, phase_index=None):
        """
        计算指定相位的压力值
        
        参数:
            tl_id (str): 信号灯ID
            phase_index (int, optional): 相位索引，None则使用当前相位
            
        返回:
            dict: 压力信息
                - phase_index: 相位索引
                - pressure: 压力值（进口队列 - 平均出口队列）
            0: 获取车道信息失败时返回
            
        压力值计算公式：
            pressure = incoming_queue - avg_outgoing_queue
            
        解释：
        - pressure > 0: 进口拥堵，出口畅通，应给绿灯
        - pressure < 0: 进口畅通，出口拥堵，不应给绿灯
        - pressure越大，该相位的优先级越高
        
        用途：
        - 最大压力信号控制算法（Max-Pressure）
        - 评估各相位的交通需求
        """
        # 获取该相位控制的车道
        phase_lanes = self.get_phase_controlled_lanes(tl_id, phase_index)
        if not phase_lanes: 
            return 0  # 无车道信息

        # 计算进口道总队列长度（停止车辆数）
        incoming_queue_length = sum(
            [traci.lane.getLastStepHaltingNumber(l) for l in phase_lanes.get('incoming_lanes', [])])
        
        # 计算出口道平均队列长度
        outgoing_lanes = phase_lanes.get('outgoing_lanes', [])
        outgoing_queue_sum = sum([traci.lane.getLastStepHaltingNumber(l) for l in outgoing_lanes])
        avg_outgoing = outgoing_queue_sum / len(outgoing_lanes) if outgoing_lanes else 0

        # 压力 = 进口队列 - 平均出口队列
        return {
            'phase_index': phase_lanes.get('phase_index'),
            'pressure': incoming_queue_length - avg_outgoing
        }

    def calculate_all_phases_pressure(self, tl_id):
        """
        计算所有相位的压力值
        
        参数:
            tl_id (str): 信号灯ID
            
        返回:
            dict: {相位索引: 压力信息}
            
        用途：
        - 对比所有相位的压力，选择最大压力相位
        - 提供给LLM作为决策依据
        """
        phase_info = self.get_phase_info(tl_id)
        phase_pressures = {}
        
        # 遍历所有相位，计算各自的压力
        for i in range(phase_info.get('num_phases', 0)):
            phase_pressures[i] = self.calculate_phase_pressure(tl_id, i)
        
        return phase_pressures

    def _collect_phase_traffic_stats(self, tl_id: str) -> Dict[int, Dict[str, float]]:
        """
        收集各相位控制车道的交通统计数据
        
        参数:
            tl_id (str): 信号灯ID
            
        返回:
            dict: {相位索引: {'queue_vehicles': 排队车辆数, 'passed_vehicles': 通过车辆数}}
            
        说明:
            - queue_vehicles: 该相位控制车道上的排队车辆数（停止车辆）
            - passed_vehicles: 该相位控制车道上已通过的车辆数（用车道平均速度/长度估算）
        """
        phase_info = self.get_phase_info(tl_id)
        num_phases = phase_info.get('num_phases', 0)
        
        stats = {}
        for phase_idx in range(num_phases):
            # 获取该相位控制的车道
            phase_lanes = self.get_phase_controlled_lanes(tl_id, phase_idx)
            incoming_lanes = phase_lanes.get('incoming_lanes', [])
            
            total_queue = 0.0
            total_passed = 0.0
            
            for lane_id in incoming_lanes:
                try:
                    # 排队车辆数（停止的车辆）
                    halting = traci.lane.getLastStepHaltingNumber(lane_id)
                    total_queue += halting
                    
                    # 通过车辆数：用车道上非停止车辆估算
                    vehicle_count = traci.lane.getLastStepVehicleNumber(lane_id)
                    # 非停止车辆视为正在通过
                    passed = max(0, vehicle_count - halting)
                    total_passed += passed
                except traci.exceptions.TraCIException:
                    continue
            
            # 计算平均值（按车道数归一化）
            num_lanes = len(incoming_lanes) if incoming_lanes else 1
            stats[phase_idx] = {
                'queue_vehicles': round(total_queue / num_lanes, 2),
                'passed_vehicles': round(total_passed / num_lanes, 2)
            }
        
        return stats

    def _format_traffic_state(self, tl_id: str, current_phase: int, current_duration: int,
                               phase_stats: Dict[int, Dict[str, float]]) -> str:
        """
        将交通状态格式化为训练数据的文本格式
        
        参数:
            tl_id (str): 信号灯ID
            current_phase (int): 当前相位索引
            current_duration (int): 当前相位持续时间
            phase_stats (dict): 各相位交通统计数据
            
        返回:
            str: 格式化的交通状态文本
        """
        phase_info = self.get_phase_info(tl_id)
        num_phases = phase_info.get('num_phases', 0)
        
        # 步骤1: 先收集所有相位控制的所有唯一车道ID
        phase_to_raw_lanes = {}  # {相位索引: [车道ID列表]}
        all_unique_lanes = set()
        for phase_idx in range(num_phases):
            phase_lanes = self.get_phase_controlled_lanes(tl_id, phase_idx)
            incoming_lanes = phase_lanes.get('incoming_lanes', [])
            phase_to_raw_lanes[phase_idx] = incoming_lanes
            all_unique_lanes.update(incoming_lanes)
        
        # 步骤2: 给每个唯一车道分配一个唯一编号（0, 1, 2, ...）
        sorted_unique_lanes = sorted(all_unique_lanes)
        lane_to_index = {lane: idx for idx, lane in enumerate(sorted_unique_lanes)}
        
        # 步骤3: 将每个相位的车道ID转换为唯一编号
        phase_to_lanes = {}
        for phase_idx in range(num_phases):
            raw_lanes = phase_to_raw_lanes[phase_idx]
            lane_indices = sorted(set(lane_to_index[lane] for lane in raw_lanes))
            phase_to_lanes[phase_idx] = lane_indices
        
        # 构建路口场景描述
        all_lanes = list(range(len(sorted_unique_lanes)))
        phase_lane_desc = "，".join([f"相位{p}控制车道{phase_to_lanes[p]}" for p in range(num_phases)])
        
        scene_desc = (
            f"路口场景描述：该路口有{num_phases}个相位，分别是{list(range(num_phases))}，"
            f"有{len(all_lanes)}个车道，分别是{all_lanes}，其中{phase_lane_desc}"
        )
        
        # 构建交通状态描述
        state_desc = f"交通状态描述：目前该交叉口的当前相位为{current_phase}，当前相位持续时间为{current_duration}。"
        
        # 各相位的车道交通数据
        phase_traffic_lines = []
        for phase_idx in range(num_phases):
            stats = phase_stats.get(phase_idx, {'queue_vehicles': 0, 'passed_vehicles': 0})
            line = (
                f"相位({phase_idx})控制的车道的排队车辆为{stats['queue_vehicles']:.2f}，"
                f"通过车辆数为{stats['passed_vehicles']:.2f}。"
            )
            phase_traffic_lines.append(line)
        
        # 组合完整的input文本
        full_text = scene_desc + "\n" + state_desc + "\n" + "\n".join(phase_traffic_lines)
        return full_text

    def _save_training_data(self, data: dict, output_file: str = "training_data.json"):
        """
        将训练数据追加保存到JSON文件
        
        参数:
            data (dict): 单条训练数据 {instruction, input, output}
            output_file (str): 输出文件路径
        """
        try:
            # 读取现有数据
            existing_data = []
            if os.path.exists(output_file):
                with open(output_file, 'r', encoding='utf-8') as f:
                    try:
                        existing_data = json.load(f)
                        if not isinstance(existing_data, list):
                            existing_data = [existing_data]
                    except json.JSONDecodeError:
                        existing_data = []
            
            # 追加新数据
            existing_data.append(data)
            
            # 保存回文件
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(existing_data, f, ensure_ascii=False, indent=2)
                
            print(f"[GRPO] 训练数据已保存到 {output_file}，当前共 {len(existing_data)} 条数据")
        except Exception as e:
            print(f"[GRPO] 保存训练数据失败: {str(e)}")

    def generate_grpo_training_data(self, tl_id: str, duration_range: tuple = (20, 90, 10),
                                      output_file: str = "training_data.json",
                                      use_max_pressure: bool = True,
                                      action_duration: int = 30) -> bool:
        """
        生成GRPO训练数据
        
        在当前相位结束时调用，遍历所有相位×持续时间组合进行反事实仿真，
        收集交通数据并保存为训练数据格式。
        
        参数:
            tl_id (str): 信号灯ID
            duration_range (tuple): (最小时长, 最大时长, 步长)，默认(20, 90, 10)
            output_file (str): 输出文件路径
            use_max_pressure (bool): 是否使用最大压力策略决定下一个状态，默认True
            action_duration (int): 使用最大压力时执行的相位持续时间，默认30秒
            
        返回:
            bool: 是否成功生成数据
        """
        try:
            # 获取相位信息
            phase_info = self.get_phase_info(tl_id)
            num_phases = phase_info.get('num_phases', 0)
            if num_phases == 0:
                print(f"[GRPO] 信号灯 {tl_id} 无相位信息")
                return False
            
            # 获取当前相位和持续时间
            current_phase_info = self.get_current_phase(tl_id)
            current_phase = current_phase_info.get('phase_index', 0)
            current_duration = int(current_phase_info.get('total_duration', 30))
            
            # === 步骤1: 保存当前仿真状态 ===
            current_time = traci.simulation.getTime()
            state_file = f"temp_grpo_state_{tl_id}_{int(current_time)}.xml"
            traci.simulation.saveState(state_file)
            print(f"[GRPO] 已保存仿真状态到 {state_file}")
            
            # === 步骤2: 收集当前交通状态作为 input ===
            current_stats = self._collect_phase_traffic_stats(tl_id)
            input_text = self._format_traffic_state(tl_id, current_phase, current_duration, current_stats)
            
            # === 步骤3: 遍历所有相位×持续时间组合 ===
            min_duration, max_duration, step = duration_range
            durations = list(range(min_duration, max_duration + 1, step))
            
            output_lines = []
            total_combinations = num_phases * len(durations)
            processed = 0
            
            for next_phase in range(num_phases):
                for duration in durations:
                    # 恢复到保存的状态
                    traci.simulation.loadState(state_file)
                    
                    # 切换到目标相位
                    traci.trafficlight.setPhase(tl_id, next_phase)
                    
                    # 仿真指定时长
                    for _ in range(duration):
                        traci.simulationStep()
                    
                    # 收集该相位持续时间结束时的交通数据
                    end_stats = self._collect_phase_traffic_stats(tl_id)
                    
                    # 格式化该组合的输出文本
                    output_line = f"下一个信号相位：{next_phase}，相位持续时间为{duration}, 该相位时间内，"
                    phase_traffic_parts = []
                    for phase_idx in range(num_phases):
                        stats = end_stats.get(phase_idx, {'queue_vehicles': 0, 'passed_vehicles': 0})
                        part = (
                            f"相位({phase_idx})控制的车道的排队车辆为{stats['queue_vehicles']:.2f}，"
                            f"通过车辆数为{stats['passed_vehicles']:.2f}"
                        )
                        phase_traffic_parts.append(part)
                    output_line += "\n" + "。\n".join(phase_traffic_parts) + "。"
                    output_lines.append(output_line)
                    
                    processed += 1
                    if processed % 10 == 0:
                        print(f"[GRPO] 进度: {processed}/{total_combinations}")
            
            # === 步骤4: 恢复原始状态 ===
            traci.simulation.loadState(state_file)
            
            # === 步骤5: 使用最大压力策略决定下一个状态（确保数据连贯性）===
            if use_max_pressure:
                # 计算最大压力相位
                max_pressure_phase = self.get_max_pressure_phase(tl_id)
                if max_pressure_phase is not None:
                    print(f"[GRPO] 使用最大压力策略: 选择相位 {max_pressure_phase}，持续 {action_duration} 秒")
                    # 切换到最大压力相位
                    traci.trafficlight.setPhase(tl_id, max_pressure_phase)
                    # 实际执行该相位指定时长
                    for _ in range(action_duration):
                        traci.simulationStep()
                    print(f"[GRPO] 已执行相位 {max_pressure_phase}，下一条数据将基于此状态")
                else:
                    print(f"[GRPO] 无法获取最大压力相位，保持当前状态")
            
            # 清理临时状态文件
            try:
                os.remove(state_file)
            except OSError:
                pass
            
            # === 步骤6: 组装训练数据并保存 ===
            instruction = (
                "你是一位交通管理专家。你可以运用你的交通常识知识来解决交通信号控制任务。"
                "根据给定的交通场景和状态，预测下一个信号相位。各个相位持续时间从20秒到90秒不等。"
                "你必须直接回答：下一个信号相位是={你优化的相位}， {你优化的该相位持续时间}"
            )
            
            training_data = {
                "instruction": instruction,
                "input": input_text,
                "output": "\n".join(output_lines)
            }
            
            self._save_training_data(training_data, output_file)
            print(f"[GRPO] 成功生成训练数据，共 {total_combinations} 个组合")
            return True
            
        except Exception as e:
            print(f"[GRPO] 生成训练数据失败: {str(e)}")
            import traceback
            traceback.print_exc()
            # 尝试清理状态文件
            try:
                if 'state_file' in locals():
                    os.remove(state_file)
            except:
                pass
            return False

    def get_max_pressure_phase(self, tl_id):
        """
        获取最大压力相位（Max-Pressure算法）
        
        参数:
            tl_id (str): 信号灯ID
            
        返回:
            int: 压力最大的相位索引
            None: 无有效相位
            
        原理：
        - 选择压力最大的相位给予绿灯
        - 这是一种经典的自适应信号控制算法
        - 能有效减少排队长度和等待时间
        """
        all_pressures = self.calculate_all_phases_pressure(tl_id)
        max_pressure = float('-inf')  # 初始化为负无穷
        max_phase = None
        
        # 遍历所有相位，找出压力最大的
        for idx, info in all_pressures.items():
            if info['pressure'] > max_pressure:
                max_pressure = info['pressure']
                max_phase = idx
        
        return max_phase

    def set_phase_switch(self, tl_id, max_pressure_phase):
        """
        切换信号灯相位（如果需要）
        
        参数:
            tl_id (str): 信号灯ID
            max_pressure_phase (int): 目标相位索引
            
        返回:
            bool: True（始终返回成功）
            
        功能：
        - 如果目标相位与当前相位不同，则切换相位
        - 记录路口状态（用于数据采集）
        """
        # 获取当前相位
        current_phase = traci.trafficlight.getPhase(tl_id)
        
        # 如果目标相位有效且与当前相位不同，则切换
        if max_pressure_phase is not None and current_phase != max_pressure_phase:
            traci.trafficlight.setPhase(tl_id, max_pressure_phase)

        # [修复] 延迟导入，记录路口状态
        # TODO: intersection_state_recorder 模块不存在,暂时注释掉
        # from sumo_sim.intersection_state_recorder import intersection_state_recorder
        # intersection_state_recorder.enqueue_state(tl_id)
        
        return True

    def get_intersection_metrics(self, tl_id: str, time_window: int = 300) -> Dict[str, float]:
        """
        计算路口的综合交通指标
        
        参数:
            tl_id (str): 信号灯ID
            time_window (int): 统计时间窗口（秒），默认300秒（5分钟）
            
        返回:
            dict: 交通指标
                - average_saturation: 平均饱和度（0-1）
                - total_vehicles: 总车辆数
                - average_queue_length: 平均队列长度（米）
                - max_saturation: 最大饱和度
                - max_queue_length: 最大队列长度（米）
                - vehicle_throughput: 车辆通过率（辆/小时）
                - congestion_index: 拥堵指数（0-1）
                - congestion_level: 拥堵等级（文字描述）
            {}: 无数据时返回空字典
            
        指标说明：
        - 饱和度：车道使用率，越高越拥堵
        - 队列长度：排队车辆占用的道路长度
        - 拥堵指数：综合指标，考虑饱和度、队列、延误
        """
        # 验证仿真状态
        if not self.simulation_started: 
            return {}
        
        # 获取历史数据（指定时间窗口）
        history = self.get_historical_data(tl_id, time_window)
        if not history or not history['timestamps']: 
            return {}  # 无历史数据

        # 获取信号灯控制的所有车道（去重）
        controlled_lanes = list(set(traci.trafficlight.getControlledLanes(tl_id)))
        
        # 初始化累计变量
        total_saturation = 0.0      # 累计饱和度
        total_vehicles = 0           # 总车辆数
        total_queue_length = 0.0    # 累计队列长度
        max_saturation = 0.0        # 最大饱和度
        max_queue_length = 0.0      # 最大队列长度
        total_delay = 0.0           # 累计延误
        valid_lanes = 0             # 有效车道数
        total_steps = 0             # 有效步数

        # 遍历历史数据的每个时间步
        for queues in history['phase_queues']:
            step_saturation = 0.0      # 该步的饱和度
            step_queue_length = 0.0    # 该步的队列长度
            step_delay = 0.0           # 该步的延误
            step_valid_lanes = 0       # 该步的有效车道数

            # 遍历每条车道，累计指标
            for lane_id in controlled_lanes:
                try:
                    # 获取车道上的车辆数
                    vehicle_count = traci.lane.getLastStepVehicleNumber(lane_id)
                    # 获取停止车辆数
                    halting_vehicles = traci.lane.getLastStepHaltingNumber(lane_id)
                    # 获取等待时间（延误）
                    mean_delay = traci.lane.getWaitingTime(lane_id)

                    # 计算饱和度（假设每辆车占5米，车道长100米）
                    saturation = ((vehicle_count + halting_vehicles) * 5) / 100
                    step_saturation += saturation
                    
                    # 计算队列长度（停止车辆数 × 5米/辆）
                    step_queue_length += (halting_vehicles * 5)
                    
                    # 累加延误
                    step_delay += mean_delay
                    
                    # 累加总车辆数
                    total_vehicles += vehicle_count
                    
                    # 有效车道计数
                    step_valid_lanes += 1
                except traci.exceptions.TraCIException:
                    continue  # 忽略TraCI异常

            # 如果该步有有效数据，累加到总计
            if step_valid_lanes > 0:
                # 计算该步的平均值并累加
                total_saturation += (step_saturation / step_valid_lanes)
                total_queue_length += (step_queue_length / step_valid_lanes)
                total_delay += (step_delay / step_valid_lanes)
                
                # 更新最大值
                max_saturation = max(max_saturation, step_saturation / step_valid_lanes)
                max_queue_length = max(max_queue_length, step_queue_length / step_valid_lanes)
                
                # 有效步数计数
                total_steps += 1
                valid_lanes = step_valid_lanes

        # 如果有有效数据，计算最终指标
        if total_steps > 0:
            # 计算平均值
            avg_saturation = total_saturation / total_steps
            avg_queue_length = total_queue_length / total_steps
            avg_delay = total_delay / total_steps
            
            # 计算车辆通过率（辆/小时）
            # (总车辆数 / 步数) × 3600秒/小时
            vehicle_throughput = (total_vehicles / total_steps) * 3600

            # 计算综合拥堵指数（0-1，加权平均）
            # 权重：饱和度40%，队列长度30%，延误30%
            congestion_index = (
                    0.4 * min(avg_saturation, 1.0) +  # 饱和度（归一化到0-1）
                    0.3 * min(avg_queue_length / (valid_lanes * 50 if valid_lanes else 1), 1.0) +  # 队列长度归一化
                    0.3 * min(avg_delay / 60, 1.0)  # 延误归一化（60秒为基准）
            )

            # 根据拥堵指数判定拥堵等级
            level = "非常畅通"
            if congestion_index >= 0.9:
                level = "严重拥堵"
            elif congestion_index >= 0.7:
                level = "中度拥堵"
            elif congestion_index >= 0.5:
                level = "轻度拥堵"
            elif congestion_index >= 0.3:
                level = "基本畅通"

            # 返回所有指标
            return {
                'average_saturation': avg_saturation,        # 平均饱和度
                'total_vehicles': total_vehicles,            # 总车辆数
                'average_queue_length': avg_queue_length,    # 平均队列长度
                'max_saturation': max_saturation,            # 最大饱和度
                'max_queue_length': max_queue_length,        # 最大队列长度
                'vehicle_throughput': vehicle_throughput,    # 车辆通过率
                'congestion_index': congestion_index,        # 拥堵指数
                'congestion_level': level                    # 拥堵等级
            }
        
        return {}  # 无有效数据

    def save_metrics_to_csv(self, tl_id, metrics, csv_file="intersection_metrics.csv"):
        """
        将路口指标保存到CSV文件
        
        参数:
            tl_id (str): 信号灯ID
            metrics (dict): 指标字典（由get_intersection_metrics返回）
            csv_file (str): CSV文件路径，默认"intersection_metrics.csv"
            
        功能：
        - 如果文件不存在，创建文件并写入表头
        - 追加一行数据到文件末尾
        - 包含时间戳、路口ID、所有交通指标
        
        用途：
        - 长期数据采集和分析
        - 生成交通报告
        - 训练机器学习模型
        """
        # 检查文件是否存在
        file_exists = os.path.isfile(csv_file)
        
        # 以追加模式打开文件
        with open(csv_file, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            # 如果文件不存在，先写入表头
            if not file_exists:
                writer.writerow([
                    "timestamp",              # 时间戳
                    "traffic_light_id",       # 信号灯ID
                    "average_saturation",     # 平均饱和度
                    "total_vehicles",         # 总车辆数
                    "average_queue_length",   # 平均队列长度
                    "max_saturation",         # 最大饱和度
                    "max_queue_length",       # 最大队列长度
                    "vehicle_throughput",     # 车辆通过率
                    "congestion_index",       # 拥堵指数
                    "congestion_level"        # 拥堵等级
                ])
            
            # 写入数据行（使用get方法提供默认值，避免KeyError）
            writer.writerow([
                datetime.datetime.now().isoformat(),           # 当前时间（ISO格式）
                tl_id,                                          # 路口ID
                metrics.get('average_saturation', 0),          # 平均饱和度
                metrics.get('total_vehicles', 0),              # 总车辆数
                metrics.get('average_queue_length', 0),        # 平均队列长度
                metrics.get('max_saturation', 0),              # 最大饱和度
                metrics.get('max_queue_length', 0),            # 最大队列长度
                metrics.get('vehicle_throughput', 0),          # 车辆通过率
                metrics.get('congestion_index', 0),            # 拥堵指数
                metrics.get('congestion_level', "")            # 拥堵等级
            ])

    # ==================== GRPO 评估专用方法 ====================
    
    def save_grpo_checkpoint(self, tl_id: str) -> str:
        """
        保存当前仿真状态到临时文件
        
        参数:
            tl_id (str): 信号灯ID（用于生成唯一的状态文件名）
            
        返回:
            str: 状态文件路径
            
        用途：
        - GRPO 训练时保存检查点，以便对多个决策从同一起点评估
        - 支持反事实推理（counterfactual reasoning）
        """
        if not self.is_connected():
            raise RuntimeError("仿真未连接，无法保存状态")
        
        current_time = traci.simulation.getTime()
        state_file = f"temp_grpo_checkpoint_{tl_id}_{int(current_time)}.xml"
        traci.simulation.saveState(state_file)
        return state_file
    
    def restore_simulation_state(self, state_file: str):
        """
        恢复仿真状态
        
        参数:
            state_file (str): 状态文件路径
            
        用途：
        - GRPO 训练时从检查点恢复，评估另一个决策
        """
        if not self.is_connected():
            raise RuntimeError("仿真未连接，无法恢复状态")
        
        if not os.path.exists(state_file):
            raise FileNotFoundError(f"状态文件不存在: {state_file}")
        
        traci.simulation.loadState(state_file)
    
    def cleanup_state_file(self, state_file: str):
        """
        清理临时状态文件
        
        参数:
            state_file (str): 状态文件路径
        """
        try:
            if os.path.exists(state_file):
                os.remove(state_file)
        except OSError:
            pass  # 删除失败不影响功能
    
    def evaluate_action_for_grpo(self, tl_id: str, phase: int, duration: int,
                                  state_file: str = None) -> Dict[str, float]:
        """
        评估单个信号控制决策的效果
        
        参数:
            tl_id (str): 信号灯ID
            phase (int): 要执行的相位索引
            duration (int): 相位持续时间（秒）
            state_file (str, optional): 如果提供，先恢复到该状态再执行
            
        返回:
            dict: 评估指标
                - passed_vehicles: 期间通过的车辆数
                - queue_vehicles: 期末排队车辆数
                - total_waiting_time: 总等待时间
                - simulation_time_after: 执行后的仿真时间
                
        用途：
        - GRPO 奖励函数中评估模型生成的信号控制决策
        """
        if not self.is_connected():
            raise RuntimeError("仿真未连接，无法评估决策")
        
        # 如果提供了状态文件，先恢复到该状态
        if state_file:
            self.restore_simulation_state(state_file)
        
        # 验证相位索引有效性
        phase_info = self.get_phase_info(tl_id)
        num_phases = phase_info.get('num_phases', 0)
        if phase < 0 or phase >= num_phases:
            phase = 0  # 无效相位则使用默认相位0
        
        # 限制持续时间在合理范围内
        duration = max(5, min(duration, 120))  # 5-120秒
        
        # 记录执行前的车辆状态（用于计算通过车辆数）
        controlled_lanes = list(set(traci.trafficlight.getControlledLanes(tl_id)))
        vehicles_before = set()
        for lane in controlled_lanes:
            try:
                vehicles_before.update(traci.lane.getLastStepVehicleIDs(lane))
            except traci.exceptions.TraCIException:
                continue
        
        # 切换到指定相位
        traci.trafficlight.setPhase(tl_id, phase)
        
        # 执行仿真指定时长
        total_waiting_time = 0.0
        for _ in range(duration):
            traci.simulationStep()
            # 累计等待时间
            total_waiting_time += self._get_current_total_waiting_time(tl_id)
        
        # 收集执行后的指标
        vehicles_after = set()
        queue_vehicles = 0
        for lane in controlled_lanes:
            try:
                current_vehicles = traci.lane.getLastStepVehicleIDs(lane)
                vehicles_after.update(current_vehicles)
                queue_vehicles += traci.lane.getLastStepHaltingNumber(lane)
            except traci.exceptions.TraCIException:
                continue
        
        # 计算通过车辆数：执行前存在但执行后不存在的车辆（已离开路口）
        passed_vehicles = len(vehicles_before - vehicles_after)
        
        return {
            'passed_vehicles': passed_vehicles,
            'queue_vehicles': queue_vehicles,
            'total_waiting_time': total_waiting_time,
            'simulation_time_after': traci.simulation.getTime()
        }
    
    def evaluate_multiple_actions_for_grpo(self, tl_id: str, 
                                            actions: List[Tuple[int, int]]) -> List[Dict[str, float]]:
        """
        批量评估多个信号控制决策（GRPO num_generations 场景）
        
        参数:
            tl_id (str): 信号灯ID
            actions (List[Tuple[int, int]]): 决策列表，每个元素为 (相位, 持续时间)
            
        返回:
            List[dict]: 每个决策的评估指标列表
            
        用途：
        - GRPO 训练时评估 num_generations 个模型生成的决策
        - 所有决策从同一个仿真状态检查点开始评估，确保公平比较
        """
        if not self.is_connected():
            raise RuntimeError("仿真未连接，无法评估决策")
        
        # 保存当前仿真状态作为检查点
        state_file = self.save_grpo_checkpoint(tl_id)
        
        results = []
        try:
            for phase, duration in actions:
                # 从检查点恢复仿真状态
                self.restore_simulation_state(state_file)
                
                # 评估该决策
                result = self.evaluate_action_for_grpo(tl_id, phase, duration)
                results.append(result)
            
            # 恢复到原始状态（用于后续实际执行最优决策或继续训练）
            self.restore_simulation_state(state_file)
            
        finally:
            # 清理临时状态文件
            self.cleanup_state_file(state_file)
        
        return results
    
    def get_current_traffic_state_prompt(self, tl_id: str) -> str:
        """
        获取当前交通状态作为 LLM prompt
        
        参数:
            tl_id (str): 信号灯ID
            
        返回:
            str: 格式化的交通状态文本（用于 GRPO 训练的 prompt）
            
        用途：
        - GRPO 在线训练时，动态生成实时交通状态作为模型输入
        """
        if not self.is_connected():
            return ""
        
        # 获取当前相位信息
        current_phase_info = self.get_current_phase(tl_id)
        current_phase = current_phase_info.get('phase_index', 0) if current_phase_info else 0
        current_duration = int(current_phase_info.get('total_duration', 30)) if current_phase_info else 30
        
        # 收集各相位的交通统计数据
        phase_stats = self._collect_phase_traffic_stats(tl_id)
        
        # 格式化为 prompt 文本
        return self._format_traffic_state(tl_id, current_phase, current_duration, phase_stats)
    
    def execute_best_action(self, tl_id: str, phase: int, duration: int):
        """
        实际执行选定的最优决策（GRPO 评估后使用）
        
        参数:
            tl_id (str): 信号灯ID
            phase (int): 要执行的相位索引
            duration (int): 相位持续时间（秒）
            
        用途：
        - GRPO 评估完所有决策后，选择最优决策实际执行
        - 推进仿真状态，为下一轮训练做准备
        """
        if not self.is_connected():
            raise RuntimeError("仿真未连接，无法执行决策")
        
        # 验证相位索引
        phase_info = self.get_phase_info(tl_id)
        num_phases = phase_info.get('num_phases', 0)
        if phase < 0 or phase >= num_phases:
            phase = 0
        
        # 限制持续时间
        duration = max(5, min(duration, 120))
        
        # 切换到指定相位并执行
        traci.trafficlight.setPhase(tl_id, phase)
        
        for _ in range(duration):
            traci.simulationStep()
    
    # ==================== GRPO 评估专用方法结束 ====================

    def close(self):
        """
        关闭仿真并清理资源

        功能：
        - 关闭TraCI连接
        - 杀掉占用端口的残留 SUMO 进程
        - 重置仿真状态标志
        """
        try:
            # 如果连接存在，关闭它
            if self.is_connected():
                traci.close()
        except Exception:
            pass  # 忽略关闭失败的错误

        # 杀掉可能残留的 SUMO 进程（占用端口未释放）
        if self._active_port is not None:
            self._kill_sumo_on_port(self._active_port)
            self._active_port = None

        # 重置状态标志
        self.simulation_started = False

    @staticmethod
    def _kill_sumo_on_port(port: int):
        """杀掉占用指定端口的 SUMO 残留进程"""
        try:
            import signal
            result = subprocess.run(
                ['lsof', '-ti', f':{port}'],
                capture_output=True, text=True, timeout=5
            )
            if result.stdout.strip():
                for pid_str in result.stdout.strip().split('\n'):
                    try:
                        pid = int(pid_str)
                        os.kill(pid, signal.SIGTERM)
                    except (ValueError, ProcessLookupError, PermissionError):
                        pass
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass  # lsof 不可用或超时，跳过


def verify_sumo_config(config_file):
    """
    验证SUMO配置文件是否存在
    
    参数:
        config_file (str): 配置文件路径
        
    返回:
        tuple: (是否有效, 验证消息)
        
    用途：
    - 在启动仿真前预检查配置文件
    """
    if not os.path.exists(config_file): 
        return False, "配置文件不存在"
    return True, "配置文件验证通过"


# === 全局变量：单例模式管理仿真器 ===
_simulation_manager = None   # 全局仿真器实例
_simulation_thread = None    # 后台仿真线程
_stop_event = Event()        # 停止信号（用于优雅退出）


def initialize_sumo(config_file=None, junctions_file=None, gui=True, history_file=None, 
                    run_in_background_thread=True, grpo_training_mode=False,
                    grpo_tl_id="J54", grpo_output_file="training_data.json",
                    grpo_duration_range=(20, 90, 10),
                    grpo_use_max_pressure=True, grpo_action_duration=30):
    """
    初始化SUMO模拟器（单例模式）
    
    参数:
        config_file (str): SUMO配置文件路径
        junctions_file (str): 路口数据文件路径
        gui (bool): 是否使用图形界面
        history_file (str): 历史数据文件路径
        run_in_background_thread (bool): 是否在后台线程运行
            - True: 自动运行模式（数据采集）
            - False: 手动控制模式（GRPO/强化学习）
        grpo_training_mode (bool): 是否启用GRPO训练数据生成模式
        grpo_tl_id (str): GRPO模式下监控的信号灯ID
        grpo_output_file (str): GRPO训练数据输出文件路径
        grpo_duration_range (tuple): GRPO相位持续时间范围 (最小, 最大, 步长)
        grpo_use_max_pressure (bool): 是否使用最大压力策略决定下一个状态，默认True
        grpo_action_duration (int): 使用最大压力时执行的相位持续时间（秒），默认30
            
    返回:
        SUMOSimulator: 仿真器实例
        None: 启动失败
        
    运行模式说明：
    1. 数据采集模式（run_in_background_thread=True）：
       - 仿真在后台线程自动运行
       - 每10秒采集一次交通数据并保存
       - 适用于长期监测、数据收集
       
    2. 手动控制模式（run_in_background_thread=False）：
       - 仿真启动后等待外部调用step()或step_with_state_reload()
       - 适用于强化学习训练、实验对比
       
    3. GRPO训练数据生成模式（grpo_training_mode=True）：
       - 在每个相位自然结束时自动生成训练数据
       - 遍历所有相位×持续时间组合进行反事实仿真
       - 使用最大压力策略决定下一个状态（确保数据连贯性）
       - 数据保存到 grpo_output_file
    """
    global _simulation_manager, _simulation_thread, _stop_event
    
    # 如果已经初始化，直接返回现有实例（单例模式）
    if _simulation_manager is not None: 
        return _simulation_manager

    # 使用默认路径（如果未指定）
    if config_file is None: 
        config_file = os.path.join(os.getcwd(), "sumo_sim/osm.sumocfg")
    if junctions_file is None: 
        junctions_file = os.path.join(os.getcwd(), "sumo_sim/J54_data.json")

    # 清除停止信号
    _stop_event.clear()
    
    # 创建仿真器实例
    _simulation_manager = SUMOSimulator(config_file, junctions_file, gui, history_file)

    # 尝试启动仿真
    if _simulation_manager.start_simulation():
        print("SUMO仿真成功启动")
        
        # 如果选择后台线程模式
        if run_in_background_thread:
            def run_simulation():
                """
                后台仿真循环
                
                功能：
                - 每秒执行一步仿真
                - 每10秒采集一次数据
                - 响应停止信号优雅退出
                - 如果启用GRPO模式，在相位结束时生成训练数据
                """
                # GRPO模式：跟踪上一步的相位
                last_phase = None
                if grpo_training_mode:
                    print(f"[GRPO] 训练数据生成模式已启用，监控信号灯: {grpo_tl_id}")
                    print(f"[GRPO] 持续时间范围: {grpo_duration_range}, 输出文件: {grpo_output_file}")
                    print(f"[GRPO] 使用最大压力策略: {grpo_use_max_pressure}, 动作持续时间: {grpo_action_duration}秒")
                    try:
                        last_phase = traci.trafficlight.getPhase(grpo_tl_id)
                    except:
                        last_phase = None
                
                while not _stop_event.is_set():
                    # 执行一步仿真
                    if not _simulation_manager.step(): 
                        break  # 仿真失败，退出循环
                    
                    # GRPO模式：检测相位切换
                    if grpo_training_mode:
                        try:
                            current_phase = traci.trafficlight.getPhase(grpo_tl_id)
                            # 检测相位是否发生变化（相位结束）
                            if last_phase is not None and current_phase != last_phase:
                                print(f"[GRPO] 检测到相位切换: {last_phase} -> {current_phase}")
                                # 在相位刚切换时生成训练数据
                                _simulation_manager.generate_grpo_training_data(
                                    grpo_tl_id, 
                                    duration_range=grpo_duration_range,
                                    output_file=grpo_output_file,
                                    use_max_pressure=grpo_use_max_pressure,
                                    action_duration=grpo_action_duration
                                )
                            last_phase = current_phase
                        except Exception as e:
                            print(f"[GRPO] 相位检测错误: {e}")
                    
                    # 每10秒采集一次数据（仿真时间，不是真实时间）
                    if _simulation_manager.get_simulation_time() % 10 == 0:
                        # 采集路口J54的交通数据
                        _simulation_manager.collect_traffic_data("J54")
                        # 计算指标（最近1小时的数据）
                        metrics = _simulation_manager.get_intersection_metrics("J54", time_window=3600)
                        # 保存到CSV文件
                        _simulation_manager.save_metrics_to_csv("J54", metrics)
                    
                    # 真实时间延迟1秒（控制仿真速度）
                    # time.sleep(1)

            # 创建并启动后台线程（daemon=True表示主线程退出时自动退出）
            _simulation_thread = Thread(target=run_simulation, daemon=True)
            _simulation_thread.start()
            mode_str = "GRPO训练数据生成模式" if grpo_training_mode else "数据采集模式"
            print(f"仿真已在后台线程中启动 ({mode_str})。")
        else:
            # 手动控制模式
            print("仿真已启动，等待外部控制 (GRPO/RL模式)。")
        
        return _simulation_manager
    else:
        # 启动失败
        return None


def stop_simulation():
    """
    停止仿真并清理资源
    
    功能：
    - 发送停止信号给后台线程
    - 等待线程结束（最多5秒）
    - 关闭TraCI连接
    - 清除全局实例
    
    用途：
    - 正常退出程序时调用
    - 重新初始化仿真前调用
    """
    global _simulation_manager, _simulation_thread
    
    if _simulation_manager:
        # 发送停止信号
        _stop_event.set()
        
        # 等待后台线程结束（最多5秒）
        if _simulation_thread: 
            _simulation_thread.join(timeout=5)
        
        # 关闭仿真器
        _simulation_manager.close()
        
        # 清除全局实例
        _simulation_manager = None


def get_simulator():
    """
    获取全局仿真器实例
    
    返回:
        SUMOSimulator: 仿真器实例
        None: 未初始化
        
    用途：
    - 在其他模块中获取仿真器实例
    - 避免重复初始化
    """
    global _simulation_manager
    return _simulation_manager


# === 主程序入口 ===
if __name__ == "__main__":
    """
    直接运行本模块时的测试代码
    
    功能：
    - 初始化仿真（可选择数据采集模式或GRPO训练数据生成模式）
    - 持续运行直到用户按Ctrl+C
    - 优雅退出并清理资源
    
    运行方式：
    1. 普通数据采集模式：python sumo_simulator.py
    2. GRPO训练数据生成模式（默认使用最大压力策略）：python sumo_simulator.py --grpo
    3. 完整参数示例：
       python sumo_simulator.py --grpo --tl-id J54 --output training_data.json \
       --min-duration 20 --max-duration 90 --duration-step 10 \
       --use-max-pressure --action-duration 30
    """
    import argparse

    def _discover_environments(environments_root: str) -> Dict[str, Dict[str, str]]:
        """
        扫描 environments/ 下的场景目录，返回：
        {
          env_name: {
            "dir": <abs_dir>,
            "sumocfg": <abs_sumocfg>,
            "net": <abs_net_xml or "">
          }
        }
        """
        envs: Dict[str, Dict[str, str]] = {}
        if not os.path.isdir(environments_root):
            return envs

        for name in sorted(os.listdir(environments_root)):
            env_dir = os.path.join(environments_root, name)
            if not os.path.isdir(env_dir):
                continue
            if name.startswith("."):
                continue

            # 找 *.sumocfg（优先同名，其次任意一个）
            sumocfg = ""
            preferred = os.path.join(env_dir, f"{name}.sumocfg")
            if os.path.exists(preferred):
                sumocfg = preferred
            else:
                candidates = sorted([os.path.join(env_dir, f) for f in os.listdir(env_dir) if f.endswith(".sumocfg")])
                if candidates:
                    sumocfg = candidates[0]

            # 找 *.net.xml（优先同名，其次任意一个）
            net = ""
            preferred_net = os.path.join(env_dir, f"{name}.net.xml")
            if os.path.exists(preferred_net):
                net = preferred_net
            else:
                candidates = sorted([os.path.join(env_dir, f) for f in os.listdir(env_dir) if f.endswith(".net.xml")])
                if candidates:
                    net = candidates[0]

            if sumocfg:
                envs[name] = {"dir": os.path.abspath(env_dir), "sumocfg": os.path.abspath(sumocfg), "net": os.path.abspath(net) if net else ""}
        return envs

    def _list_tls_ids_from_net(net_xml_path: str) -> List[str]:
        """从 *.net.xml 中提取 <tlLogic id="..."> 的 id 列表。"""
        if not net_xml_path or not os.path.exists(net_xml_path):
            return []
        tls_ids: List[str] = []
        try:
            # iterparse 更省内存，适合大网
            for event, elem in ET.iterparse(net_xml_path, events=("end",)):
                if elem.tag == "tlLogic":
                    tl_id = elem.attrib.get("id")
                    if tl_id:
                        tls_ids.append(tl_id)
                    elem.clear()
        except Exception:
            return []
        return sorted(set(tls_ids))

    def _build_help_epilog(envs: Dict[str, Dict[str, str]], tls_preview_limit: int = 30) -> str:
        if not envs:
            return ""
        lines: List[str] = []
        lines.append("可选场景与信号交叉口(traffic light)列表：")
        lines.append("  - 使用 --env 选择场景；使用 --tl-id 选择该场景中的一个信号灯ID。")
        lines.append("  - 查看某场景的完整 TLS 列表：python sumo_simulator.py --list-tls <env>\n")
        for env_name, meta in envs.items():
            tls_ids = _list_tls_ids_from_net(meta.get("net", ""))
            if not tls_ids:
                lines.append(f"- {env_name}: 未从 net.xml 解析到 tlLogic（或该场景无信号灯）")
                continue
            preview = ", ".join(tls_ids[:tls_preview_limit])
            suffix = "" if len(tls_ids) <= tls_preview_limit else f", ... (共{len(tls_ids)}个)"
            lines.append(f"- {env_name}: {preview}{suffix}")
        return "\n".join(lines)

    environments_root = os.path.join(os.getcwd(), "environments")
    envs = _discover_environments(environments_root)
    env_choices = sorted(envs.keys())

    parser = argparse.ArgumentParser(
        description='SUMO交通仿真器',
        formatter_class=argparse.RawTextHelpFormatter,
        epilog=_build_help_epilog(envs)
    )
    parser.add_argument('--env', '--scenario', dest='env', type=str, choices=env_choices, default=None,
                        help='选择 environments/ 下的场景名（例如 grid4x4）。不填则使用默认 sumo_sim/osm.sumocfg')
    parser.add_argument('--config', type=str, default=None,
                        help='直接指定 .sumocfg 配置文件路径（优先级高于 --env）')
    parser.add_argument('--junctions-file', type=str, default=None,
                        help='(可选) 指定路口数据 JSON 文件路径；不提供则不加载此配置')
    parser.add_argument('--list-envs', action='store_true',
                        help='列出可选场景名并退出')
    parser.add_argument('--list-tls', type=str, default=None, metavar='ENV',
                        help='列出指定场景 ENV 的可选信号灯ID并退出')
    parser.add_argument('--grpo', action='store_true', 
                        help='启用GRPO训练数据生成模式')
    parser.add_argument('--tl-id', type=str, default='J54',
                        help='信号灯ID (默认: J54)')
    parser.add_argument('--output', type=str, default='training_data.json',
                        help='GRPO训练数据输出文件 (默认: training_data.json)')
    parser.add_argument('--min-duration', type=int, default=20,
                        help='最小相位持续时间 (默认: 20)')
    parser.add_argument('--max-duration', type=int, default=90,
                        help='最大相位持续时间 (默认: 90)')
    parser.add_argument('--duration-step', type=int, default=10,
                        help='相位持续时间步长 (默认: 10)')
    parser.add_argument('--no-gui', action='store_true',
                        help='不使用图形界面')
    parser.add_argument('--use-max-pressure', action='store_true', default=True,
                        help='使用最大压力策略决定下一状态 (默认: 启用)')
    parser.add_argument('--no-max-pressure', action='store_true',
                        help='禁用最大压力策略，使用SUMO默认控制')
    parser.add_argument('--action-duration', type=int, default=30,
                        help='最大压力策略执行的相位持续时间 (默认: 30秒)')
    
    args = parser.parse_args()

    if args.list_envs:
        if not env_choices:
            print("未发现任何 environments/ 场景（或场景目录缺少 .sumocfg）。")
        else:
            print("可选场景：")
            for name in env_choices:
                print(f"- {name}")
        sys.exit(0)

    if args.list_tls:
        env_name = args.list_tls
        if env_name not in envs:
            print(f"错误: 未知场景 {env_name!r}。可选场景: {', '.join(env_choices) if env_choices else '(无)'}")
            sys.exit(2)
        tls_ids = _list_tls_ids_from_net(envs[env_name].get("net", ""))
        print(f"场景 {env_name} 可选信号灯ID（共{len(tls_ids)}个）：")
        for tl in tls_ids:
            print(tl)
        sys.exit(0)
    
    # 解析配置文件：优先 --config，其次 --env，否则使用默认 sumo_sim/osm.sumocfg
    config_file = None
    if args.config:
        config_file = os.path.abspath(args.config)
    elif args.env:
        config_file = envs[args.env]["sumocfg"]

    junctions_file = os.path.abspath(args.junctions_file) if args.junctions_file else None

    # 若选择了 env 且未显式指定 tl-id，则尽量给一个更合理的默认值（该 env 的第一个 tlLogic）
    if args.env and (args.tl_id == 'J54' or not args.tl_id):
        tls_ids = _list_tls_ids_from_net(envs[args.env].get("net", ""))
        if tls_ids:
            args.tl_id = tls_ids[0]

    # 若选择了 env，则校验 tl-id 是否存在于该 env 的 tlLogic 列表中（若能解析到）
    if args.env:
        tls_ids = _list_tls_ids_from_net(envs[args.env].get("net", ""))
        if tls_ids and args.tl_id not in tls_ids:
            print(f"错误: tl-id={args.tl_id!r} 不在场景 {args.env!r} 的可选TLS列表中。")
            print("提示: 运行 `python sumo_simulator.py --list-tls {}` 查看完整列表。".format(args.env))
            sys.exit(2)

    # 处理最大压力策略开关
    use_max_pressure = not args.no_max_pressure
    
    try:
        if args.grpo:
            print("="*50)
            print("GRPO训练数据生成模式")
            print("="*50)
            print(f"信号灯ID: {args.tl_id}")
            print(f"输出文件: {args.output}")
            print(f"持续时间范围: {args.min_duration}-{args.max_duration}秒, 步长{args.duration_step}秒")
            print(f"最大压力策略: {'启用' if use_max_pressure else '禁用'}")
            if use_max_pressure:
                print(f"动作持续时间: {args.action_duration}秒")
            print("="*50)
        
        # 初始化仿真
        simulator = initialize_sumo(
            config_file=config_file,
            junctions_file=junctions_file,
            gui=not args.no_gui,
            grpo_training_mode=args.grpo,
            grpo_tl_id=args.tl_id,
            grpo_output_file=args.output,
            grpo_duration_range=(args.min_duration, args.max_duration, args.duration_step),
            grpo_use_max_pressure=use_max_pressure,
            grpo_action_duration=args.action_duration
        )
        
        if simulator:
            print("\n仿真运行中... 按Ctrl+C停止\n")
            # 主线程保持运行（等待Ctrl+C）
            while True: 
                time.sleep(1)
    except KeyboardInterrupt:
        # 用户按Ctrl+C，停止仿真
        print("\n正在停止仿真...")
        stop_simulation()
        print("仿真已停止。")
