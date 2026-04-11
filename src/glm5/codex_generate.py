"""通过 Codex MCP 批量生成 SFT 数据

使用本地 Codex MCP server 调用 GPT-5.2 生成 think 链和 solution。
比 GLM-5 API 快得多，且输出格式更稳定。

运行方式 (由 Claude 调用，不直接运行):
    此脚本提供批量生成的辅助函数，实际调用通过 Claude 的 mcp__codex__codex 工具完成。
"""

import json
import os
from typing import List, Dict, Any, Optional

from src.glm5.prompt import build_glm5_prompts
from src.glm5.validator import parse_glm5_output, validate_constraints

__all__ = ["build_codex_prompt", "process_codex_response", "load_progress", "save_result"]


def build_codex_prompt(sample: dict) -> str:
    """为 Codex MCP 构建完整的 prompt（system + user 合并为一个 prompt）

    Args:
        sample: train.jsonl 中的一行数据

    Returns:
        合并后的完整 prompt 字符串
    """
    system_prompt, user_prompt = build_glm5_prompts(sample)
    return f"{system_prompt}\n\n{user_prompt}\n\n请直接输出推理和方案，不要使用任何工具。"


def process_codex_response(
    content: str,
    sample: dict,
    sample_id: str,
) -> dict:
    """处理 Codex MCP 返回的内容

    Args:
        content: Codex 返回的文本（可能包含 JSON wrapper）
        sample: 原始样本数据
        sample_id: 样本唯一 ID

    Returns:
        结果字典
    """
    # Codex MCP 返回 JSON，需要提取 content 字段
    if isinstance(content, str):
        try:
            data = json.loads(content)
            if "content" in data:
                content = data["content"]
        except json.JSONDecodeError:
            pass  # 已经是纯文本

    parsed = parse_glm5_output(content)
    if not parsed.success:
        return {
            "id": sample_id,
            "status": "parse_failed",
            "error": parsed.error,
            "raw_content": content[:500],
            "sample": sample,
        }

    phase_waits = sample["prediction"]["phase_waits"]
    valid, reason = validate_constraints(parsed.solution, phase_waits)

    if valid:
        return {
            "id": sample_id,
            "status": "success",
            "think_text": parsed.think_text,
            "solution": parsed.solution,
            "think_length": parsed.think_length,
            "sample": sample,
        }
    else:
        return {
            "id": sample_id,
            "status": "constraint_failed",
            "error": reason,
            "raw_content": content[:500],
            "sample": sample,
        }


def load_progress(output_path: str) -> set:
    """加载已完成的 ID 集合用于断点续传

    Args:
        output_path: results.jsonl 路径

    Returns:
        已完成的 sample_id 集合
    """
    completed = set()
    if not os.path.exists(output_path):
        return completed
    with open(output_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                try:
                    record = json.loads(line)
                    if record.get("status") == "success":
                        completed.add(record["id"])
                except (json.JSONDecodeError, KeyError):
                    continue
    return completed


def save_result(result: dict, output_path: str):
    """追加一条结果到 output_path

    Args:
        result: 结果字典
        output_path: jsonl 文件路径
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(result, ensure_ascii=False) + "\n")


def sample_id(sample: dict) -> str:
    """生成样本唯一 ID

    Args:
        sample: train.jsonl 中的一行数据

    Returns:
        格式为 "tl_id:as_of" 的唯一标识
    """
    return f"{sample['metadata']['tl_id']}:{sample['prediction']['as_of']}"
