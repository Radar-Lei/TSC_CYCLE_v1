# -*- coding: utf-8 -*-
"""
SFT Training Script for TSC-CYCLE

使用 unsloth 对 GLM-4.7-Flash 进行 LoRA 微调，学习 <start_working_out>...<end_working_out><SOLUTION>...</SOLUTION> 输出格式。
"""

import argparse
import json
import os
import shutil
from pathlib import Path

import torch
from datasets import Dataset
from unsloth import FastLanguageModel
from trl import SFTTrainer, SFTConfig


def ensure_model(config: dict):
    """确保模型可用。

    支持两种模式：
    1. 本地模型路径（如 model/Qwen3-4B-Base）
    2. HuggingFace repo ID（如 unsloth/Qwen3-32B-unsloth-bnb-4bit），由 Unsloth 自动下载
    """
    model_config = config["training"]["sft"]["model"]
    model_path = model_config["model_name"]
    model_id = model_config.get("model_id", "")

    # HuggingFace repo ID 格式（包含 /），Unsloth 会自动处理下载
    if "/" in model_path:
        print(f"[模型] 使用 HuggingFace 模型: {model_path}（Unsloth 自动下载）")
        return model_path

    if os.path.isdir(model_path) and os.path.exists(os.path.join(model_path, "config.json")):
        print(f"[模型] 本地模型已存在: {model_path}")
        return model_path

    if not model_id:
        raise RuntimeError(f"本地模型 {model_path} 不存在且未配置 model_id，无法下载")

    print(f"[模型] 本地模型不存在，从 ModelScope 下载: {model_id}")
    from modelscope import snapshot_download
    snapshot_download(model_id, local_dir=model_path)
    print(f"[模型] 下载完成: {model_path}")
    return model_path


def load_config(config_path: str) -> dict:
    """从配置文件加载超参数和路径配置"""
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    return config


def setup_model(config: dict):
    """
    加载模型并配置 LoRA

    支持 GLM-4.7-Flash 模型。
    GLM 使用类似 LLaMA 的 attention 架构，target_modules 兼容。

    Returns:
        tuple: (model, tokenizer, is_peft) - is_peft 表示是否使用 Hugging Face PEFT
    """
    model_config = config["training"]["sft"]["model"]
    seed = config["training"]["sft"].get("seed", 3407)

    # 检测是否为 GLM 模型
    is_glm = "GLM" in model_config["model_name"]
    if is_glm:
        print("[模型] 检测到 GLM 模型，使用标准加载方式")

    # 尝试使用 Unsloth 加载（对大多数模型有效）
    try:
        model, tokenizer = FastLanguageModel.from_pretrained(
            model_name=model_config["model_name"],
            max_seq_length=model_config["max_seq_length"],
            load_in_4bit=model_config["load_in_4bit"],
            fast_inference=model_config.get("fast_inference", False),
            max_lora_rank=model_config["lora_rank"],
            gpu_memory_utilization=model_config["gpu_memory_utilization"],
            trust_remote_code=True,
        )
    except Exception as e:
        # 如果 Unsloth 加载失败，尝试使用 Hugging Face 原生方式
        print(f"[警告] Unsloth 加载失败: {e}")
        print("[回退] 尝试使用 Hugging Face 原生加载 + PEFT...")
        from transformers import AutoModelForCausalLM, AutoTokenizer
        from peft import get_peft_model, LoraConfig, TaskType

        tokenizer = AutoTokenizer.from_pretrained(
            model_config["model_name"],
            trust_remote_code=True
        )
        model = AutoModelForCausalLM.from_pretrained(
            model_config["model_name"],
            torch_dtype=torch.bfloat16,
            device_map="auto",
            trust_remote_code=True
        )

        # 配置 LoRA
        lora_config = LoraConfig(
            task_type=TaskType.CAUSAL_LM,
            r=model_config["lora_rank"],
            lora_alpha=model_config["lora_alpha"],
            target_modules=model_config["target_modules"],
            lora_dropout=0,
            bias="none",
        )
        model = get_peft_model(model, lora_config)
        print("[回退] Hugging Face 原生加载成功")
        return model, tokenizer, True  # 返回 True 表示使用 Hugging Face PEFT

    # 使用 Unsloth 的 PEFT 配置
    model = FastLanguageModel.get_peft_model(
        model,
        r=model_config["lora_rank"],
        target_modules=model_config["target_modules"],
        lora_alpha=model_config["lora_alpha"],
        lora_dropout=0,
        bias="none",
        use_gradient_checkpointing="unsloth",
        random_state=seed,
    )

    return model, tokenizer


def patch_thinking_tags(tokenizer):
    """
    最小化修改 GLM 原生 chat template：将 <think></think> 替换为项目自定义标签
    
    GLM-4.7-Flash 原生使用 <think></think> 作为思考标签。
    为了与项目的 <start_working_out>/<end_working_out> 标签一致，
    只做最小化修改，保留其余 GLM 原生格式（角色标记等）。
    """
    if tokenizer.chat_template:
        tokenizer.chat_template = (
            tokenizer.chat_template
            .replace("<think>", "<start_working_out>")
            .replace("</think>", "<end_working_out>")
        )
        print("[模板] 已将 GLM 原生 <think> 标签替换为 <start_working_out>")
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


def train_model(model, tokenizer, dataset, config: dict, is_peft: bool = False):
    """
    训练模型

    参考 qwen3_(4b)_grpo.py 第 161-182 行

    Args:
        is_peft: 如果为 True，使用 Hugging Face 原生 SFTTrainer
    """
    sft_config = config["training"]["sft"]
    sft_output = config["paths"].get("sft_output", "outputs/sft/model")
    checkpoints_dir = os.path.join(os.path.dirname(sft_output), "checkpoints")

    if is_peft:
        # Hugging Face 原生 SFTTrainer
        from transformers import TrainingArguments, Trainer
        trainer = Trainer(
            model=model,
            args=TrainingArguments(
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
                output_dir=checkpoints_dir,
                gradient_checkpointing=False,
                remove_unused_columns=False,
            ),
            train_dataset=dataset,
        )
    else:
        # Unsloth SFTTrainer
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
                output_dir=checkpoints_dir,
                gradient_checkpointing=False,
            ),
        )

    # 只训练 assistant 的响应部分，忽略 user 输入的损失
    # 参考 glm_flash_a100(80gb).py 行 176-180
    from unsloth.chat_templates import train_on_responses_only
    trainer = train_on_responses_only(
        trainer,
        # Qwen3 chat template 使用 <|im_start|>user / <|im_start|>assistant 边界
        instruction_part="<|im_start|>user\n",
        response_part="<|im_start|>assistant\n",
    )
    print("[训练] 已配置 train_on_responses_only - 仅在 assistant 响应上计算损失")

    print("[开始训练]")
    trainer.train()
    print("[训练完成]")

    return model


def save_model(model, tokenizer, output_path: str, config: dict, is_peft: bool = False):
    """
    保存合并后的完整模型（用于后续 GGUF 转换）
    """
    os.makedirs(output_path, exist_ok=True)

    print(f"[保存模型] 保存合并后的完整模型到 {output_path}")

    if is_peft:
        # HF PEFT 路径
        merged_model = model
        if hasattr(model, "merge_and_unload"):
            print("[保存模型] 检测到 LoRA adapter，正在合并到基座模型...")
            merged_model = model.merge_and_unload()
        merged_model.save_pretrained(output_path)
        tokenizer.save_pretrained(output_path)
    else:
        # Unsloth 路径：使用 save_pretrained_merged 正确处理 4-bit 量化模型
        print("[保存模型] 使用 Unsloth save_pretrained_merged 合并 LoRA...")
        model.save_pretrained_merged(
            output_path,
            tokenizer,
            save_method="merged_16bit",
        )

    # 兜底补齐 config.json（极端情况下 save_pretrained 未写出）
    base_model_config = os.path.join(config["training"]["sft"]["model"]["model_name"], "config.json")
    output_model_config = os.path.join(output_path, "config.json")
    if not os.path.exists(output_model_config) and os.path.exists(base_model_config):
        shutil.copy2(base_model_config, output_model_config)
        print(f"[保存模型] 已补充基座 config.json: {output_model_config}")

    print("[保存完成] 完整模型已保存（可直接用于 GGUF 转换）")


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

    # 2. 确保模型存在（不存在则从 ModelScope 下载）
    ensure_model(config)

    # 3. 设置模型
    print("[模型] 加载 GLM-4.7-Flash 并配置 LoRA")
    result = setup_model(config)
    if len(result) == 3:
        model, tokenizer, is_peft = result
    else:
        model, tokenizer = result
        is_peft = False

    # 4. 修改 chat template（将 GLM 原生 <think> 替换为项目标签）
    print("[模板] 修改 chat template (think -> start_working_out)")
    tokenizer = patch_thinking_tags(tokenizer)

    # 5. 加载数据
    sft_data_path = os.path.join(config["paths"]["sft_data_dir"], "sft_train.jsonl")
    max_seq_length = config["training"]["sft"]["model"]["max_seq_length"]
    print(f"[数据] 加载 SFT 数据: {sft_data_path}")
    dataset = load_sft_data(sft_data_path, tokenizer, max_seq_length)

    # 5.5 验证 chat template 格式（打印一条样本）
    if len(dataset) > 0:
        print("\n[验证] Chat template 格式示例（前 500 字符）:")
        sample_text = dataset[0]["text"]
        print(sample_text[:500])
        print("...\n")

    # 6. 训练
    model = train_model(model, tokenizer, dataset, config, is_peft=is_peft)

    # 7. 保存模型
    output_path = config["paths"]["sft_output"]
    save_model(model, tokenizer, output_path, config, is_peft=is_peft)

    print("=" * 50)
    print("[完成] SFT 训练流程完成")
    print(f"[模型输出] {output_path}")
    print("=" * 50)


if __name__ == "__main__":
    main()
