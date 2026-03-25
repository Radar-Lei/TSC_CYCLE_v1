"""
GLM-5 结果到 SFT 训练数据的组装脚本

将 Phase 2 的 GLM-5 生成结果 (outputs/glm5/results.jsonl) 转换为
SFT 训练数据格式 (outputs/sft/sft_train.jsonl)，使其可直接被 src/sft/train.py 加载。

输入格式 (results.jsonl 每行):
    {"prompt": "...", "think": "...", "solution": [...], ...}

输出格式 (sft_train.jsonl 每行):
    {"messages": [{"role": "system", ...}, {"role": "user", ...}, {"role": "assistant", ...}]}
"""

import argparse
import json
import os
from typing import Dict, Any, Optional

from src.data_generator.prompt_builder import SYSTEM_PROMPT

__all__ = ["main", "assemble_sft_record"]


def assemble_sft_record(record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    将 results.jsonl 单行记录转换为 SFT messages 格式

    Args:
        record: results.jsonl 中的一行 JSON 对象，包含 prompt, think, solution 字段

    Returns:
        messages 格式字典，或 None（当 solution 为空/缺失时）
    """
    prompt = record.get("prompt", "")
    think = record.get("think", "")
    solution = record.get("solution")

    # 跳过无效记录
    if not solution:
        return None

    # 构建 assistant content
    solution_json = json.dumps(solution, ensure_ascii=False, separators=(",", ":"))
    assistant_content = (
        f"<start_working_out>{think}<end_working_out>"
        f"<SOLUTION>{solution_json}</SOLUTION>"
    )

    return {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": assistant_content},
        ]
    }


def main():
    """CLI 入口：从 results.jsonl 组装 sft_train.jsonl"""
    parser = argparse.ArgumentParser(
        description="将 GLM-5 生成结果组装为 SFT 训练数据"
    )
    parser.add_argument(
        "--input",
        default="outputs/glm5/results.jsonl",
        help="输入文件路径 (默认: outputs/glm5/results.jsonl)",
    )
    parser.add_argument(
        "--output",
        default="outputs/sft/sft_train.jsonl",
        help="输出文件路径 (默认: outputs/sft/sft_train.jsonl)",
    )
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"[组装] 错误: 输入文件不存在: {args.input}")
        return

    # 确保输出目录存在
    os.makedirs(os.path.dirname(args.output), exist_ok=True)

    total = 0
    assembled = 0
    skipped = 0

    with open(args.input, "r", encoding="utf-8") as fin, \
         open(args.output, "w", encoding="utf-8") as fout:
        for line_num, line in enumerate(fin, 1):
            line = line.strip()
            if not line:
                continue
            total += 1

            try:
                record = json.loads(line)
            except json.JSONDecodeError as e:
                print(f"[组装] 警告: 第 {line_num} 行 JSON 解析失败: {e}")
                skipped += 1
                continue

            result = assemble_sft_record(record)
            if result is None:
                print(f"[组装] 警告: 第 {line_num} 行 solution 为空或缺失，跳过")
                skipped += 1
                continue

            fout.write(json.dumps(result, ensure_ascii=False) + "\n")
            assembled += 1

    print(f"[组装] 完成: 总条数={total}, 成功组装={assembled}, 跳过={skipped}")


if __name__ == "__main__":
    main()
