"""Prompt builder — single source of truth for teacher / student / eval.

The format MUST match the v4 protocol exactly:
  - System prefix: "你是交通信号配时优化专家。"
  - 【cycle_predict_input_json】 ... 【/cycle_predict_input_json】 wrapping the prediction JSON
  - Hard constraints + decision hint
  - Output requirements: <start_working_out>...</end_working_out><SOLUTION>...</SOLUTION>

Custom thinking tags (intentionally NOT in Qwen3 vocab):
  <start_working_out> / </end_working_out>  — replaces native <think>/</think>
  <SOLUTION> / </SOLUTION>                  — final JSON dict

The assistant turn during SFT MUST be prefixed with `<start_working_out>` so the
model only learns to emit content (no leading whitespace, no native <think>).
"""

from __future__ import annotations

import json
from typing import Any

# Tags. Each is multi-token under Qwen3 BPE tokenizer (verified by tokenizer_check).
TAG_THINK_OPEN = "<start_working_out>"
TAG_THINK_CLOSE = "</end_working_out>"
TAG_SOLUTION_OPEN = "<SOLUTION>"
TAG_SOLUTION_CLOSE = "</SOLUTION>"

MALFORMED_THINK_CLOSE = "<end_working_out>"
NATIVE_THINK_TAGS = ("<think>", "</think>")

SYSTEM_PROMPT = "你是交通信号配时优化专家。"

USER_TEMPLATE = """{system}
【cycle_predict_input_json】{input_json}【/cycle_predict_input_json】

任务（必须完成）：
基于 prediction.phase_waits 的 pred_saturation，在满足全部硬约束前提下，输出下一周期各相位最终绿灯时间 final（单位：秒）。

输入字段说明：
- prediction.phase_waits[*].min_green / max_green：绿灯时长上下限，单位秒。
- prediction.phase_waits[*].pred_wait：预测等待车辆数。
- prediction.phase_waits[*].pred_saturation：预测饱和度（pred_wait / capacity）。
- prediction.phase_waits[*].capacity：相位容量，仅供参考。

硬约束（必须满足）：
1) 相位顺序固定：严格按 prediction.phase_waits 的顺序考虑并输出；不可跳相、不可重排。
2) 每相位约束：final 必须满足 prediction.phase_waits[*].min_green ≤ final ≤ prediction.phase_waits[*].max_green。
3) final 必须为整数秒。

决策提示（非硬约束）：
- 最终决策以 pred_saturation 为主，capacity 仅供参考。

输出要求（必须严格遵守）：
1) 必须先输出 <start_working_out>...</end_working_out>，其中只写思考分析过程，不要输出最终 JSON。
2) 随后输出 <SOLUTION>...</SOLUTION>；<SOLUTION> 内只允许最终 JSON，不允许其它文本。
3) JSON 顶层必须是对象(dict)，键为相位ID的字符串，值为整数秒，键必须使用双引号。
4) 必须覆盖 prediction.phase_waits 中所有相位ID，不能缺少或多余。
5) 除 <start_working_out>...</end_working_out> 与 <SOLUTION>...</SOLUTION> 外，不允许输出任何其它文本。
"""


def build_user_prompt(prediction_input: dict[str, Any]) -> str:
    """Build the user-side prompt text (system + framed JSON + instructions).

    Parameters
    ----------
    prediction_input : dict
        {"prediction": {"as_of": str, "phase_waits": [...]}}.
    """
    # Pretty-printed JSON to match reality.log exactly (2-space indent).
    input_json = json.dumps(prediction_input, indent=2, ensure_ascii=False)
    return USER_TEMPLATE.format(system=SYSTEM_PROMPT, input_json=input_json)


def build_assistant_prefill() -> str:
    """The assistant turn MUST start with the opening think tag — model only
    learns content, not the tag emission decision."""
    return TAG_THINK_OPEN


def build_full_assistant(reasoning: str, solution: dict[str, int]) -> str:
    """Assemble a full assistant turn for SFT training."""
    sol_json = json.dumps(solution, ensure_ascii=False)
    return (
        f"{TAG_THINK_OPEN}{reasoning}{TAG_THINK_CLOSE}"
        f"{TAG_SOLUTION_OPEN}{sol_json}{TAG_SOLUTION_CLOSE}"
    )


def parse_assistant_output(text: str) -> tuple[str, dict[str, int] | None]:
    """Parse model output into (reasoning, solution_dict).

    Returns (reasoning, None) if SOLUTION block missing or unparseable.
    """
    reasoning = ""
    solution: dict[str, int] | None = None

    if MALFORMED_THINK_CLOSE in text or any(tag in text for tag in NATIVE_THINK_TAGS):
        return "", None

    # Reasoning: between <start_working_out> and </end_working_out>
    if TAG_THINK_OPEN in text and TAG_THINK_CLOSE in text:
        a = text.index(TAG_THINK_OPEN) + len(TAG_THINK_OPEN)
        b = text.index(TAG_THINK_CLOSE, a)
        reasoning = text[a:b].strip()
    elif TAG_THINK_CLOSE in text:
        # Pre-filled tag was already injected; reasoning is everything before close
        b = text.index(TAG_THINK_CLOSE)
        reasoning = text[:b].strip()

    # Solution: between <SOLUTION> and </SOLUTION>
    if TAG_SOLUTION_OPEN in text and TAG_SOLUTION_CLOSE in text:
        a = text.index(TAG_SOLUTION_OPEN) + len(TAG_SOLUTION_OPEN)
        b = text.index(TAG_SOLUTION_CLOSE, a)
        try:
            parsed = json.loads(text[a:b].strip())
            if isinstance(parsed, dict):
                # Coerce values to int if possible
                solution = {str(k): int(v) for k, v in parsed.items()}
        except (json.JSONDecodeError, ValueError, TypeError):
            solution = None

    return reasoning, solution
