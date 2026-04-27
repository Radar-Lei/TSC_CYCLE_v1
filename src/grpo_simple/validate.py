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

from src.grpo_simple.rewards import (
    calculate_target_green,
    extract_solution_from_completion,
)

DETAIL_SCHEMA = [
    "constraint_status",
    "failure_bucket",
    "final",
    "is_clip_sensitive",
    "is_match",
    "match_threshold_hit",
    "max_green",
    "min_green",
    "normalized_deviation",
    "phase_id",
    "pred_saturation",
    "raw_target",
    "sample_id",
    "target_green",
]


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
    from unsloth import FastLanguageModel
    from src.grpo_simple.train import setup_chat_template

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
    phase_details = []
    for pw, sol in zip(phase_waits, solution):
        if not isinstance(sol, dict) or not isinstance(sol.get("final"), int):
            return None

        min_green = int(pw["min_green"])
        max_green = int(pw["max_green"])
        pred_saturation = float(pw.get("pred_saturation", 0.0))
        raw_target = round(max_green * max(pred_saturation, 0.0))
        target_green = calculate_target_green(pw)
        final = sol["final"]
        range_width = max(max_green - min_green, 1)
        deviation = abs(final - target_green) / range_width
        is_match = deviation <= 0.1
        deviations.append(deviation)
        phase_details.append(
            {
                "phase_id": pw.get("phase_id"),
                "pred_saturation": pred_saturation,
                "min_green": min_green,
                "max_green": max_green,
                "raw_target": raw_target,
                "target_green": target_green,
                "final": final,
                "normalized_deviation": deviation,
                "is_match": is_match,
                "is_clip_sensitive": target_green in (min_green, max_green),
            }
        )

    return {
        "deviations": deviations,
        "phase_details": phase_details,
        "mean": statistics.mean(deviations),
        "median": statistics.median(deviations),
        "max": max(deviations),
        "match_rate": sum(1 for d in deviations if d <= 0.1) / len(deviations),
    }


def _round_metric(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    return round(value, 4)


def _make_phase_detail(
    sample_id: str,
    phase_wait: Optional[Dict[str, Any]],
    solution_phase: Optional[Dict[str, Any]],
    failure_bucket: str,
    constraint_status: str,
) -> Dict[str, Any]:
    phase_wait = phase_wait or {}
    solution_phase = solution_phase if isinstance(solution_phase, dict) else {}

    min_green = int(phase_wait["min_green"]) if "min_green" in phase_wait else None
    max_green = int(phase_wait["max_green"]) if "max_green" in phase_wait else None
    pred_saturation = (
        float(phase_wait.get("pred_saturation", 0.0)) if phase_wait else None
    )
    raw_target = round(max_green * max(pred_saturation, 0.0)) if max_green is not None and pred_saturation is not None else None
    target_green = calculate_target_green(phase_wait) if phase_wait else None
    final = solution_phase.get("final")
    normalized_deviation = None
    if (
        target_green is not None
        and isinstance(final, int)
        and min_green is not None
        and max_green is not None
    ):
        range_width = max(max_green - min_green, 1)
        normalized_deviation = abs(final - target_green) / range_width

    match_threshold_hit = normalized_deviation is not None and normalized_deviation <= 0.1
    is_clip_sensitive = (
        target_green in (min_green, max_green)
        if target_green is not None and min_green is not None and max_green is not None
        else False
    )

    return {
        "sample_id": sample_id,
        "phase_id": phase_wait.get("phase_id", solution_phase.get("phase_id")),
        "pred_saturation": pred_saturation,
        "min_green": min_green,
        "max_green": max_green,
        "raw_target": raw_target,
        "target_green": target_green,
        "final": final,
        "normalized_deviation": normalized_deviation,
        "match_threshold_hit": match_threshold_hit,
        "is_match": bool(match_threshold_hit),
        "is_clip_sensitive": is_clip_sensitive,
        "constraint_status": constraint_status,
        "failure_bucket": failure_bucket,
    }


def _build_root_cause_summary(
    samples: List[Dict[str, Any]],
    completions: List[str],
    format_results: List[Dict[str, Any]],
    constraint_results: List[Dict[str, Any]],
    saturation_results: List[Optional[Dict[str, Any]]],
    seed: int,
    requested_samples: int,
    sample_mode: str,
) -> Dict[str, Any]:
    detail_records = []
    failure_examples = {
        "format_failure": [],
        "constraint_failure": [],
        "saturation_mismatch": [],
        "large_deviation": [],
        "clip_sensitive": [],
    }
    failure_buckets = {
        "format_failure": 0,
        "constraint_failure": 0,
        "saturation_mismatch": 0,
        "saturation_match": 0,
    }

    for sample, completion, fmt, cst, sat in zip(
        samples, completions, format_results, constraint_results, saturation_results
    ):
        sample_id = sample.get("sample_id") or f"sample-{len(detail_records)}"
        phase_waits = extract_phase_waits(sample["prompt"]) or []
        solution = extract_solution_from_completion(completion) or []
        solution_by_phase = {
            item.get("phase_id"): item
            for item in solution
            if isinstance(item, dict) and item.get("phase_id") is not None
        }

        if not fmt["all_pass"]:
            failure_buckets["format_failure"] += 1
            for phase_wait in phase_waits[:1] or [{}]:
                detail = _make_phase_detail(
                    sample_id,
                    phase_wait,
                    solution_by_phase.get(phase_wait.get("phase_id"), {}),
                    "format_failure",
                    "format_failure",
                )
                detail_records.append(detail)
                failure_examples["format_failure"].append({
                    "sample_id": sample_id,
                    "phase_id": detail["phase_id"],
                })
            continue

        if not cst["all_pass"] or sat is None:
            failure_buckets["constraint_failure"] += 1
            for phase_wait in phase_waits[:1] or [{}]:
                detail = _make_phase_detail(
                    sample_id,
                    phase_wait,
                    solution_by_phase.get(phase_wait.get("phase_id"), {}),
                    "constraint_failure",
                    "constraint_failure",
                )
                detail_records.append(detail)
                failure_examples["constraint_failure"].append({
                    "sample_id": sample_id,
                    "phase_id": detail["phase_id"],
                })
            continue

        failure_buckets["saturation_mismatch"] += sum(
            1 for phase in sat["phase_details"] if not phase["is_match"]
        )
        failure_buckets["saturation_match"] += sum(
            1 for phase in sat["phase_details"] if phase["is_match"]
        )

        for phase in sat["phase_details"]:
            failure_bucket = "saturation_match" if phase["is_match"] else "saturation_mismatch"
            detail = {
                "sample_id": sample_id,
                "phase_id": phase["phase_id"],
                "pred_saturation": phase["pred_saturation"],
                "min_green": phase["min_green"],
                "max_green": phase["max_green"],
                "raw_target": phase["raw_target"],
                "target_green": phase["target_green"],
                "final": phase["final"],
                "normalized_deviation": phase["normalized_deviation"],
                "match_threshold_hit": phase["is_match"],
                "is_match": phase["is_match"],
                "is_clip_sensitive": phase["is_clip_sensitive"],
                "constraint_status": "constraint_pass",
                "failure_bucket": failure_bucket,
            }
            detail_records.append(detail)
            if failure_bucket == "saturation_mismatch":
                failure_examples["saturation_mismatch"].append({
                    "sample_id": sample_id,
                    "phase_id": phase["phase_id"],
                    "normalized_deviation": _round_metric(phase["normalized_deviation"]),
                })
            if phase["normalized_deviation"] is not None and phase["normalized_deviation"] > 0.1:
                failure_examples["large_deviation"].append({
                    "sample_id": sample_id,
                    "phase_id": phase["phase_id"],
                    "normalized_deviation": _round_metric(phase["normalized_deviation"]),
                })
            if phase["is_clip_sensitive"]:
                failure_examples["clip_sensitive"].append({
                    "sample_id": sample_id,
                    "phase_id": phase["phase_id"],
                    "target_green": phase["target_green"],
                })

    analysis_summary = {
        "near_threshold_phase_count": sum(
            1
            for detail in detail_records
            if detail["normalized_deviation"] is not None and 0.08 <= detail["normalized_deviation"] <= 0.15
        ),
        "clip_sensitive_phase_count": sum(1 for detail in detail_records if detail["is_clip_sensitive"]),
        "clip_sensitive_match_count": sum(
            1 for detail in detail_records if detail["is_clip_sensitive"] and detail["is_match"]
        ),
    }

    return {
        "detail_schema": sorted(DETAIL_SCHEMA),
        "details_preview": detail_records,
        "failure_buckets": failure_buckets,
        "failure_examples": failure_examples,
        "analysis_summary": analysis_summary,
        "saturation_evaluable": sum(
            1
            for cst, sat in zip(constraint_results, saturation_results)
            if cst["all_pass"] and sat is not None
        ),
        "sample_manifest": {
            "seed": seed,
            "requested_samples": requested_samples,
            "manifest_size": len(samples),
            "sample_mode": sample_mode,
            "sample_ids": [sample.get("sample_id") for sample in samples],
        },
    }


def run_validation(
    config: dict, num_samples: int, seed: int
) -> Dict[str, Any]:
    """运行完整验证流程。"""
    data_dir = config["paths"].get("grpo_simple_data_dir", "outputs/grpo_simple")
    data_path = os.path.join(data_dir, "grpo_train.jsonl")
    samples = load_test_data(data_path, num_samples, seed)

    model, tokenizer = load_model(config)

    print("[推理] 开始生成...")
    completions = generate_completions(model, tokenizer, samples)

    format_results = []
    constraint_results = []
    saturation_results = []

    for sample, completion in zip(samples, completions):
        fmt = check_format(completion)
        format_results.append(fmt)

        cst = check_constraints(sample["prompt"], completion)
        constraint_results.append(cst)

        saturation_results.append(check_saturation(sample["prompt"], completion))

    total = len(samples)
    format_pass = sum(1 for r in format_results if r["all_pass"])
    constraint_pass = sum(1 for r in constraint_results if r["all_pass"])

    format_pass_rate = format_pass / total if total > 0 else 0
    constraint_pass_rate = constraint_pass / total if total > 0 else 0

    sat_deviations_all = []
    evaluable_saturation_results = [s for s in saturation_results if s is not None]
    for saturation_result in evaluable_saturation_results:
        sat_deviations_all.extend(saturation_result["deviations"])

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
    root_cause = _build_root_cause_summary(
        samples=samples,
        completions=completions,
        format_results=format_results,
        constraint_results=constraint_results,
        saturation_results=saturation_results,
        seed=seed,
        requested_samples=num_samples,
        sample_mode="random",
    )

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
        "saturation_samples_evaluated": root_cause["saturation_evaluable"],
        "overall": overall,
        "sampled_cases": total,
        "sample_manifest": root_cause["sample_manifest"],
        "root_cause": {
            "detail_schema": root_cause["detail_schema"],
            "details_preview": root_cause["details_preview"],
            "failure_buckets": root_cause["failure_buckets"],
            "failure_examples": root_cause["failure_examples"],
            "analysis_summary": root_cause["analysis_summary"],
            "saturation_evaluable": root_cause["saturation_evaluable"],
        },
    }

    return result


def main():
    parser = argparse.ArgumentParser(description="Validate GRPO Simple trained model")
    parser.add_argument("--config", default="config/config_8b.json", help="配置文件路径")
    parser.add_argument("--num-samples", type=int, default=100, help="测试样本数")
    parser.add_argument("--output", default=None, help="JSON 输出路径（默认 stdout）")
    parser.add_argument("--sample-manifest-out", default=None, help="sample manifest 输出路径")
    parser.add_argument("--details-output", default=None, help="detail records 输出路径")
    parser.add_argument("--failure-examples-out", default=None, help="failure examples 输出路径")
    parser.add_argument("--seed", type=int, default=42, help="随机种子")
    parser.add_argument("--sample-mode", default="random", help="抽样模式标记")
    args = parser.parse_args()

    with open(args.config, "r", encoding="utf-8") as f:
        config = json.load(f)

    result = run_validation(config, args.num_samples, args.seed)
    result["sample_manifest"]["sample_mode"] = args.sample_mode

    output_json = json.dumps(result, indent=2, ensure_ascii=False)

    if args.output:
        os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output_json)
        print(f"\n[结果] 已保存到 {args.output}")
    else:
        print(f"\n{output_json}")

    if args.sample_manifest_out:
        os.makedirs(os.path.dirname(args.sample_manifest_out) or ".", exist_ok=True)
        with open(args.sample_manifest_out, "w", encoding="utf-8") as f:
            json.dump(result["sample_manifest"], f, indent=2, ensure_ascii=False)

    if args.details_output:
        os.makedirs(os.path.dirname(args.details_output) or ".", exist_ok=True)
        with open(args.details_output, "w", encoding="utf-8") as f:
            json.dump(result["root_cause"]["details_preview"], f, indent=2, ensure_ascii=False)

    if args.failure_examples_out:
        os.makedirs(os.path.dirname(args.failure_examples_out) or ".", exist_ok=True)
        with open(args.failure_examples_out, "w", encoding="utf-8") as f:
            json.dump(result["root_cause"]["failure_examples"], f, indent=2, ensure_ascii=False)

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
