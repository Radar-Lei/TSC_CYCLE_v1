"""
LLM 输出解析和验证模块

从 LLM 输出中提取配时方案并验证约束条件。

主要功能:
- parse_llm_timing: 从 SOLUTION 标签或原始 JSON 中提取并验证
- TimingPlan: 配时方案数据类
- PhaseTiming: 相位配时数据类
- ParseResult: 解析结果数据类
"""

import json
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, List, Optional

from loguru import logger

if TYPE_CHECKING:
    from TSC_CYCLE.benchmark.prompt_builder import PhaseWaitData


@dataclass
class PhaseTiming:
    """相位配时数据

    表示单个相位的配时信息。

    Attributes:
        phase_id: LLM 友好的连续编号 (0, 1, 2, ...)
        sumo_phase_index: SUMO 实际相位索引 (可能是 0, 2, 4, 6)
        final: 最终绿灯时间 (秒)
    """
    phase_id: int
    sumo_phase_index: int
    final: int

    def to_dict(self) -> dict:
        """转换为字典格式"""
        return {
            "phase_id": self.phase_id,
            "sumo_phase_index": self.sumo_phase_index,
            "final": self.final
        }


@dataclass
class TimingPlan:
    """配时方案

    包含所有相位的配时信息。

    Attributes:
        phases: PhaseTiming 列表
    """
    phases: List[PhaseTiming]

    def to_dict(self) -> dict:
        """转换为字典格式"""
        return {
            "phases": [p.to_dict() for p in self.phases]
        }

    def get_total_duration(self) -> int:
        """获取总周期时长"""
        return sum(p.final for p in self.phases)


@dataclass
class ParseResult:
    """解析结果

    表示 LLM 输出的解析结果。

    Attributes:
        success: 是否成功解析
        plan: 解析后的配时方案 (成功时)
        error: 错误信息 (失败时)
    """
    success: bool
    plan: Optional[TimingPlan] = None
    error: Optional[str] = None


def parse_llm_timing(
    llm_output: str,
    expected_phases: int,
    min_green: int,
    max_green: int,
    phase_waits: Optional[List["PhaseWaitData"]] = None,
    expect_raw_json: bool = False,
) -> ParseResult:
    """解析 LLM 输出并验证配时约束

    从 LLM 输出中提取 JSON，并验证约束条件。
    支持两种模式：
    1. SOLUTION 标签模式 (expect_raw_json=False): 从 <SOLUTION>...</SOLUTION> 中提取 JSON
    2. 原始 JSON 模式 (expect_raw_json=True): 直接解析整个输出为 JSON

    解析步骤:
    1. 根据 expect_raw_json 决定如何提取 JSON 内容
    2. 将内容解析为 JSON 数组
    3. 验证约束条件:
       - JSON 解析成功
       - 数组长度与 expected_phases 匹配
       - 每个元素包含 phase_id 和 final 字段
       - phase_id 顺序正确 (0, 1, 2, ... 或 1, 2, 3, ...)
       - final 值在 [min_green, max_green] 范围内

    Args:
        llm_output: LLM 生成的文本输出 (可能包含 SOLUTION 标签或直接是 JSON)
        expected_phases: 期望的相位数量
        min_green: 最小绿灯时间 (秒)
        max_green: 最大绿灯时间 (秒)
        phase_waits: 可选的 PhaseWaitData 列表，用于获取 sumo_phase_index 映射
        expect_raw_json: 如果为 True，将整个输出视为原始 JSON（用于结构化输出模式）
                        如果为 False，会先尝试从 SOLUTION 标签中提取

    Returns:
        ParseResult:
        - success=True, plan=TimingPlan: 解析成功
        - success=False, error=str: 解析失败，包含错误信息

    Example:
        >>> # SOLUTION tag mode
        >>> output = '''
        ... <start_working_out>推理过程...</end_working_out>
        ... <SOLUTION>
        ... [{"phase_id": 0, "final": 30}, {"phase_id": 1, "final": 25}]
        ... </SOLUTION>
        ... '''
        >>> result = parse_llm_timing(output, expected_phases=2, min_green=10, max_green=60)
        >>> result.success
        True

        >>> # Raw JSON mode (structured output)
        >>> raw_json = '[{"phase_id": 0, "final": 30}, {"phase_id": 1, "final": 25}]'
        >>> result = parse_llm_timing(raw_json, expected_phases=2, min_green=10, max_green=60, expect_raw_json=True)
        >>> result.success
        True
    """
    # Step 1: 提取 JSON 内容
    json_str: str | None = None

    if expect_raw_json:
        # Structured output: the entire response IS the JSON
        json_str = llm_output.strip()
        logger.debug("Parsing as raw JSON (structured output mode)")
    else:
        # Standard mode: extract from SOLUTION tag
        solution_pattern = re.compile(
            r'<SOLUTION>\s*(.*?)\s*</SOLUTION>',
            re.DOTALL | re.IGNORECASE
        )
        solution_match = solution_pattern.search(llm_output)

        if solution_match:
            json_str = solution_match.group(1).strip()
            logger.debug("Extracted JSON from SOLUTION tag")
        else:
            # Fallback: try to parse entire output as JSON (some models forget tags)
            json_str = llm_output.strip()
            logger.warning("No SOLUTION tag found, attempting raw JSON parse as fallback")

    if not json_str:
        error_msg = "Empty JSON content"
        logger.warning(error_msg)
        return ParseResult(success=False, error=error_msg)

    # Step 2: 解析 JSON
    try:
        parsed_json = json.loads(json_str)
    except json.JSONDecodeError as e:
        error_msg = f"JSON parse error: {str(e)}"
        logger.warning(error_msg)
        return ParseResult(success=False, error=error_msg)

    # Step 3: 验证是数组
    if not isinstance(parsed_json, list):
        error_msg = f"JSON root must be an array, got {type(parsed_json).__name__}"
        logger.warning(error_msg)
        return ParseResult(success=False, error=error_msg)

    # Step 4: 验证数组长度
    if len(parsed_json) != expected_phases:
        error_msg = (
            f"Array length mismatch: expected {expected_phases} phases, "
            f"got {len(parsed_json)}"
        )
        logger.warning(error_msg)
        return ParseResult(success=False, error=error_msg)

    # Step 5: 解析并验证每个元素
    phases: List[PhaseTiming] = []
    for i, element in enumerate(parsed_json):
        # 验证元素是对象
        if not isinstance(element, dict):
            error_msg = (
                f"Element {i} must be an object, got {type(element).__name__}"
            )
            logger.warning(error_msg)
            return ParseResult(success=False, error=error_msg)

        # 验证包含 phase_id 字段
        if "phase_id" not in element:
            error_msg = f"Element {i} missing 'phase_id' field"
            logger.warning(error_msg)
            return ParseResult(success=False, error=error_msg)

        # 验证包含 final 字段
        if "final" not in element:
            error_msg = f"Element {i} missing 'final' field"
            logger.warning(error_msg)
            return ParseResult(success=False, error=error_msg)

        # 提取值
        phase_id = element["phase_id"]
        final = element["final"]

        # 验证类型
        if not isinstance(phase_id, int):
            error_msg = f"Element {i}: phase_id must be an integer, got {type(phase_id).__name__}"
            logger.warning(error_msg)
            return ParseResult(success=False, error=error_msg)

        if not isinstance(final, (int, float)):
            error_msg = f"Element {i}: final must be a number, got {type(final).__name__}"
            logger.warning(error_msg)
            return ParseResult(success=False, error=error_msg)

        # 将 final 转换为整数
        final_int = int(final)

        # Step 6: 验证相位顺序
        # 接受 0-based (0, 1, 2, ...) 或 1-based (1, 2, 3, ...)
        expected_0based = i
        expected_1based = i + 1
        if phase_id != expected_0based and phase_id != expected_1based:
            error_msg = (
                f"Phase order error: element {i} has phase_id={phase_id}, "
                f"expected {expected_0based} or {expected_1based}"
            )
            logger.warning(error_msg)
            return ParseResult(success=False, error=error_msg)

        # Step 7: 验证时间范围
        if final_int < min_green or final_int > max_green:
            error_msg = (
                f"Phase {phase_id} final={final_int} out of range: "
                f"must be between {min_green} and {max_green}"
            )
            logger.warning(error_msg)
            return ParseResult(success=False, error=error_msg)

        # 获取 sumo_phase_index 映射
        if phase_waits and i < len(phase_waits):
            sumo_idx = phase_waits[i].sumo_phase_index
        else:
            # 如果没有提供映射，使用 phase_id 作为默认值
            sumo_idx = phase_id

        phases.append(PhaseTiming(
            phase_id=phase_id,
            sumo_phase_index=sumo_idx,
            final=final_int
        ))

    # 解析成功
    plan = TimingPlan(phases=phases)
    logger.info(
        "Successfully parsed timing plan: {} phases, total duration={}s",
        len(phases),
        plan.get_total_duration()
    )

    return ParseResult(success=True, plan=plan)
