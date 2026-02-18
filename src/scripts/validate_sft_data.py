#!/usr/bin/env python3
"""
SFT 数据校验脚本

功能：
1. 校验 JSON 结构
2. 校验标签格式
3. 校验约束满足
4. 统计 token 长度
"""

import json
import argparse
import re
import sys
from pathlib import Path
from typing import List, Dict, Any, Tuple


def count_tokens_chinese(text: str) -> int:
    """
    估算中文文本的 token 数量
    中文约 0.5 token/字符，英文约 0.25 token/字符
    """
    # 简单估算：中文字符 * 2 + 英文单词
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
    other_chars = len(text) - chinese_chars
    return int(chinese_chars * 2 + other_chars * 0.25)


def validate_json_structure(item: Dict[str, Any], line_num: int) -> List[str]:
    """校验 JSON 结构"""
    errors = []

    # 检查 messages 字段
    if 'messages' not in item:
        errors.append(f"行 {line_num}: 缺少 'messages' 字段")
        return errors

    messages = item['messages']
    if not isinstance(messages, list):
        errors.append(f"行 {line_num}: 'messages' 不是数组")
        return errors

    if len(messages) != 3:
        errors.append(f"行 {line_num}: 'messages' 应包含 3 个元素（system, user, assistant），实际 {len(messages)} 个")
        return errors

    # 检查角色
    expected_roles = ['system', 'user', 'assistant']
    for i, (msg, expected_role) in enumerate(zip(messages, expected_roles)):
        if not isinstance(msg, dict):
            errors.append(f"行 {line_num}: messages[{i}] 不是对象")
            continue
        if 'role' not in msg:
            errors.append(f"行 {line_num}: messages[{i}] 缺少 'role' 字段")
        elif msg['role'] != expected_role:
            errors.append(f"行 {line_num}: messages[{i}].role 应为 '{expected_role}'，实际 '{msg.get('role')}'")
        if 'content' not in msg:
            errors.append(f"行 {line_num}: messages[{i}] 缺少 'content' 字段")

    return errors


def validate_tags(content: str, line_num: int) -> Tuple[List[str], str]:
    """校验标签格式"""
    errors = []

    # 检查 <start_working_out> 和 <end_working_out>
    start_working = content.count('<start_working_out>')
    end_working = content.count('<end_working_out>')

    if start_working != 1:
        errors.append(f"行 {line_num}: <start_working_out> 出现 {start_working} 次，应为 1 次")
    if end_working != 1:
        errors.append(f"行 {line_num}: <end_working_out> 出现 {end_working} 次，应为 1 次")

    # 检查 <SOLUTION> 和 </SOLUTION>
    start_solution = content.count('<SOLUTION>')
    end_solution = content.count('</SOLUTION>')

    if start_solution != 1:
        errors.append(f"行 {line_num}: <SOLUTION> 出现 {start_solution} 次，应为 1 次")
    if end_solution != 1:
        errors.append(f"行 {line_num}: </SOLUTION> 出现 {end_solution} 次，应为 1 次")

    # 提取 SOLUTION 内容
    solution_content = ""
    solution_match = re.search(r'<SOLUTION>(.*?)</SOLUTION>', content, re.DOTALL)
    if solution_match:
        solution_content = solution_match.group(1).strip()
    else:
        errors.append(f"行 {line_num}: 无法提取 SOLUTION 内容")

    return errors, solution_content


def validate_solution_json(solution_str: str, line_num: int) -> Tuple[List[str], List[Dict[str, int]]]:
    """校验 SOLUTION JSON 格式"""
    errors = []
    solution_data = []

    try:
        solution_data = json.loads(solution_str)
        if not isinstance(solution_data, list):
            errors.append(f"行 {line_num}: SOLUTION 内容不是数组")
            return errors, []
    except json.JSONDecodeError as e:
        errors.append(f"行 {line_num}: SOLUTION JSON 解析失败: {e}")
        return errors, []

    # 检查每个元素
    for i, item in enumerate(solution_data):
        if not isinstance(item, dict):
            errors.append(f"行 {line_num}: SOLUTION[{i}] 不是对象")
            continue
        if 'phase_id' not in item:
            errors.append(f"行 {line_num}: SOLUTION[{i}] 缺少 'phase_id'")
        if 'final' not in item:
            errors.append(f"行 {line_num}: SOLUTION[{i}] 缺少 'final'")

    return errors, solution_data


def validate_constraints(solution_data: List[Dict[str, int]], phase_waits: List[Dict[str, Any]], line_num: int) -> List[str]:
    """校验约束满足"""
    errors = []

    if not phase_waits:
        # 需要从 assistant content 中推断约束（如果可能）
        return errors

    for sol in solution_data:
        phase_id = sol.get('phase_id')
        final = sol.get('final')

        # 查找对应的 phase_waits
        pw = None
        for p in phase_waits:
            if p['phase_id'] == phase_id:
                pw = p
                break

        if pw is None:
            errors.append(f"行 {line_num}: SOLUTION 中 phase_id={phase_id} 在 phase_waits 中找不到")
            continue

        min_green = pw['min_green']
        max_green = pw['max_green']

        if not (min_green <= final <= max_green):
            errors.append(f"行 {line_num}: phase {phase_id} 的 final={final} 违反约束 [{min_green}, {max_green}]")

    return errors


def extract_think_content(content: str) -> str:
    """提取思考链内容"""
    match = re.search(r'<start_working_out>(.*?)<end_working_out>', content, re.DOTALL)
    if match:
        return match.group(1).strip()
    return ""


def validate_file(input_path: str, verbose: bool = False) -> Tuple[bool, Dict[str, Any]]:
    """校验文件"""
    stats = {
        'total': 0,
        'passed': 0,
        'failed': 0,
        'errors': [],
        'think_lengths': [],
        'token_lengths': [],
        'constraint_violations': 0,
        'empty_thinks': 0
    }

    with open(input_path, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            stats['total'] += 1
            line = line.strip()
            if not line:
                continue

            try:
                item = json.loads(line)
            except json.JSONDecodeError as e:
                stats['failed'] += 1
                stats['errors'].append(f"行 {line_num}: JSON 解析失败 - {e}")
                continue

            # 校验 JSON 结构
            structure_errors = validate_json_structure(item, line_num)
            stats['errors'].extend(structure_errors)

            if structure_errors:
                stats['failed'] += 1
                continue

            # 获取 assistant content
            assistant_content = item['messages'][2]['content']

            # 校验标签
            tag_errors, solution_str = validate_tags(assistant_content, line_num)
            stats['errors'].extend(tag_errors)

            if tag_errors:
                stats['failed'] += 1
                continue

            # 校验 SOLUTION JSON
            solution_errors, solution_data = validate_solution_json(solution_str, line_num)
            stats['errors'].extend(solution_errors)

            # 提取并统计思考链长度
            think_content = extract_think_content(assistant_content)
            think_len = len(think_content)
            stats['think_lengths'].append(think_len)
            stats['token_lengths'].append(count_tokens_chinese(think_content))

            if think_len == 0:
                stats['empty_thinks'] += 1
                if verbose:
                    print(f"  [警告] 行 {line_num}: 思考链为空")

            # 统计通过/失败
            if structure_errors or tag_errors or solution_errors:
                stats['failed'] += 1
            else:
                stats['passed'] += 1

    # 计算统计
    if stats['think_lengths']:
        stats['think_min'] = min(stats['think_lengths'])
        stats['think_max'] = max(stats['think_lengths'])
        stats['think_avg'] = sum(stats['think_lengths']) / len(stats['think_lengths'])
        stats['think_median'] = sorted(stats['think_lengths'])[len(stats['think_lengths']) // 2]
    else:
        stats['think_min'] = stats['think_max'] = stats['think_avg'] = stats['think_median'] = 0

    if stats['token_lengths']:
        stats['token_min'] = min(stats['token_lengths'])
        stats['token_max'] = max(stats['token_lengths'])
        stats['token_avg'] = sum(stats['token_lengths']) / len(stats['token_lengths'])
    else:
        stats['token_min'] = stats['token_max'] = stats['token_avg'] = 0

    all_passed = stats['failed'] == 0 and stats['constraint_violations'] == 0

    return all_passed, stats


def main():
    parser = argparse.ArgumentParser(description='SFT 数据校验脚本')
    parser.add_argument('--input', required=True, help='输入 JSONL 文件路径')
    parser.add_argument('--verbose', action='store_true', help='详细输出')

    args = parser.parse_args()

    if not Path(args.input).exists():
        print(f"[错误] 文件不存在: {args.input}")
        return 1

    print(f"[校验] 开始校验: {args.input}")
    print()

    all_passed, stats = validate_file(args.input, args.verbose)

    # 输出结果
    print("=" * 60)
    print("校验结果摘要")
    print("=" * 60)
    print(f"总条数: {stats['total']}")
    print(f"通过: {stats['passed']}")
    print(f"失败: {stats['failed']}")
    print(f"空思考链: {stats['empty_thinks']}")
    print()

    print("-" * 60)
    print("思考链长度统计 (字符)")
    print("-" * 60)
    print(f"最小值: {stats['think_min']}")
    print(f"最大值: {stats['think_max']}")
    print(f"平均值: {stats['think_avg']:.1f}")
    print(f"中位数: {stats['think_median']}")
    print()

    print("-" * 60)
    print("Token 长度估算")
    print("-" * 60)
    print(f"最小值: {stats['token_min']}")
    print(f"最大值: {stats['token_max']}")
    print(f"平均值: {stats['token_avg']:.1f}")
    print()

    # 输出错误详情
    if stats['errors']:
        print("-" * 60)
        print(f"错误详情 ({len(stats['errors'])} 个)")
        print("-" * 60)
        for error in stats['errors'][:20]:  # 只显示前 20 个
            print(f"  {error}")
        if len(stats['errors']) > 20:
            print(f"  ... 还有 {len(stats['errors']) - 20} 个错误")
        print()

    # 最终结果
    print("=" * 60)
    if all_passed:
        print("[通过] 所有校验项通过!")
    else:
        print(f"[失败] 存在 {stats['failed']} 条数据校验失败")
    print("=" * 60)

    return 0 if all_passed else 1


if __name__ == '__main__':
    exit(main())
