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
import os
from pathlib import Path

from src.grpo.trainer import GRPOConfig, load_sft_model, create_grpo_trainer
from src.grpo.data_loader import load_training_data, prepare_grpo_dataset
from src.grpo.format_reward import (
    match_format_exactly,
    match_format_approximately,
    check_phase_validity,
)
from src.grpo.simulation_reward import compute_simulation_reward


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="GRPO training for traffic signal cycle optimization"
    )

    # 模型和数据路径
    parser.add_argument(
        "--sft-adapter",
        type=str,
        default="outputs/sft/final",
        help="SFT adapter 路径 (默认: outputs/sft/final)"
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        default="data/training",
        help="训练数据目录 (默认: data/training)"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="outputs/grpo",
        help="输出目录 (默认: outputs/grpo)"
    )

    # 训练参数
    parser.add_argument(
        "--max-steps",
        type=int,
        default=100,
        help="最大训练步数 (默认: 100)"
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

    # SUMO 配置
    parser.add_argument(
        "--net-file",
        type=str,
        default="sumo_simulation/environments/chengdu/chengdu.net.xml",
        help="SUMO 网络文件路径"
    )
    parser.add_argument(
        "--sumocfg",
        type=str,
        default="sumo_simulation/environments/chengdu/chengdu.sumocfg",
        help="SUMO 配置文件路径"
    )
    parser.add_argument(
        "--cycle-duration",
        type=int,
        default=90,
        help="评估周期时长 (秒, 默认: 90)"
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=4,
        help="并行 SUMO 评估的 worker 数量 (默认: 4)"
    )

    return parser.parse_args()


def main():
    """主训练流程"""
    args = parse_args()

    print("=" * 60)
    print("GRPO Training for Traffic Signal Cycle Optimization")
    print("=" * 60)
    print()

    # 1. 加载 SFT 模型
    print(f"[1/6] Loading SFT model from {args.sft_adapter}...")
    try:
        model, tokenizer = load_sft_model(args.sft_adapter)
        print(f"  ✓ Model loaded successfully")
    except Exception as e:
        print(f"  ✗ Failed to load model: {e}")
        return 1

    # 2. 加载训练数据
    print(f"\n[2/6] Loading training data from {args.data_dir}...")
    try:
        samples = load_training_data(args.data_dir, limit=args.data_limit)
        print(f"  ✓ Loaded {len(samples)} training samples")

        # 准备 GRPO 数据集
        dataset = prepare_grpo_dataset(samples, tokenizer)
        print(f"  ✓ Prepared GRPO dataset: {len(dataset)} samples")

    except FileNotFoundError as e:
        print(f"  ✗ Training data not found: {e}")
        print(f"  Hint: Run Phase 2 data generation first")
        return 1
    except Exception as e:
        print(f"  ✗ Failed to load data: {e}")
        return 1

    # 3. 配置奖励函数
    print(f"\n[3/6] Configuring reward functions...")
    reward_funcs = [
        match_format_exactly,
        match_format_approximately,
        check_phase_validity,
    ]
    print(f"  ✓ Format rewards: match_format_exactly, match_format_approximately")
    print(f"  ✓ Phase validity: check_phase_validity")

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
    else:
        print(f"  ! Simulation reward disabled (--disable-simulation)")

    # 4. 创建训练器
    print(f"\n[4/6] Creating GRPO trainer...")
    config = GRPOConfig(
        max_steps=args.max_steps,
        output_dir=args.output_dir,
    )
    print(f"  Configuration:")
    print(f"    - max_steps: {config.max_steps}")
    print(f"    - learning_rate: {config.learning_rate}")
    print(f"    - num_generations: {config.num_generations}")
    print(f"    - gradient_accumulation_steps: {config.gradient_accumulation_steps}")
    print(f"    - output_dir: {config.output_dir}")

    try:
        trainer = create_grpo_trainer(model, tokenizer, dataset, reward_funcs, config)
        print(f"  ✓ Trainer created")
    except Exception as e:
        print(f"  ✗ Failed to create trainer: {e}")
        return 1

    # 5. 训练
    print(f"\n[5/6] Starting GRPO training...")
    print(f"  Total samples: {len(dataset)}")
    print(f"  Training steps: {config.max_steps}")
    print()

    try:
        result = trainer.train()
        print()
        print(f"  ✓ Training completed")
        print(f"    - Total steps: {result.global_step}")
        print(f"    - Final loss: {result.training_loss:.4f}")
    except Exception as e:
        print(f"  ✗ Training failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

    # 6. 保存模型
    print(f"\n[6/6] Saving model to {args.output_dir}/final...")
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
    except Exception as e:
        print(f"  ✗ Failed to save model: {e}")
        return 1

    # 完成
    print()
    print("=" * 60)
    print("✅ GRPO Training Complete!")
    print("=" * 60)
    print(f"Model saved to: {output_path}")
    print()

    return 0


if __name__ == "__main__":
    exit(main())
