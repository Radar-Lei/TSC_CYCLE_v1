#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GRPO Training Script for TSC-CYCLE

Uses unsloth + LoRA on SFT-trained model with GRPO reinforcement learning.
Reward functions integrate SUMO simulation feedback for signal timing optimization.
"""

import argparse
import json
import os
from pathlib import Path
from typing import Tuple

import torch
from datasets import Dataset
from unsloth import FastLanguageModel
from trl import GRPOConfig, GRPOTrainer


def load_config(config_path: str) -> dict:
    """Load hyperparameters from config file."""
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    return config


def ensure_model(config: dict) -> str:
    """Ensure SFT model exists locally.

    Unlike SFT training, GRPO requires the SFT model to exist.
    Does NOT download from modelscope - SFT model must be pre-trained.
    """
    model_config = config["training"]["grpo"]["model"]
    model_path = model_config["model_name"]

    if os.path.isdir(model_path) and os.path.exists(os.path.join(model_path, "config.json")):
        print(f"[模型] SFT 模型已存在: {model_path}")
        return model_path

    raise RuntimeError(
        f"SFT 模型不存在: {model_path}\n"
        f"GRPO 训练需要先完成 SFT 训练。请运行 ./docker/sft_train.sh"
    )


def setup_model(config: dict):
    """Load SFT model and configure LoRA for GRPO training.

    Similar to SFT setup but:
    - Loads from outputs/sft/model (not base model)
    - Uses fast_inference=False (no vLLM per user decision)
    """
    model_config = config["training"]["grpo"]["model"]
    seed = config["training"]["grpo"].get("seed", 3407)

    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=model_config["model_name"],
        max_seq_length=model_config["max_seq_length"],
        load_in_4bit=model_config["load_in_4bit"],
        fast_inference=model_config.get("fast_inference", False),
        max_lora_rank=model_config["lora_rank"],
        gpu_memory_utilization=model_config["gpu_memory_utilization"],
    )

    model = FastLanguageModel.get_peft_model(
        model,
        r=model_config["lora_rank"],
        target_modules=model_config["target_modules"],
        lora_alpha=model_config["lora_alpha"],
        use_gradient_checkpointing="unsloth",
        random_state=seed,
    )

    return model, tokenizer


def setup_chat_template(tokenizer):
    """Set up chat template - IDENTICAL to src/sft/train.py.

    Tags:
        - reasoning_start = "<start_working_out>"
        - reasoning_end = "<end_working_out>"
        - solution_start = "<SOLUTION>"
        - solution_end = "</SOLUTION>"
    """
    reasoning_start = "<start_working_out>"
    reasoning_end = "<end_working_out>"
    solution_start = "<SOLUTION>"
    solution_end = "</SOLUTION>"

    system_prompt = (
        "你是交通信号配时优化专家。\n"
        "请认真分析预测得到的下个周期各个相位的交通状态，给出下个周期的配时方案，并给出你的推理过程。\n"
        "将推理过程放在 <start_working_out> 和 <end_working_out> 之间。\n"
        "然后,将你的最终方案放在 <SOLUTION> 和 </SOLUTION> 之间。"
    )

    # Chat template (identical to sft/train.py)
    chat_template = \
        "{% if messages[0]['role'] == 'system' %}"\
            "{{ messages[0]['content'] + eos_token }}"\
            "{% set loop_messages = messages[1:] %}"\
        "{% else %}"\
            "{{ '{system_prompt}' + eos_token }}"\
            "{% set loop_messages = messages %}"\
        "{% endif %}"\
        "{% for message in loop_messages %}"\
            "{% if message['role'] == 'user' %}"\
                "{{ message['content'] }}"\
            "{% elif message['role'] == 'assistant' %}"\
                "{{ message['content'] + eos_token }}"\
            "{% endif %}"\
        "{% endfor %}"\
        "{% if add_generation_prompt %}{{ '{reasoning_start}' }}"\
        "{% endif %}"

    # Replace placeholders
    chat_template = chat_template\
        .replace("'{system_prompt}'", f"'{system_prompt}'")\
        .replace("'{reasoning_start}'", f"'{reasoning_start}'")

    tokenizer.chat_template = chat_template

    return tokenizer


def load_grpo_data(data_path: str, tokenizer, max_seq_length: int) -> Tuple[Dataset, int]:
    """Load GRPO training data.

    Format: outputs/grpo/grpo_train.jsonl
    Each line: {"prompt": [...], "metadata": {"state_file": "...", "tl_id": "..."}}

    Returns:
        dataset: HuggingFace Dataset with columns [prompt, state_file, tl_id]
        max_prompt_length: Maximum prompt length after filtering
    """
    data_list = []

    with open(data_path, 'r', encoding='utf-8') as f:
        for line in f:
            data = json.loads(line.strip())
            data_list.append(data)

    # Convert to Dataset
    dataset_dict = {
        "prompt": [d["prompt"] for d in data_list],
        "state_file": [d["metadata"]["state_file"] for d in data_list],
        "tl_id": [d["metadata"]["tl_id"] for d in data_list],
    }
    dataset = Dataset.from_dict(dataset_dict)

    # Compute prompt lengths for filtering (top 90% quantile)
    def compute_prompt_length(examples):
        lengths = []
        for prompt in examples["prompt"]:
            tokens = tokenizer.apply_chat_template(prompt, tokenize=True, add_generation_prompt=True)
            lengths.append(len(tokens))
        return {"prompt_length": lengths}

    dataset = dataset.map(compute_prompt_length, batched=True)

    # Filter by 90% quantile (reference: qwen3_(4b)_grpo.py lines 398-411)
    import numpy as np
    quantile_90 = np.quantile(dataset["prompt_length"], 0.9)
    original_count = len(dataset)
    dataset = dataset.filter(lambda x: x["prompt_length"] <= quantile_90)
    filtered_count = len(dataset)

    print(f"[数据加载] 原始样本数: {original_count}, 90%分位数过滤后: {filtered_count}")

    # Compute max prompt length
    max_prompt_length = max(dataset["prompt_length"])

    return dataset, max_prompt_length


def train_model(model, tokenizer, dataset, config: dict, reward_funcs: list, max_prompt_len: int):
    """Train model with GRPO.

    Key differences from SFT:
        - Uses GRPOConfig instead of SFTConfig
        - Passes reward_funcs to GRPOTrainer
        - No vLLM (use_vllm=False is implicit in fast_inference=False)
    """
    grpo_config = config["training"]["grpo"]

    max_prompt_length = max_prompt_len + 1
    max_completion_length = grpo_config["model"]["max_seq_length"] - max_prompt_length

    print(f"[GRPO 配置] max_prompt_length={max_prompt_length}, max_completion_length={max_completion_length}")

    training_args = GRPOConfig(
        # Core GRPO parameters
        temperature=grpo_config["temperature"],
        num_generations=grpo_config["num_generations"],
        beta=grpo_config["kl_coef"],

        # Sequence length
        max_prompt_length=max_prompt_length,
        max_completion_length=max_completion_length,

        # Optimization
        learning_rate=grpo_config["learning_rate"],
        weight_decay=grpo_config["weight_decay"],
        warmup_ratio=grpo_config["warmup_ratio"],
        lr_scheduler_type=grpo_config["lr_scheduler_type"],
        optim=grpo_config["optim"],

        # Training control
        per_device_train_batch_size=grpo_config["per_device_train_batch_size"],
        gradient_accumulation_steps=grpo_config["gradient_accumulation_steps"],
        num_train_epochs=grpo_config["num_train_epochs"],

        # Logging and checkpointing
        logging_steps=grpo_config["logging_steps"],
        save_steps=grpo_config["save_steps"],
        save_total_limit=grpo_config["save_total_limit"],
        report_to=grpo_config["report_to"],
        output_dir="outputs/grpo/checkpoints",

        # Hardware
        bf16=grpo_config.get("bf16", True),
        seed=grpo_config.get("seed", 3407),
    )

    trainer = GRPOTrainer(
        model=model,
        processing_class=tokenizer,
        reward_funcs=reward_funcs,
        args=training_args,
        train_dataset=dataset,
    )

    print("[开始训练] GRPO 训练...")
    trainer.train()
    print("[训练完成]")

    return model


def save_model(model, tokenizer, output_path: str):
    """Merge LoRA and save complete model.

    Same as SFT: save as merged_16bit to outputs/grpo/model.
    """
    os.makedirs(output_path, exist_ok=True)

    print(f"[保存模型] 合并 LoRA 并保存到 {output_path}")
    model.save_pretrained_merged(
        output_path,
        tokenizer,
        save_method="merged_16bit",
    )
    print("[保存完成]")


def main():
    parser = argparse.ArgumentParser(description="GRPO Training for TSC-CYCLE")
    parser.add_argument(
        "--config",
        type=str,
        default="config/config.json",
        help="配置文件路径"
    )
    args = parser.parse_args()

    # 1. Load config
    print(f"[配置] 加载配置文件: {args.config}")
    config = load_config(args.config)

    # 2. Ensure SFT model exists
    ensure_model(config)

    # 3. Setup model
    print("[模型] 加载 SFT 模型并配置 LoRA")
    model, tokenizer = setup_model(config)

    # 4. Setup chat template
    print("[模板] 设置自定义 chat template")
    tokenizer = setup_chat_template(tokenizer)

    # 5. Initialize reward functions
    from src.grpo.rewards import init_rewards
    baseline_path = config["paths"]["grpo_baseline"]
    print(f"[Rewards] 初始化 reward 函数，baseline: {baseline_path}")
    init_rewards(args.config, baseline_path)

    # 6. Load data
    data_path = os.path.join(config["paths"]["grpo_data_dir"], "grpo_train.jsonl")
    max_seq_length = config["training"]["grpo"]["model"]["max_seq_length"]
    print(f"[数据] 加载 GRPO 数据: {data_path}")
    dataset, max_prompt_len = load_grpo_data(data_path, tokenizer, max_seq_length)

    # 7. Import reward functions
    from src.grpo.rewards import (
        match_format_exactly,
        match_format_approximately,
        check_constraints,
        sumo_simulation_reward,
        think_length_reward,
    )

    reward_funcs = [
        match_format_exactly,
        match_format_approximately,
        check_constraints,
        sumo_simulation_reward,
        think_length_reward,
    ]

    # 8. Train
    model = train_model(model, tokenizer, dataset, config, reward_funcs, max_prompt_len)

    # 9. Save
    output_path = config["paths"]["grpo_output"]
    save_model(model, tokenizer, output_path)

    print("=" * 50)
    print("[完成] GRPO 训练流程完成")
    print(f"[模型输出] {output_path}")
    print("=" * 50)


if __name__ == "__main__":
    main()
