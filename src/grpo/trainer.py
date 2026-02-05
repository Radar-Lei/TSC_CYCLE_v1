"""GRPO 训练配置和训练器创建

提供 GRPO 训练所需的配置和工具函数:
- GRPOConfig: GRPO 训练参数配置
- load_sft_model: 加载 SFT 训练后的模型
- create_grpo_trainer: 创建 TRL GRPOTrainer 实例
- create_sampling_params: 创建 vLLM 采样参数
"""

from dataclasses import dataclass
from typing import Tuple, Any, List, Callable, Dict
from pathlib import Path


@dataclass
class GRPOConfig:
    """
    GRPO 训练参数配置

    参考 Qwen3_(4B)_GRPO.ipynb 和 04-CONTEXT.md:
    - max_steps = 100 (快速验证)
    - learning_rate = 5e-6 (GRPO 推荐学习率)
    - num_generations = 4 (每个 prompt 生成 4 个候选)
    - gradient_accumulation_steps = 4 (提升训练稳定性)
    """

    # 训练规模
    max_steps: int = 100
    max_epochs: int = 1

    # Batch 配置
    per_device_train_batch_size: int = 1
    num_generations: int = 4
    gradient_accumulation_steps: int = 4

    # 学习率
    learning_rate: float = 5e-6
    warmup_ratio: float = 0.1
    lr_scheduler_type: str = "linear"

    # 优化器
    optim: str = "adamw_8bit"
    weight_decay: float = 0.001

    # 生成参数
    temperature: float = 1.0
    max_prompt_length: int = 512
    max_completion_length: int = 1024

    # 输出
    output_dir: str = "outputs/grpo"
    save_steps: int = 50
    logging_steps: int = 1
    report_to: str = "none"

    # 其他
    seed: int = 3407


def load_sft_model(
    adapter_path: str = "outputs/sft/final"
) -> Tuple[Any, Any]:
    """
    加载 SFT 训练后的模型

    使用 Unsloth 加载基础模型并应用 SFT 阶段保存的 LoRA adapter。

    Args:
        adapter_path: SFT adapter 路径 (包含 adapter_model.safetensors)

    Returns:
        (model, tokenizer): 加载了 LoRA adapter 的模型和 tokenizer

    示例:
        >>> model, tokenizer = load_sft_model("outputs/sft/final")
        >>> # 模型已加载 SFT adapter,可以用于 GRPO 训练
    """
    from unsloth import FastLanguageModel

    adapter_path = Path(adapter_path)

    # 检查 adapter 是否存在
    if not adapter_path.exists():
        raise FileNotFoundError(
            f"SFT adapter not found: {adapter_path}\n"
            f"Please run SFT training first (Phase 3)"
        )

    # 检查必需文件
    required_files = ["adapter_config.json", "adapter_model.safetensors"]
    for filename in required_files:
        if not (adapter_path / filename).exists():
            raise FileNotFoundError(
                f"Missing required file: {adapter_path / filename}"
            )

    # 加载模型并应用 LoRA adapter
    # 注意: GRPO 训练需要使用 4bit 量化以节省 GPU 内存
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=str(adapter_path),
        max_seq_length=2048,
        load_in_4bit=True,  # GRPO 使用 4bit 量化
        device_map=None,    # 让 Trainer 管理设备
        fast_inference=False,  # 训练模式
        gpu_memory_utilization=0.9,
    )

    # 重新启用 LoRA 以支持训练
    # Unsloth 在加载时会自动应用 adapter,但需要显式启用训练模式
    model = FastLanguageModel.get_peft_model(
        model,
        # adapter_config.json 中的配置会自动应用
        # 这里只需要指定训练相关的参数
        use_gradient_checkpointing="unsloth",
        random_state=3407,
    )

    return model, tokenizer


def create_sampling_params(
    tokenizer,
    config: GRPOConfig
) -> Dict[str, Any]:
    """
    创建 vLLM 采样参数

    用于 GRPO 训练期间的模型生成。

    Args:
        tokenizer: Tokenizer 实例 (用于获取 eos_token_id)
        config: GRPO 配置

    Returns:
        采样参数字典,包含:
        - temperature: 采样温度
        - max_tokens: 最大生成 token 数
        - stop: 停止 token 列表

    示例:
        >>> from src.sft.model_loader import load_model_for_sft
        >>> _, tokenizer = load_model_for_sft()
        >>> config = GRPOConfig()
        >>> params = create_sampling_params(tokenizer, config)
        >>> params["temperature"]
        1.0
    """
    # vLLM SamplingParams
    # 参考 Qwen3_(4B)_GRPO.ipynb cell 20
    sampling_params = {
        "temperature": config.temperature,
        "max_tokens": config.max_completion_length,
        # 停止 token: eos_token
        "stop": [tokenizer.eos_token] if hasattr(tokenizer, "eos_token") else [],
    }

    return sampling_params


def create_grpo_trainer(
    model,
    tokenizer,
    dataset,
    reward_funcs: List[Callable],
    config: GRPOConfig = None
):
    """
    创建 TRL GRPOTrainer 实例

    Args:
        model: 模型实例 (已加载 SFT adapter)
        tokenizer: Tokenizer 实例 (已配置 chat template)
        dataset: 训练数据集 (HuggingFace Dataset)
        reward_funcs: 奖励函数列表
        config: GRPO 配置,默认使用 GRPOConfig()

    Returns:
        GRPOTrainer 实例

    示例:
        >>> from src.grpo.format_reward import match_format_exactly
        >>> from src.grpo.simulation_reward import compute_simulation_reward
        >>>
        >>> model, tokenizer = load_sft_model()
        >>> dataset = prepare_grpo_dataset(samples, tokenizer)
        >>>
        >>> reward_funcs = [
        ...     match_format_exactly,
        ...     compute_simulation_reward
        ... ]
        >>>
        >>> trainer = create_grpo_trainer(model, tokenizer, dataset, reward_funcs)
        >>> trainer.train()
    """
    from trl import GRPOConfig as TRLGRPOConfig, GRPOTrainer

    if config is None:
        config = GRPOConfig()

    # 创建 TRL GRPOConfig
    training_args = TRLGRPOConfig(
        output_dir=config.output_dir,
        num_train_epochs=config.max_epochs,
        max_steps=config.max_steps,
        per_device_train_batch_size=config.per_device_train_batch_size,
        gradient_accumulation_steps=config.gradient_accumulation_steps,
        learning_rate=config.learning_rate,
        warmup_ratio=config.warmup_ratio,
        lr_scheduler_type=config.lr_scheduler_type,
        optim=config.optim,
        weight_decay=config.weight_decay,
        logging_steps=config.logging_steps,
        save_steps=config.save_steps,
        report_to=config.report_to,
        seed=config.seed,
        # GRPO 特定参数
        num_generations=config.num_generations,
        max_prompt_length=config.max_prompt_length,
        max_completion_length=config.max_completion_length,
        temperature=config.temperature,
    )

    # 创建 GRPOTrainer
    trainer = GRPOTrainer(
        model=model,
        args=training_args,
        tokenizer=tokenizer,
        train_dataset=dataset,
        reward_funcs=reward_funcs,
    )

    return trainer


if __name__ == "__main__":
    # 自测试
    print("Testing trainer module...")

    # 验证 GRPOConfig 默认值
    config = GRPOConfig()
    assert config.max_steps == 100
    assert config.learning_rate == 5e-6
    assert config.num_generations == 4
    assert config.gradient_accumulation_steps == 4
    assert config.temperature == 1.0
    print("✓ GRPOConfig defaults correct")

    # 验证 create_sampling_params
    class MockTokenizer:
        eos_token = "</s>"

    tokenizer = MockTokenizer()
    params = create_sampling_params(tokenizer, config)
    assert params["temperature"] == 1.0
    assert params["max_tokens"] == 1024
    assert params["stop"] == ["</s>"]
    print("✓ create_sampling_params works")

    print("✅ trainer module tests passed!")
