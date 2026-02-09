#!/usr/bin/env python3
"""
GRPO 数据生成脚本

从 train.jsonl 读取全部样本并转换为 GRPO 训练格式。
GRPO 格式: prompt 为 messages 数组（system + user），metadata 包含 state_file 和原始 metadata 字段。
"""

import json
import argparse
from pathlib import Path
from typing import Dict, Any


# System prompt (与 SFT 阶段一致)
SYSTEM_PROMPT = (
    "你是交通信号配时优化专家。\n"
    "请认真分析预测得到的下个周期各个相位的交通状态，给出下个周期的配时方案，并给出你的推理过程。\n"
    "将推理过程放在 <think> 和 </think> 之间。\n"
    "然后，将你的最终方案放在 <CyclePlan> 和 </CyclePlan> 之间。"
)


def convert_state_file_to_relative(state_file: str) -> str:
    """
    将 state_file 从绝对路径转换为相对路径。

    例如:
    输入: "/home/samuel/SCU_TSC/outputs/states/arterial4x4_10/state_xxx.xml"
    输出: "outputs/states/arterial4x4_10/state_xxx.xml"
    """
    marker = "outputs/states/"
    idx = state_file.find(marker)
    if idx != -1:
        return state_file[idx:]
    else:
        # Fallback: 如果没有找到 marker，返回原始路径
        return state_file


def convert_to_grpo_format(sample: Dict[str, Any]) -> Dict[str, Any]:
    """
    将原始训练样本转换为 GRPO 格式。

    Args:
        sample: 原始样本，包含 prompt, prediction, state_file, metadata

    Returns:
        GRPO 格式的样本，包含 prompt (messages 数组) 和 metadata
    """
    # 提取 user content: 去掉 prompt 第一行（旧的 system prompt）
    original_prompt = sample['prompt']
    lines = original_prompt.split('\n')
    # 第一行是 "你是交通信号配时优化专家。"，去掉
    user_content = '\n'.join(lines[1:])

    # 转换 state_file 为相对路径
    relative_state_file = convert_state_file_to_relative(sample['state_file'])

    # 组装 messages
    messages = [
        {'role': 'system', 'content': SYSTEM_PROMPT},
        {'role': 'user', 'content': user_content}
    ]

    # 组装 metadata: state_file + 原始 metadata 字段
    metadata = {
        'state_file': relative_state_file,
        **sample['metadata']
    }

    return {
        'prompt': messages,
        'metadata': metadata
    }


def generate_grpo_data(input_path: str, output_path: str):
    """
    生成 GRPO 训练数据。

    Args:
        input_path: 输入文件路径（train.jsonl）
        output_path: 输出文件路径（grpo_train.jsonl）
    """
    print(f"[GRPO 数据生成] 读取输入文件: {input_path}")

    # 读取原始样本
    samples = []
    with open(input_path, 'r', encoding='utf-8') as f:
        for line in f:
            samples.append(json.loads(line.strip()))

    print(f"[GRPO 数据生成] 读取到 {len(samples)} 条样本")

    # 转换为 GRPO 格式
    grpo_samples = []
    scenario_stats = {}
    path_conversion_stats = {
        'converted': 0,
        'fallback': 0
    }

    for sample in samples:
        grpo_sample = convert_to_grpo_format(sample)
        grpo_samples.append(grpo_sample)

        # 统计场景分布
        state_file = sample['state_file']
        if 'chengdu' in state_file:
            scenario = 'chengdu'
        elif 'arterial4x4_10' in state_file:
            scenario = 'arterial4x4_10'
        else:
            scenario = 'unknown'
        scenario_stats[scenario] = scenario_stats.get(scenario, 0) + 1

        # 统计路径转换结果
        if grpo_sample['metadata']['state_file'].startswith('outputs/'):
            path_conversion_stats['converted'] += 1
        else:
            path_conversion_stats['fallback'] += 1

    # 写入输出文件
    output_dir = Path(output_path).parent
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"[GRPO 数据生成] 写入输出文件: {output_path}")
    with open(output_path, 'w', encoding='utf-8') as f:
        for grpo_sample in grpo_samples:
            f.write(json.dumps(grpo_sample, ensure_ascii=False) + '\n')

    # 打印统计信息
    print(f"\n[统计信息]")
    print(f"  总样本数: {len(grpo_samples)}")
    print(f"  场景分布:")
    for scenario, count in sorted(scenario_stats.items()):
        print(f"    {scenario}: {count}")
    print(f"  State file 路径转换:")
    print(f"    成功转换为相对路径: {path_conversion_stats['converted']}")
    print(f"    Fallback (保持原样): {path_conversion_stats['fallback']}")
    print(f"\n[GRPO 数据生成] 完成!")


def main():
    parser = argparse.ArgumentParser(description='GRPO 数据生成脚本')
    parser.add_argument(
        '--input',
        default='outputs/data/train.jsonl',
        help='输入文件路径（默认: outputs/data/train.jsonl）'
    )
    parser.add_argument(
        '--output',
        default='outputs/grpo/grpo_train.jsonl',
        help='输出文件路径（默认: outputs/grpo/grpo_train.jsonl）'
    )
    parser.add_argument(
        '--config',
        default='config/config.json',
        help='配置文件路径（默认: config/config.json，预留扩展）'
    )

    args = parser.parse_args()

    # 生成 GRPO 数据
    generate_grpo_data(args.input, args.output)


if __name__ == '__main__':
    main()
