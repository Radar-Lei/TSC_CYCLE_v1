#!/usr/bin/env python3
"""
训练数据生成 CLI

并行运行 SUMO 仿真,生成包含早/平/晚高峰标签的训练数据。

使用示例:
    python -m src.scripts.generate_training_data
    python -m src.scripts.generate_training_data --workers 4 --dry-run
    python -m src.scripts.generate_training_data --rou-dir path/to/daily --verbose
"""

import argparse
import os
import sys
import glob
import json
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from src.data_generator.parallel_runner import run_parallel_simulation


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description='生成包含时段标签的 GRPO 训练数据',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 使用默认参数生成数据
  python -m src.scripts.generate_training_data

  # 指定 4 个并行进程
  python -m src.scripts.generate_training_data --workers 4

  # Dry-run 模式 (仅显示将处理的文件)
  python -m src.scripts.generate_training_data --dry-run

  # 详细输出
  python -m src.scripts.generate_training_data --verbose
        """
    )

    parser.add_argument(
        '--rou-dir',
        type=str,
        default='sumo_simulation/environments/chengdu/chengdu_daily',
        help='流量文件目录 (默认: sumo_simulation/environments/chengdu/chengdu_daily)'
    )

    parser.add_argument(
        '--phase-config',
        type=str,
        default='output/phase_config.json',
        help='Phase 1 输出的相位配置 (默认: output/phase_config.json)'
    )

    parser.add_argument(
        '--output-dir',
        type=str,
        default='data/training',
        help='训练数据输出目录 (默认: data/training)'
    )

    parser.add_argument(
        '--state-dir',
        type=str,
        default='data/states',
        help='状态快照目录 (默认: data/states)'
    )

    parser.add_argument(
        '--workers',
        type=int,
        default=None,
        help='并行进程数 (默认: 自动检测 min(cpu_count, 8))'
    )

    parser.add_argument(
        '--sim-end',
        type=int,
        default=86400,
        help='仿真结束时间秒数 (默认: 86400 = 24小时)'
    )

    parser.add_argument(
        '--warmup-steps',
        type=int,
        default=300,
        help='预热步数 (默认: 300)'
    )

    parser.add_argument(
        '--incremental',
        action='store_true',
        default=True,
        help='增量模式,跳过已存在的日期 (默认: True)'
    )

    parser.add_argument(
        '--no-incremental',
        dest='incremental',
        action='store_false',
        help='禁用增量模式,重新生成所有数据'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='仅显示将处理的文件,不实际运行'
    )

    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='详细输出'
    )

    parser.add_argument(
        '--time-ranges',
        type=str,
        default='[]',
        help='时间段配置 JSON (e.g., [{"start":"07:00","end":"09:00"}])'
    )

    return parser.parse_args()


def main():
    """主函数"""
    args = parse_args()

    # 转换为绝对路径
    rou_dir = os.path.abspath(args.rou_dir)
    phase_config = os.path.abspath(args.phase_config)
    output_dir = os.path.abspath(args.output_dir)
    state_dir = os.path.abspath(args.state_dir)

    # 检查必需文件
    if not os.path.exists(rou_dir):
        print(f"错误: 流量文件目录不存在: {rou_dir}")
        sys.exit(1)

    if not os.path.exists(phase_config):
        print(f"错误: 相位配置文件不存在: {phase_config}")
        sys.exit(1)

    # 扫描流量文件
    rou_files = sorted(glob.glob(os.path.join(rou_dir, '*.rou.xml')))

    if not rou_files:
        print(f"错误: 在 {rou_dir} 中未找到 .rou.xml 文件")
        sys.exit(1)

    # Dry-run 模式
    if args.dry_run:
        print("=" * 60)
        print("DRY RUN MODE - 将处理以下文件:")
        print("=" * 60)
        print(f"流量文件目录: {rou_dir}")
        print(f"相位配置: {phase_config}")
        print(f"输出目录: {output_dir}")
        print(f"状态快照目录: {state_dir}")
        print(f"并行进程数: {args.workers or 'auto'}")
        print(f"仿真结束时间: {args.sim_end}s")
        print(f"预热步数: {args.warmup_steps}")
        print(f"增量模式: {args.incremental}")
        print()
        print(f"找到 {len(rou_files)} 个流量文件:")
        for i, f in enumerate(rou_files, 1):
            print(f"  {i}. {os.path.basename(f)}")
        print()
        print("(使用 --no-dry-run 实际运行仿真)")
        return

    # 配置字典
    # 需要 sumocfg 路径
    sumocfg = os.path.join(
        os.path.dirname(rou_dir),
        'chengdu.sumocfg'
    )

    if not os.path.exists(sumocfg):
        print(f"错误: SUMO 配置文件不存在: {sumocfg}")
        sys.exit(1)

    config = {
        'sumocfg': sumocfg,
        'phase_config_path': phase_config,
        'output_dir': output_dir,
        'state_dir': state_dir,
        'warmup_steps': args.warmup_steps,
        'sim_end': args.sim_end,
        'incremental': args.incremental,
        'time_ranges': json.loads(args.time_ranges) if args.time_ranges else []
    }

    # 显示配置
    print("=" * 60)
    print("训练数据生成配置")
    print("=" * 60)
    print(f"流量文件: {len(rou_files)} 个")
    print(f"相位配置: {phase_config}")
    print(f"输出目录: {output_dir}")
    print(f"状态快照目录: {state_dir}")
    print(f"并行进程数: {args.workers or 'auto'}")
    print(f"仿真时长: {args.sim_end}s ({args.sim_end/3600:.1f} 小时)")
    print(f"预热步数: {args.warmup_steps}")
    print(f"增量模式: {'是' if args.incremental else '否'}")
    if config['time_ranges']:
        print(f"时间段过滤: {len(config['time_ranges'])} 个时段")
        for tr in config['time_ranges']:
            print(f"  - {tr['start']} ~ {tr['end']}")
    else:
        print(f"时间段过滤: 全天")
    print("=" * 60)
    print()

    # 运行并行仿真
    try:
        results = run_parallel_simulation(
            rou_dir,
            config,
            num_workers=args.workers
        )

        # 输出结果
        print()
        print("=" * 60)
        print("生成完成")
        print("=" * 60)
        print(f"处理天数: {results['total_days']}")
        print(f"成功: {results['successful']}")
        print(f"失败: {results['failed']}")
        print(f"总样本数: {results['total_samples']:,}")
        print()

        # 时段分布
        period_stats = results['samples_by_period']
        total = results['total_samples']
        if total > 0:
            print("时段分布:")
            morning = period_stats.get('morning_peak', 0)
            evening = period_stats.get('evening_peak', 0)
            off_peak = period_stats.get('off_peak', 0)

            print(f"- 早高峰 (07:00-09:00): {morning:,} 条 ({morning/total*100:.1f}%)")
            print(f"- 晚高峰 (17:00-19:00): {evening:,} 条 ({evening/total*100:.1f}%)")
            print(f"- 平峰: {off_peak:,} 条 ({off_peak/total*100:.1f}%)")
        print("=" * 60)

        # 显示错误
        if results['errors']:
            print()
            print("错误:")
            for error in results['errors']:
                print(f"  - {error}")

        # 输出路径
        print()
        print(f"训练数据保存在: {output_dir}")
        print(f"状态快照保存在: {state_dir}")
        print(f"元数据: {os.path.join(output_dir, 'metadata.json')}")

    except KeyboardInterrupt:
        print("\n\n中断: 用户取消操作")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n错误: {str(e)}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
