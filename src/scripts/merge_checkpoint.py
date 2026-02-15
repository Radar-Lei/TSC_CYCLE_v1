#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Checkpoint Merge Script for TSC-CYCLE

Merges LoRA adapter from GRPO checkpoint with SFT base model,
producing a complete standalone model ready for GGUF conversion.

Usage:
    python -m src.scripts.merge_checkpoint
    python -m src.scripts.merge_checkpoint --checkpoint checkpoint-5000
    python -m src.scripts.merge_checkpoint --config config/config.json
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

import torch


def load_config(config_path: str) -> dict:
    """Load configuration from JSON file."""
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def find_latest_checkpoint(checkpoints_dir: str) -> str:
    """Find the latest checkpoint directory by step number."""
    if not os.path.isdir(checkpoints_dir):
        raise FileNotFoundError(f"Checkpoints directory not found: {checkpoints_dir}")

    checkpoints = []
    pattern = re.compile(r'checkpoint-(\d+)')

    for name in os.listdir(checkpoints_dir):
        match = pattern.match(name)
        if match:
            step = int(match.group(1))
            adapter_path = os.path.join(checkpoints_dir, name, "adapter_model.safetensors")
            if os.path.exists(adapter_path):
                checkpoints.append((step, name))
            else:
                print(f"[跳过] {name} - 无 adapter_model.safetensors")

    if not checkpoints:
        raise FileNotFoundError(
            f"No valid checkpoints found in {checkpoints_dir}\n"
            "Expected directories named 'checkpoint-XXXX' containing adapter_model.safetensors"
        )

    checkpoints.sort(reverse=True)
    latest_step, latest_name = checkpoints[0]

    return os.path.join(checkpoints_dir, latest_name)


def merge_checkpoint(
    base_model_path: str,
    checkpoint_path: str,
    output_path: str,
    max_seq_length: int = 2048,
    lora_rank: int = 32,
) -> None:
    """
    Merge LoRA adapter from checkpoint with base model.

    Args:
        base_model_path: Path to SFT base model (outputs/sft/model)
        checkpoint_path: Path to checkpoint directory containing adapter
        output_path: Path to save merged model
        max_seq_length: Maximum sequence length
        lora_rank: LoRA rank (must match training config)
    """
    print(f"[基础模型] {base_model_path}")
    print(f"[Checkpoint] {checkpoint_path}")
    print(f"[输出路径] {output_path}")
    print()

    # Import unsloth here to show errors clearly
    from unsloth import FastLanguageModel

    # Load base model
    print("[加载] 正在加载基础模型...")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=base_model_path,
        max_seq_length=max_seq_length,
        load_in_4bit=False,  # Load in 16bit for merge
        fast_inference=False,
        max_lora_rank=lora_rank,
        gpu_memory_utilization=0.9,
    )
    print("[加载] 基础模型加载完成")

    # Load LoRA adapter
    print("[合并] 正在加载 LoRA adapter...")
    from peft import PeftModel

    model = PeftModel.from_pretrained(model, checkpoint_path)
    print("[合并] LoRA adapter 加载完成")

    # Merge and save
    print(f"[保存] 正在合并并保存到 {output_path}...")
    os.makedirs(output_path, exist_ok=True)

    # Merge LoRA weights into base model
    merged_model = model.merge_and_unload()

    # Save merged model
    merged_model.save_pretrained(output_path)
    tokenizer.save_pretrained(output_path)

    print("[保存] 模型合并完成")
    print()

    # Verify output
    safetensor_files = list(Path(output_path).glob("*.safetensors"))
    print(f"[验证] 输出目录: {output_path}")
    print(f"[验证] Safetensors 文件数: {len(safetensor_files)}")
    for f in safetensor_files:
        size_mb = f.stat().st_size / (1024 * 1024)
        print(f"  - {f.name}: {size_mb:.1f} MB")


def main():
    parser = argparse.ArgumentParser(
        description="Merge GRPO checkpoint with SFT base model",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python -m src.scripts.merge_checkpoint
    python -m src.scripts.merge_checkpoint --checkpoint checkpoint-5000
    python -m src.scripts.merge_checkpoint --output outputs/grpo/model_v2
        """
    )
    parser.add_argument(
        "--config",
        default="config/config.json",
        help="Path to config file (default: config/config.json)"
    )
    parser.add_argument(
        "--checkpoint",
        help="Specific checkpoint name (e.g., checkpoint-5000). Default: latest"
    )
    parser.add_argument(
        "--output",
        help="Output directory for merged model. Default: from config (outputs/grpo/model)"
    )
    parser.add_argument(
        "--base-model",
        help="Base model path. Default: from config (outputs/sft/model)"
    )

    args = parser.parse_args()

    # Load config
    config = load_config(args.config)

    # Resolve paths
    checkpoints_dir = os.path.join(config["paths"]["grpo_data_dir"], "checkpoints")
    base_model_path = args.base_model or config["training"]["grpo"]["model"]["model_name"]
    output_path = args.output or config["paths"]["grpo_output"]

    # Find checkpoint
    if args.checkpoint:
        checkpoint_path = os.path.join(checkpoints_dir, args.checkpoint)
        if not os.path.isdir(checkpoint_path):
            print(f"[错误] Checkpoint 不存在: {checkpoint_path}")
            sys.exit(1)
    else:
        print(f"[查找] 在 {checkpoints_dir} 中搜索最新 checkpoint...")
        checkpoint_path = find_latest_checkpoint(checkpoints_dir)
        print(f"[找到] 最新 checkpoint: {os.path.basename(checkpoint_path)}")

    # Verify checkpoint has adapter
    adapter_file = os.path.join(checkpoint_path, "adapter_model.safetensors")
    if not os.path.exists(adapter_file):
        print(f"[错误] Checkpoint 中未找到 adapter: {adapter_file}")
        sys.exit(1)

    # Verify base model exists
    if not os.path.isdir(base_model_path):
        print(f"[错误] 基础模型不存在: {base_model_path}")
        print("请先运行 ./docker/sft_train.sh 完成 SFT 训练")
        sys.exit(1)

    print("=" * 50)
    print("GRPO Checkpoint 合并工具")
    print("=" * 50)

    # Get LoRA config from training config
    lora_rank = config["training"]["grpo"]["model"]["lora_rank"]
    max_seq_length = config["training"]["grpo"]["model"]["max_seq_length"]

    # Merge
    merge_checkpoint(
        base_model_path=base_model_path,
        checkpoint_path=checkpoint_path,
        output_path=output_path,
        max_seq_length=max_seq_length,
        lora_rank=lora_rank,
    )

    print("=" * 50)
    print("[完成] 模型合并成功")
    print(f"[输出] {output_path}")
    print()
    print("下一步: 运行 ./docker/convert_gguf.sh 转换为 GGUF 格式")
    print("=" * 50)


if __name__ == "__main__":
    main()
