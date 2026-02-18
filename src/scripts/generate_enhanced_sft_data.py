#!/usr/bin/env python3
"""
增强版 SFT 数据生成脚本

功能：读取现有的 think_workspace.jsonl，扩展 think 字段内容到 200-300 中文字符
"""

import json
import argparse
import shutil
from pathlib import Path
from typing import List, Dict, Any
import subprocess


def analyze_saturation_level(saturation: float) -> str:
    """分析饱和度水平"""
    if saturation > 1.0:
        return "高饱和度（超过容量），交通压力较大"
    elif saturation > 0.7:
        return "较高饱和度，交通流量接近容量"
    elif saturation > 0.5:
        return "中等饱和度，交通流量适中"
    elif saturation > 0.3:
        return "较低饱和度，交通压力较小"
    else:
        return "低饱和度，交通畅通"


def generate_enhanced_think(phase_waits: List[Dict[str, Any]], solution: List[Dict[str, Any]]) -> str:
    """
    生成增强版思考链内容（200-300 中文字符）

    内容包含：
    1. 交通状态整体分析
    2. 各相位饱和度解读
    3. 配时决策推理过程
    4. 约束满足验证
    """

    # 1. 整体交通状态分析
    saturations = [pw['pred_saturation'] for pw in phase_waits]
    max_sat = max(saturations)
    min_sat = min(saturations)
    avg_sat = sum(saturations) / len(saturations)

    # 判断整体状态
    if max_sat > 1.0:
        overall_status = "当前整体交通压力较大，存在高饱和度相位需要优先处理"
    elif avg_sat > 0.6:
        overall_status = "当前整体交通流量较高，需要合理分配绿灯时间"
    else:
        overall_status = "当前整体交通状况良好，可按需分配绿灯时间"

    think_parts = [f"## 交通状态整体分析\n{overall_status}。"]

    # 2. 各相位详细分析
    phase_analysis = []
    for pw, sol in zip(phase_waits, solution):
        phase_id = pw['phase_id']
        sat = pw['pred_saturation']
        min_green = pw['min_green']
        max_green = pw['max_green']
        final = sol['final']

        sat_level = analyze_saturation_level(sat)

        # 计算分配比例
        if max_sat > 0:
            ratio = sat / max_sat
        else:
            ratio = 0

        # 分析决策依据
        if sat > 1.0:
            decision = f"该相位饱和度为 {sat:.2f}，{sat_level}，因此分配最大绿灯时间 {max_green}s 以缓解拥堵"
        elif sat > 0.5:
            decision = f"该相位饱和度为 {sat:.2f}，{sat_level}，根据比例分配绿灯时间 {final}s"
        else:
            decision = f"该相位饱和度为 {sat:.2f}，{sat_level}，分配最小绿灯时间 {min_green}s 即可满足需求"

        phase_analysis.append(f"**相位 {phase_id}**：{decision}（min={min_green}s, max={max_green}s）")

    think_parts.append(f"## 各相位分析\n" + "\n".join(phase_analysis))

    # 3. 配时决策总结
    decision_summary = f"## 配时决策\n综合以上分析，各相位的最终绿灯时间配置如下："
    for sol in solution:
        pw = next(pw for pw in phase_waits if pw['phase_id'] == sol['phase_id'])
        think_parts.append(decision_summary)
        break

    allocation_details = []
    for sol in solution:
        pw = next(pw for pw in phase_waits if pw['phase_id'] == sol['phase_id'])
        allocation_details.append(f"- 相位 {sol['phase_id']}：{sol['final']}s")

    think_parts[-1] += "\n" + "\n".join(allocation_details)

    # 4. 约束验证
    constraint_checks = []
    all_valid = True
    for pw, sol in zip(phase_waits, solution):
        if pw['min_green'] <= sol['final'] <= pw['max_green']:
            constraint_checks.append(f"相位 {sol['phase_id']}：final={sol['final']}s 满足 [{pw['min_green']}, {pw['max_green']}] 约束")
        else:
            constraint_checks.append(f"相位 {sol['phase_id']}：final={sol['final']}s 违反约束 [{pw['min_green']}, {pw['max_green']}]")
            all_valid = False

    validation_result = "所有约束均已满足" if all_valid else "存在约束违反，需要重新检查"
    think_parts.append(f"## 约束验证\n{validation_result}：\n" + "\n".join(constraint_checks))

    return "\n\n".join(think_parts)


def backup_file(file_path: str) -> str:
    """备份文件"""
    backup_path = file_path + ".bak"
    if Path(file_path).exists():
        shutil.copy2(file_path, backup_path)
        print(f"[备份] 已创建备份: {backup_path}")
    return backup_path


def main():
    parser = argparse.ArgumentParser(description='增强版 SFT 数据生成脚本')
    parser.add_argument('--workspace', default='outputs/sft/think_workspace.jsonl',
                        help='输入工作区文件路径')
    parser.add_argument('--output', default='outputs/sft/think_workspace.jsonl',
                        help='输出工作区文件路径')
    parser.add_argument('--samples', default='outputs/sft/sampled_100.jsonl',
                        help='原始样本文件路径')
    parser.add_argument('--no-backup', action='store_true',
                        help='不创建备份文件')

    args = parser.parse_args()

    # 备份原文件
    if not args.no_backup and args.workspace == args.output:
        backup_file(args.workspace)

    print(f"[读取] 工作区文件: {args.workspace}")

    # 读取工作区数据
    workspace_data = []
    with open(args.workspace, 'r', encoding='utf-8') as f:
        for line in f:
            workspace_data.append(json.loads(line.strip()))

    print(f"[读取] 共 {len(workspace_data)} 条数据")

    # 处理每条数据
    enhanced_data = []
    think_lengths = []

    for item in workspace_data:
        # 生成增强版 think
        enhanced_think = generate_enhanced_think(item['phase_waits'], item['solution'])
        think_lengths.append(len(enhanced_think))

        # 更新数据
        enhanced_item = item.copy()
        enhanced_item['think'] = enhanced_think
        enhanced_data.append(enhanced_item)

        # 打印进度
        if (len(enhanced_data)) % 10 == 0:
            print(f"[进度] 已处理 {len(enhanced_data)}/{len(workspace_data)} 条")

    # 写入输出文件
    print(f"[写入] 输出文件: {args.output}")
    with open(args.output, 'w', encoding='utf-8') as f:
        for item in enhanced_data:
            f.write(json.dumps(item, ensure_ascii=False) + '\n')

    # 统计
    avg_length = sum(think_lengths) / len(think_lengths)
    min_length = min(think_lengths)
    max_length = max(think_lengths)

    print(f"\n[统计]")
    print(f"  总条数: {len(enhanced_data)}")
    print(f"  Think 长度: min={min_length}, max={max_length}, avg={avg_length:.1f}")
    print(f"  目标范围: 200-300 中文字符")

    # 调用 generate_sft_data.py assemble 生成最终训练数据
    output_sft = args.output.replace('think_workspace.jsonl', 'sft_train.jsonl')
    print(f"\n[组装] 调用 generate_sft_data.py assemble...")
    result = subprocess.run([
        'python3', 'src/scripts/generate_sft_data.py', 'assemble',
        '--workspace', args.output,
        '--samples', args.samples,
        '--output', output_sft
    ], capture_output=True, text=True)

    print(result.stdout)
    if result.returncode != 0:
        print(f"[错误] {result.stderr}")
        return 1

    print(f"\n[完成] 增强版 SFT 数据已生成!")
    return 0


if __name__ == '__main__':
    exit(main())
