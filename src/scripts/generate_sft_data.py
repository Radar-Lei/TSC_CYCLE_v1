#!/usr/bin/env python3
"""
SFT 数据组装与校验脚本

功能 A (prepare): 生成 solution 值 + 导出数据框架
功能 B (assemble): 组装最终 JSONL 格式的 SFT 训练数据
"""

import json
import argparse
import re
from pathlib import Path
from typing import List, Dict, Any


def calculate_solution(phase_waits: List[Dict[str, Any]]) -> List[Dict[str, int]]:
    """
    基于 pred_saturation 按比例在 [min_green, max_green] 范围内分配 final 值

    策略:
    - saturation 越高的相位分配越接近 max_green
    - saturation 为 0 的相位分配 min_green
    - 线性映射并确保满足硬约束
    """
    solution = []

    # 提取所有 saturation 值
    saturations = [pw['pred_saturation'] for pw in phase_waits]
    max_sat = max(saturations) if saturations else 0
    min_sat = min(saturations) if saturations else 0

    for pw in phase_waits:
        phase_id = pw['phase_id']
        sat = pw['pred_saturation']
        min_green = pw['min_green']
        max_green = pw['max_green']

        # 计算 final 值
        if max_sat == min_sat:
            # 所有相位 saturation 相同,分配 min_green
            final = min_green
        elif sat == 0:
            # saturation 为 0,分配 min_green
            final = min_green
        else:
            # 线性映射: sat 越大越接近 max_green
            # ratio = (sat - min_sat) / (max_sat - min_sat)
            # final = min_green + ratio * (max_green - min_green)
            ratio = sat / max_sat
            final = min_green + ratio * (max_green - min_green)
            final = round(final)

        # 硬约束: clamp 到 [min_green, max_green]
        final = max(min_green, min(max_green, int(final)))

        solution.append({
            'phase_id': phase_id,
            'final': final
        })

    return solution


def prepare(input_path: str, output_path: str):
    """
    功能 A: 读取样本数据,生成 solution,导出工作区文件
    """
    print(f"[PREPARE] 读取输入文件: {input_path}")

    samples = []
    with open(input_path, 'r', encoding='utf-8') as f:
        for line in f:
            samples.append(json.loads(line.strip()))

    print(f"[PREPARE] 读取到 {len(samples)} 条样本")

    workspace_data = []
    for idx, sample in enumerate(samples):
        phase_waits = sample['prediction']['phase_waits']
        solution = calculate_solution(phase_waits)

        # 验证约束
        for pw, sol in zip(phase_waits, solution):
            assert pw['phase_id'] == sol['phase_id'], f"Phase ID 不匹配: {pw['phase_id']} vs {sol['phase_id']}"
            assert pw['min_green'] <= sol['final'] <= pw['max_green'], \
                f"Final 值违反约束: phase {pw['phase_id']}, final={sol['final']}, range=[{pw['min_green']}, {pw['max_green']}]"

        workspace_item = {
            'index': idx,
            'tl_id': sample['metadata']['tl_id'],
            'scenario': 'chengdu' if 'chengdu' in sample['state_file'] else 'arterial4x4_10',
            'phase_waits': phase_waits,
            'solution': solution,
            'think': ''
        }
        workspace_data.append(workspace_item)

    print(f"[PREPARE] 写入工作区文件: {output_path}")
    with open(output_path, 'w', encoding='utf-8') as f:
        for item in workspace_data:
            f.write(json.dumps(item, ensure_ascii=False) + '\n')

    print(f"[PREPARE] 完成! 已生成 {len(workspace_data)} 条工作区数据")
    print(f"[PREPARE] 所有 solution 已通过约束校验")


def assemble(workspace_path: str, samples_path: str, output_path: str):
    """
    功能 B: 组装最终 JSONL 格式的 SFT 训练数据
    """
    print(f"[ASSEMBLE] 读取工作区文件: {workspace_path}")
    workspace_data = []
    with open(workspace_path, 'r', encoding='utf-8') as f:
        for line in f:
            workspace_data.append(json.loads(line.strip()))

    print(f"[ASSEMBLE] 读取原始样本文件: {samples_path}")
    samples = []
    with open(samples_path, 'r', encoding='utf-8') as f:
        for line in f:
            samples.append(json.loads(line.strip()))

    assert len(workspace_data) == len(samples), f"数据数量不匹配: {len(workspace_data)} vs {len(samples)}"

    print(f"[ASSEMBLE] 组装 SFT 训练数据...")

    sft_data = []
    stats = {
        'total': 0,
        'constraint_violations': 0,
        'empty_thinks': 0,
        'think_lengths': []
    }

    for workspace_item, sample in zip(workspace_data, samples):
        # 双重校验
        think_text = workspace_item['think']
        solution = workspace_item['solution']
        phase_waits = workspace_item['phase_waits']

        # 校验 think 非空
        if not think_text or think_text.strip() == '':
            stats['empty_thinks'] += 1
            print(f"[警告] Index {workspace_item['index']} 的 think 为空")

        stats['think_lengths'].append(len(think_text))

        # 校验约束
        for pw, sol in zip(phase_waits, solution):
            if pw['phase_id'] != sol['phase_id']:
                stats['constraint_violations'] += 1
                print(f"[错误] Index {workspace_item['index']}: Phase ID 不匹配")
            if not (pw['min_green'] <= sol['final'] <= pw['max_green']):
                stats['constraint_violations'] += 1
                print(f"[错误] Index {workspace_item['index']}: Final 值违反约束 (phase {pw['phase_id']})")

        # 提取原始 prompt,去掉第一行系统角色行
        original_prompt = sample['prompt']
        lines = original_prompt.split('\n')
        # 第一行是 "你是交通信号配时优化专家。",去掉
        user_content = '\n'.join(lines[1:])

        # 组装 solution JSON
        solution_json = json.dumps(solution, ensure_ascii=False)

        # 组装 assistant content
        assistant_content = f"<think>{think_text}<think><solution>{solution_json}<solution>"

        # 组装 messages
        sft_item = {
            'messages': [
                {'role': 'system', 'content': '你是交通信号配时优化专家。'},
                {'role': 'user', 'content': user_content},
                {'role': 'assistant', 'content': assistant_content}
            ]
        }

        sft_data.append(sft_item)
        stats['total'] += 1

    print(f"[ASSEMBLE] 写入输出文件: {output_path}")
    with open(output_path, 'w', encoding='utf-8') as f:
        for item in sft_data:
            f.write(json.dumps(item, ensure_ascii=False) + '\n')

    # 打印统计
    avg_think_length = sum(stats['think_lengths']) / len(stats['think_lengths']) if stats['think_lengths'] else 0
    print(f"\n[统计]")
    print(f"  总条数: {stats['total']}")
    print(f"  Think 平均长度: {avg_think_length:.1f} 字符")
    print(f"  约束违反数: {stats['constraint_violations']} (应为 0)")
    print(f"  空 Think 数: {stats['empty_thinks']} (应为 0)")
    print(f"\n[ASSEMBLE] 完成!")


def main():
    parser = argparse.ArgumentParser(description='SFT 数据组装与校验脚本')
    subparsers = parser.add_subparsers(dest='command', help='子命令')

    # prepare 子命令
    prepare_parser = subparsers.add_parser('prepare', help='生成 solution + 导出工作区文件')
    prepare_parser.add_argument('--input', required=True, help='输入样本文件 (sampled_100.jsonl)')
    prepare_parser.add_argument('--output', required=True, help='输出工作区文件 (think_workspace.jsonl)')

    # assemble 子命令
    assemble_parser = subparsers.add_parser('assemble', help='组装最终 SFT 训练数据')
    assemble_parser.add_argument('--workspace', required=True, help='工作区文件 (think_workspace.jsonl)')
    assemble_parser.add_argument('--samples', required=True, help='原始样本文件 (sampled_100.jsonl)')
    assemble_parser.add_argument('--output', required=True, help='输出文件 (sft_train.jsonl)')

    args = parser.parse_args()

    if args.command == 'prepare':
        prepare(args.input, args.output)
    elif args.command == 'assemble':
        assemble(args.workspace, args.samples, args.output)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
