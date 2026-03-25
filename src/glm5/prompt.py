"""
GLM-5 Prompt 构建模块

为 GLM-5 批量生成构建 system prompt 和 user prompt。
复用现有 PromptBuilder 生成 user prompt，并在 system prompt 中追加
think 链长度引导，确保 GLM-5 生成约 500 token 的推理过程。
"""

from src.data_generator.prompt_builder import SYSTEM_PROMPT, PromptBuilder
from src.data_generator.models import Prediction

__all__ = ["build_glm5_prompts", "GLM5_SYSTEM_PROMPT"]


# GLM-5 专用 system prompt: 基于原始 SYSTEM_PROMPT 追加 think 链长度引导
GLM5_SYSTEM_PROMPT = (
    SYSTEM_PROMPT
    + "\n"
    + "请确保推理过程（即 <start_working_out> 和 <end_working_out> 之间的内容）"
    + "约 500 token，充分分析每个相位的饱和度与绿灯需求。"
)


def build_glm5_prompts(sample: dict) -> tuple:
    """
    从 train.jsonl 样本构建 GLM-5 请求所需的 system prompt 和 user prompt。

    Args:
        sample: train.jsonl 中的一行数据，包含 "prediction" 字段

    Returns:
        (system_prompt, user_prompt) 元组
        - system_prompt: GLM5_SYSTEM_PROMPT，含 think 链长度引导
        - user_prompt: 由 PromptBuilder 生成的标准 prompt
    """
    prediction = Prediction.from_dict(sample["prediction"])
    user_prompt = PromptBuilder().build_prompt(prediction)
    return (GLM5_SYSTEM_PROMPT, user_prompt)
