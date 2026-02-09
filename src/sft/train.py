# -*- coding: utf-8 -*-
"""
SFT Training Script for TSC-CYCLE

使用 unsloth 对 Qwen3-4B-Base 进行 LoRA 微调，学习 <think>...<think><solution>...<solution> 输出格式。
"""

import argparse
import json
import os
from pathlib import Path

import torch
from datasets import Dataset
from unsloth import FastLanguageModel
from trl import SFTTrainer, SFTConfig


def load_config(config_path: str) -> dict:
    """从配置文件加载超参数和路径配置"""
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    return config


def setup_model(config: dict):
    """
    加载 Qwen3-4B-Base 模型并配置 LoRA

    参考 qwen3_(4b)_grpo.py 第 9-33 行
    """
    model_config = config["training"]["sft"]["model"]
    seed = config["training"]["sft"].get("seed", 3407)

    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=model_config["model_name"],
        max_seq_length=model_config["max_seq_length"],
        load_in_4bit=model_config["load_in_4bit"],
        fast_inference=True,
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
    """
    设置自定义 chat template

    参考 qwen3_(4b)_grpo.py 第 41-81 行，但适配项目标签格式：
    - reasoning_start = "<think>"
    - reasoning_end = "<think>"  (注意：与 start 相同，这是项目约定)
    - solution_start = "<solution>"
    - solution_end = "<solution>"  (同理)
    """
    reasoning_start = "<think>"
    reasoning_end = "<think>"  # 项目约定：开标签重复作为关闭标签
    solution_start = "<solution>"
    solution_end = "<solution>"  # 同理

    system_prompt = "你是交通信号配时优化专家。"

    # 创建 chat template（参考 qwen3_(4b)_grpo.py 第 59-81 行）
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

    # 替换占位符为实际值
    chat_template = chat_template\
        .replace("'{system_prompt}'", f"'{system_prompt}'")\
        .replace("'{reasoning_start}'", f"'{reasoning_start}'")

    tokenizer.chat_template = chat_template

    return tokenizer


def load_sft_data(data_path: str, tokenizer, max_seq_length: int):
    """
    加载 SFT 训练数据

    数据格式: outputs/sft/sft_train.jsonl
    每行: {"messages": [{"role": "system", "content": "..."}, ...]}

    参考 qwen3_(4b)_grpo.py 第 146-149 行：过滤超过 max_seq_length/2 的样本
    """
    data_list = []

    with open(data_path, 'r', encoding='utf-8') as f:
        for line in f:
            data = json.loads(line.strip())
            data_list.append(data)

    # 转换为 HuggingFace Dataset 并计算长度
    dataset_dict = {"messages": [d["messages"] for d in data_list]}
    dataset = Dataset.from_dict(dataset_dict)

    # 计算 tokenized 长度并过滤
    def compute_length(examples):
        lengths = []
        for messages in examples["messages"]:
            tokens = tokenizer.apply_chat_template(messages, tokenize=True)
            lengths.append(len(tokens))
        return {"length": lengths}

    dataset = dataset.map(compute_length, batched=True)

    # 过滤掉超过 max_seq_length/2 的样本（参考 qwen3_(4b)_grpo.py 第 146-149 行）
    original_count = len(dataset)
    dataset = dataset.filter(lambda x: x["length"] <= max_seq_length / 2)
    filtered_count = len(dataset)

    print(f"[数据加载] 原始样本数: {original_count}, 过滤后: {filtered_count}")

    # 转换为 text 格式
    def format_to_text(examples):
        texts = []
        for messages in examples["messages"]:
            text = tokenizer.apply_chat_template(messages, tokenize=False)
            texts.append(text)
        return {"text": texts}

    dataset = dataset.map(format_to_text, batched=True)

    return dataset


def train_model(model, tokenizer, dataset, config: dict):
    """
    训练模型

    参考 qwen3_(4b)_grpo.py 第 161-182 行
    """
    sft_config = config["training"]["sft"]

    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=dataset,
        args=SFTConfig(
            dataset_text_field=sft_config["dataset_text_field"],
            per_device_train_batch_size=sft_config["per_device_train_batch_size"],
            gradient_accumulation_steps=sft_config["gradient_accumulation_steps"],
            warmup_steps=sft_config["warmup_steps"],
            num_train_epochs=sft_config["num_train_epochs"],
            learning_rate=sft_config["learning_rate"],
            logging_steps=sft_config["logging_steps"],
            optim=sft_config["optim"],
            weight_decay=sft_config["weight_decay"],
            lr_scheduler_type=sft_config["lr_scheduler_type"],
            seed=sft_config["seed"],
            report_to=sft_config["report_to"],
            save_steps=sft_config.get("save_steps", 100),
            save_total_limit=sft_config.get("save_total_limit", 3),
            bf16=sft_config.get("bf16", True),
            output_dir="outputs/sft/checkpoints",
        ),
    )

    print("[开始训练]")
    trainer.train()
    print("[训练完成]")

    return model


def save_model(model, tokenizer, output_path: str):
    """
    合并 LoRA 并保存完整模型

    参考 qwen3_(4b)_grpo.py 第 564-566 行
    使用 save_pretrained_merged 保存 merged_16bit 格式
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
    parser = argparse.ArgumentParser(description="SFT Training for TSC-CYCLE")
    parser.add_argument(
        "--config",
        type=str,
        default="config/config.json",
        help="配置文件路径"
    )
    args = parser.parse_args()

    # 1. 加载配置
    print(f"[配置] 加载配置文件: {args.config}")
    config = load_config(args.config)

    # 2. 设置模型
    print("[模型] 加载 Qwen3-4B-Base 并配置 LoRA")
    model, tokenizer = setup_model(config)

    # 3. 设置 chat template
    print("[模板] 设置自定义 chat template")
    tokenizer = setup_chat_template(tokenizer)

    # 4. 加载数据
    sft_data_path = os.path.join(config["paths"]["sft_data_dir"], "sft_train.jsonl")
    max_seq_length = config["training"]["sft"]["model"]["max_seq_length"]
    print(f"[数据] 加载 SFT 数据: {sft_data_path}")
    dataset = load_sft_data(sft_data_path, tokenizer, max_seq_length)

    # 5. 训练
    model = train_model(model, tokenizer, dataset, config)

    # 6. 保存模型
    output_path = config["paths"]["sft_output"]
    save_model(model, tokenizer, output_path)

    print("=" * 50)
    print("[完成] SFT 训练流程完成")
    print(f"[模型输出] {output_path}")
    print("=" * 50)


if __name__ == "__main__":
    main()
