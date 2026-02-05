"""格式奖励函数

评估模型输出是否符合预期格式: <think>...</think>[{phase_id, final}...]

参考 Qwen3_(4B)_GRPO.ipynb 的多级奖励策略:
- 完全匹配: +3.0
- 部分匹配: 按符号计分 (+/-0.5)
- 相位有效性: 检查 phase_id 和 final 范围
"""

import re
import json
from typing import List, Dict, Optional, Any


# 复用 format_validator 的正则表达式
THINK_PATTERN = re.compile(r"<think>(.*?)</think>", re.DOTALL)
JSON_PATTERN = re.compile(r"\[.*?\]", re.DOTALL)


def extract_json_from_completion(text: str) -> Optional[List[Dict]]:
    """从模型输出中提取 JSON 数组

    Args:
        text: 模型输出文本

    Returns:
        解析后的 JSON 数组,失败返回 None
    """
    match = JSON_PATTERN.search(text)
    if not match:
        return None

    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


def match_format_exactly(completions: List[List[Dict]], **kwargs) -> List[float]:
    """格式完全匹配奖励

    检查格式: <think>...</think>[{phase_id, final}...]
    - 完全匹配: +3.0
    - 否则: 0.0

    Args:
        completions: List[List[Dict]] - 每个 completion 是 messages 列表
            例: [[{"role": "assistant", "content": "<think>...</think>[...]"}]]
        **kwargs: 兼容 TRL GRPOTrainer reward_funcs 签名

    Returns:
        奖励分数列表,与 completions 长度一致
    """
    rewards = []

    for completion in completions:
        # 提取 assistant 消息内容
        content = ""
        for msg in completion:
            if msg.get("role") == "assistant":
                content = msg.get("content", "")
                break

        # 检查完整格式
        has_think = THINK_PATTERN.search(content) is not None
        think_match = THINK_PATTERN.search(content)
        has_valid_think = think_match is not None and len(think_match.group(1).strip()) >= 10

        json_array = extract_json_from_completion(content)
        has_valid_json = json_array is not None and len(json_array) > 0

        # 检查 JSON 结构
        valid_structure = False
        if has_valid_json:
            valid_structure = True
            for item in json_array:
                if not isinstance(item, dict):
                    valid_structure = False
                    break
                if "phase_id" not in item or "final" not in item:
                    valid_structure = False
                    break
                if not isinstance(item["phase_id"], int):
                    valid_structure = False
                    break
                if not isinstance(item["final"], (int, float)):
                    valid_structure = False
                    break

        # 完全匹配: think 内容充足 + JSON 结构正确
        if has_valid_think and valid_structure:
            rewards.append(3.0)
        else:
            rewards.append(0.0)

    return rewards


def match_format_approximately(completions: List[List[Dict]], **kwargs) -> List[float]:
    """格式部分匹配奖励

    按符号计分:
    - </think> 出现 1 次: +0.5, 否则 -1.0
    - [ 出现 1 次: +0.5, 否则 -1.0
    - ] 出现 1 次: +0.5, 否则 -1.0
    - "phase_id" 出现至少 1 次: +0.5, 否则 -1.0
    - "final" 出现至少 1 次: +0.5, 否则 -1.0

    Args:
        completions: List[List[Dict]] - 每个 completion 是 messages 列表
        **kwargs: 兼容 TRL GRPOTrainer reward_funcs 签名

    Returns:
        奖励分数列表,范围 -5.0 到 +2.5
    """
    rewards = []

    for completion in completions:
        # 提取 assistant 消息内容
        content = ""
        for msg in completion:
            if msg.get("role") == "assistant":
                content = msg.get("content", "")
                break

        score = 0.0

        # 检查 </think>
        think_count = content.count("</think>")
        score += 0.5 if think_count == 1 else -1.0

        # 检查 [
        bracket_open_count = content.count("[")
        score += 0.5 if bracket_open_count == 1 else -1.0

        # 检查 ]
        bracket_close_count = content.count("]")
        score += 0.5 if bracket_close_count == 1 else -1.0

        # 检查 "phase_id"
        has_phase_id = '"phase_id"' in content or "'phase_id'" in content
        score += 0.5 if has_phase_id else -1.0

        # 检查 "final"
        has_final = '"final"' in content or "'final'" in content
        score += 0.5 if has_final else -1.0

        rewards.append(score)

    return rewards


def check_phase_validity(
    completions: List[List[Dict]],
    phase_config: Dict[int, Dict[str, Any]],
    **kwargs
) -> List[float]:
    """相位有效性检查

    检查:
    - phase_id 是否存在于 phase_config 中
    - final 是否在 min_green 到 max_green 范围内

    Args:
        completions: List[List[Dict]] - 每个 completion 是 messages 列表
        phase_config: Dict[int, Dict] - 相位配置
            例: {0: {"min_green": 10, "max_green": 60}, ...}
        **kwargs: 兼容 TRL GRPOTrainer reward_funcs 签名

    Returns:
        奖励分数列表:
        - 全部有效: +1.0
        - 任一无效: -2.0
        - 无法解析: 0.0
    """
    rewards = []

    for completion in completions:
        # 提取 assistant 消息内容
        content = ""
        for msg in completion:
            if msg.get("role") == "assistant":
                content = msg.get("content", "")
                break

        # 提取 JSON 数组
        json_array = extract_json_from_completion(content)
        if json_array is None:
            rewards.append(0.0)
            continue

        # 检查每个相位配置
        all_valid = True
        for item in json_array:
            if not isinstance(item, dict):
                all_valid = False
                break

            phase_id = item.get("phase_id")
            final = item.get("final")

            # 检查 phase_id 是否存在
            if phase_id not in phase_config:
                all_valid = False
                break

            # 检查 final 是否在范围内
            phase_info = phase_config[phase_id]
            min_green = phase_info.get("min_green", 5)
            max_green = phase_info.get("max_green", 120)

            if not isinstance(final, (int, float)):
                all_valid = False
                break

            if not (min_green <= final <= max_green):
                all_valid = False
                break

        # 返回奖励
        if all_valid:
            rewards.append(1.0)
        else:
            rewards.append(-2.0)

    return rewards


if __name__ == "__main__":
    # 自测试
    print("Testing format_reward...")

    # 测试完全匹配
    print("\n1. Testing match_format_exactly...")
    completions = [[{
        "role": "assistant",
        "content": "<think>分析交通流量,相位 1 需要更长绿灯时间</think>[{\"phase_id\": 1, \"final\": 40}]"
    }]]
    scores = match_format_exactly(completions)
    assert scores[0] == 3.0, f"Expected 3.0, got {scores[0]}"
    print(f"  ✓ Perfect format: {scores[0]}")

    # 测试不完整格式
    completions = [[{
        "role": "assistant",
        "content": "</think>[{\"phase_id\": 1}]"
    }]]
    scores = match_format_exactly(completions)
    assert scores[0] == 0.0, f"Expected 0.0 for incomplete format, got {scores[0]}"
    print(f"  ✓ Incomplete format: {scores[0]}")

    # 测试部分匹配
    print("\n2. Testing match_format_approximately...")
    completions = [[{
        "role": "assistant",
        "content": "</think>[{\"phase_id\": 1, \"final\": 40}]"
    }]]
    scores = match_format_approximately(completions)
    print(f"  ✓ Partial match score: {scores[0]} (expected 2.5)")
    assert scores[0] == 2.5, f"Expected 2.5, got {scores[0]}"

    # 测试完全缺失
    completions = [[{
        "role": "assistant",
        "content": "just some random text"
    }]]
    scores = match_format_approximately(completions)
    print(f"  ✓ No match score: {scores[0]} (expected -5.0)")
    assert scores[0] == -5.0, f"Expected -5.0, got {scores[0]}"

    # 测试相位有效性
    print("\n3. Testing check_phase_validity...")
    phase_config = {
        0: {"min_green": 10, "max_green": 60},
        1: {"min_green": 10, "max_green": 60},
    }

    # 有效配置
    completions = [[{
        "role": "assistant",
        "content": "<think>test</think>[{\"phase_id\": 0, \"final\": 30}, {\"phase_id\": 1, \"final\": 40}]"
    }]]
    scores = check_phase_validity(completions, phase_config)
    assert scores[0] == 1.0, f"Expected 1.0 for valid config, got {scores[0]}"
    print(f"  ✓ Valid phase config: {scores[0]}")

    # 无效 phase_id
    completions = [[{
        "role": "assistant",
        "content": "<think>test</think>[{\"phase_id\": 99, \"final\": 30}]"
    }]]
    scores = check_phase_validity(completions, phase_config)
    assert scores[0] == -2.0, f"Expected -2.0 for invalid phase_id, got {scores[0]}"
    print(f"  ✓ Invalid phase_id: {scores[0]}")

    # 超出范围的 final
    completions = [[{
        "role": "assistant",
        "content": "<think>test</think>[{\"phase_id\": 0, \"final\": 200}]"
    }]]
    scores = check_phase_validity(completions, phase_config)
    assert scores[0] == -2.0, f"Expected -2.0 for out-of-range final, got {scores[0]}"
    print(f"  ✓ Out-of-range final: {scores[0]}")

    # 无法解析
    completions = [[{
        "role": "assistant",
        "content": "invalid json"
    }]]
    scores = check_phase_validity(completions, phase_config)
    assert scores[0] == 0.0, f"Expected 0.0 for unparseable, got {scores[0]}"
    print(f"  ✓ Unparseable: {scores[0]}")

    print("\n✅ All format_reward tests passed!")
