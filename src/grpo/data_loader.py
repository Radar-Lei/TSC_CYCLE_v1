"""GRPO 训练数据加载器

从 Phase 2 生成的训练数据中加载样本,转换为 GRPO 训练格式。

主要功能:
- load_training_data: 从 JSONL 文件加载训练样本
- prepare_grpo_dataset: 转换为 HuggingFace Dataset
- get_system_prompt: 获取系统提示
"""

import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from datasets import Dataset

from src.data_generator.models import TrainingSample
from src.sft.chat_template import SYSTEM_PROMPT


def get_system_prompt() -> str:
    """
    获取系统提示

    复用 SFT 阶段的系统提示,保持一致性。

    Returns:
        系统提示字符串
    """
    return SYSTEM_PROMPT


def load_training_data(
    data_dir: str = "outputs/training",
    limit: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    从 data_dir 加载所有训练样本

    Args:
        data_dir: 训练数据目录路径,包含 samples_*.jsonl 文件
                  默认 outputs/training (与 Phase 2 generate_training_data.py 输出一致)
        limit: 限制加载数量 (可选)

    Returns:
        训练样本列表,每个样本为字典格式

    示例:
        >>> samples = load_training_data("outputs/training", limit=100)
        >>> len(samples)
        100
        >>> samples[0].keys()
        dict_keys(['prompt', 'prediction', 'state_file', 'metadata'])
    """
    data_path = Path(data_dir)

    # 检查目录是否存在
    if not data_path.exists():
        raise FileNotFoundError(f"Data directory not found: {data_dir}")

    # 查找所有 samples_*.jsonl 文件
    jsonl_files = sorted(data_path.glob("samples_*.jsonl"))

    if not jsonl_files:
        raise FileNotFoundError(f"No samples_*.jsonl files found in {data_dir}")

    samples = []

    for jsonl_file in jsonl_files:
        with open(jsonl_file, 'r', encoding='utf-8') as f:
            for line in f:
                if limit is not None and len(samples) >= limit:
                    return samples

                # 解析 JSON
                data = json.loads(line.strip())

                # 转换为 TrainingSample 对象并立即转换回字典
                # 这样可以验证数据格式的正确性
                sample = TrainingSample.from_dict(data)
                samples.append(sample.to_dict())

    # 应用 limit
    if limit is not None:
        samples = samples[:limit]

    return samples


def prepare_grpo_dataset(
    samples: List[Dict[str, Any]],
    tokenizer
) -> Dataset:
    """
    将训练样本转换为 GRPO 训练格式

    GRPO 训练需要:
    - prompt: 聊天格式的输入 (包含 system 和 user 消息)
    - state_file: SUMO 状态快照路径 (用于仿真奖励计算)
    - tl_id: 信号灯 ID (用于评估)
    - metadata: 其他元数据

    Args:
        samples: 训练样本列表 (load_training_data 的输出)
        tokenizer: Tokenizer 实例 (已配置 chat template)

    Returns:
        HuggingFace Dataset,包含以下字段:
        - prompt: 格式化的输入文本 (应用 chat_template)
        - state_file: 状态快照路径
        - tl_id: 信号灯 ID
        - metadata: 元数据字典

    示例:
        >>> from src.sft.model_loader import load_model_for_sft
        >>> _, tokenizer = load_model_for_sft()
        >>> samples = load_training_data("data/training", limit=10)
        >>> dataset = prepare_grpo_dataset(samples, tokenizer)
        >>> len(dataset)
        10
        >>> dataset[0].keys()
        dict_keys(['prompt', 'state_file', 'tl_id', 'metadata'])
    """
    # 构建 GRPO 训练格式
    grpo_data = []

    for sample in samples:
        # 构建 messages 格式
        messages = [
            {"role": "system", "content": get_system_prompt()},
            {"role": "user", "content": sample["prompt"]}
        ]

        # 应用 chat template 并添加 generation prompt
        # add_generation_prompt=True 会在末尾添加 <think> 标签
        formatted_prompt = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True
        )

        # 提取元数据
        metadata = sample.get("metadata", {})
        tl_id = metadata.get("tl_id", "unknown")

        # 构建 GRPO 数据项
        grpo_item = {
            "prompt": formatted_prompt,
            "state_file": sample["state_file"],
            "tl_id": tl_id,
            "metadata": metadata,
        }

        grpo_data.append(grpo_item)

    # 转换为 HuggingFace Dataset
    dataset = Dataset.from_list(grpo_data)

    return dataset


if __name__ == "__main__":
    # 自测试
    print("Testing data_loader module...")

    # 测试 get_system_prompt
    prompt = get_system_prompt()
    assert "交通信号配时优化" in prompt
    assert "<think>" in prompt
    print("✓ get_system_prompt works")

    print("✅ data_loader module tests passed!")
