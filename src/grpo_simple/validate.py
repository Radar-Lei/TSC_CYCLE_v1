#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简化版 GRPO 模型自动验证脚本。

自动加载训练产出模型，用测试数据推理，检查格式/约束/饱和度比例，输出 JSON 摘要。
"""

import argparse
import json
import os
import random
import statistics
import sys
from typing import Any, Dict, List, Optional, Tuple

import torch
from unsloth import FastLanguageModel

from src.grpo_simple.rewards import (
    calculate_target_green,
    extract_solution_from_completion,
)
from src.grpo_simple.train import setup_chat_template


def load_test_data(data_path: str, num_samples: int, seed: int) -> List[Dict[str, Any]]:
    """从训练数据中随机抽取测试样本。"""
    all_data = []
    with open(data_path, "r", encoding="utf-8") as f:
        for line in f:
            all_data.append(json.loads(line.strip()))

    random.seed(seed)
    if num_samples >= len(all_data):
        samples = all_data
    else:
        samples = random.sample(all_data, num_samples)

    print(f"[数据] 总样本数: {len(all_data)}, 测试样本数: {len(samples)}")
    return samples


def load_model(config: dict):
    """加载训练产出的 GRPO 模型。"""
    model_path = config["paths"].get("grpo_simple_output", "outputs/grpo_simple/model")
    print(f"[模型] 加载验证模型: {model_path}")

    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=model_path,
        max_seq_length=2048,
        dtype=torch.float16,
        load_in_4bit=False,
    )
    model.eval()

    tokenizer = setup_chat_template(tokenizer)
    return model, tokenizer


def generate_completions(
    model, tokenizer, samples: List[Dict[str, Any]], max_new_tokens: int = 1024
) -> List[str]:
    """对每个测试样本生成 completion。"""
    completions = []
    for i, sample in enumerate(samples):
        prompt = sample["prompt"]
        # apply_chat_template(tokenize=True) 可能返回 Encoding 对象而非 tensor，
        # 因此先渲染为字符串再手动 encode
        rendered = tokenizer.apply_chat_template(
            prompt, tokenize=False, add_generation_prompt=True
        )
        input_ids = tokenizer.encode(rendered, return_tensors="pt").to(model.device)
        prompt_len = input_ids.shape[-1]

        with torch.no_grad():
            outputs = model.generate(
                input_ids=input_ids,
                max_new_tokens=max_new_tokens,
                temperature=0.1,
                top_p=0.95,
                do_sample=True,
            )

        generated_ids = outputs[0][prompt_len:]
        # 1. skip_special_tokens=True 去掉 <|endoftext|> 等特殊 token（与训练时一致）
        # 2. 补回 generation prompt "<start_working_out>"
        decoded = tokenizer.decode(generated_ids, skip_special_tokens=True)
        completion = "<start_working_out>" + decoded
        completions.append(completion)

        if (i + 1) % 10 == 0 or i == 0:
            print(f"[推理] {i + 1}/{len(samples)} 完成")

    return completions


def extract_phase_waits(prompt: List[Dict[str, str]]) -> Optional[List[Dict[str, Any]]]:
    """从 prompt 中提取 phase_waits。"""
    import re

    prompt_content = prompt[-1].get("content", "")
    match = re.search(r'"phase_waits"\s*:\s*(\[.*?\])', prompt_content, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return None


def check_format(completion: str) -> Dict[str, Any]:
    """检查单条 completion 的格式正确性。"""
    checks = {
        "start_working_out": completion.count("<start_working_out>") == 1,
        "end_working_out": completion.count("<end_working_out>") == 1,
        "solution_open": completion.count("<SOLUTION>") == 1,
        "solution_close": completion.count("</SOLUTION>") == 1,
    }

    json_parseable = False
    solution = extract_solution_from_completion(completion)
    if solution is not None:
        json_parseable = True

    checks["json_parseable"] = json_parseable
    checks["all_pass"] = all(checks.values())
    return checks


def check_constraints(
    prompt: List[Dict[str, str]], completion: str
) -> Dict[str, Any]:
    """检查单条 completion 的约束满足情况。"""
    result = {
        "phase_order_correct": False,
        "all_final_integer": False,
        "all_in_range": False,
        "all_pass": False,
    }

    phase_waits = extract_phase_waits(prompt)
    solution = extract_solution_from_completion(completion)

    if phase_waits is None or solution is None:
        return result

    expected_ids = [p["phase_id"] for p in phase_waits]
    actual_ids = [s.get("phase_id") for s in solution if isinstance(s, dict)]

    result["phase_order_correct"] = expected_ids == actual_ids

    all_int = True
    all_range = True
    for phase_wait, sol_phase in zip(phase_waits, solution):
        if not isinstance(sol_phase, dict):
            all_int = False
            all_range = False
            break

        final = sol_phase.get("final")
        if not isinstance(final, int):
            all_int = False
            continue

        min_g = int(phase_wait["min_green"])
        max_g = int(phase_wait["max_green"])
        if not (min_g <= final <= max_g):
            all_range = False

    result["all_final_integer"] = all_int
    result["all_in_range"] = all_range
    result["all_pass"] = all(
        [result["phase_order_correct"], result["all_final_integer"], result["all_in_range"]]
    )
    return result


def check_saturation(
    prompt: List[Dict[str, str]], completion: str
) -> Optional[Dict[str, Any]]:
    """检查饱和度比例分配偏差。返回 None 表示无法计算。"""
    phase_waits = extract_phase_waits(prompt)
    solution = extract_solution_from_completion(completion)

    if phase_waits is None or solution is None or len(phase_waits) != len(solution):
        return None

    deviations = []
    for pw, sol in zip(phase_waits, solution):
        if not isinstance(sol, dict) or not isinstance(sol.get("final"), int):
            return None

        target = calculate_target_green(pw)
        range_width = max(int(pw["max_green"]) - int(pw["min_green"]), 1)
        deviation = abs(sol["final"] - target) / range_width
        deviations.append(deviation)

    return {
        "deviations": deviations,
        "mean": statistics.mean(deviations),
        "median": statistics.median(deviations),
        "max": max(deviations),
        "match_rate": sum(1 for d in deviations if d <= 0.1) / len(deviations),
    }


def run_validation(
    config: dict, num_samples: int, seed: int
) -> Dict[str, Any]:
    """运行完整验证流程。"""
    # 加载数据
    data_dir = config["paths"].get("grpo_simple_data_dir", "outputs/grpo_simple")
    data_path = os.path.join(data_dir, "grpo_train.jsonl")
    samples = load_test_data(data_path, num_samples, seed)

    # 加载模型
    model, tokenizer = load_model(config)

    # 生成 completions
    print("[推理] 开始生成...")
    completions = generate_completions(model, tokenizer, samples)

    # 检查
    format_results = []
    constraint_results = []
    saturation_results = []

    for sample, completion in zip(samples, completions):
        fmt = check_format(completion)
        format_results.append(fmt)

        cst = check_constraints(sample["prompt"], completion)
        constraint_results.append(cst)

        sat = check_saturation(sample["prompt"], completion)
        if sat is not None:
            saturation_results.append(sat)

    # 汇总
    total = len(samples)
    format_pass = sum(1 for r in format_results if r["all_pass"])
    constraint_pass = sum(1 for r in constraint_results if r["all_pass"])

    format_pass_rate = format_pass / total if total > 0 else 0
    constraint_pass_rate = constraint_pass / total if total > 0 else 0

    sat_deviations_all = []
    for s in saturation_results:
        sat_deviations_all.extend(s["deviations"])

    saturation_stats = {
        "mean": statistics.mean(sat_deviations_all) if sat_deviations_all else None,
        "median": statistics.median(sat_deviations_all) if sat_deviations_all else None,
        "max": max(sat_deviations_all) if sat_deviations_all else None,
    }
    saturation_match_rate = (
        sum(1 for d in sat_deviations_all if d <= 0.1) / len(sat_deviations_all)
        if sat_deviations_all
        else 0
    )

    overall = "PASS" if format_pass_rate >= 0.8 and constraint_pass_rate >= 0.8 else "FAIL"

    result = {
        "total_samples": total,
        "format_pass_rate": round(format_pass_rate, 4),
        "format_details": {
            "pass": format_pass,
            "fail": total - format_pass,
        },
        "constraint_pass_rate": round(constraint_pass_rate, 4),
        "constraint_details": {
            "pass": constraint_pass,
            "fail": total - constraint_pass,
            "phase_order_pass": sum(1 for r in constraint_results if r["phase_order_correct"]),
            "all_integer_pass": sum(1 for r in constraint_results if r["all_final_integer"]),
            "all_in_range_pass": sum(1 for r in constraint_results if r["all_in_range"]),
        },
        "saturation_match_rate": round(saturation_match_rate, 4),
        "saturation_deviation": {
            k: round(v, 4) if v is not None else None for k, v in saturation_stats.items()
        },
        "saturation_samples_evaluated": len(saturation_results),
        "overall": overall,
    }

    return result


def main():
    parser = argparse.ArgumentParser(description="Validate GRPO Simple trained model")
    parser.add_argument("--config", default="config/config.json", help="配置文件路径")
    parser.add_argument("--num-samples", type=int, default=100, help="测试样本数")
    parser.add_argument("--output", default=None, help="JSON 输出路径（默认 stdout）")
    parser.add_argument("--seed", type=int, default=42, help="随机种子")
    args = parser.parse_args()

    with open(args.config, "r", encoding="utf-8") as f:
        config = json.load(f)

    result = run_validation(config, args.num_samples, args.seed)

    output_json = json.dumps(result, indent=2, ensure_ascii=False)

    if args.output:
        os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output_json)
        print(f"\n[结果] 已保存到 {args.output}")
    else:
        print(f"\n{output_json}")

    # 打印摘要
    print(f"\n{'=' * 50}")
    print(f"[验证摘要]")
    print(f"  样本数:         {result['total_samples']}")
    print(f"  格式通过率:     {result['format_pass_rate']:.1%}")
    print(f"  约束通过率:     {result['constraint_pass_rate']:.1%}")
    print(f"  饱和度匹配率:   {result['saturation_match_rate']:.1%}")
    if result["saturation_deviation"]["mean"] is not None:
        print(f"  饱和度偏差均值: {result['saturation_deviation']['mean']:.4f}")
    print(f"  总体结论:       {result['overall']}")
    print(f"{'=' * 50}")

    sys.exit(0 if result["overall"] == "PASS" else 1)


if __name__ == "__main__":
    main()
