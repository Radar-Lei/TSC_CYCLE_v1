#!/usr/bin/env python3
"""
样本抽取脚本：从 train.jsonl 中均匀抽取约 100 条代表性样本

抽取策略：
1. 确保覆盖所有 34 个 tl_id，每个至少 1 条
2. 按饱和度分布补充剩余配额，优先补充 high 饱和度样本
3. 确保两个场景(arterial4x4_10, chengdu)各约 50 条
4. 确保 2/3/4 相位样本都有覆盖
"""

import argparse
import json
import random
from pathlib import Path
from collections import defaultdict
from typing import List, Dict, Any


def calculate_sample_saturation(sample: Dict[str, Any]) -> float:
    """计算样本的饱和度(取所有相位中的最大值)"""
    phase_waits = sample['prediction']['phase_waits']
    return max(phase['pred_saturation'] for phase in phase_waits)


def get_saturation_category(saturation: float) -> str:
    """获取饱和度类别"""
    if saturation == 0.0:
        return 'zero'
    elif saturation < 0.5:
        return 'low'
    elif saturation < 1.0:
        return 'medium'
    else:
        return 'high'


def get_phase_count(sample: Dict[str, Any]) -> int:
    """获取样本的相位数"""
    return len(sample['prediction']['phase_waits'])


def load_samples(input_path: str) -> List[Dict[str, Any]]:
    """加载所有样本"""
    samples = []
    with open(input_path, 'r', encoding='utf-8') as f:
        for line in f:
            samples.append(json.loads(line.strip()))
    return samples


def select_samples(samples: List[Dict[str, Any]], target_count: int, seed: int = 42) -> List[Dict[str, Any]]:
    """
    执行样本抽取

    策略：
    1. 每个 tl_id 至少抽 1 条
    2. 剩余配额按饱和度分布补充（优先 high）
    3. 确保场景分布均匀
    4. 确保相位数覆盖
    """
    random.seed(seed)

    # 按 tl_id 分组
    samples_by_tl = defaultdict(list)
    for sample in samples:
        tl_id = sample['metadata']['tl_id']
        samples_by_tl[tl_id].append(sample)

    print(f"总样本数: {len(samples)}")
    print(f"交叉口数: {len(samples_by_tl)}")

    # 第一步：每个 tl_id 至少抽 1 条
    selected = []
    for tl_id, tl_samples in samples_by_tl.items():
        selected.append(random.choice(tl_samples))

    print(f"第一步完成: 已选 {len(selected)} 条 (每个 tl_id 至少 1 条)")

    # 计算剩余配额
    remaining_quota = target_count - len(selected)

    # 收集未选中的样本
    selected_set = set(id(s) for s in selected)
    remaining_samples = [s for s in samples if id(s) not in selected_set]

    # 第二步：按饱和度分布补充
    # 将剩余样本按饱和度分类
    samples_by_saturation = defaultdict(list)
    for sample in remaining_samples:
        sat = calculate_sample_saturation(sample)
        category = get_saturation_category(sat)
        samples_by_saturation[category].append(sample)

    # 打印饱和度分布
    print("\n剩余样本饱和度分布:")
    for cat in ['zero', 'low', 'medium', 'high']:
        count = len(samples_by_saturation[cat])
        print(f"  {cat}: {count} 条")

    # 分配配额：优先 high，然后按比例分配其他
    # high 占 40%, medium 占 30%, low 占 20%, zero 占 10%
    quotas = {
        'high': int(remaining_quota * 0.40),
        'medium': int(remaining_quota * 0.30),
        'low': int(remaining_quota * 0.20),
        'zero': int(remaining_quota * 0.10)
    }

    # 调整配额以确保总和等于 remaining_quota
    total_allocated = sum(quotas.values())
    if total_allocated < remaining_quota:
        quotas['high'] += (remaining_quota - total_allocated)

    print(f"\n第二步配额分配 (剩余 {remaining_quota} 条):")
    for cat, quota in quotas.items():
        print(f"  {cat}: {quota} 条")

    # 从每个类别抽取
    for category, quota in quotas.items():
        available = samples_by_saturation[category]
        if len(available) <= quota:
            # 全部选中
            selected.extend(available)
        else:
            # 随机抽取
            selected.extend(random.sample(available, quota))

    print(f"\n第二步完成: 已选 {len(selected)} 条")

    # 打乱顺序
    random.shuffle(selected)

    return selected


def print_statistics(samples: List[Dict[str, Any]]):
    """打印抽取统计"""
    print("\n" + "="*60)
    print("抽取统计信息")
    print("="*60)

    # 总数
    print(f"\n总样本数: {len(samples)}")

    # 按场景分布
    scenario_counts = defaultdict(int)
    for sample in samples:
        state_file = sample['state_file']
        if 'arterial4x4_10' in state_file:
            scenario_counts['arterial4x4_10'] += 1
        elif 'chengdu' in state_file:
            scenario_counts['chengdu'] += 1
        else:
            scenario_counts['unknown'] += 1

    print("\n按场景分布:")
    for scenario, count in sorted(scenario_counts.items()):
        print(f"  {scenario}: {count} 条")

    # 按 tl_id 分布
    tl_counts = defaultdict(int)
    for sample in samples:
        tl_id = sample['metadata']['tl_id']
        tl_counts[tl_id] += 1

    print(f"\n按 tl_id 分布 (共 {len(tl_counts)} 个交叉口):")
    for tl_id, count in sorted(tl_counts.items()):
        print(f"  {tl_id}: {count} 条")

    # 按饱和度区间分布
    sat_counts = defaultdict(int)
    for sample in samples:
        sat = calculate_sample_saturation(sample)
        category = get_saturation_category(sat)
        sat_counts[category] += 1

    print("\n按饱和度区间分布:")
    for cat in ['zero', 'low', 'medium', 'high']:
        count = sat_counts.get(cat, 0)
        print(f"  {cat} (saturation {'= 0.0' if cat == 'zero' else '< 0.5' if cat == 'low' else '< 1.0' if cat == 'medium' else '>= 1.0'}): {count} 条")

    # 按相位数分布
    phase_counts = defaultdict(int)
    for sample in samples:
        phase_count = get_phase_count(sample)
        phase_counts[phase_count] += 1

    print("\n按相位数分布:")
    for phase_num, count in sorted(phase_counts.items()):
        print(f"  {phase_num} 相位: {count} 条")

    print("\n" + "="*60)


def main():
    parser = argparse.ArgumentParser(description='从 train.jsonl 中抽取代表性样本')
    parser.add_argument('--input', required=True, help='输入文件路径 (train.jsonl)')
    parser.add_argument('--output', required=True, help='输出文件路径')
    parser.add_argument('--count', type=int, default=100, help='目标样本数 (默认 100)')
    parser.add_argument('--seed', type=int, default=42, help='随机种子 (默认 42)')

    args = parser.parse_args()

    # 加载样本
    print(f"正在加载样本: {args.input}")
    samples = load_samples(args.input)

    # 抽取样本
    print(f"\n开始抽取 {args.count} 条样本 (随机种子: {args.seed})")
    selected_samples = select_samples(samples, args.count, args.seed)

    # 创建输出目录
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 写出结果
    print(f"\n正在写出结果: {args.output}")
    with open(args.output, 'w', encoding='utf-8') as f:
        for sample in selected_samples:
            f.write(json.dumps(sample, ensure_ascii=False) + '\n')

    # 打印统计
    print_statistics(selected_samples)

    print(f"\n完成! 已抽取 {len(selected_samples)} 条样本到 {args.output}")


if __name__ == '__main__':
    main()
