#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简化版 GRPO reward 函数。

设计目标：
1. 保持与 SFT 阶段一致的输出标签与 solution JSON 协议
2. 继续校验 phase 顺序、整数 final 和最小/最大绿约束
3. 用饱和度比例分配的目标绿灯时长替代 SUMO 仿真 reward
"""

import json
import re
from typing import Any, Dict, List, Optional


_config: Optional[Dict[str, Any]] = None

MATCH_FORMAT = re.compile(
    r"<end_working_out>.*?<SOLUTION>(.+?)</SOLUTION>\s*$",
    flags=re.DOTALL,
)


def init_rewards(config_path: str):
    """从配置文件加载简化版 reward 参数。"""
    global _config

    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)
    _config = config["training"]["grpo_simple"]["reward"]


def _ensure_config() -> Dict[str, Any]:
    if _config is None:
        raise RuntimeError("reward 未初始化，请先调用 init_rewards(config_path)")
    return _config


def _extract_phase_waits(prompt: List[Dict[str, str]]) -> Optional[List[Dict[str, Any]]]:
    if not prompt:
        return None

    prompt_content = prompt[-1].get("content", "")
    phase_waits_match = re.search(
        r'"phase_waits"\s*:\s*(\[.*?\])',
        prompt_content,
        re.DOTALL,
    )
    if not phase_waits_match:
        return None

    try:
        phase_waits = json.loads(phase_waits_match.group(1))
    except json.JSONDecodeError:
        return None

    if not isinstance(phase_waits, list):
        return None
    return phase_waits


def extract_solution_from_completion(completion_text: str) -> Optional[List[Dict[str, Any]]]:
    match = MATCH_FORMAT.search(completion_text)
    if not match:
        return None

    try:
        solution = json.loads(match.group(1))
    except json.JSONDecodeError:
        return None

    if not isinstance(solution, list):
        return None
    return solution


def calculate_target_green(phase_wait: Dict[str, Any]) -> int:
    """按用户要求计算目标绿灯时长。

    规则：
    - 基线公式：round(max_green * pred_saturation)
    - 再裁剪到 [min_green, max_green]
    - 负饱和度按 0 处理，大于 1 的情况允许被裁剪到 max_green
    """
    min_green = int(phase_wait["min_green"])
    max_green = int(phase_wait["max_green"])
    pred_saturation = max(0.0, float(phase_wait.get("pred_saturation", 0.0)))

    raw_target = round(max_green * pred_saturation)
    return min(max(raw_target, min_green), max_green)


def match_format_exactly(completions, **kwargs) -> List[float]:
    config = _ensure_config()
    scores = []
    for completion in completions:
        response = completion[0]["content"]
        scores.append(config["format_exact_score"] if MATCH_FORMAT.search(response) else 0.0)
    return scores


def match_format_approximately(completions, **kwargs) -> List[float]:
    config = _ensure_config()
    tag_present = config["format_approx_scores"]["tag_present"]
    tag_absent = config["format_approx_scores"]["tag_absent"]

    scores = []
    for completion in completions:
        response = completion[0]["content"]
        score = 0.0
        score += tag_present if response.count("<end_working_out>") == 1 else tag_absent
        score += tag_present if response.count("<SOLUTION>") == 1 else tag_absent
        score += tag_present if response.count("</SOLUTION>") == 1 else tag_absent
        scores.append(score)
    return scores


def check_constraints(prompts, completions, **kwargs) -> List[float]:
    config = _ensure_config()
    phase_order_weight = config["constraint_phase_order_weight"]
    green_range_weight = config["constraint_green_range_weight"]

    scores = []
    for prompt, completion in zip(prompts, completions):
        solution = extract_solution_from_completion(completion[0]["content"])
        phase_waits = _extract_phase_waits(prompt)
        if solution is None or phase_waits is None:
            scores.append(-2.0)
            continue

        expected_phase_ids = [phase["phase_id"] for phase in phase_waits]
        total_phases = len(expected_phase_ids)
        if total_phases == 0:
            scores.append(0.0)
            continue

        output_phase_ids = [phase.get("phase_id") for phase in solution if isinstance(phase, dict)]
        if len(output_phase_ids) != total_phases:
            phase_order_score = 0.0
        else:
            correct_positions = sum(
                1 for expected, actual in zip(expected_phase_ids, output_phase_ids)
                if expected == actual
            )
            phase_order_score = (correct_positions / total_phases) * phase_order_weight

        satisfying_count = 0
        for phase in solution:
            if not isinstance(phase, dict):
                continue

            phase_id = phase.get("phase_id")
            final = phase.get("final")
            constraint = next((item for item in phase_waits if item["phase_id"] == phase_id), None)
            if constraint is None:
                continue

            min_green = int(constraint["min_green"])
            max_green = int(constraint["max_green"])
            if isinstance(final, int) and min_green <= final <= max_green:
                satisfying_count += 1

        green_range_score = (satisfying_count / max(len(solution), 1)) * green_range_weight
        scores.append(phase_order_score + green_range_score)

    return scores


def saturation_proportional_reward(prompts, completions, **kwargs) -> List[float]:
    """根据 completion 与目标绿灯时长的接近程度打分。"""
    config = _ensure_config()
    max_score = config["saturation_target_score"]
    invalid_score = config.get("invalid_completion_score", 0.0)

    scores = []
    for prompt, completion in zip(prompts, completions):
        solution = extract_solution_from_completion(completion[0]["content"])
        phase_waits = _extract_phase_waits(prompt)
        if solution is None or phase_waits is None or len(solution) != len(phase_waits):
            scores.append(invalid_score)
            continue

        valid = True
        closeness_scores = []

        for expected, actual in zip(phase_waits, solution):
            if not isinstance(actual, dict):
                valid = False
                break

            expected_phase_id = expected["phase_id"]
            actual_phase_id = actual.get("phase_id")
            final = actual.get("final")

            if actual_phase_id != expected_phase_id or not isinstance(final, int):
                valid = False
                break

            min_green = int(expected["min_green"])
            max_green = int(expected["max_green"])
            if not (min_green <= final <= max_green):
                valid = False
                break

            target = calculate_target_green(expected)
            range_width = max(max_green - min_green, 1)
            closeness = max(0.0, 1.0 - abs(final - target) / range_width)
            closeness_scores.append(closeness)

        if not valid or not closeness_scores:
            scores.append(invalid_score)
            continue

        scores.append(sum(closeness_scores) / len(closeness_scores) * max_score)

    return scores


def think_length_reward(completions, **kwargs) -> List[float]:
    config = _ensure_config()
    min_tokens = config["think_min_tokens"]
    max_tokens = config["think_max_tokens"]
    penalty = config["think_penalty"]
    bonus = config.get("think_bonus", 0.0)

    scores = []
    for completion in completions:
        response = completion[0]["content"]
        think_end_pos = response.find("<end_working_out>")
        if think_end_pos == -1:
            scores.append(penalty)
            continue

        think_content = response[:think_end_pos]
        think_tokens = len(think_content) / 2

        if think_tokens < min_tokens:
            score = penalty * (1 - think_tokens / min_tokens)
        elif think_tokens > max_tokens:
            score = penalty * (think_tokens / max_tokens - 1)
        else:
            score = bonus

        scores.append(score)

    return scores
