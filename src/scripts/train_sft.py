#!/usr/bin/env python3
"""SFT 训练脚本 - 让 Qwen3-4B 学会输出格式

完整训练流程:
1. 加载模型 (Qwen3-4B + LoRA)
2. 准备数据 (从 JSONL 加载并 train/val 分割)
3. 执行训练 (300 steps)
4. 保存模型 (LoRA adapter)
5. 验证输出格式
"""

import argparse
import json
import logging
from pathlib import Path
import sys


def setup_logging(output_dir):
    """配置日志输出到终端和文件

    Args:
        output_dir: 输出目录
    """
    # 确保输出目录存在
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    # 配置日志格式
    log_format = '%(asctime)s - %(levelname)s - %(message)s'

    # 配置根 logger
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # 清除现有 handlers
    logger.handlers.clear()

    # 终端输出 handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter(log_format))
    logger.addHandler(console_handler)

    # 文件输出 handler
    log_file = Path(output_dir) / "training.log"
    file_handler = logging.FileHandler(log_file, mode='a', encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter(log_format))
    logger.addHandler(file_handler)

    logging.info(f"Logging to file: {log_file}")


def find_latest_checkpoint(output_dir):
    """查找最新的 checkpoint

    Args:
        output_dir: 输出目录

    Returns:
        最新 checkpoint 路径,如果没有则返回 None
    """
    output_path = Path(output_dir)
    if not output_path.exists():
        return None

    checkpoints = list(output_path.glob("checkpoint-*"))
    if not checkpoints:
        return None

    # 按 checkpoint 编号排序
    checkpoints.sort(key=lambda p: int(p.name.split("-")[1]))
    return str(checkpoints[-1])


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
    parser.add_argument("--val-ratio", type=float, default=0.1, help="验证集比例")
    parser.add_argument("--resume-from", default=None, help="从 checkpoint 恢复训练")
    args = parser.parse_args()

    # 加载 JSON 配置
    config = load_config(args.config)

    # 应用配置优先级: 命令行 > config.json > 代码默认值
    if args.data_dir is None:
        args.data_dir = get_nested(config, "paths", "data_dir", default="outputs/sft")
    if args.output_dir is None:
        args.output_dir = get_nested(config, "paths", "sft_output", default="outputs/sft")
    if args.max_steps is None:
        args.max_steps = get_nested(config, "training", "sft", "max_steps", default=300)

    # 配置日志输出
    setup_logging(args.output_dir)

    logging.info("=" * 50)
    logging.info("SFT Training - Format Learning")
    logging.info("=" * 50)
    logging.info(f"Data directory: {args.data_dir}")
    logging.info(f"Output directory: {args.output_dir}")
    logging.info(f"Max steps: {args.max_steps}")
    logging.info(f"Validation ratio: {args.val_ratio}")
    if args.resume_from:
        logging.info(f"Resume from: {args.resume_from}")

    # 检查 resume checkpoint
    resume_from_checkpoint = None
    if args.resume_from:
        if Path(args.resume_from).exists():
            resume_from_checkpoint = args.resume_from
            logging.info(f"Will resume from checkpoint: {resume_from_checkpoint}")
        else:
            logging.error(f"Checkpoint not found: {args.resume_from}")
            sys.exit(1)
    else:
        # 检测是否存在 checkpoint（但不自动恢复）
        latest_checkpoint = find_latest_checkpoint(args.output_dir)
        if latest_checkpoint:
            logging.info(f"Found existing checkpoint: {latest_checkpoint}")
            logging.info(f"To resume training, use: --resume-from {latest_checkpoint}")

    # 1. 加载模型
    logging.info("\n[1/4] Loading model...")
    from src.sft.model_loader import load_model_for_sft, SFTConfig
    model, tokenizer = load_model_for_sft()
    logging.info("Model loaded: Qwen3-4B + LoRA (rank=32, alpha=64)")

    # 打印可训练参数
    from src.sft.model_loader import print_trainable_params
    print_trainable_params(model)

    # 2. 准备数据
    logging.info("\n[2/4] Preparing dataset...")
    from src.sft.trainer import prepare_dataset, split_dataset

    train_data_path = f"{args.data_dir}/train.jsonl"
    logging.info(f"Loading data from: {train_data_path}")

    full_dataset = prepare_dataset(train_data_path, tokenizer)
    logging.info(f"Total examples: {len(full_dataset)}")

    # 划分 train/val
    train_dataset, val_dataset = split_dataset(full_dataset, val_ratio=args.val_ratio)
    logging.info(f"Train examples: {len(train_dataset)}")
    logging.info(f"Val examples: {len(val_dataset)}")

    # 打印第一条示例的长度
    first_text = train_dataset[0]["text"]
    logging.info(f"First example length: {len(first_text)} chars")

    # 3. 训练
    logging.info("\n[3/4] Training...")
    from src.sft.trainer import SFTTrainerWrapper, TrainingArgs
    training_args = TrainingArgs(
        output_dir=args.output_dir,
        max_steps=args.max_steps,
    )
    trainer = SFTTrainerWrapper(
        model, tokenizer, train_dataset, eval_dataset=val_dataset, args=training_args
    )

    logging.info(f"Starting training for {args.max_steps} steps...")
    logging.info(f"Learning rate: {training_args.learning_rate}")
    logging.info(f"Optimizer: {training_args.optim}")
    logging.info(f"BF16: {training_args.bf16}")
    logging.info(f"Logging every {training_args.logging_steps} steps")
    logging.info(f"Saving checkpoints every {training_args.save_steps} steps")
    logging.info(f"Keeping {training_args.save_total_limit} recent checkpoints")
    logging.info("")

    result = trainer.train(resume_from_checkpoint=resume_from_checkpoint)

    logging.info(f"\nTraining completed!")
    logging.info(f"Final loss: {result.training_loss:.4f}")

    # 4. 保存模型
    logging.info("\n[4/4] Saving model...")
    final_path = f"{args.output_dir}/final"
    trainer.save_model(final_path)
    logging.info(f"Model saved to: {final_path}")

    # 列出保存的文件
    final_dir = Path(final_path)
    if final_dir.exists():
        saved_files = list(final_dir.glob("*"))
        logging.info(f"Saved files:")
        for f in sorted(saved_files):
            file_size = f.stat().st_size
            if file_size > 1024 * 1024:
                size_str = f"{file_size / (1024 * 1024):.1f} MB"
            else:
                size_str = f"{file_size / 1024:.1f} KB"
            logging.info(f"  - {f.name} ({size_str})")

    # 5. 验证输出格式
    logging.info("\n[Validation] Testing model output...")
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

    logging.info(f"Format valid: {is_valid}")
    if is_valid:
        logging.info("Model successfully learned output format!")
    else:
        logging.warning("Format validation failed (may need more training)")

    # 打印部分输出
    if len(output) > 500:
        logging.info(f"Sample output:\n{output[:500]}...")
    else:
        logging.info(f"Sample output:\n{output}")

    logging.info("\n" + "=" * 50)
    logging.info("Training Complete!")
    logging.info("=" * 50)
    logging.info(f"\nNext steps:")
    logging.info(f"  1. Check training logs in {args.output_dir}/training.log")
    logging.info(f"  2. Test model with different inputs")
    logging.info(f"  3. Proceed to Phase 4 (GRPO training)")


if __name__ == "__main__":
    main()
