"""
GLM-5 输出解析和约束校验模块

解析 GLM-5 生成的文本，提取 think 链和 solution JSON，
并校验 solution 是否满足相位顺序、绿灯范围、整数类型等约束。
"""

import json
import re
from dataclasses import dataclass, field
from typing import List, Dict, Any

__all__ = ["parse_glm5_output", "validate_constraints", "ParsedOutput"]


@dataclass
class ParsedOutput:
    """
    GLM-5 输出解析结果

    Attributes:
        success: 解析是否成功
        think_text: <start_working_out> 和 <end_working_out> 之间的推理内容
        solution: SOLUTION 标签内的 JSON 数组
        think_length: think_text 的字符数 (粗略 token 估计)
        raw_content: 原始输出内容
        error: 解析失败时的错误信息
    """
    success: bool
    think_text: str = ""
    solution: list = field(default_factory=list)
    think_length: int = 0
    raw_content: str = ""
    error: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "success": self.success,
            "think_text": self.think_text,
            "solution": self.solution,
            "think_length": self.think_length,
            "raw_content": self.raw_content,
            "error": self.error,
        }


# 预编译正则
_THINK_PATTERN = re.compile(
    r"<start_working_out>(.*?)<end_working_out>", re.DOTALL
)
_THINK_NO_START_PATTERN = re.compile(
    r"^(.*?)<end_working_out>", re.DOTALL
)
_SOLUTION_PATTERN = re.compile(
    r"<SOLUTION>(.*?)</SOLUTION>", re.DOTALL
)


def parse_glm5_output(content: str) -> ParsedOutput:
    """
    解析 GLM-5 输出文本，提取 think 链和 solution JSON。

    支持两种格式:
    1. 完整标签: <start_working_out>思考<end_working_out><SOLUTION>...</SOLUTION>
    2. 无起始标签: 思考<end_working_out><SOLUTION>...</SOLUTION>

    Args:
        content: GLM-5 生成的原始文本

    Returns:
        ParsedOutput 解析结果
    """
    # 提取 think 链
    think_match = _THINK_PATTERN.search(content)
    if think_match:
        think_text = think_match.group(1)
    else:
        # 尝试无 <start_working_out> 前缀的格式
        think_no_start = _THINK_NO_START_PATTERN.search(content)
        if think_no_start:
            think_text = think_no_start.group(1)
        else:
            return ParsedOutput(
                success=False,
                raw_content=content,
                error="未找到 <end_working_out> 标签",
            )

    # 提取 solution
    solution_match = _SOLUTION_PATTERN.search(content)
    if not solution_match:
        return ParsedOutput(
            success=False,
            think_text=think_text,
            raw_content=content,
            error="未找到 <SOLUTION>...</SOLUTION> 标签",
        )

    solution_text = solution_match.group(1).strip()

    # 解析 JSON
    try:
        solution = json.loads(solution_text)
    except json.JSONDecodeError as e:
        return ParsedOutput(
            success=False,
            think_text=think_text,
            raw_content=content,
            error=f"SOLUTION JSON 解析失败: {e}",
        )

    # 验证结果是 list
    if not isinstance(solution, list):
        return ParsedOutput(
            success=False,
            think_text=think_text,
            raw_content=content,
            error=f"SOLUTION 必须为数组, 实际为 {type(solution).__name__}",
        )

    return ParsedOutput(
        success=True,
        think_text=think_text,
        solution=solution,
        think_length=len(think_text),
        raw_content=content,
    )


def validate_constraints(
    solution: List[Dict[str, Any]],
    phase_waits: List[Dict[str, Any]],
) -> tuple:
    """
    校验 solution 是否满足约束条件。

    校验项:
    1. 相位数量匹配
    2. 相位顺序一致
    3. final 为整数类型
    4. 绿灯时间在 [min_green, max_green] 范围内

    Args:
        solution: 解析后的 solution JSON 数组
        phase_waits: 原始样本中的 phase_waits 列表

    Returns:
        (valid, error_message) 元组，valid 为 True 时 error_message 为空字符串
    """
    # 检查数量匹配
    if len(solution) != len(phase_waits):
        return (
            False,
            f"相位数量不匹配: 期望{len(phase_waits)}个, 实际{len(solution)}个",
        )

    # 逐相位校验
    for i, (sol, pw) in enumerate(zip(solution, phase_waits)):
        expected_id = pw["phase_id"]
        actual_id = sol.get("phase_id")

        # 检查相位顺序
        if actual_id != expected_id:
            expected_order = [p["phase_id"] for p in phase_waits]
            actual_order = [s.get("phase_id") for s in solution]
            return (
                False,
                f"相位顺序不一致: 期望{expected_order}, 实际{actual_order}",
            )

        final = sol.get("final")

        # 检查 final 是否为整数
        if not isinstance(final, int):
            return (
                False,
                f"phase_id={actual_id} final 必须为整数, 实际为{type(final).__name__}",
            )

        # 检查绿灯时间范围
        min_green = pw["min_green"]
        max_green = pw["max_green"]
        if final < min_green or final > max_green:
            return (
                False,
                f"phase_id={actual_id} 绿灯时间{final}越界 [{min_green}, {max_green}]",
            )

    return (True, "")
