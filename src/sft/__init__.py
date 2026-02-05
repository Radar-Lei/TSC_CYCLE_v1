"""
SFT (Supervised Fine-Tuning) 模块。

包含模型加载、chat template 配置、格式验证等 SFT 训练基础设施。
"""

from .chat_template import (
    THINKING_START,
    THINKING_END,
    SYSTEM_PROMPT,
    CHAT_TEMPLATE,
    setup_tokenizer,
)
from .model_loader import (
    SFTConfig,
    load_model_for_sft,
    print_trainable_params,
)
from .format_validator import (
    validate_format,
    validate_json_structure,
    extract_think_content,
    extract_json_array,
)
from .trainer import (
    TrainingArgs,
    SFTTrainerWrapper,
    prepare_dataset,
    validate_model_output,
)

__all__ = [
    "THINKING_START",
    "THINKING_END",
    "SYSTEM_PROMPT",
    "CHAT_TEMPLATE",
    "setup_tokenizer",
    "SFTConfig",
    "load_model_for_sft",
    "print_trainable_params",
    "validate_format",
    "validate_json_structure",
    "extract_think_content",
    "extract_json_array",
    "TrainingArgs",
    "SFTTrainerWrapper",
    "prepare_dataset",
    "validate_model_output",
]
