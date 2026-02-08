"""GRPO 训练入口脚本

组装完整的 GRPO 训练流程:
1. 加载模型 (基础模型或 SFT 模型)
2. 加载训练数据
3. 配置奖励函数
4. 创建训练器
5. 执行训练
6. 保存模型

使用方法:
    # 直接使用 Thinking 模型（跳过 SFT）:
    python -m src.scripts.train_grpo --model-name unsloth/Qwen3-4B-Thinking-2507

    # 或使用 SFT 模型:
    python -m src.scripts.train_grpo --sft-adapter outputs/sft/model/final

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

from src.grpo.trainer import GRPOConfig, load_sft_model, load_base_model, create_grpo_trainer
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
        "--model-name",
        type=str,
        default=None,
        help="基础模型名称，直接加载（跳过 SFT）。默认: unsloth/Qwen3-4B-Thinking-2507"
    )
    parser.add_argument(
        "--sft-adapter",
        type=str,
        default=None,
        help="SFT adapter 路径 (默认: outputs/sft/model/final)"
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
    if args.model_name is None:
        args.model_name = get_nested(config, "training", "grpo", "model_name", default=None)
    if args.sft_adapter is None:
        sft_output = get_nested(config, "paths", "sft_output", default="outputs/sft/model")
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

    # 训练配置 — 完整读取 config.json 中所有 GRPO 参数
    grpo = lambda key, default: get_nested(config, "training", "grpo", key, default=default)

    if args.max_steps is None:
        args.max_steps = grpo("max_steps", 100)
    if args.num_generations is None:
        args.num_generations = grpo("num_generations", 4)

    # 以下参数仅从 config.json 读取（无命令行覆盖）
    args.max_epochs = grpo("max_epochs", 1)
    args.per_device_train_batch_size = grpo("per_device_train_batch_size", 1)
    args.gradient_accumulation_steps = grpo("gradient_accumulation_steps", 4)
    args.learning_rate = grpo("learning_rate", 5e-6)
    args.warmup_ratio = grpo("warmup_ratio", 0.1)
    args.lr_scheduler_type = grpo("lr_scheduler_type", "linear")
    args.optim = grpo("optim", "adamw_8bit")
    args.weight_decay = grpo("weight_decay", 0.001)
    args.temperature = grpo("temperature", 0.9)
    args.max_prompt_length = grpo("max_prompt_length", 512)
    args.max_completion_length = grpo("max_completion_length", 1024)
    args.save_steps = grpo("save_steps", 50)
    args.logging_steps = grpo("logging_steps", 1)
    args.bf16 = grpo("bf16", True)
    args.save_total_limit = grpo("save_total_limit", 3)
    args.seed = grpo("seed", 3407)

    # LoRA 和模型参数
    args.lora_r = grpo("lora_r", 32)
    args.lora_alpha = grpo("lora_alpha", 64)
    args.max_seq_length = grpo("max_seq_length", 2048)

    # generation_config 覆盖参数
    gen = lambda key, default: get_nested(config, "training", "grpo", "generation", key, default=default)
    args.gen_max_length = gen("max_length", 2048)
    args.gen_temperature = gen("temperature", 0.9)
    args.gen_top_p = gen("top_p", 0.95)

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

    # generation_config 参数字典
    generation_config = {
        "max_length": args.gen_max_length,
        "temperature": args.gen_temperature,
        "top_p": args.gen_top_p,
    }

    # 1. 加载模型
    if args.model_name:
        # 直接加载基础模型（跳过 SFT）
        print(f"[1/6] Loading base model: {args.model_name}...")
        logging.info(f"[1/6] Loading base model: {args.model_name}...")
        try:
            model, tokenizer = load_base_model(
                args.model_name,
                lora_r=args.lora_r,
                lora_alpha=args.lora_alpha,
                max_seq_length=args.max_seq_length,
                generation_config=generation_config,
            )
            print(f"  ✓ Model loaded (skip SFT)")
            logging.info(f"  ✓ Model loaded (skip SFT)")
        except Exception as e:
            print(f"  ✗ Failed to load model: {e}")
            logging.error(f"  ✗ Failed to load model: {e}")
            return 1
    else:
        # 从 SFT adapter 加载（原有路径）
        print(f"[1/6] Loading SFT model from {args.sft_adapter}...")
        logging.info(f"[1/6] Loading SFT model from {args.sft_adapter}...")
        sft_path = Path(args.sft_adapter)
        if not sft_path.exists():
            error_msg = (f"SFT adapter not found: {args.sft_adapter}\n"
                        f"Please run SFT training first, or use --model-name to load a base model directly")
            print(f"  ✗ {error_msg}")
            logging.error(error_msg)
            return 1
        try:
            model, tokenizer = load_sft_model(
                args.sft_adapter,
                max_seq_length=args.max_seq_length,
                generation_config=generation_config,
            )
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
        max_epochs=args.max_epochs,
        per_device_train_batch_size=args.per_device_train_batch_size,
        num_generations=args.num_generations,
        gradient_accumulation_steps=args.gradient_accumulation_steps,
        learning_rate=args.learning_rate,
        warmup_ratio=args.warmup_ratio,
        lr_scheduler_type=args.lr_scheduler_type,
        optim=args.optim,
        weight_decay=args.weight_decay,
        temperature=args.temperature,
        max_prompt_length=args.max_prompt_length,
        max_completion_length=args.max_completion_length,
        output_dir=args.output_dir,
        save_steps=args.save_steps,
        logging_steps=args.logging_steps,
        bf16=args.bf16,
        save_total_limit=args.save_total_limit,
        seed=args.seed,
    )
    print(f"  Configuration:")
    print(f"    - max_steps: {config.max_steps}")
    print(f"    - learning_rate: {config.learning_rate}")
    print(f"    - temperature: {config.temperature}")
    print(f"    - num_generations: {config.num_generations}")
    print(f"    - per_device_train_batch_size: {config.per_device_train_batch_size}")
    print(f"    - gradient_accumulation_steps: {config.gradient_accumulation_steps}")
    print(f"    - max_prompt_length: {config.max_prompt_length}")
    print(f"    - max_completion_length: {config.max_completion_length}")
    print(f"    - bf16: {config.bf16}")
    print(f"    - output_dir: {config.output_dir}")
    print(f"    - generation_config: {generation_config}")
    logging.info(f"  Configuration:")
    logging.info(f"    - max_steps: {config.max_steps}")
    logging.info(f"    - learning_rate: {config.learning_rate}")
    logging.info(f"    - temperature: {config.temperature}")
    logging.info(f"    - num_generations: {config.num_generations}")
    logging.info(f"    - per_device_train_batch_size: {config.per_device_train_batch_size}")
    logging.info(f"    - gradient_accumulation_steps: {config.gradient_accumulation_steps}")
    logging.info(f"    - max_prompt_length: {config.max_prompt_length}")
    logging.info(f"    - max_completion_length: {config.max_completion_length}")
    logging.info(f"    - bf16: {config.bf16}")
    logging.info(f"    - output_dir: {config.output_dir}")
    logging.info(f"    - generation_config: {generation_config}")

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
