"""
SUMO 仿真评估器

用于评估模型生成的信号周期方案,从 Phase 2 保存的状态快照恢复仿真,
应用方案并运行 1 个周期 (60-90s) 评估效果。

主要组件:
- EvaluationResult: 评估结果数据类
- SUMOEvaluator: SUMO 仿真评估器
- evaluate_single: 多进程入口函数
"""

import os
import sys
import signal
import time
from dataclasses import dataclass
from typing import Optional, List, Dict, Tuple
from pathlib import Path

# 配置 SUMO_HOME
if 'SUMO_HOME' not in os.environ:
    possible_paths = [
        "/usr/share/sumo",
        "/usr/local/share/sumo",
        "/usr/lib/sumo",
        "/opt/homebrew/opt/sumo/share/sumo",
        "/usr/local/opt/sumo/share/sumo",
    ]
    for path in possible_paths:
        if os.path.exists(path):
            os.environ['SUMO_HOME'] = path
            break

if 'SUMO_HOME' in os.environ:
    tools = os.path.join(os.environ['SUMO_HOME'], 'tools')
    sys.path.append(tools)

try:
    import traci
except ImportError:
    sys.exit("错误: 无法导入 traci。请检查 SUMO 是否安装")


@dataclass
class EvaluationResult:
    """
    评估结果数据类

    Attributes:
        queue_length: 平均排队长度 (越低越好)
        throughput: 通过车辆数 (越高越好)
        waiting_time: 平均等待时间 (越低越好)
        success: 评估是否成功
        error: 错误信息 (成功时为 None)
    """
    queue_length: float
    throughput: int
    waiting_time: float
    success: bool
    error: Optional[str] = None


class TimeoutException(Exception):
    """超时异常"""
    pass


def timeout_handler(signum, frame):
    """超时信号处理器"""
    raise TimeoutException("Evaluation timeout")


class SUMOEvaluator:
    """
    SUMO 仿真评估器

    用于评估模型生成的周期方案:
    1. 从状态快照恢复 SUMO 仿真
    2. 应用模型生成的周期方案
    3. 运行 1 个周期 (60-90s) 评估效果
    4. 收集排队长度、通行量、等待时间三个指标
    """

    def __init__(
        self,
        net_file: str,
        sumocfg: str,
        cycle_duration: int = 90
    ):
        """
        初始化评估器

        Args:
            net_file: 网络文件路径
            sumocfg: SUMO 配置文件模板路径
            cycle_duration: 评估周期时长 (秒), 默认 90
        """
        self.net_file = os.path.abspath(net_file)
        self.sumocfg = os.path.abspath(sumocfg)
        self.cycle_duration = cycle_duration
        self.connection_label = None

        # 验证文件存在
        if not os.path.exists(self.net_file):
            raise FileNotFoundError(f"网络文件不存在: {self.net_file}")
        if not os.path.exists(self.sumocfg):
            raise FileNotFoundError(f"配置文件不存在: {self.sumocfg}")

    def load_state(self, state_file: str, port: int) -> bool:
        """
        启动 SUMO 并加载状态快照

        Args:
            state_file: 状态快照文件路径
            port: TraCI 连接端口 (避免冲突)

        Returns:
            是否成功加载
        """
        try:
            # 验证状态文件存在
            if not os.path.exists(state_file):
                raise FileNotFoundError(f"State file not found: {state_file}")

            # 构建 SUMO 启动命令 (使用无 GUI 模式)
            sumo_binary = os.path.join(os.environ.get('SUMO_HOME', '/usr/share/sumo'), 'bin', 'sumo')
            if not os.path.exists(sumo_binary):
                sumo_binary = 'sumo'  # 尝试使用系统路径

            sumo_cmd = [
                sumo_binary,
                "-c", self.sumocfg,
                "--step-length", "1.0",
                "--no-warnings", "true",
                "--no-step-log",
                "--duration-log.disable"
            ]

            # 启动 TraCI 连接
            self.connection_label = f"eval_{port}"
            traci.start(
                sumo_cmd,
                port=port,
                label=self.connection_label,
                numRetries=3
            )

            # 加载状态快照
            traci.simulation.loadState(state_file, useConnection=self.connection_label)

            return True

        except Exception as e:
            # 加载失败,清理连接
            self._cleanup_connection()
            raise RuntimeError(f"Failed to load state: {str(e)}")

    def apply_phase_plan(self, tl_id: str, plan: List[Dict]) -> bool:
        """
        验证模型生成的周期方案是否有效

        Args:
            tl_id: 信号灯 ID
            plan: 相位配置列表,格式: [{"phase_id": 1, "final": 40}, {"phase_id": 2, "final": 30}]

        Returns:
            是否有效

        Note:
            实际的相位切换在 run_cycle() 中按顺序执行
        """
        try:
            if not plan:
                return False

            # 验证信号灯存在
            tl_ids = traci.trafficlight.getIDList(useConnection=self.connection_label)
            if tl_id not in tl_ids:
                raise ValueError(f"Traffic light {tl_id} not found")

            # 获取相位信息
            logic = traci.trafficlight.getAllProgramLogics(tl_id, useConnection=self.connection_label)[0]
            num_phases = len(logic.phases)

            # 验证方案有效性
            for phase_config in plan:
                phase_id = phase_config.get('phase_id')
                duration = phase_config.get('final')

                # 验证相位 ID
                if phase_id is None or phase_id < 0 or phase_id >= num_phases:
                    raise ValueError(f"Invalid phase_id: {phase_id}")

                # 验证持续时间
                if duration is None or duration < 5 or duration > 120:
                    raise ValueError(f"Invalid duration: {duration}")

            return True

        except Exception as e:
            raise RuntimeError(f"Failed to validate phase plan: {str(e)}")

    def run_cycle(self, tl_id: str, plan: List[Dict]) -> EvaluationResult:
        """
        按照模型给出的相位方案执行完整周期并收集指标

        Args:
            tl_id: 信号灯 ID
            plan: 相位配置列表,格式: [{"phase_id": 1, "final": 40}, ...]

        Returns:
            评估结果

        Throughput 计算说明:
            统计在评估周期内离开信号灯控制车道的车辆数 (即成功通过路口的车辆)
            通过追踪每个时间步车道上的车辆 ID 变化来计算
        """
        try:
            # 获取信号灯控制的车道
            controlled_lanes = list(set(
                traci.trafficlight.getControlledLanes(
                    tl_id,
                    useConnection=self.connection_label
                )
            ))

            # 初始化累计指标
            total_queue = 0.0
            total_waiting = 0.0
            step_count = 0

            # 用于计算精确通过量的变量
            # 记录初始时刻在控制车道上的所有车辆
            prev_vehicles_on_lanes: set = set()
            for lane_id in controlled_lanes:
                try:
                    vehicle_ids = traci.lane.getLastStepVehicleIDs(
                        lane_id,
                        useConnection=self.connection_label
                    )
                    prev_vehicles_on_lanes.update(vehicle_ids)
                except traci.exceptions.TraCIException:
                    continue

            # 统计离开控制车道的车辆 (通过路口的车辆)
            vehicles_passed: set = set()

            # 按相位顺序执行完整周期
            for phase_config in plan:
                phase_id = phase_config['phase_id']
                duration = int(phase_config['final'])

                # 切换到该相位
                traci.trafficlight.setPhase(
                    tl_id,
                    phase_id,
                    useConnection=self.connection_label
                )

                # 执行该相位的完整时长
                for _ in range(duration):
                    # 推进仿真
                    traci.simulationStep(useConnection=self.connection_label)

                    # 收集指标
                    step_queue = 0.0
                    step_waiting = 0.0
                    current_vehicles_on_lanes: set = set()

                    for lane_id in controlled_lanes:
                        try:
                            # 排队车辆数
                            halting = traci.lane.getLastStepHaltingNumber(
                                lane_id,
                                useConnection=self.connection_label
                            )
                            step_queue += halting

                            # 等待时间
                            waiting = traci.lane.getWaitingTime(
                                lane_id,
                                useConnection=self.connection_label
                            )
                            step_waiting += waiting

                            # 获取当前车道上的车辆 ID
                            vehicle_ids = traci.lane.getLastStepVehicleIDs(
                                lane_id,
                                useConnection=self.connection_label
                            )
                            current_vehicles_on_lanes.update(vehicle_ids)

                        except traci.exceptions.TraCIException:
                            continue

                    # 计算本步离开控制车道的车辆 (在上一步存在但本步不在)
                    left_vehicles = prev_vehicles_on_lanes - current_vehicles_on_lanes
                    vehicles_passed.update(left_vehicles)

                    # 更新上一步的车辆集合
                    prev_vehicles_on_lanes = current_vehicles_on_lanes

                    # 累加
                    total_queue += step_queue
                    total_waiting += step_waiting
                    step_count += 1

            # 计算平均值
            avg_queue = total_queue / step_count if step_count > 0 else 0.0
            avg_waiting = total_waiting / step_count if step_count > 0 else 0.0

            # 通过量 = 离开控制车道的车辆数
            total_throughput = len(vehicles_passed)

            return EvaluationResult(
                queue_length=avg_queue,
                throughput=total_throughput,
                waiting_time=avg_waiting,
                success=True,
                error=None
            )

        except Exception as e:
            return EvaluationResult(
                queue_length=0.0,
                throughput=0,
                waiting_time=0.0,
                success=False,
                error=f"Evaluation failed: {str(e)}"
            )

    def close(self):
        """关闭 SUMO 连接"""
        self._cleanup_connection()

    def _cleanup_connection(self):
        """清理 TraCI 连接"""
        try:
            if self.connection_label:
                traci.close(useConnection=self.connection_label)
                self.connection_label = None
        except Exception:
            pass


def evaluate_single(args: tuple) -> EvaluationResult:
    """
    多进程入口函数

    Args:
        args: (state_file, tl_id, plan, config, port) 元组
            - state_file: 状态快照文件路径
            - tl_id: 信号灯 ID
            - plan: 周期方案列表
            - config: 配置字典 {'net_file': ..., 'sumocfg': ..., 'cycle_duration': ...}
            - port: TraCI 端口

    Returns:
        评估结果
    """
    state_file, tl_id, plan, config, port = args

    evaluator = None

    try:
        # 设置超时 (120 秒)
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(120)

        # 创建评估器
        evaluator = SUMOEvaluator(
            net_file=config['net_file'],
            sumocfg=config['sumocfg'],
            cycle_duration=config.get('cycle_duration', 90)
        )

        # 加载状态 (重试 2 次)
        load_success = False
        for attempt in range(3):
            try:
                evaluator.load_state(state_file, port)
                load_success = True
                break
            except Exception as e:
                if attempt == 2:
                    raise e
                time.sleep(0.5)

        if not load_success:
            return EvaluationResult(
                queue_length=0.0,
                throughput=0,
                waiting_time=0.0,
                success=False,
                error="Failed to load state after 3 attempts"
            )

        # 应用方案
        evaluator.apply_phase_plan(tl_id, plan)

        # 运行评估 (按模型给出的相位方案执行完整周期)
        result = evaluator.run_cycle(tl_id, plan)

        # 取消超时
        signal.alarm(0)

        return result

    except TimeoutException:
        return EvaluationResult(
            queue_length=0.0,
            throughput=0,
            waiting_time=0.0,
            success=False,
            error="Evaluation timeout (>120s)"
        )

    except FileNotFoundError as e:
        return EvaluationResult(
            queue_length=0.0,
            throughput=0,
            waiting_time=0.0,
            success=False,
            error=f"State file not found: {str(e)}"
        )

    except Exception as e:
        return EvaluationResult(
            queue_length=0.0,
            throughput=0,
            waiting_time=0.0,
            success=False,
            error=f"Unexpected error: {str(e)}"
        )

    finally:
        # 确保清理资源
        if evaluator:
            try:
                evaluator.close()
            except Exception:
                pass

        # 取消超时
        try:
            signal.alarm(0)
        except Exception:
            pass
