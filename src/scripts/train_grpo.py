"""GRPO 训练入口脚本

组装完整的 GRPO 训练流程:
1. 加载 SFT 模型
2. 加载训练数据
3. 配置奖励函数
4. 创建训练器
5. 执行训练
6. 保存模型

使用方法:
    python -m src.scripts.train_grpo --max-steps 100

Docker 执行:
    docker run --rm \\
      --gpus all \\
      --shm-size=32GB \\
      --user $(id -u):$(id -g) \\
      -v "$(pwd):/home/samuel/SCU_TSC:rw" \\
      -w /home/samuel/SCU_TSC \\
      -e HF_HOME=/home/samuel/SCU_TSC/model \\
      -e MODELSCOPE_CACHE=/home/samuel/SCU_TSC/model \\
      -e UNSLOTH_USE_MODELSCOPE=1 \\
      -e SUMO_HOME=/usr/share/sumo \\
      --entrypoint python3 \\
      qwen3-tsc-grpo:latest \\
      -m src.scripts.train_grpo --max-steps 100
"""

import argparse
import json
import logging
import os
from pathlib import Path

from src.grpo.trainer import GRPOConfig, load_sft_model, create_grpo_trainer
from src.grpo.data_loader import load_training_data, prepare_grpo_dataset
from src.grpo.format_reward import (
    graded_format_reward,
    check_phase_validity,
)
from src.grpo.simulation_reward import compute_simulation_reward


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


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="GRPO training for traffic signal cycle optimization"
    )

    # 配置文件
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="JSON 配置文件路径"
    )

    # 模型和数据路径
    parser.add_argument(
        "--sft-adapter",
        type=str,
        default=None,
        help="SFT adapter 路径 (默认: outputs/sft/final)"
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        default=None,
        help="训练数据目录 (默认: data/training)"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="输出目录 (默认: outputs/grpo)"
    )

    # 训练参数
    parser.add_argument(
        "--max-steps",
        type=int,
        default=None,
        help="最大训练步数 (默认: 100)"
    )
    parser.add_argument(
        "--num-generations",
        type=int,
        default=None,
        help="每个 prompt 生成的样本数 (默认: 4)"
    )
    parser.add_argument(
        "--data-limit",
        type=int,
        default=None,
        help="限制训练数据量 (默认: None, 使用全部数据)"
    )

    # 奖励函数配置
    parser.add_argument(
        "--disable-simulation",
        action="store_true",
        help="禁用仿真评估,仅使用格式奖励 (用于调试)"
    )

    # 训练恢复
    parser.add_argument(
        "--resume-from",
        type=str,
        default=None,
        help="从 checkpoint 恢复训练 (e.g., outputs/grpo/checkpoint-50)"
    )

    # SUMO 配置
    parser.add_argument(
        "--net-file",
        type=str,
        default=None,
        help="SUMO 网络文件路径"
    )
    parser.add_argument(
        "--sumocfg",
        type=str,
        default=None,
        help="SUMO 配置文件路径"
    )
    parser.add_argument(
        "--cycle-duration",
        type=int,
        default=None,
        help="评估周期时长 (秒, 默认: 90)"
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=None,
        help="并行 SUMO 评估的 worker 数量 (默认: 4)"
    )

    return parser.parse_args()


def apply_config(args):
    """应用配置优先级: 命令行 > config.json > 代码默认值"""
    config = load_config(args.config)

    # 路径配置
    if args.sft_adapter is None:
        sft_output = get_nested(config, "paths", "sft_output", default="outputs/sft")
        args.sft_adapter = f"{sft_output}/final"
    if args.data_dir is None:
        args.data_dir = get_nested(config, "paths", "data_dir", default="outputs/training")
    if args.output_dir is None:
        args.output_dir = get_nested(config, "paths", "grpo_output", default="outputs/grpo")
    if args.net_file is None:
        args.net_file = get_nested(
            config, "paths", "net_file",
            default="sumo_simulation/environments/chengdu/chengdu.net.xml"
        )
    if args.sumocfg is None:
        args.sumocfg = get_nested(
            config, "paths", "sumocfg",
            default="sumo_simulation/environments/chengdu/chengdu.sumocfg"
        )

    # 训练配置
    if args.max_steps is None:
        args.max_steps = get_nested(config, "training", "grpo", "max_steps", default=100)
    if args.num_generations is None:
        args.num_generations = get_nested(config, "training", "grpo", "num_generations", default=4)

    # 仿真配置
    if args.cycle_duration is None:
        args.cycle_duration = get_nested(config, "simulation", "cycle_duration", default=90)
    if args.max_workers is None:
        args.max_workers = get_nested(config, "simulation", "parallel_workers", default=4)

    return args


def main():
    """主训练流程"""
    args = parse_args()

    # 应用配置优先级: 命令行 > config.json > 代码默认值
    args = apply_config(args)

    # 配置日志
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    log_file = output_dir / "training.log"

    # 配置 logging: 同时输出到文件和终端
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )

    logging.info("=" * 60)
    logging.info("GRPO Training for Traffic Signal Cycle Optimization")
    logging.info("=" * 60)
    logging.info("")

    print("=" * 60)
    print("GRPO Training for Traffic Signal Cycle Optimization")
    print("=" * 60)
    print()

    # 1. 加载 SFT 模型
    print(f"[1/6] Loading SFT model from {args.sft_adapter}...")
    logging.info(f"[1/6] Loading SFT model from {args.sft_adapter}...")

    # 检查 SFT adapter 是否存在
    sft_path = Path(args.sft_adapter)
    if not sft_path.exists():
        error_msg = f"SFT adapter not found: {args.sft_adapter}\n" \
                    f"Please run SFT training first (Phase 3, Plan 01)\n" \
                    f"Expected path: outputs/sft/final/"
        print(f"  ✗ {error_msg}")
        logging.error(error_msg)
        return 1

    try:
        model, tokenizer = load_sft_model(args.sft_adapter)
        print(f"  ✓ Model loaded successfully")
        logging.info(f"  ✓ Model loaded successfully")
    except Exception as e:
        print(f"  ✗ Failed to load model: {e}")
        logging.error(f"  ✗ Failed to load model: {e}")
        return 1

    # 2. 加载训练数据
    print(f"\n[2/6] Loading training data from {args.data_dir}...")
    logging.info(f"[2/6] Loading training data from {args.data_dir}...")
    try:
        samples = load_training_data(args.data_dir, limit=args.data_limit)
        print(f"  ✓ Loaded {len(samples)} training samples")
        logging.info(f"  ✓ Loaded {len(samples)} training samples")

        # 准备 GRPO 数据集
        dataset = prepare_grpo_dataset(samples, tokenizer)
        print(f"  ✓ Prepared GRPO dataset: {len(dataset)} samples")
        logging.info(f"  ✓ Prepared GRPO dataset: {len(dataset)} samples")

    except FileNotFoundError as e:
        print(f"  ✗ Training data not found: {e}")
        print(f"  Hint: Run Phase 2 data generation first")
        logging.error(f"  ✗ Training data not found: {e}")
        return 1
    except Exception as e:
        print(f"  ✗ Failed to load data: {e}")
        logging.error(f"  ✗ Failed to load data: {e}")
        return 1

    # 3. 配置奖励函数
    print(f"\n[3/6] Configuring reward functions...")
    logging.info(f"[3/6] Configuring reward functions...")
    reward_funcs = [
        graded_format_reward,
        check_phase_validity,
    ]
    print(f"  ✓ Format rewards: graded_format_reward (3-level grading)")
    print(f"  ✓ Phase validity: check_phase_validity")
    logging.info(f"  ✓ Format rewards: graded_format_reward (3-level grading)")
    logging.info(f"  ✓ Phase validity: check_phase_validity")

    if not args.disable_simulation:
        # 构建仿真评估配置
        phase_config = {
            "net_file": args.net_file,
            "sumocfg": args.sumocfg,
            "cycle_duration": args.cycle_duration,
            "max_workers": args.max_workers,
        }

        # 添加仿真奖励函数
        # 注意: compute_simulation_reward 需要额外参数,通过 **kwargs 传递
        reward_funcs.append(
            lambda completions, **kwargs: compute_simulation_reward(
                completions,
                phase_config=phase_config,
                **kwargs
            )
        )
        print(f"  ✓ Simulation reward: compute_simulation_reward")
        print(f"    - Net file: {args.net_file}")
        print(f"    - Cycle duration: {args.cycle_duration}s")
        print(f"    - Max workers: {args.max_workers}")
        logging.info(f"  ✓ Simulation reward: compute_simulation_reward")
        logging.info(f"    - Net file: {args.net_file}")
        logging.info(f"    - Cycle duration: {args.cycle_duration}s")
        logging.info(f"    - Max workers: {args.max_workers}")
    else:
        print(f"  ! Simulation reward disabled (--disable-simulation)")
        logging.warning(f"  ! Simulation reward disabled (--disable-simulation)")

    # 4. 创建训练器
    print(f"\n[4/6] Creating GRPO trainer...")
    logging.info(f"[4/6] Creating GRPO trainer...")
    config = GRPOConfig(
        max_steps=args.max_steps,
        num_generations=args.num_generations,
        output_dir=args.output_dir,
    )
    print(f"  Configuration:")
    print(f"    - max_steps: {config.max_steps}")
    print(f"    - learning_rate: {config.learning_rate}")
    print(f"    - num_generations: {config.num_generations}")
    print(f"    - gradient_accumulation_steps: {config.gradient_accumulation_steps}")
    print(f"    - output_dir: {config.output_dir}")
    logging.info(f"  Configuration:")
    logging.info(f"    - max_steps: {config.max_steps}")
    logging.info(f"    - learning_rate: {config.learning_rate}")
    logging.info(f"    - num_generations: {config.num_generations}")
    logging.info(f"    - gradient_accumulation_steps: {config.gradient_accumulation_steps}")
    logging.info(f"    - output_dir: {config.output_dir}")

    try:
        trainer = create_grpo_trainer(model, tokenizer, dataset, reward_funcs, config)
        print(f"  ✓ Trainer created")
        logging.info(f"  ✓ Trainer created")
    except Exception as e:
        print(f"  ✗ Failed to create trainer: {e}")
        logging.error(f"  ✗ Failed to create trainer: {e}")
        return 1

    # 5. 训练
    print(f"\n[5/6] Starting GRPO training...")
    logging.info(f"[5/6] Starting GRPO training...")
    print(f"  Total samples: {len(dataset)}")
    print(f"  Training steps: {config.max_steps}")
    logging.info(f"  Total samples: {len(dataset)}")
    logging.info(f"  Training steps: {config.max_steps}")

    # 检查是否有 checkpoint 可以恢复
    if args.resume_from:
        print(f"  Resuming from checkpoint: {args.resume_from}")
        logging.info(f"  Resuming from checkpoint: {args.resume_from}")
    else:
        # 检查 output_dir 中是否有 checkpoint
        checkpoint_dirs = list(output_dir.glob("checkpoint-*"))
        if checkpoint_dirs:
            print(f"  Found {len(checkpoint_dirs)} checkpoint(s) in {output_dir}")
            print(f"  Use --resume-from to resume from a checkpoint")
            logging.info(f"  Found {len(checkpoint_dirs)} checkpoint(s) in {output_dir}")

    print()

    try:
        if args.resume_from:
            result = trainer.train(resume_from_checkpoint=args.resume_from)
        else:
            result = trainer.train()
        print()
        print(f"  ✓ Training completed")
        print(f"    - Total steps: {result.global_step}")
        print(f"    - Final loss: {result.training_loss:.4f}")
        logging.info(f"  ✓ Training completed")
        logging.info(f"    - Total steps: {result.global_step}")
        logging.info(f"    - Final loss: {result.training_loss:.4f}")
    except Exception as e:
        print(f"  ✗ Training failed: {e}")
        logging.error(f"  ✗ Training failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

    # 6. 保存模型
    print(f"\n[6/6] Saving model to {args.output_dir}/final...")
    logging.info(f"[6/6] Saving model to {args.output_dir}/final...")
    try:
        output_path = Path(args.output_dir) / "final"
        output_path.mkdir(parents=True, exist_ok=True)

        # 保存 LoRA adapter
        model.save_pretrained(str(output_path))
        tokenizer.save_pretrained(str(output_path))

        print(f"  ✓ Model saved to {output_path}")
        print(f"    - adapter_model.safetensors")
        print(f"    - adapter_config.json")
        print(f"    - tokenizer_config.json")
        logging.info(f"  ✓ Model saved to {output_path}")
        logging.info(f"    - adapter_model.safetensors")
        logging.info(f"    - adapter_config.json")
        logging.info(f"    - tokenizer_config.json")
    except Exception as e:
        print(f"  ✗ Failed to save model: {e}")
        logging.error(f"  ✗ Failed to save model: {e}")
        return 1

    # 完成
    print()
    print("=" * 60)
    print("✅ GRPO Training Complete!")
    print("=" * 60)
    print(f"Model saved to: {output_path}")
    print(f"Training log: {log_file}")
    print()

    logging.info("=" * 60)
    logging.info("✅ GRPO Training Complete!")
    logging.info("=" * 60)
    logging.info(f"Model saved to: {output_path}")
    logging.info(f"Training log: {log_file}")

    return 0


if __name__ == "__main__":
    exit(main())
