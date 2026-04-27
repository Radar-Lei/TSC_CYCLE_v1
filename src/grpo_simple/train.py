#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简化版 GRPO 训练入口。

与 `src/grpo/train.py` 的区别：
- 不加载 baseline
- 不运行 SUMO reward
- 使用 `src/grpo_simple/rewards.py` 中的饱和度比例 reward
- 默认读取 `outputs/grpo_simple/grpo_train.jsonl`
"""

import argparse
import json
import os
from typing import Tuple

import torch
from datasets import Dataset
from unsloth import FastLanguageModel
from trl import GRPOConfig, GRPOTrainer



def load_config(config_path: str) -> dict:
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def ensure_model(config: dict) -> str:
    model_config = config["training"]["grpo_simple"]["model"]
    model_path = model_config["model_name"]

    if os.path.isdir(model_path) and os.path.exists(os.path.join(model_path, "config.json")):
        print(f"[模型] SFT 模型已存在: {model_path}")
        return model_path

    raise RuntimeError(
        f"SFT 模型不存在: {model_path}\n"
        f"简化版 GRPO 训练需要先完成 SFT 训练。"
    )


def setup_model(config: dict):
    model_config = config["training"]["grpo_simple"]["model"]
    seed = config["training"]["grpo_simple"].get("seed", 3407)

    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=model_config["model_name"],
        max_seq_length=model_config["max_seq_length"],
        dtype=torch.float16,
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
    reasoning_start = "<start_working_out>"

    system_prompt = (
        "你是交通信号配时优化专家。\n"
        "请认真分析预测得到的下个周期各个相位的交通状态，给出下个周期的配时方案，并给出你的推理过程。\n"
        "将推理过程放在 <start_working_out> 和 <end_working_out> 之间。\n"
        "然后,将你的最终方案放在 <SOLUTION> 和 </SOLUTION> 之间。"
    )

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

    chat_template = chat_template\
        .replace("'{system_prompt}'", f"'{system_prompt}'")\
        .replace("'{reasoning_start}'", f"'{reasoning_start}'")
    tokenizer.chat_template = chat_template
    return tokenizer


def load_grpo_data(data_path: str, tokenizer) -> Tuple[Dataset, int]:
    data_list = []
    with open(data_path, "r", encoding="utf-8") as f:
        for line in f:
            data_list.append(json.loads(line.strip()))

    # 在构建 Dataset 之前计算 prompt 长度，避免 HF Dataset 将
    # list-of-dicts 转为 dict-of-lists 导致 apply_chat_template 失败。
    # 注意：apply_chat_template(tokenize=True) 可能返回 Encoding 对象而非 token ID 列表，
    # 因此先渲染为字符串再用 tokenizer.encode 获取实际 token 数
    max_prompt_length = 0
    for item in data_list:
        rendered = tokenizer.apply_chat_template(
            item["prompt"],
            tokenize=False,
            add_generation_prompt=True,
        )
        tokens = tokenizer.encode(rendered)
        max_prompt_length = max(max_prompt_length, len(tokens))

    dataset = Dataset.from_dict(
        {
            "prompt": [item["prompt"] for item in data_list],
            "state_file": [item["metadata"].get("state_file") for item in data_list],
            "tl_id": [item["metadata"].get("tl_id") for item in data_list],
        }
    )

    print(f"[数据加载] 样本数: {len(dataset)}, 最大 prompt 长度: {max_prompt_length}")
    return dataset, max_prompt_length


def train_model(model, tokenizer, dataset, config: dict, reward_funcs: list, max_prompt_len: int):
    grpo_config = config["training"]["grpo_simple"]
    checkpoints_dir = config["paths"].get("grpo_simple_checkpoints", "outputs/grpo_simple/checkpoints")

    max_prompt_length = max_prompt_len + 1
    max_completion_length = grpo_config["model"]["max_seq_length"] - max_prompt_length
    print(
        f"[GRPO Simple 配置] max_prompt_length={max_prompt_length}, "
        f"max_completion_length={max_completion_length}"
    )

    training_args = GRPOConfig(
        temperature=grpo_config["temperature"],
        num_generations=grpo_config["num_generations"],
        beta=grpo_config["kl_coef"],
        max_prompt_length=max_prompt_length,
        max_completion_length=max_completion_length,
        learning_rate=grpo_config["learning_rate"],
        weight_decay=grpo_config["weight_decay"],
        warmup_ratio=grpo_config["warmup_ratio"],
        lr_scheduler_type=grpo_config["lr_scheduler_type"],
        optim=grpo_config["optim"],
        per_device_train_batch_size=grpo_config["per_device_train_batch_size"],
        gradient_accumulation_steps=grpo_config["gradient_accumulation_steps"],
        max_steps=grpo_config.get("max_steps", -1),
        num_train_epochs=grpo_config["num_train_epochs"],
        logging_steps=grpo_config["logging_steps"],
        save_steps=grpo_config["save_steps"],
        save_total_limit=grpo_config["save_total_limit"],
        report_to=grpo_config["report_to"],
        output_dir=checkpoints_dir,
        fp16=True,
        bf16=False,
        seed=grpo_config.get("seed", 3407),
    )

    # Unsloth/PEFT 兼容：GRPOTrainer 初始化时访问 model.warnings_issued，
    # 但 PEFT 模型未暴露此属性，需手动补上
    if not hasattr(model, "warnings_issued"):
        model.warnings_issued = {}

    trainer = GRPOTrainer(
        model=model,
        processing_class=tokenizer,
        reward_funcs=reward_funcs,
        args=training_args,
        train_dataset=dataset,
    )

    # 自动检测最新 checkpoint 并恢复
    resume_ckpt = None
    if os.path.isdir(checkpoints_dir):
        ckpts = sorted(
            [d for d in os.listdir(checkpoints_dir) if d.startswith("checkpoint-")],
            key=lambda x: int(x.split("-")[1]),
        )
        if ckpts:
            resume_ckpt = os.path.join(checkpoints_dir, ckpts[-1])
            print(f"[恢复训练] 从 {resume_ckpt} 恢复")

    print("[开始训练] 简化版 GRPO 训练...")
    trainer.train(resume_from_checkpoint=resume_ckpt)
    print("[训练完成]")
    return model


def save_model(model, tokenizer, output_path: str):
    os.makedirs(output_path, exist_ok=True)
    print(f"[保存模型] 合并 LoRA 并保存到 {output_path}")
    model.save_pretrained_merged(
        output_path,
        tokenizer,
        save_method="merged_16bit",
    )
    print("[保存完成]")


def main():
    parser = argparse.ArgumentParser(description="Simplified GRPO Training for TSC-CYCLE")
    parser.add_argument(
        "--config",
        type=str,
        default="config/config.json",
        help="配置文件路径",
    )
    args = parser.parse_args()

    print(f"[配置] 加载配置文件: {args.config}")
    config = load_config(args.config)

    ensure_model(config)

    print("[模型] 加载 SFT 模型并配置 LoRA")
    model, tokenizer = setup_model(config)

    print("[模板] 设置自定义 chat template")
    tokenizer = setup_chat_template(tokenizer)

    from src.grpo_simple.rewards import (
        check_constraints,
        init_rewards,
        match_format_approximately,
        match_format_exactly,
        saturation_proportional_reward,
        think_length_reward,
    )

    print("[Rewards] 初始化简化版 reward")
    init_rewards(args.config)
    reward_cfg = config["training"]["grpo_simple"]["reward"]
    print(
        "[Rewards] saturation_target_score={score}, near_miss_penalty={near}, "
        "exact_hit_bonus={exact}, off_by_one_bonus={off1}, clip_bonus={clip_b}, clip_penalty={clip_p}".format(
            score=reward_cfg["saturation_target_score"],
            near=reward_cfg.get("saturation_near_miss_penalty", 0.0),
            exact=reward_cfg.get("saturation_exact_hit_bonus", 0.0),
            off1=reward_cfg.get("saturation_off_by_one_bonus", 0.0),
            clip_b=reward_cfg.get("clip_sensitive_bonus", 0.0),
            clip_p=reward_cfg.get("clip_sensitive_penalty", 0.0),
        )
    )
    print(
        "[训练配置] epochs={epochs}, max_steps={steps}, lr={lr}, num_generations={gens}, kl_coef={kl}".format(
            epochs=config["training"]["grpo_simple"]["num_train_epochs"],
            steps=config["training"]["grpo_simple"].get("max_steps", -1),
            lr=config["training"]["grpo_simple"]["learning_rate"],
            gens=config["training"]["grpo_simple"]["num_generations"],
            kl=config["training"]["grpo_simple"]["kl_coef"],
        )
    )

    data_dir = config["paths"].get("grpo_simple_data_dir", "outputs/grpo_simple")
    data_path = os.path.join(data_dir, "grpo_train.jsonl")
    print(f"[数据] 加载 GRPO 数据: {data_path}")
    dataset, max_prompt_len = load_grpo_data(data_path, tokenizer)

    reward_funcs = [
        match_format_exactly,
        match_format_approximately,
        check_constraints,
        saturation_proportional_reward,
        think_length_reward,
    ]

    model = train_model(model, tokenizer, dataset, config, reward_funcs, max_prompt_len)

    output_path = config["paths"].get("grpo_simple_output", "outputs/grpo_simple/model")
    save_model(model, tokenizer, output_path)

    print("=" * 50)
    print("[完成] 简化版 GRPO 训练流程完成")
    print(f"[模型输出] {output_path}")
    print("=" * 50)


if __name__ == "__main__":
    main()
