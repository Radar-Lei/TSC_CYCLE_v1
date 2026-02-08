"""
仿真奖励函数

将 SUMO 评估结果转换为奖励信号,用于 GRPO 训练。

主要组件:
- compute_metric_reward: 将评估指标转换为奖励分数
- compute_simulation_reward: TRL GRPOTrainer 兼容的奖励函数
- parallel_evaluate: 并行评估多个方案
"""

import json
import re
from typing import List, Dict, Any, Optional
from multiprocessing import Pool

from .sumo_evaluator import SUMOEvaluator, EvaluationResult, evaluate_single


# 指标权重 (三个指标等权分配)
QUEUE_WEIGHT = 0.33      # 排队长度
THROUGHPUT_WEIGHT = 0.33  # 通行量
WAITING_WEIGHT = 0.34     # 等待时间

# 参考值 (用于归一化)
QUEUE_REF = 50.0         # 排队长度参考值 (50 辆车)
THROUGHPUT_REF = 100.0   # 通行量参考值 (100 辆车)
WAITING_REF = 60.0       # 等待时间参考值 (60 秒)


def compute_metric_reward(
    result: EvaluationResult,
    baseline: Optional[EvaluationResult] = None
) -> float:
    """
    将评估指标转换为奖励分数

    Args:
        result: 评估结果
        baseline: 对比基准 (可选), 如果提供则计算相对改进

    Returns:
        奖励分数,范围 [-1, 1]
        - 评估失败: -1.0
        - 评估成功: 根据指标计算,越好越接近 +1

    计算逻辑:
        1. 排队长度: 越低越好,归一化到 [0, 1]
        2. 通行量: 越高越好,归一化到 [0, 1]
        3. 等待时间: 越低越好,归一化到 [0, 1]
        4. 加权平均,映射到 [-1, 1]
    """
    # 评估失败返回负奖励
    if not result.success:
        return -1.0

    # 计算各指标的归一化分数 [0, 1]

    # 排队长度: 越低越好
    queue_score = max(0.0, 1.0 - result.queue_length / QUEUE_REF)

    # 通行量: 越高越好
    throughput_score = min(1.0, result.throughput / THROUGHPUT_REF)

    # 等待时间: 越低越好
    waiting_score = max(0.0, 1.0 - result.waiting_time / WAITING_REF)

    # 加权平均
    score = (
        QUEUE_WEIGHT * queue_score +
        THROUGHPUT_WEIGHT * throughput_score +
        WAITING_WEIGHT * waiting_score
    )

    # 映射到 [-1, 1] 范围
    # score 范围 [0, 1] -> 映射到 [-1, 1]
    reward = score * 2.0 - 1.0

    # 如果提供了 baseline,计算相对改进
    if baseline is not None and baseline.success:
        baseline_reward = compute_metric_reward(baseline, baseline=None)
        # 相对改进 (差异)
        improvement = reward - baseline_reward
        # 缩放到 [-1, 1]
        return max(-1.0, min(1.0, improvement))

    return reward


def parse_plan_from_completion(completion: str) -> Optional[List[Dict]]:
    """
    从模型输出中解析周期方案

    Args:
        completion: 模型生成的文本

    Returns:
        方案列表,格式: [{"phase_id": 1, "final": 40}, ...] 或 None (解析失败)

    示例:
        输入: "<think>...</think>[{\"phase_id\": 1, \"final\": 40}, {\"phase_id\": 2, \"final\": 30}]"
        输出: [{"phase_id": 1, "final": 40}, {"phase_id": 2, "final": 30}]
    """
    try:
        # 提取 JSON 数组部分 (在 </think> 之后)
        # 查找 </think> 标签
        think_end = completion.find('</think>')
        if think_end != -1:
            json_part = completion[think_end + len('</think>'):]
        else:
            json_part = completion

        # 查找 JSON 数组 [...]
        match = re.search(r'\[.*\]', json_part, re.DOTALL)
        if not match:
            return None

        json_str = match.group(0)

        # 解析 JSON
        plan = json.loads(json_str)

        # 验证格式
        if not isinstance(plan, list):
            return None

        for item in plan:
            if not isinstance(item, dict):
                return None
            if 'phase_id' not in item or 'final' not in item:
                return None

        return plan

    except Exception:
        return None


def compute_simulation_reward(
    completions: List[str],
    prompts: List[str],
    state_files: List[str],
    tl_ids: List[str],
    phase_config: Dict[str, Any],
    **kwargs
) -> List[float]:
    """
    TRL GRPOTrainer 兼容的仿真奖励函数

    NaN 跳过策略：当 JSON 解析失败或评估失败时，返回 float('nan')，
    TRL GRPOTrainer 会自动跳过 NaN 值，不参与梯度计算。

    Args:
        completions: 模型生成的输出列表
        prompts: 对应的输入提示列表 (未使用,但保持签名兼容)
        state_files: 状态快照文件路径列表
        tl_ids: 信号灯 ID 列表
        phase_config: 评估配置字典:
            - net_file: 网络文件路径
            - sumocfg: SUMO 配置文件路径
            - cycle_duration: 评估周期时长
            - max_workers: 并行 worker 数量
        **kwargs: 其他参数 (保持签名兼容)

    Returns:
        奖励列表,长度与 completions 相同
        - JSON 解析失败: float('nan') (跳过)
        - 评估失败: float('nan') (跳过)
        - 评估成功: 根据指标计算的奖励分数 [-1, 1]

    处理逻辑:
        1. 从每个 completion 中解析周期方案
        2. 并行调用 SUMO 评估器
        3. 计算仿真奖励
    """
    # 构建评估任务列表
    evaluations = []
    base_port = 20000

    for i, (completion, state_file, tl_id) in enumerate(zip(completions, state_files, tl_ids)):
        # 解析方案
        plan = parse_plan_from_completion(completion)

        # JSON 解析失败,标记为 None (后续返回 NaN)
        if plan is None:
            evaluations.append(None)
            continue

        # 分配端口 (避免冲突)
        port = base_port + i

        # 构建评估参数
        eval_args = (state_file, tl_id, plan, phase_config, port)
        evaluations.append(eval_args)

    # 并行评估
    max_workers = phase_config.get('max_workers', 4)
    results = parallel_evaluate(evaluations, max_workers=max_workers)

    # 计算奖励
    rewards = []
    for result in results:
        if result is None:
            # JSON 解析失败 -> NaN (跳过)
            rewards.append(float('nan'))
        elif not result.success:
            # 评估失败 (SUMO 崩溃/超时) -> NaN (跳过)
            rewards.append(float('nan'))
        else:
            # 评估成功,计算奖励
            reward = compute_metric_reward(result)
            rewards.append(reward)

    return rewards


def parallel_evaluate(
    evaluations: List[Optional[tuple]],
    max_workers: int = 4,
    timeout: int = 120
) -> List[Optional[EvaluationResult]]:
    """
    并行评估多个方案

    Args:
        evaluations: 评估任务列表,每个元素为:
            - None: JSON 解析失败,跳过评估
            - (state_file, tl_id, plan, config, port): 评估参数元组
        max_workers: 并行 worker 数量
        timeout: 评估超时时间(秒),默认 120

    Returns:
        评估结果列表,长度与 evaluations 相同
        - None: JSON 解析失败
        - EvaluationResult: 评估结果 (可能成功或失败)

    统计信息:
        - 成功数: 评估成功的样本数
        - 失败数: 评估失败的样本数 (SUMO 崩溃/超时)
        - 跳过数: JSON 解析失败的样本数
    """
    # 过滤出需要评估的任务
    valid_tasks = []
    task_indices = []

    for i, task in enumerate(evaluations):
        if task is not None:
            valid_tasks.append(task)
            task_indices.append(i)

    # 并行评估
    if valid_tasks:
        with Pool(processes=max_workers) as pool:
            valid_results = pool.map(evaluate_single, valid_tasks)
    else:
        valid_results = []

    # 重建完整结果列表 (包含 None)
    results = [None] * len(evaluations)
    for idx, result in zip(task_indices, valid_results):
        results[idx] = result

    # 统计评估结果
    skipped = sum(1 for r in results if r is None)
    success = sum(1 for r in results if r is not None and r.success)
    failed = sum(1 for r in results if r is not None and not r.success)

    print(f"Evaluation stats: {success} success, {failed} failed, {skipped} skipped (total: {len(results)})")

    return results
