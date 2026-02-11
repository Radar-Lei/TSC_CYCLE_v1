#!/usr/bin/env python3
"""
GRPO Training Analysis Script

解析 GRPO 训练日志，提取关键指标：
- Zero-std 统计（reward_std == 0 的步数比例）
- Reward 分布统计（均值、标准差、分位数）
- Reward 趋势（按训练阶段分段统计）
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import List, Dict, Any
import numpy as np


def parse_training_log(log_path: Path) -> List[Dict[str, Any]]:
    """
    从训练日志中提取每步的训练指标。

    GRPOTrainer 输出格式示例：
    {'loss': 0.5, 'reward': 1.2, 'reward_std': 0.3, ...}

    返回：包含所有步指标的字典列表
    """
    metrics = []

    if not log_path.exists():
        print(f"警告: 日志文件不存在 - {log_path}")
        return metrics

    with open(log_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()

            # 尝试匹配包含 reward 和 reward_std 的行
            if 'reward' not in line or 'reward_std' not in line:
                continue

            # 尝试解析为 dict（处理 Python dict 格式，使用单引号）
            try:
                # 尝试直接 eval（小心安全性，仅用于日志解析）
                # 先尝试 JSON（双引号）
                if line.startswith('{'):
                    try:
                        data = json.loads(line)
                        metrics.append(data)
                        continue
                    except json.JSONDecodeError:
                        pass

                # 如果 JSON 失败，尝试 eval Python dict（单引号）
                if line.startswith('{'):
                    # 替换单引号为双引号进行 JSON 解析
                    line_normalized = line.replace("'", '"')
                    try:
                        data = json.loads(line_normalized)
                        metrics.append(data)
                        continue
                    except:
                        pass

            except Exception:
                # 解析失败，静默跳过
                continue

    return metrics


def calculate_zero_std_ratio(metrics: List[Dict[str, Any]], threshold: float = 0.01) -> tuple:
    """
    计算 Zero-std 步数占比。

    参数:
        metrics: 训练指标列表
        threshold: 标准差阈值，低于此值视为 zero-std（默认 0.01）

    返回:
        (zero_std_count, total_count, ratio)
    """
    total = len(metrics)
    if total == 0:
        return 0, 0, 0.0

    zero_count = sum(1 for m in metrics if m.get('reward_std', 1.0) < threshold)
    ratio = zero_count / total

    return zero_count, total, ratio


def calculate_reward_distribution(metrics: List[Dict[str, Any]]) -> Dict[str, float]:
    """
    计算 Reward 分布统计。

    返回:
        包含均值、标准差、分位数等统计量的字典
    """
    if not metrics:
        return {
            'mean': 0.0,
            'std': 0.0,
            'min': 0.0,
            'max': 0.0,
            'p10': 0.0,
            'p25': 0.0,
            'p50': 0.0,
            'p75': 0.0,
            'p90': 0.0,
        }

    rewards = [m.get('reward', 0.0) for m in metrics]
    rewards_np = np.array(rewards)

    return {
        'mean': float(np.mean(rewards_np)),
        'std': float(np.std(rewards_np)),
        'min': float(np.min(rewards_np)),
        'max': float(np.max(rewards_np)),
        'p10': float(np.percentile(rewards_np, 10)),
        'p25': float(np.percentile(rewards_np, 25)),
        'p50': float(np.percentile(rewards_np, 50)),
        'p75': float(np.percentile(rewards_np, 75)),
        'p90': float(np.percentile(rewards_np, 90)),
    }


def calculate_reward_trend(metrics: List[Dict[str, Any]], n_segments: int = 10) -> List[Dict[str, Any]]:
    """
    计算 Reward 趋势（按训练阶段分段）。

    参数:
        metrics: 训练指标列表
        n_segments: 分段数（默认 10，即每段 10%）

    返回:
        包含每段统计的列表
    """
    if not metrics:
        return []

    total = len(metrics)
    segment_size = max(1, total // n_segments)

    trends = []
    for i in range(n_segments):
        start_idx = i * segment_size
        end_idx = min((i + 1) * segment_size, total) if i < n_segments - 1 else total

        if start_idx >= total:
            break

        segment_metrics = metrics[start_idx:end_idx]
        rewards = [m.get('reward', 0.0) for m in segment_metrics]

        trends.append({
            'segment': i + 1,
            'start_pct': int(i * 100 / n_segments),
            'end_pct': int((i + 1) * 100 / n_segments) if i < n_segments - 1 else 100,
            'mean': float(np.mean(rewards)),
            'count': len(rewards),
        })

    return trends


def generate_report(metrics: List[Dict[str, Any]]) -> str:
    """
    生成训练分析报告文本。
    """
    if not metrics:
        return """==========================================
GRPO 训练分析报告
==========================================

[错误]
无法从日志中解析任何训练步数据。
请检查日志文件格式是否正确。
==========================================
"""

    # 计算各项指标
    zero_count, total, zero_ratio = calculate_zero_std_ratio(metrics)
    dist = calculate_reward_distribution(metrics)
    trends = calculate_reward_trend(metrics)

    # 构建报告
    report_lines = [
        "=" * 42,
        "GRPO 训练分析报告",
        "=" * 42,
        "",
        "[训练概况]",
        f"总训练步数: {total}",
        "",
        "[Zero-std 统计]",
        f"Zero-std 步数: {zero_count} / {total} ({zero_ratio * 100:.1f}%)",
        f"阈值: reward_std < 0.01",
        "",
        "[Reward 分布]",
        f"均值: {dist['mean']:.4f}",
        f"标准差: {dist['std']:.4f}",
        f"分位数: 10%={dist['p10']:.4f}, 25%={dist['p25']:.4f}, 50%={dist['p50']:.4f}, 75%={dist['p75']:.4f}, 90%={dist['p90']:.4f}",
        f"最小值: {dist['min']:.4f}, 最大值: {dist['max']:.4f}",
        "",
        "[Reward 趋势]",
    ]

    for trend in trends:
        report_lines.append(
            f"步骤 {trend['start_pct']}-{trend['end_pct']}%: 均值 {trend['mean']:.4f} (n={trend['count']})"
        )

    report_lines.append("=" * 42)

    return "\n".join(report_lines)


def main():
    parser = argparse.ArgumentParser(
        description="分析 GRPO 训练日志，提取关键指标"
    )
    parser.add_argument(
        '--log',
        type=str,
        required=True,
        help="训练日志文件路径"
    )
    parser.add_argument(
        '--output',
        type=str,
        default='outputs/grpo/grpo_analysis.txt',
        help="分析报告输出路径（默认: outputs/grpo/grpo_analysis.txt）"
    )

    args = parser.parse_args()

    log_path = Path(args.log)
    output_path = Path(args.output)

    # 解析日志
    print(f"正在解析训练日志: {log_path}")
    metrics = parse_training_log(log_path)

    if not metrics:
        print("警告: 未能从日志中提取任何训练步数据")
    else:
        print(f"成功提取 {len(metrics)} 步训练指标")

    # 生成报告
    report = generate_report(metrics)

    # 打印到终端
    print("\n" + report)

    # 保存到文件
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(report)

    print(f"\n分析报告已保存至: {output_path}")


if __name__ == '__main__':
    main()
