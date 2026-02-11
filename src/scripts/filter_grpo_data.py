#!/usr/bin/env python3
"""
GRPO 数据过滤脚本 - 剔除空交叉口和极低流量样本

Purpose: 从 grpo_train.jsonl 中剔除所有相位 pred_saturation 总和低于阈值的样本。
这些样本对 GRPO 训练无贡献（baseline passed=0, queue=0 时 reward 无法产生有意义梯度）。

Output:
- grpo_train_filtered.jsonl: 保留样本
- grpo_train_rejected.jsonl: 剔除样本
- grpo_train_filter_report.txt: 统计报告

Usage:
  python -m src.scripts.filter_grpo_data --config config/config.json
  python -m src.scripts.filter_grpo_data --input path/to/grpo_train.jsonl --threshold 0.1
"""

import argparse
import json
import os
import re
import sys


def parse_saturation_sum(sample):
    """从单条样本提取 phase_waits 并计算 saturation_sum。

    Args:
        sample: GRPO 样本字典，包含 'prompt' 字段

    Returns:
        float: 所有相位 pred_saturation 之和，若解析失败返回 0.0
    """
    try:
        # 提取 prompt 最后一条 user message 的 content
        prompt_content = sample["prompt"][-1]["content"]

        # 使用与 baseline.py 相同的正则提取 phase_waits
        phase_waits_match = re.search(r'"phase_waits"\s*:\s*(\[.*?\])', prompt_content, re.DOTALL)
        if not phase_waits_match:
            return 0.0

        phase_waits = json.loads(phase_waits_match.group(1))

        # 计算所有相位 pred_saturation 之和
        saturation_sum = sum(phase["pred_saturation"] for phase in phase_waits)
        return saturation_sum
    except Exception:
        return 0.0


def filter_data(input_path, output_path, rejected_path, threshold):
    """主过滤函数。

    Args:
        input_path: 输入 grpo_train.jsonl 路径
        output_path: 输出 filtered.jsonl 路径
        rejected_path: 输出 rejected.jsonl 路径
        threshold: saturation_sum 阈值

    Returns:
        dict: 统计数据字典
    """
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"输入文件不存在: {input_path}")

    # 统计数据
    stats = {
        "input_path": input_path,
        "output_path": output_path,
        "rejected_path": rejected_path,
        "threshold": threshold,
        "total_samples": 0,
        "kept_samples": 0,
        "rejected_samples": 0,
        "all_saturations": [],
        "kept_saturations": [],
        "rejected_saturations": []
    }

    # 创建输出目录
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    os.makedirs(os.path.dirname(rejected_path), exist_ok=True)

    # 逐行读取并分流
    with open(input_path, 'r') as f_in, \
         open(output_path, 'w') as f_out, \
         open(rejected_path, 'w') as f_rej:

        for line in f_in:
            sample = json.loads(line.strip())
            stats["total_samples"] += 1

            saturation_sum = parse_saturation_sum(sample)
            stats["all_saturations"].append(saturation_sum)

            if saturation_sum < threshold:
                # 剔除样本
                f_rej.write(json.dumps(sample, ensure_ascii=False) + '\n')
                stats["rejected_samples"] += 1
                stats["rejected_saturations"].append(saturation_sum)
            else:
                # 保留样本
                f_out.write(json.dumps(sample, ensure_ascii=False) + '\n')
                stats["kept_samples"] += 1
                stats["kept_saturations"].append(saturation_sum)

    return stats


def calculate_distribution_stats(values):
    """计算分布统计量（min/max/mean/median）。"""
    if not values:
        return {"min": 0.0, "max": 0.0, "mean": 0.0, "median": 0.0}

    values_sorted = sorted(values)
    n = len(values_sorted)
    median = values_sorted[n // 2] if n % 2 == 1 else (values_sorted[n // 2 - 1] + values_sorted[n // 2]) / 2

    return {
        "min": min(values),
        "max": max(values),
        "mean": sum(values) / len(values),
        "median": median
    }


def format_report(stats):
    """格式化统计报告。

    Args:
        stats: filter_data 返回的统计字典

    Returns:
        str: 格式化的中文报告
    """
    total = stats["total_samples"]
    kept = stats["kept_samples"]
    rejected = stats["rejected_samples"]
    rejected_pct = (rejected / total * 100) if total > 0 else 0.0

    all_dist = calculate_distribution_stats(stats["all_saturations"])
    kept_dist = calculate_distribution_stats(stats["kept_saturations"])
    rejected_dist = calculate_distribution_stats(stats["rejected_saturations"])

    report = f"""=== GRPO 数据过滤报告 ===
过滤阈值: saturation_sum < {stats['threshold']}
输入文件: {stats['input_path']}
过滤前: {total} 条
过滤后: {kept} 条
剔除: {rejected} 条 ({rejected_pct:.1f}%)

流量分布 (saturation_sum):
  全部样本: min={all_dist['min']:.4f} max={all_dist['max']:.4f} mean={all_dist['mean']:.4f} median={all_dist['median']:.4f}
  保留样本: min={kept_dist['min']:.4f} max={kept_dist['max']:.4f} mean={kept_dist['mean']:.4f} median={kept_dist['median']:.4f}
  剔除样本: min={rejected_dist['min']:.4f} max={rejected_dist['max']:.4f} mean={rejected_dist['mean']:.4f} median={rejected_dist['median']:.4f}

输出文件:
  保留: {stats['output_path']}
  剔除: {stats['rejected_path']}
"""

    return report


def main():
    parser = argparse.ArgumentParser(description="过滤 GRPO 训练数据中的空交叉口和极低流量样本")
    parser.add_argument("--config", default="config/config.json", help="配置文件路径")
    parser.add_argument("--input", default=None, help="输入文件路径（覆盖配置）")
    parser.add_argument("--output", default=None, help="输出文件路径（覆盖配置）")
    parser.add_argument("--threshold", type=float, default=None, help="saturation_sum 阈值（覆盖配置）")
    args = parser.parse_args()

    # 加载配置
    try:
        with open(args.config) as f:
            config = json.load(f)
    except FileNotFoundError:
        print(f"错误: 配置文件不存在: {args.config}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"错误: 配置文件 JSON 格式错误: {e}", file=sys.stderr)
        sys.exit(1)

    # 获取过滤配置
    try:
        filter_config = config["training"]["grpo"]["data_filter"]
    except KeyError:
        print("错误: 配置文件缺少 training.grpo.data_filter 字段", file=sys.stderr)
        sys.exit(1)

    # 路径计算
    grpo_data_dir = config["paths"]["grpo_data_dir"]

    # 输入路径
    if args.input:
        input_path = args.input
    elif filter_config["input"] is not None:
        input_path = filter_config["input"]
    else:
        input_path = os.path.join(grpo_data_dir, "grpo_train.jsonl")

    # 输出路径（基于输入文件名 + suffix）
    if args.output:
        output_path = args.output
    else:
        input_dir = os.path.dirname(input_path)
        input_basename = os.path.basename(input_path)
        input_name, input_ext = os.path.splitext(input_basename)
        output_suffix = filter_config["output_suffix"]
        output_path = os.path.join(input_dir, f"{input_name}{output_suffix}{input_ext}")

    # Rejected 路径
    input_dir = os.path.dirname(input_path)
    input_basename = os.path.basename(input_path)
    input_name, input_ext = os.path.splitext(input_basename)
    rejected_suffix = filter_config["rejected_suffix"]
    rejected_path = os.path.join(input_dir, f"{input_name}{rejected_suffix}{input_ext}")

    # 阈值
    threshold = args.threshold if args.threshold is not None else filter_config["saturation_sum_threshold"]

    # 执行过滤
    print(f"[过滤] 开始过滤数据...")
    print(f"[过滤] 输入: {input_path}")
    print(f"[过滤] 阈值: saturation_sum < {threshold}")

    try:
        stats = filter_data(input_path, output_path, rejected_path, threshold)
    except FileNotFoundError as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"错误: 过滤过程出错: {e}", file=sys.stderr)
        sys.exit(1)

    # 生成报告
    report = format_report(stats)

    # 打印到终端
    print("\n" + report)

    # 写入文本文件
    report_path = os.path.join(
        os.path.dirname(output_path),
        f"{os.path.splitext(os.path.basename(input_path))[0]}_filter_report.txt"
    )
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report)

    print(f"[报告] 统计报告已保存到: {report_path}")
    print("[完成] 数据过滤完成")


if __name__ == "__main__":
    main()
