"""
模型加载模块,封装 Unsloth 模型加载和 LoRA 配置。

用于 SFT 训练的模型加载和配置,包括:
- SFTConfig: LoRA 训练配置
- load_model_for_sft: 加载模型并配置 LoRA
- print_trainable_params: 打印可训练参数统计
"""

from dataclasses import dataclass, field
from typing import Tuple, Any


@dataclass
class SFTConfig:
    """
    SFT 训练配置。

    参考 Qwen3_(4B)_GRPO.ipynb cell 8 和 03-CONTEXT.md:
    - rank = 32 (中等配置)
    - alpha = 64 (rank * 2)
    - load_in_4bit = False (SFT 使用 16bit 精度)
    """

    model_name: str = "unsloth/Qwen3-4B-Base"
    max_seq_length: int = 2048
    lora_rank: int = 32
    lora_alpha: int = 64  # 2 * rank
    load_in_4bit: bool = False  # SFT 用 16bit
    gpu_memory_utilization: float = 0.9
    target_modules: list = field(
        default_factory=lambda: [
            "q_proj",
            "k_proj",
            "v_proj",
            "o_proj",
            "gate_proj",
            "up_proj",
            "down_proj",
        ]
    )


def load_model_for_sft(config: SFTConfig = None) -> Tuple[Any, Any]:
    """
    加载 Qwen3-4B 模型并配置 LoRA。

    使用 Unsloth 的 FastLanguageModel 加载基础模型,
    然后应用 LoRA (Low-Rank Adaptation) 进行高效微调。

    Args:
        config: SFT 配置,默认使用 SFTConfig()

    Returns:
        (model, tokenizer): 配置好 LoRA 的模型和 tokenizer

    Note:
        此函数需要 GPU 环境才能运行。
    """
    from unsloth import FastLanguageModel
    from .chat_template import setup_tokenizer

    if config is None:
        config = SFTConfig()

    # 加载基础模型
    # device_map 必须设为 None,否则与 Trainer 不兼容
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=config.model_name,
        max_seq_length=config.max_seq_length,
        load_in_4bit=config.load_in_4bit,
        device_map=None,  # 禁用 auto device_map,使用 Trainer 的设备管理
        fast_inference=False,  # 训练模式,非推理加速模式
        max_lora_rank=config.lora_rank,
        gpu_memory_utilization=config.gpu_memory_utilization,
    )

    # 配置 LoRA
    model = FastLanguageModel.get_peft_model(
        model,
        r=config.lora_rank,
        lora_alpha=config.lora_alpha,
        target_modules=config.target_modules,
        lora_dropout=0,
        bias="none",
        use_gradient_checkpointing="unsloth",
        random_state=3407,
    )

    # 配置 chat template
    tokenizer = setup_tokenizer(tokenizer)

    return model, tokenizer


def print_trainable_params(model):
    """
    打印模型可训练参数统计。

    Args:
        model: 模型实例
    """
    trainable_params = 0
    all_params = 0
    for _, param in model.named_parameters():
        all_params += param.numel()
        if param.requires_grad:
            trainable_params += param.numel()

    percentage = 100 * trainable_params / all_params

    print(f"Trainable params: {trainable_params:,}")
    print(f"All params: {all_params:,}")
    print(f"Trainable%: {percentage:.2f}%")
