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


def graded_format_reward(completions: List[List[Dict]], **kwargs) -> List[float]:
    """分级格式奖励函数

    实现三级评分系统（满分 3.0）:
    - Level 0: 无输出或完全无关 (0.0)
    - Level 1: <think>...</think> 标签正确 (+0.5)
    - Level 2: JSON 可解析 (+1.0, 累计 1.5)
    - Level 3: 字段完整 (+1.5, 累计 3.0)

    注意：CoT 空占位策略下，<think></think> 空内容也是合法的。

    Args:
        completions: List[List[Dict]] - 每个 completion 是 messages 列表
            例: [[{"role": "assistant", "content": "<think>...</think>[...]"}]]
        **kwargs: 兼容 TRL GRPOTrainer reward_funcs 签名

    Returns:
        奖励分数列表，范围 [0.0, 3.0]
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

        # Level 1: 检查 <think>...</think> 标签对
        think_match = THINK_PATTERN.search(content)
        if think_match is not None:
            score += 0.5  # 不要求内容非空

        # Level 2: 检查 JSON 可解析
        json_array = extract_json_from_completion(content)
        if json_array is not None:
            score += 1.0

            # Level 3: 检查字段完整
            fields_complete = True
            if len(json_array) == 0:
                fields_complete = False
            else:
                for item in json_array:
                    if not isinstance(item, dict):
                        fields_complete = False
                        break
                    if "phase_id" not in item or "final" not in item:
                        fields_complete = False
                        break
                    if not isinstance(item["phase_id"], int):
                        fields_complete = False
                        break
                    if not isinstance(item["final"], (int, float)):
                        fields_complete = False
                        break
                    # 检查 final 值在合理范围
                    if not (5 <= item["final"] <= 120):
                        fields_complete = False
                        break

            if fields_complete:
                score += 1.5

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

    # 测试分级评分
    print("\n1. Testing graded_format_reward...")

    # Level 3 满分
    completions = [[{
        "role": "assistant",
        "content": "<think>分析交通流量</think>[{\"phase_id\": 1, \"final\": 40}]"
    }]]
    scores = graded_format_reward(completions)
    assert scores[0] == 3.0, f"Expected 3.0, got {scores[0]}"
    print(f"  ✓ Level 3 (full marks): {scores[0]}")

    # Level 1 只有 think 标签
    completions = [[{
        "role": "assistant",
        "content": "<think>test</think>invalid"
    }]]
    scores = graded_format_reward(completions)
    assert scores[0] == 0.5, f"Expected 0.5, got {scores[0]}"
    print(f"  ✓ Level 1 (think only): {scores[0]}")

    # Level 2 有 think + 可解析 JSON 但字段不完整
    completions = [[{
        "role": "assistant",
        "content": "<think>x</think>[{\"foo\": 1}]"
    }]]
    scores = graded_format_reward(completions)
    assert scores[0] == 1.5, f"Expected 1.5, got {scores[0]}"
    print(f"  ✓ Level 2 (think + parseable JSON): {scores[0]}")

    # Level 0 无输出
    completions = [[{
        "role": "assistant",
        "content": "random text"
    }]]
    scores = graded_format_reward(completions)
    assert scores[0] == 0.0, f"Expected 0.0, got {scores[0]}"
    print(f"  ✓ Level 0 (no format): {scores[0]}")

    # 测试空 think 内容（CoT 空占位策略）
    completions = [[{
        "role": "assistant",
        "content": "<think>\n\n</think>[{\"phase_id\": 1, \"final\": 40}]"
    }]]
    scores = graded_format_reward(completions)
    assert scores[0] == 3.0, f"Expected 3.0 for empty think, got {scores[0]}"
    print(f"  ✓ Empty think (CoT placeholder): {scores[0]}")

    # 测试相位有效性
    print("\n2. Testing check_phase_validity...")
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
