"""输出格式验证器

验证模型输出是否符合预期格式: <think>...</think>[{phase_id, final}...]
"""

import re
import json
from typing import Optional


# 正则表达式模式
THINK_PATTERN = re.compile(r"<think>(.*?)</think>", re.DOTALL)
JSON_PATTERN = re.compile(r"\[.*?\]", re.DOTALL)


def extract_think_content(text: str) -> Optional[str]:
    """提取 <think> 标签内的内容

    Args:
        text: 完整输出文本

    Returns:
        <think> 标签内的内容,如果不存在则返回 None
    """
    match = THINK_PATTERN.search(text)
    if match:
        return match.group(1).strip()
    return None


def extract_json_array(text: str) -> Optional[list]:
    """提取并解析 JSON 数组

    Args:
        text: 完整输出文本

    Returns:
        解析后的 JSON 数组,如果解析失败则返回 None
    """
    match = JSON_PATTERN.search(text)
    if not match:
        return None

    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


def validate_format(output_text: str) -> tuple[bool, list[str]]:
    """验证完整输出格式

    检查:
    1. <think>...</think> 标签存在且内容非空(至少 10 字符)
    2. JSON 数组 [...] 存在

    Args:
        output_text: 模型输出文本

    Returns:
        (is_valid, errors_list) - 是否有效和错误列表
    """
    errors = []

    # 检查 <think> 标签
    think_content = extract_think_content(output_text)
    if think_content is None:
        errors.append("Missing <think>...</think> tags")
    elif len(think_content) < 10:
        errors.append(f"Think content too short ({len(think_content)} chars, minimum 10)")

    # 检查 JSON 数组是否存在
    json_match = JSON_PATTERN.search(output_text)
    if not json_match:
        errors.append("Missing JSON array [...]")

    return len(errors) == 0, errors


def validate_json_structure(json_str: str) -> tuple[bool, list[str]]:
    """验证 JSON 结构

    检查:
    1. 可解析为 JSON 数组
    2. 每个元素是 dict
    3. 每个元素包含 phase_id 字段 (int)
    4. 每个元素包含 final 字段 (int)
    5. final 在合理范围 (5-120)

    Args:
        json_str: JSON 字符串

    Returns:
        (is_valid, errors_list) - 是否有效和错误列表
    """
    errors = []

    # 解析 JSON
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        errors.append(f"JSON parse error: {e}")
        return False, errors

    # 检查是否为数组
    if not isinstance(data, list):
        errors.append(f"JSON is not an array, got {type(data).__name__}")
        return False, errors

    # 检查数组是否为空
    if len(data) == 0:
        errors.append("JSON array is empty")
        return False, errors

    # 检查每个元素
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            errors.append(f"Item {i} is not a dict, got {type(item).__name__}")
            continue

        # 检查 phase_id
        if "phase_id" not in item:
            errors.append(f"Item {i} missing 'phase_id' field")
        elif not isinstance(item["phase_id"], int):
            errors.append(f"Item {i} 'phase_id' is not int, got {type(item['phase_id']).__name__}")

        # 检查 final
        if "final" not in item:
            errors.append(f"Item {i} missing 'final' field")
        elif not isinstance(item["final"], (int, float)):
            errors.append(f"Item {i} 'final' is not a number, got {type(item['final']).__name__}")
        elif not (5 <= item["final"] <= 120):
            errors.append(f"Item {i} 'final' out of range (5-120), got {item['final']}")

    return len(errors) == 0, errors


if __name__ == "__main__":
    # 自测试
    print("Testing format_validator...")

    # 测试正确格式
    valid_output = '<think>观察排队情况,相位 1 饱和度高</think>[{"phase_id": 1, "final": 40}]'
    is_valid, errors = validate_format(valid_output)
    assert is_valid, f"Should be valid: {errors}"
    print("✓ Valid format test passed")

    # 测试缺少 think
    invalid_output = '[{"phase_id": 1, "final": 40}]'
    is_valid, errors = validate_format(invalid_output)
    assert not is_valid, "Should fail without think"
    print("✓ Missing think test passed")

    # 测试 think 内容太短
    short_think = '<think>短</think>[{"phase_id": 1, "final": 40}]'
    is_valid, errors = validate_format(short_think)
    assert not is_valid, "Should fail with short think"
    print("✓ Short think test passed")

    # 测试错误的 JSON (缺少 final)
    json_str = '[{"phase_id": 1}]'
    is_valid, errors = validate_json_structure(json_str)
    assert not is_valid, f"Should fail without final: {errors}"
    print("✓ Missing final test passed")

    # 测试正确的 JSON
    json_str = '[{"phase_id": 1, "final": 40}, {"phase_id": 2, "final": 30}]'
    is_valid, errors = validate_json_structure(json_str)
    assert is_valid, f"Should be valid: {errors}"
    print("✓ Valid JSON test passed")

    # 测试 final 超出范围
    json_str = '[{"phase_id": 1, "final": 200}]'
    is_valid, errors = validate_json_structure(json_str)
    assert not is_valid, "Should fail with out-of-range final"
    print("✓ Out-of-range final test passed")

    print("\n✅ All format validator tests passed!")
