#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简化版 GRPO 模型验证脚本（HuggingFace transformers 版本）。

绕过 unsloth/triton，直接用 transformers AutoModelForCausalLM 推理，
避免 CPU offload 引发的 CUDA illegal memory access。
"""

import argparse
import json
import os
import random
import statistics
import sys
from typing import Any, Dict, List, Optional

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

from src.grpo_simple.rewards import (
    calculate_target_green,
    extract_solution_from_completion,
)
from src.grpo_simple.train import setup_chat_template


def load_test_data(data_path: str, num_samples: int, seed: int) -> List[Dict[str, Any]]:
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
    model_path = config["paths"].get("grpo_simple_output", "outputs/grpo_simple/model")
    load_in_4bit = config.get("training", {}).get("grpo_simple", {}).get("model", {}).get("load_in_4bit", False)
    print(f"[模型] 加载验证模型 (transformers): {model_path}")
    if load_in_4bit:
        print("[模型] 使用 BnB 4-bit 量化加载")

    tokenizer = AutoTokenizer.from_pretrained(model_path)

    load_kwargs = {
        "torch_dtype": torch.float16,
        "low_cpu_mem_usage": True,
    }
    if load_in_4bit:
        from transformers import BitsAndBytesConfig
        load_kwargs["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_compute_dtype=torch.float16,
        )
        load_kwargs["device_map"] = "auto"
    else:
        load_kwargs["device_map"] = {"": 0}

    model = AutoModelForCausalLM.from_pretrained(model_path, **load_kwargs)
    model.eval()

    tokenizer = setup_chat_template(tokenizer)
    return model, tokenizer


def generate_completions(model, tokenizer, samples, max_new_tokens=1024):
    completions = []
    for i, sample in enumerate(samples):
        prompt = sample["prompt"]
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
                pad_token_id=tokenizer.eos_token_id,
            )

        generated_ids = outputs[0][prompt_len:]
        decoded = tokenizer.decode(generated_ids, skip_special_tokens=True)
        completion = "<start_working_out>" + decoded
        completions.append(completion)

        if (i + 1) % 50 == 0 or i == 0:
            print(f"[推理] {i + 1}/{len(samples)} 完成", flush=True)

    return completions


def extract_phase_waits(prompt):
    import re
    prompt_content = prompt[-1].get("content", "")
    match = re.search(r'"phase_waits"\s*:\s*(\[.*?\])', prompt_content, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return None


def check_format(completion):
    checks = {
        "start_working_out": completion.count("<start_working_out>") == 1,
        "end_working_out": completion.count("<end_working_out>") == 1,
        "solution_open": completion.count("<SOLUTION>") == 1,
        "solution_close": completion.count("</SOLUTION>") == 1,
    }
    json_parseable = extract_solution_from_completion(completion) is not None
    checks["json_parseable"] = json_parseable
    checks["all_pass"] = all(checks.values())
    return checks


def check_constraints(prompt, completion):
    result = {
        "phase_order_correct": False,
        "all_final_integer": False,
        "all_in_range": False,
        "all_pass": False,
        "violations": [],
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
    for pw, sp in zip(phase_waits, solution):
        if not isinstance(sp, dict):
            all_int = False
            all_range = False
            continue
        final = sp.get("final")
        if not isinstance(final, int):
            all_int = False
            continue
        min_g = int(pw["min_green"])
        max_g = int(pw["max_green"])
        if not (min_g <= final <= max_g):
            all_range = False
            result["violations"].append({
                "phase_id": pw["phase_id"],
                "min_green": min_g,
                "max_green": max_g,
                "final": final,
            })

    result["all_final_integer"] = all_int
    result["all_in_range"] = all_range
    result["all_pass"] = all([result["phase_order_correct"], all_int, all_range])
    return result


def check_saturation(prompt, completion):
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
        deviations.append(abs(sol["final"] - target) / range_width)

    return {"deviations": deviations}


def run_validation(config, num_samples, seed):
    data_dir = config["paths"].get("grpo_simple_data_dir", "outputs/grpo_simple")
    data_path = os.path.join(data_dir, "grpo_train.jsonl")
    samples = load_test_data(data_path, num_samples, seed)

    model, tokenizer = load_model(config)

    print("[推理] 开始生成...", flush=True)
    completions = generate_completions(model, tokenizer, samples)

    format_results = []
    constraint_results = []
    saturation_deviations = []
    all_violations = []

    for sample, completion in zip(samples, completions):
        fmt = check_format(completion)
        format_results.append(fmt)
        cst = check_constraints(sample["prompt"], completion)
        constraint_results.append(cst)
        if cst["violations"]:
            all_violations.extend(cst["violations"])
        sat = check_saturation(sample["prompt"], completion)
        if sat is not None:
            saturation_deviations.extend(sat["deviations"])

    total = len(samples)
    format_pass = sum(1 for r in format_results if r["all_pass"])
    constraint_pass = sum(1 for r in constraint_results if r["all_pass"])

    sat_match = (
        sum(1 for d in saturation_deviations if d <= 0.1) / len(saturation_deviations)
        if saturation_deviations else 0
    )

    overall = "PASS" if format_pass / total >= 0.95 and constraint_pass / total >= 0.95 else "FAIL"

    return {
        "total_samples": total,
        "format_pass_rate": round(format_pass / total, 4),
        "format_details": {"pass": format_pass, "fail": total - format_pass},
        "constraint_pass_rate": round(constraint_pass / total, 4),
        "constraint_details": {
            "pass": constraint_pass,
            "fail": total - constraint_pass,
            "phase_order_pass": sum(1 for r in constraint_results if r["phase_order_correct"]),
            "all_integer_pass": sum(1 for r in constraint_results if r["all_final_integer"]),
            "all_in_range_pass": sum(1 for r in constraint_results if r["all_in_range"]),
        },
        "saturation_match_rate": round(sat_match, 4),
        "saturation_deviation": {
            "mean": round(statistics.mean(saturation_deviations), 4) if saturation_deviations else None,
            "median": round(statistics.median(saturation_deviations), 4) if saturation_deviations else None,
            "max": round(max(saturation_deviations), 4) if saturation_deviations else None,
        },
        "saturation_samples_evaluated": len(saturation_deviations) // (len(samples[0].get("prompt", [])) if samples else 1),
        "violation_count": len(all_violations),
        "violation_examples": all_violations[:10],
        "overall": overall,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/config.json")
    parser.add_argument("--num-samples", type=int, default=2000)
    parser.add_argument("--output", default=None)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    with open(args.config) as f:
        config = json.load(f)

    result = run_validation(config, args.num_samples, args.seed)

    output_json = json.dumps(result, indent=2, ensure_ascii=False)
    if args.output:
        os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
        with open(args.output, "w") as f:
            f.write(output_json)
        print(f"\n[结果] 已保存到 {args.output}")
    else:
        print(f"\n{output_json}")

    print(f"\n{'=' * 50}")
    print("[验证摘要]")
    print(f"  样本数:         {result['total_samples']}")
    print(f"  格式通过率:     {result['format_pass_rate']:.2%}")
    print(f"  约束通过率:     {result['constraint_pass_rate']:.2%}")
    print(f"    - 顺序正确:   {result['constraint_details']['phase_order_pass']}/{result['total_samples']}")
    print(f"    - 整数:       {result['constraint_details']['all_integer_pass']}/{result['total_samples']}")
    print(f"    - 范围内:     {result['constraint_details']['all_in_range_pass']}/{result['total_samples']}")
    print(f"  违规相位次数:   {result['violation_count']}")
    print(f"  饱和度匹配率:   {result['saturation_match_rate']:.2%}")
    if result["saturation_deviation"]["mean"] is not None:
        print(f"  饱和度偏差均值: {result['saturation_deviation']['mean']:.4f}")
    print(f"  总体结论:       {result['overall']}")
    print(f"{'=' * 50}")

    sys.exit(0 if result["overall"] == "PASS" else 1)


if __name__ == "__main__":
    main()
