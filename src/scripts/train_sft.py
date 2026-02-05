#!/usr/bin/env python3
"""SFT 训练脚本 - 让 Qwen3-4B 学会输出格式

完整训练流程:
1. 加载模型 (Qwen3-4B + LoRA)
2. 准备数据 (从 JSONL 加载)
3. 执行训练 (300 steps)
4. 保存模型 (LoRA adapter)
5. 验证输出格式
"""

import argparse
import json
from pathlib import Path


def load_config(config_path):
    """从 JSON 文件加载配置"""
    if config_path and Path(config_path).exists():
        with open(config_path) as f:
            return json.load(f)
    return {}


def get_nested(config, *keys, default=None):
    """获取嵌套配置值"""
    value = config
    for key in keys:
        if isinstance(value, dict):
            value = value.get(key)
        else:
            return default
    return value if value is not None else default


def main():
    parser = argparse.ArgumentParser(description="Train SFT model")
    parser.add_argument("--config", help="JSON 配置文件路径")
    parser.add_argument("--data-dir", default=None, help="训练数据目录")
    parser.add_argument("--output-dir", default=None, help="输出目录")
    parser.add_argument("--max-steps", type=int, default=None, help="训练步数")
    parser.add_argument("--validate-every", type=int, default=None, help="每 N 步验证格式")
    args = parser.parse_args()

    # 加载 JSON 配置
    config = load_config(args.config)

    # 应用配置优先级: 命令行 > config.json > 代码默认值
    if args.data_dir is None:
        args.data_dir = get_nested(config, "paths", "data_dir", default="data/sft")
    if args.output_dir is None:
        args.output_dir = get_nested(config, "paths", "sft_output", default="outputs/sft")
    if args.max_steps is None:
        args.max_steps = get_nested(config, "training", "sft", "max_steps", default=300)
    if args.validate_every is None:
        args.validate_every = get_nested(config, "training", "sft", "validate_every", default=50)

    print("=" * 50)
    print("SFT Training - Format Learning")
    print("=" * 50)

    # 1. 加载模型
    print("\n[1/4] Loading model...")
    from src.sft.model_loader import load_model_for_sft, SFTConfig
    model, tokenizer = load_model_for_sft()
    print("  ✓ Model loaded: Qwen3-4B + LoRA (rank=32, alpha=64)")

    # 打印可训练参数
    from src.sft.model_loader import print_trainable_params
    print_trainable_params(model)

    # 2. 准备数据
    print("\n[2/4] Preparing dataset...")
    from src.sft.trainer import prepare_dataset
    train_dataset = prepare_dataset(f"{args.data_dir}/train.jsonl", tokenizer)
    print(f"  ✓ Training examples: {len(train_dataset)}")

    # 打印第一条示例的长度
    first_text = train_dataset[0]["text"]
    print(f"  ✓ First example length: {len(first_text)} chars")

    # 3. 训练
    print("\n[3/4] Training...")
    from src.sft.trainer import SFTTrainerWrapper, TrainingArgs
    training_args = TrainingArgs(
        output_dir=args.output_dir,
        max_steps=args.max_steps,
    )
    trainer = SFTTrainerWrapper(model, tokenizer, train_dataset, training_args)

    print(f"  Starting training for {args.max_steps} steps...")
    print(f"  Learning rate: {training_args.learning_rate}")
    print(f"  Optimizer: {training_args.optim}")
    print(f"  Logging every {training_args.logging_steps} steps")
    print(f"  Saving checkpoints every {training_args.save_steps} steps")
    print("")

    result = trainer.train()

    print(f"\n  ✓ Training completed!")
    print(f"  Final loss: {result.training_loss:.4f}")

    # 4. 保存模型
    print("\n[4/4] Saving model...")
    final_path = f"{args.output_dir}/final"
    trainer.save_model(final_path)
    print(f"  ✓ Model saved to: {final_path}")

    # 列出保存的文件
    final_dir = Path(final_path)
    if final_dir.exists():
        saved_files = list(final_dir.glob("*"))
        print(f"  Saved files:")
        for f in sorted(saved_files):
            file_size = f.stat().st_size
            if file_size > 1024 * 1024:
                size_str = f"{file_size / (1024 * 1024):.1f} MB"
            else:
                size_str = f"{file_size / 1024:.1f} KB"
            print(f"    - {f.name} ({size_str})")

    # 5. 验证输出格式
    print("\n[Validation] Testing model output...")
    from src.sft.trainer import validate_model_output
    from src.sft.format_validator import validate_format

    test_input = json.dumps({
        "prediction": {
            "phase_waits": [
                {
                    "phase_id": 1,
                    "pred_saturation": 1.5,
                    "min_green": 20,
                    "max_green": 40,
                    "capacity": 30
                },
                {
                    "phase_id": 2,
                    "pred_saturation": 0.3,
                    "min_green": 10,
                    "max_green": 30,
                    "capacity": 25
                }
            ]
        }
    })

    output, is_valid = validate_model_output(model, tokenizer, test_input)

    print(f"  Format valid: {is_valid}")
    if is_valid:
        print("  ✓ Model successfully learned output format!")
    else:
        print("  ✗ Format validation failed (may need more training)")

    # 打印部分输出
    if len(output) > 500:
        print(f"  Sample output:\n{output[:500]}...")
    else:
        print(f"  Sample output:\n{output}")

    print("\n" + "=" * 50)
    print("Training Complete!")
    print("=" * 50)
    print(f"\nNext steps:")
    print(f"  1. Check training logs in {args.output_dir}")
    print(f"  2. Test model with different inputs")
    print(f"  3. Proceed to Phase 4 (GRPO training)")


if __name__ == "__main__":
    main()
