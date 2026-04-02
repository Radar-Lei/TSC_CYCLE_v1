#!/usr/bin/env python3
"""
生成简化版 GRPO 训练数据。

数据源直接使用原始 `outputs/data/train.jsonl`，不依赖 GLM-5 生成的 SFT 数据。
输出格式与 TRL/GRPO 训练保持一致：`prompt` 为 messages，`metadata` 保留原始上下文。
"""

import argparse
import json
from pathlib import Path
from typing import Any, Dict


SYSTEM_PROMPT = (
    "你是交通信号配时优化专家。\n"
    "请认真分析预测得到的下个周期各个相位的交通状态，给出下个周期的配时方案，并给出你的推理过程。\n"
    "将推理过程放在 <start_working_out> 和 <end_working_out> 之间。\n"
    "然后，将你的最终方案放在 <SOLUTION> 和 </SOLUTION> 之间。"
)


def convert_state_file_to_relative(state_file: str) -> str:
    marker = "outputs/states/"
    idx = state_file.find(marker)
    return state_file[idx:] if idx != -1 else state_file


def convert_to_grpo_simple_format(sample: Dict[str, Any]) -> Dict[str, Any]:
    prompt = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": sample["prompt"]},
    ]

    metadata = {
        "state_file": convert_state_file_to_relative(sample["state_file"]),
        "source": "outputs/data/train.jsonl",
        **sample.get("metadata", {}),
    }

    return {
        "prompt": prompt,
        "metadata": metadata,
    }


def generate_data(input_path: str, output_path: str):
    input_file = Path(input_path)
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    total = 0
    with input_file.open("r", encoding="utf-8") as fin, output_file.open("w", encoding="utf-8") as fout:
        for line in fin:
            sample = json.loads(line)
            record = convert_to_grpo_simple_format(sample)
            fout.write(json.dumps(record, ensure_ascii=False) + "\n")
            total += 1

    print(f"[GRPO Simple 数据] 输入: {input_path}")
    print(f"[GRPO Simple 数据] 输出: {output_path}")
    print(f"[GRPO Simple 数据] 样本数: {total}")


def main():
    parser = argparse.ArgumentParser(description="Generate simplified GRPO training data")
    parser.add_argument(
        "--input",
        default="outputs/data/train.jsonl",
        help="输入文件路径（默认: outputs/data/train.jsonl）",
    )
    parser.add_argument(
        "--output",
        default="outputs/grpo_simple/grpo_train.jsonl",
        help="输出文件路径（默认: outputs/grpo_simple/grpo_train.jsonl）",
    )
    args = parser.parse_args()

    generate_data(args.input, args.output)


if __name__ == "__main__":
    main()
