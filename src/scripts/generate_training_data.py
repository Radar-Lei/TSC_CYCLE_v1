#!/usr/bin/env python3
"""
训练数据生成 CLI

并行运行 SUMO 仿真,生成包含早/平/晚高峰标签的训练数据。
时段配置从 config/config.json 读取。

使用示例:
    python -m src.scripts.generate_training_data
    python -m src.scripts.generate_training_data --workers 4 --dry-run
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
from src.data_generator.intersection_parallel import IntersectionParallelRunner


def discover_environments(environments_dir: str) -> List[Dict[str, str]]:
    """
    发现 environments 目录下的所有场景

    Args:
        environments_dir: environments 目录路径

    Returns:
        场景列表: [{"name": "arterial4x4_1", "sumocfg": "...", "net_file": "...", "rou_file": "...", "dir": "..."}, ...]
    """
    environments_dir = os.path.abspath(environments_dir)

    if not os.path.isdir(environments_dir):
        print(f"错误: 环境目录不存在: {environments_dir}")
        return []

    scenarios = []

    for entry in sorted(os.listdir(environments_dir)):
        scenario_dir = os.path.join(environments_dir, entry)

        # 跳过非目录
        if not os.path.isdir(scenario_dir):
            continue

        # 查找必需的文件
        sumocfg_files = glob.glob(os.path.join(scenario_dir, '*.sumocfg'))
        net_files = glob.glob(os.path.join(scenario_dir, '*.net.xml'))
        rou_files = glob.glob(os.path.join(scenario_dir, '*.rou.xml'))

        # 验证文件完整性
        if not sumocfg_files:
            print(f"警告: 场景 {entry} 缺少 .sumocfg 文件,跳过")
            continue
        if not net_files:
            print(f"警告: 场景 {entry} 缺少 .net.xml 文件,跳过")
            continue
        if not rou_files:
            print(f"警告: 场景 {entry} 缺少 .rou.xml 文件,跳过")
            continue

        # 每个场景只使用第一个匹配的文件
        scenarios.append({
            "name": entry,
            "sumocfg": os.path.abspath(sumocfg_files[0]),
            "net_file": os.path.abspath(net_files[0]),
            "rou_file": os.path.abspath(rou_files[0]),
            "dir": scenario_dir
        })

    return scenarios


def load_config(config_path: str) -> dict:
    """加载 JSON 配置文件"""
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description='生成包含时段标签的训练数据',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 使用默认参数生成数据
  python -m src.scripts.generate_training_data

  # 指定 4 个并行进程
  python -m src.scripts.generate_training_data --workers 4

  # Dry-run 模式 (仅显示将处理的文件)
  python -m src.scripts.generate_training_data --dry-run
        """
    )

    parser.add_argument(
        '--config',
        type=str,
        default='config/config.json',
        help='配置文件路径 (默认: config/config.json)'
    )

    parser.add_argument(
        '--environments-dir',
        type=str,
        default=None,
        help='Environments 目录路径 (多场景模式，优先级高于 --rou-dir)'
    )

    parser.add_argument(
        '--rou-dir',
        type=str,
        default='sumo_simulation/environments/chengdu/chengdu_daily',
        help='流量文件目录 (单场景模式，已废弃，建议使用 --environments-dir)'
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
        default='outputs/data',
        help='训练数据输出目录 (默认: outputs/data)'
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
        help='并行进程数 (默认: 从 config.json 读取)'
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
        default=None,
        help='预热步数 (默认: 从 config.json 读取)'
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
        '--max-rou-files',
        type=int,
        default=None,
        help='最多处理的 .rou.xml 文件数量 (默认: 从 config.json 读取，null 表示不限制)'
    )

    parser.add_argument(
        '--intersection-parallel',
        action='store_true',
        default=False,
        help='启用交叉口级别并行模式 (通过复制 .rou.xml 实现真正的交叉口并行)'
    )

    parser.add_argument(
        '--intersection-groups',
        type=int,
        default=None,
        help='交叉口并行模式下，将交叉口分成多少组 (默认: 等于 workers 数)'
    )

    return parser.parse_args()


def main():
    """主函数"""
    args = parse_args()

    # 加载配置文件
    config_path = os.path.abspath(args.config)
    if os.path.exists(config_path):
        json_config = load_config(config_path)
        sim_config = json_config.get('simulation', {})
        paths_config = json_config.get('paths', {})
    else:
        print(f"警告: 配置文件不存在: {config_path}，使用默认配置")
        json_config = {}
        sim_config = {}
        paths_config = {}

    # 从配置文件读取参数（命令行参数优先）
    time_ranges = sim_config.get('time_ranges', [])
    warmup_steps = args.warmup_steps or sim_config.get('warmup_steps', 300)
    workers = args.workers or sim_config.get('parallel_workers', None)
    max_rou_files = args.max_rou_files if args.max_rou_files is not None else sim_config.get('max_rou_files', None)

    # 确定是多场景模式还是单场景模式
    environments_dir = args.environments_dir or paths_config.get('environments_dir')

    if environments_dir:
        # 多场景模式
        run_multi_scenario_mode(
            environments_dir=environments_dir,
            args=args,
            time_ranges=time_ranges,
            warmup_steps=warmup_steps,
            workers=workers
        )
    else:
        # 单场景模式（向后兼容）
        run_single_scenario_mode(
            args=args,
            time_ranges=time_ranges,
            warmup_steps=warmup_steps,
            workers=workers,
            max_rou_files=max_rou_files
        )


def run_multi_scenario_mode(
    environments_dir: str,
    args,
    time_ranges: List[Dict[str, str]],
    warmup_steps: int,
    workers: int
):
    """
    多场景模式: 遍历 environments 目录下的所有场景

    Args:
        environments_dir: environments 目录路径
        args: 命令行参数
        time_ranges: 时间段配置
        warmup_steps: 预热步数
        workers: 并行进程数
    """
    # 发现所有场景
    environments_dir = os.path.abspath(environments_dir)
    scenarios = discover_environments(environments_dir)

    if not scenarios:
        print(f"错误: 在 {environments_dir} 中未找到有效场景")
        sys.exit(1)

    print(f"发现 {len(scenarios)} 个场景")

    # Dry-run 模式
    if args.dry_run:
        print("=" * 60)
        print("DRY RUN MODE - 发现的场景:")
        print("=" * 60)
        print(f"Environments 目录: {environments_dir}")
        print(f"输出目录: {os.path.abspath(args.output_dir)}")
        print(f"并行进程数: {workers or 'auto'}")
        print(f"预热步数: {warmup_steps}")
        print()
        print(f"场景列表 ({len(scenarios)} 个):")
        for i, scenario in enumerate(scenarios[:10], 1):
            print(f"  {i}. {scenario['name']}")
            print(f"     - sumocfg: {scenario['sumocfg']}")
            print(f"     - net_file: {scenario['net_file']}")
            print(f"     - rou_file: {scenario['rou_file']}")
        if len(scenarios) > 10:
            print(f"  ... 共 {len(scenarios)} 个场景")
        print()
        print("(移除 --dry-run 实际运行仿真)")
        return

    # 创建输出目录
    output_base = os.path.abspath(args.output_dir)
    os.makedirs(output_base, exist_ok=True)

    # 为每个场景生成数据
    from multiprocessing import Pool
    import time

    total_samples = 0
    total_successful = 0
    total_failed = 0

    print("=" * 60)
    print("开始多场景训练数据生成")
    print("=" * 60)
    print(f"场景数: {len(scenarios)}")
    print(f"并行进程数: {workers or 'auto'}")
    print(f"预热步数: {warmup_steps}")
    print("=" * 60)
    print()

    for idx, scenario in enumerate(scenarios, 1):
        scenario_name = scenario['name']
        print(f"[{idx}/{len(scenarios)}] 处理场景: {scenario_name}")

        # 为该场景生成 phase_config
        phase_config_path = os.path.join(output_base, f"phase_config_{scenario_name}.json")

        # 检查 phase_config 是否已存在（增量模式）
        if args.incremental and os.path.exists(phase_config_path):
            print(f"  ✓ Phase config 已存在: {phase_config_path}")
        else:
            # 生成 phase_config
            print(f"  生成 phase_config...")
            try:
                from src.scripts.process_phases import process_traffic_lights, save_result_to_json

                result = process_traffic_lights(scenario['net_file'])
                save_result_to_json(result, phase_config_path)
                print(f"  ✓ Phase config 生成成功")
            except Exception as e:
                print(f"  ✗ Phase config 生成失败: {e}")
                total_failed += 1
                continue

        # 场景的输出目录
        scenario_output_dir = os.path.join(output_base, scenario_name)
        scenario_state_dir = os.path.join(args.state_dir, scenario_name)
        os.makedirs(scenario_output_dir, exist_ok=True)
        os.makedirs(scenario_state_dir, exist_ok=True)

        # 配置字典
        config = {
            'sumocfg': scenario['sumocfg'],
            'phase_config_path': phase_config_path,
            'output_dir': scenario_output_dir,
            'state_dir': scenario_state_dir,
            'warmup_steps': warmup_steps,
            'sim_end': args.sim_end,
            'incremental': args.incremental,
            'time_ranges': time_ranges,
            'base_date': scenario_name  # 使用场景名作为日期标识
        }

        # 该场景的 rou_files 列表（只有 1 个）
        rou_files = [scenario['rou_file']]

        # 运行仿真
        try:
            start_time = time.time()

            # 使用场景级别并行（不使用交叉口并行，因为每个场景只有 1 个 rou 文件）
            results = run_parallel_simulation(
                rou_files,
                config,
                num_workers=1  # 每个场景只有 1 个文件，不需要内部并行
            )

            elapsed_time = time.time() - start_time

            # 输出结果
            if results['successful'] > 0:
                total_successful += 1
                total_samples += results['total_samples']
                print(f"  ✓ 成功: {results['total_samples']} 个样本, 耗时 {elapsed_time:.1f}s")
            else:
                total_failed += 1
                print(f"  ✗ 失败: {results.get('errors', ['未知错误'])}")

        except Exception as e:
            total_failed += 1
            print(f"  ✗ 异常: {str(e)}")

    # 最终汇总
    print()
    print("=" * 60)
    print("多场景数据生成完成")
    print("=" * 60)
    print(f"总场景数: {len(scenarios)}")
    print(f"成功: {total_successful}")
    print(f"失败: {total_failed}")
    print(f"总样本数: {total_samples:,}")
    print(f"训练数据保存在: {output_base}")
    print("=" * 60)


def run_single_scenario_mode(
    args,
    time_ranges: List[Dict[str, str]],
    warmup_steps: int,
    workers: int,
    max_rou_files: int
):
    """
    单场景模式: 向后兼容旧的 --rou-dir 参数

    Args:
        args: 命令行参数
        time_ranges: 时间段配置
        warmup_steps: 预热步数
        workers: 并行进程数
        max_rou_files: 最大 rou 文件数量
    """
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

    # 应用 max_rou_files 限制
    total_rou_files = len(rou_files)
    if max_rou_files is not None and max_rou_files > 0:
        rou_files = rou_files[:max_rou_files]
        print(f"注意: 限制处理前 {len(rou_files)} 个文件 (共 {total_rou_files} 个)")

    # 计算仿真时长（基于 time_ranges）
    if time_ranges:
        total_sim_hours = 0
        for tr in time_ranges:
            start_parts = tr['start'].split(':')
            end_parts = tr['end'].split(':')
            start_sec = int(start_parts[0]) * 3600 + int(start_parts[1]) * 60
            end_sec = int(end_parts[0]) * 3600 + int(end_parts[1]) * 60
            total_sim_hours += (end_sec - start_sec) / 3600
        sim_desc = f"{len(time_ranges)} 个时段共 {total_sim_hours:.1f} 小时"
    else:
        sim_desc = f"全天 {args.sim_end/3600:.1f} 小时"

    # Dry-run 模式
    if args.dry_run:
        print("=" * 60)
        print("DRY RUN MODE - 将处理以下文件:")
        print("=" * 60)
        print(f"流量文件目录: {rou_dir}")
        print(f"相位配置: {phase_config}")
        print(f"输出目录: {output_dir}")
        print(f"状态快照目录: {state_dir}")
        print(f"并行进程数: {workers or 'auto'}")
        print(f"仿真范围: {sim_desc}")
        if time_ranges:
            for tr in time_ranges:
                print(f"  - {tr['start']} ~ {tr['end']}")
        print(f"预热步数: {warmup_steps}")
        print(f"增量模式: {args.incremental}")
        print()
        print(f"找到 {len(rou_files)} 个流量文件:")
        for i, f in enumerate(rou_files[:10], 1):
            print(f"  {i}. {os.path.basename(f)}")
        if len(rou_files) > 10:
            print(f"  ... 共 {len(rou_files)} 个文件")
        print()
        print("(移除 --dry-run 实际运行仿真)")
        return

    # 需要 sumocfg 路径
    sumocfg = os.path.join(
        os.path.dirname(rou_dir),
        'chengdu.sumocfg'
    )

    if not os.path.exists(sumocfg):
        print(f"错误: SUMO 配置文件不存在: {sumocfg}")
        sys.exit(1)

    # 配置字典
    config = {
        'sumocfg': sumocfg,
        'phase_config_path': phase_config,
        'output_dir': output_dir,
        'state_dir': state_dir,
        'warmup_steps': warmup_steps,
        'sim_end': args.sim_end,
        'incremental': args.incremental,
        'time_ranges': time_ranges
    }

    # 显示配置
    print("=" * 60)
    print("训练数据生成配置")
    print("=" * 60)
    print(f"流量文件: {len(rou_files)} 个")
    print(f"相位配置: {phase_config}")
    print(f"输出目录: {output_dir}")
    print(f"状态快照目录: {state_dir}")
    print(f"并行进程数: {workers or 'auto'}")
    print(f"仿真范围: {sim_desc}")
    if time_ranges:
        for tr in time_ranges:
            print(f"  - {tr['start']} ~ {tr['end']}")
    print(f"预热步数: {warmup_steps}")
    print(f"增量模式: {'是' if args.incremental else '否'}")
    print("=" * 60)
    print()

    # 运行并行仿真
    try:
        if args.intersection_parallel:
            # 交叉口级别并行模式
            print(f"使用交叉口级别并行模式")
            runner = IntersectionParallelRunner(
                rou_files=rou_files,
                config=config,
                num_workers=workers,
                intersection_groups=args.intersection_groups
            )
            results = runner.run()
        else:
            # 传统按天并行模式
            results = run_parallel_simulation(
                rou_files,
                config,
                num_workers=workers
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
