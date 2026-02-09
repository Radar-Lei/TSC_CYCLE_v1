"""SFT 训练器封装模块

封装 SFTTrainer 配置和训练流程,包括:
- TrainingArgs: 训练配置参数
- SFTTrainerWrapper: 训练器封装类
- prepare_dataset: 数据准备函数
- validate_model_output: 模型输出验证函数
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Tuple
import json


@dataclass
class TrainingArgs:
    """SFT 训练参数配置

    参考 Qwen3_(4B)_GRPO.ipynb 和 03-RESEARCH.md:
    - max_steps=300 (固定步数)
    - learning_rate=2e-4
    - optim=adamw_8bit (节省内存)
    """

    output_dir: str = "outputs/sft/model"
    per_device_train_batch_size: int = 1
    gradient_accumulation_steps: int = 1
    warmup_steps: int = 5
    max_steps: int = 300  # 固定 300 steps
    learning_rate: float = 2e-4
    logging_steps: int = 5
    save_steps: int = 100
    save_total_limit: int = 3  # 保留最近 3 个 checkpoint
    optim: str = "adamw_8bit"
    weight_decay: float = 0.001
    lr_scheduler_type: str = "linear"
    seed: int = 3407
    report_to: str = "none"
    bf16: bool = True  # bf16 全精度训练
    logging_dir: str = None  # 将在 __post_init__ 中设置

    def __post_init__(self):
        """初始化后处理"""
        if self.logging_dir is None:
            self.logging_dir = f"{self.output_dir}/logs"


class SFTTrainerWrapper:
    """SFT 训练器封装类

    封装 TRL SFTTrainer,提供统一的训练接口。
    """

    def __init__(self, model, tokenizer, train_dataset, args: TrainingArgs = None):
        """初始化训练器

        Args:
            model: 模型实例 (已配置 LoRA)
            tokenizer: Tokenizer 实例 (已配置 chat template)
            train_dataset: 训练数据集 (HuggingFace Dataset)
            args: 训练参数,默认使用 TrainingArgs()
        """
        self.model = model
        self.tokenizer = tokenizer
        self.train_dataset = train_dataset
        self.args = args or TrainingArgs()
        self._trainer = None

    def _create_trainer(self):
        """创建 SFTTrainer 实例"""
        from trl import SFTTrainer, SFTConfig

        # 构建配置参数
        config_kwargs = {
            "output_dir": self.args.output_dir,
            "dataset_text_field": "text",
            "per_device_train_batch_size": self.args.per_device_train_batch_size,
            "gradient_accumulation_steps": self.args.gradient_accumulation_steps,
            "warmup_steps": self.args.warmup_steps,
            "max_steps": self.args.max_steps,
            "learning_rate": self.args.learning_rate,
            "logging_steps": self.args.logging_steps,
            "save_steps": self.args.save_steps,
            "save_total_limit": self.args.save_total_limit,
            "optim": self.args.optim,
            "weight_decay": self.args.weight_decay,
            "lr_scheduler_type": self.args.lr_scheduler_type,
            "seed": self.args.seed,
            "report_to": self.args.report_to,
            "bf16": self.args.bf16,
            "logging_dir": self.args.logging_dir,
        }

        sft_config = SFTConfig(**config_kwargs)

        self._trainer = SFTTrainer(
            model=self.model,
            tokenizer=self.tokenizer,
            train_dataset=self.train_dataset,
            args=sft_config,
        )

    def train(self, resume_from_checkpoint=None):
        """执行训练

        Args:
            resume_from_checkpoint: checkpoint 路径，用于恢复训练

        Returns:
            训练结果 (TrainOutput)
        """
        if self._trainer is None:
            self._create_trainer()
        return self._trainer.train(resume_from_checkpoint=resume_from_checkpoint)

    def save_model(self, path: str = None):
        """保存训练后的模型

        Args:
            path: 保存路径,默认为 {output_dir}/final
        """
        path = path or f"{self.args.output_dir}/final"
        self._trainer.save_model(path)
        self.model.save_pretrained(path)
        self.tokenizer.save_pretrained(path)


def prepare_dataset(data_path: str, tokenizer):
    """准备训练数据集

    从 JSONL 文件加载数据,应用 chat template 转换。
    数据必须已包含 messages 字段（由 Phase 2 的 CoT 转换生成）。

    Args:
        data_path: JSONL 文件路径
        tokenizer: Tokenizer 实例 (已配置 chat template)

    Returns:
        HuggingFace Dataset,包含 text 字段
    """
    from datasets import Dataset

    # 读取 JSONL
    data = []
    with open(data_path, 'r', encoding='utf-8') as f:
        for line in f:
            sample = json.loads(line)

            # 验证数据格式
            if "messages" not in sample:
                raise ValueError(
                    f"Data format error: missing 'messages' field. "
                    f"Expected data from Phase 2 CoT conversion (convert_to_sft_format). "
                    f"Sample keys: {list(sample.keys())}"
                )

            # 逐条应用 chat template
            text = tokenizer.apply_chat_template(
                sample["messages"],
                tokenize=False
            )

            data.append({"text": text})

    # 转换为 Dataset
    dataset = Dataset.from_list(data)

    return dataset


def validate_model_output(model, tokenizer, test_input: str) -> Tuple[str, bool]:
    """验证模型输出格式

    生成模型输出并验证格式是否正确。

    Args:
        model: 模型实例
        tokenizer: Tokenizer 实例
        test_input: 测试输入 (JSON 字符串)

    Returns:
        (output_text, is_valid) - 输出文本和格式是否有效
    """
    from .format_validator import validate_format
    from .chat_template import SYSTEM_PROMPT

    # 构建输入
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": test_input},
    ]

    input_text = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True
    )

    # 生成输出 (参考 Qwen3_(4B)_GRPO.ipynb cell 29)
    import torch

    # 修复 unsloth fast inference 路径中 _per_layer_device_index 为 None 的问题
    # 训练后各层可能没有设置此属性，导致 move_to_device 收到 None 报错
    base_model = model.model if hasattr(model, "model") else model
    inner_model = base_model.model if hasattr(base_model, "model") else base_model
    if hasattr(inner_model, "layers"):
        for layer in inner_model.layers:
            if getattr(layer, "_per_layer_device_index", None) is None:
                layer._per_layer_device_index = 0

    inputs = tokenizer(input_text, return_tensors="pt").to("cuda")
    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=512,
            temperature=0,
        )

    # 解码输出
    output_text = tokenizer.decode(outputs[0], skip_special_tokens=False)

    # 验证格式
    is_valid, errors = validate_format(output_text)

    if not is_valid:
        print(f"Format validation errors: {errors}")

    return output_text, is_valid


if __name__ == "__main__":
    # 自测试
    print("Testing trainer module...")

    # 验证 TrainingArgs 默认值
    args = TrainingArgs()
    assert args.max_steps == 300
    assert args.learning_rate == 2e-4
    assert args.optim == 'adamw_8bit'

    print(f"✓ TrainingArgs defaults: steps={args.max_steps}, lr={args.learning_rate}")
    print(f"✓ Trainer module syntax OK")
