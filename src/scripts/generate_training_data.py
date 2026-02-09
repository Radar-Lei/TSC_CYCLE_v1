#!/usr/bin/env python3
"""
训练数据生成 CLI - 扁平任务池模式

将所有场景的所有交叉口展开为统一任务列表,使用单个 worker 池并行消费。

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
from multiprocessing import Pool
from datetime import datetime

import concurrent.futures

# 添加项目根目录到 Python 路径
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))


def discover_environments(environments_dir: str) -> list[dict[str, str]]:
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
            print(f"错误: 场景 {entry} 缺少 .sumocfg 文件,跳过")
            # 缺少 .sumocfg 是严重错误，虽然这里写了跳过，但根据 Task 要求应该报错停止
            # 但为了不破坏 discover_environments 的签名，我们在外部处理空列表，或者在这里 raise
            # 原始代码是 continue，Task 要求"立即报错停止"
            print(f"CRITICAL: 场景 {entry} 缺少 .sumocfg 文件")
            sys.exit(1)
        if not net_files:
            print(f"错误: 场景 {entry} 缺少 .net.xml 文件")
            sys.exit(1)
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
        description='生成训练数据 - 扁平任务池模式',
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
        help='Environments 目录路径'
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
        default='outputs/states',
        help='状态快照目录 (默认: outputs/states)'
    )

    parser.add_argument(
        '--workers',
        type=int,
        default=None,
        help='并行进程数 (默认: 从 config.json 读取)'
    )

    parser.add_argument(
        '--warmup-steps',
        type=int,
        default=None,
        help='预热步数 (默认: 从 config.json 读取)'
    )

    parser.add_argument(
        '--scenarios',
        type=str,
        default=None,
        help='指定场景列表 (逗号分隔), 如: arterial4x4_1,chengdu'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='仅显示将处理的任务,不实际运行'
    )

    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='详细输出'
    )

    return parser.parse_args()


def _simulate_intersection(args):
    """
    单个交叉口的仿真 worker

    Args:
        args: (task_id, scenario_name, rou_file, config) 元组

    Returns:
        结果字典: {'status': 'success'/'error', 'scenario_name': ..., 'tl_id': ..., 'samples': [...], 'error': ...}
    """
    task_id, scenario_name, rou_file, config = args

    try:
        from src.data_generator.day_simulator import DaySimulator

        # 运行仿真 (DaySimulator 已支持 target_tl_ids)
        simulator = DaySimulator(task_id, rou_file, config)
        result = simulator.run()

        # 添加场景名称到结果中
        result['scenario_name'] = scenario_name

        return result

    except Exception as e:
        return {
            'status': 'error',
            'scenario_name': scenario_name,
            'tl_id': config.get('target_tl_ids', ['unknown'])[0] if config.get('target_tl_ids') else 'unknown',
            'samples': [],
            'error': str(e),
            'sample_count': 0
        }


def save_samples_to_jsonl(samples: list[dict], output_path: str):
    """
    将样本列表保存为 JSONL 格式

    Args:
        samples: 样本列表
        output_path: 输出文件路径
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        for sample in samples:
            json_line = json.dumps(sample, ensure_ascii=False)
            f.write(json_line + '\n')


def convert_to_sft_format(raw_jsonl_path: str, sft_jsonl_path: str):
    """
    将原始 JSONL 训练数据转换为 CoT 格式 SFT 训练数据

    Args:
        raw_jsonl_path: 原始 train.jsonl 路径（包含 prompt, prediction, state_file, metadata）
        sft_jsonl_path: SFT 训练数据输出路径（chat 格式）

    输出格式:
        {
          "messages": [
            {"role": "system", "content": "你是交通信号配时优化专家。"},
            {"role": "user", "content": "<JSON 输入块 + 任务描述>"},
            {"role": "assistant", "content": "<think>\n\n</think>\n[{\"phase_id\": N, \"final\": M}, ...]"}
          ]
        }

    assistant content 构建逻辑:
        1. <think> 部分：使用空占位符 "<think>\n\n</think>"，不生成任何分析文本
        2. JSON 部分：基于 pred_saturation 计算 final 绿灯时间
           - 饱和度 > 1.0：偏向 max_green
           - 饱和度 < 0.5：偏向 min_green
           - 其他：按饱和度线性插值 min_green 到 max_green
           - final 必须为整数，且满足 min_green <= final <= max_green
    """
    os.makedirs(os.path.dirname(sft_jsonl_path), exist_ok=True)

    success_count = 0
    total_count = 0

    with open(raw_jsonl_path, 'r', encoding='utf-8') as infile, \
         open(sft_jsonl_path, 'w', encoding='utf-8') as outfile:

        for line in infile:
            if not line.strip():
                continue

            total_count += 1

            try:
                # 解析原始样本
                sample = json.loads(line)
                prompt = sample['prompt']
                prediction = sample['prediction']

                # 1. 提取 system role (从 prompt 第一行)
                prompt_lines = prompt.split('\n')
                system_content = prompt_lines[0]  # "你是交通信号配时优化专家。"

                # 2. 提取 user content (去掉第一行系统角色行)
                user_content = '\n'.join(prompt_lines[1:])

                # 3. 构建 assistant content
                # a. think 标签（空占位符）
                think_part = "<think>\n\n</think>"

                # b. JSON 部分（基于 pred_saturation 计算 final）
                phase_waits = prediction['phase_waits']
                final_json = []

                for pw in phase_waits:
                    phase_id = pw['phase_id']
                    pred_saturation = pw['pred_saturation']
                    min_green = pw['min_green']
                    max_green = pw['max_green']

                    # 基于饱和度计算 final
                    if pred_saturation > 1.0:
                        # 饱和度高：偏向 max_green
                        final = max_green
                    elif pred_saturation < 0.5:
                        # 饱和度低：偏向 min_green
                        final = min_green
                    else:
                        # 中等饱和度：线性插值
                        # final = min_green + (max_green - min_green) * (pred_saturation - 0.5) / 0.5
                        # 简化为：final = min_green + (max_green - min_green) * pred_saturation
                        final = min_green + (max_green - min_green) * pred_saturation

                    # 确保 final 为整数，且在范围内
                    final = int(round(final))
                    final = max(min_green, min(max_green, final))

                    final_json.append({
                        "phase_id": phase_id,
                        "final": final
                    })

                # 格式化 JSON 输出
                json_output = json.dumps(final_json, ensure_ascii=False)
                assistant_content = f"{think_part}\n{json_output}"

                # 4. 构建 SFT 样本
                sft_sample = {
                    "messages": [
                        {"role": "system", "content": system_content},
                        {"role": "user", "content": user_content},
                        {"role": "assistant", "content": assistant_content}
                    ]
                }

                # 写入 SFT JSONL
                sft_line = json.dumps(sft_sample, ensure_ascii=False)
                outfile.write(sft_line + '\n')

                success_count += 1

            except Exception as e:
                print(f"警告: 转换样本失败: {e}")
                continue

    return {
        'total': total_count,
        'success': success_count,
        'failed': total_count - success_count
    }


def main():
    """主函数 - 扁平任务池模式"""
    args = parse_args()

    # 加载配置
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

    # 确定参数 (命令行 > config.json)
    environments_dir = args.environments_dir or paths_config.get('environments_dir', 'sumo_simulation/environments')
    workers = args.workers or sim_config.get('parallel_workers', None)
    warmup_steps = args.warmup_steps or sim_config.get('warmup_steps', 300)
    output_dir = os.path.abspath(args.output_dir)
    state_dir = os.path.abspath(args.state_dir)

    # 发现场景
    scenarios = discover_environments(os.path.abspath(environments_dir))
    if not scenarios:
        print(f"错误: 未找到有效场景")
        sys.exit(1)

    # 过滤场景 (--scenarios)
    if args.scenarios:
        target_scenarios = [s.strip() for s in args.scenarios.split(',')]
        filtered_scenarios = []
        for s in scenarios:
            if s['name'] in target_scenarios:
                filtered_scenarios.append(s)

        # 检查是否有未找到的场景
        found_names = [s['name'] for s in filtered_scenarios]
        for target in target_scenarios:
            if target not in found_names:
                print(f"错误: 指定的场景 '{target}' 未找到")
                sys.exit(1)

        scenarios = filtered_scenarios
        print(f"过滤后场景数: {len(scenarios)}")

    print(f"发现 {len(scenarios)} 个场景")

    # Dry-run 模式
    if args.dry_run:
        print("=" * 60)
        print("DRY RUN MODE")
        print("=" * 60)
        print(f"Environments 目录: {environments_dir}")
        print(f"输出目录: {output_dir}")
        print(f"并行进程数: {workers or 'auto'}")
        print(f"预热步数: {warmup_steps}")
        print()
        print(f"场景列表 ({len(scenarios)} 个):")
        for i, scenario in enumerate(scenarios[:10], 1):
            print(f"  {i}. {scenario['name']}")
        if len(scenarios) > 10:
            print(f"  ... 共 {len(scenarios)} 个场景")
        print()
        print("(移除 --dry-run 实际运行仿真)")
        return

    # 创建输出目录
    os.makedirs(output_dir, exist_ok=True)

    print("=" * 60)
    print("扁平任务池模式 - 数据生成")
    print("=" * 60)
    print(f"场景数: {len(scenarios)}")
    print(f"并行进程数: {workers or 'auto'}")
    print(f"预热步数: {warmup_steps}")
    print("=" * 60)
    print()

    # ── 阶段 1: 为每个场景生成 phase_config (串行,轻量) ──
    print("阶段 1: 生成 phase_config...")
    tasks = []
    task_id = 0

    for idx, scenario in enumerate(scenarios, 1):
        scenario_name = scenario['name']
        phase_config_path = os.path.join(output_dir, f"phase_config_{scenario_name}.json")

        # 如果 phase_config 不存在,生成它
        if not os.path.exists(phase_config_path):
            print(f"  生成 phase_config: {scenario_name}...")
            try:
                from src.scripts.process_phases import process_traffic_lights, save_result_to_json
                result = process_traffic_lights(scenario['net_file'])
                save_result_to_json(result, phase_config_path)
            except Exception as e:
                print(f"  ✗ Phase config 生成失败 ({scenario_name}): {e}")
                continue

        # 从 phase_config 读取交叉口列表
        try:
            phase_config = load_config(phase_config_path)
            tl_ids = list(phase_config.get('traffic_lights', {}).keys())
        except Exception as e:
            print(f"  ✗ 读取 phase_config 失败 ({scenario_name}): {e}")
            continue

        if not tl_ids:
            print(f"  警告: 场景 {scenario_name} 没有交叉口,跳过")
            continue

        # 场景的输出和状态目录
        scenario_output_dir = os.path.join(output_dir, scenario_name)
        scenario_state_dir = os.path.join(state_dir, scenario_name)
        os.makedirs(scenario_output_dir, exist_ok=True)
        os.makedirs(scenario_state_dir, exist_ok=True)

        # 生成唯一日期 (场景索引分布到多个月份)
        day_of_year = idx + 1
        month = (day_of_year - 1) // 28 + 1
        day = (day_of_year - 1) % 28 + 1
        base_date = f'2026-{month:02d}-{day:02d}'

        # ── 阶段 2: 为每个交叉口创建任务 ──
        for tl_id in tl_ids:
            # 配置字典 (每个交叉口一个独立 SUMO 实例)
            config = {
                'sumocfg': scenario['sumocfg'],
                'phase_config_path': phase_config_path,
                'output_dir': scenario_output_dir,
                'state_dir': scenario_state_dir,
                'warmup_steps': warmup_steps,
                'base_date': base_date,
                'target_tl_ids': [tl_id]  # 单个交叉口
            }

            tasks.append((task_id, scenario_name, scenario['rou_file'], config))
            task_id += 1

    if not tasks:
        print("错误: 没有可运行的任务")
        sys.exit(1)

    print(f"阶段 2: 生成 {len(tasks)} 个任务 (所有场景 × 所有交叉口)")
    print()

    # ── 阶段 3: 并行消费任务 (扁平任务池) ──
    # 限制 worker 数量不超过配置
    max_workers_config = sim_config.get('parallel_workers', 12)
    requested_workers = workers or max_workers_config
    num_workers = min(requested_workers, max_workers_config)
    num_workers = min(num_workers, len(tasks))

    print(f"阶段 3: 启动 {num_workers} 个并行 worker...")
    print()

    # 按场景收集结果
    results_by_scenario = {}
    failed_count = 0

    # 使用 ProcessPoolExecutor 替代 multiprocessing.Pool 以支持更好的错误处理和取消
    # 使用 ProcessPoolExecutor 替代 multiprocessing.Pool 以支持更好的错误处理和取消
    with concurrent.futures.ProcessPoolExecutor(max_workers=num_workers) as executor:
        # 提交所有任务
        future_to_task = {executor.submit(_simulate_intersection, task): task for task in tasks}

        try:
            for i, future in enumerate(concurrent.futures.as_completed(future_to_task), 1):
                task = future_to_task[future]
                try:
                    result = future.result()
                except Exception as exc:
                    print(f"任务抛出异常: {exc}")
                    # 立即取消所有未完成的任务
                    for f in future_to_task:
                        f.cancel()
                    executor.shutdown(wait=False)
                    sys.exit(1)

                scenario_name = result['scenario_name']

                if result['status'] == 'success':
                    # 收集样本
                    if scenario_name not in results_by_scenario:
                        results_by_scenario[scenario_name] = []
                    results_by_scenario[scenario_name].extend(result['samples'])

                    # 简洁模式日志
                    print(f"  ✓ [{i}/{len(tasks)}] {scenario_name} / {result['metadata']['tl_id']} 完成 "
                          f"({result['sample_count']} samples)")
                else:
                    # Fail-fast: 任一任务失败立即终止
                    failed_count += 1
                    error_msg = result.get('error', '未知错误')
                    tl_id = result.get('tl_id', 'unknown')

                    print()
                    print("=" * 60)
                    print("错误: 任务失败 (fail-fast 模式)")
                    print("=" * 60)
                    print(f"失败任务: {scenario_name} / {tl_id}")
                    print(f"错误信息: {error_msg}")

                    # 立即取消所有未完成的任务
                    for f in future_to_task:
                        f.cancel()
                    executor.shutdown(wait=False)
                    sys.exit(1)

        except KeyboardInterrupt:
            print("\n用户中断执行，正在停止所有任务...")
            executor.shutdown(wait=False)
            sys.exit(1)

    print()
    print("=" * 60)
    print("阶段 4: 合并结果")
    print("=" * 60)

    # ── 阶段 4: 合并每个场景的结果到 samples_<date>.jsonl ──
    total_samples = 0
    for scenario_name, samples in results_by_scenario.items():
        if not samples:
            continue

        # 从第一个样本获取 date
        date = samples[0]['metadata']['date']
        scenario_output_dir = os.path.join(output_dir, scenario_name)

        # 保存到 samples_<date>.jsonl
        output_file = os.path.join(scenario_output_dir, f'samples_{date}.jsonl')
        save_samples_to_jsonl(samples, output_file)

        total_samples += len(samples)
        print(f"  ✓ {scenario_name}: {len(samples)} 个样本 -> {output_file}")

    print()
    print(f"总样本数: {total_samples:,}")

    # ── 阶段 5: 合并所有场景到 train.jsonl ──
    print()
    print("=" * 60)
    print("阶段 5: 合并到 train.jsonl")
    print("=" * 60)

    training_data_dir = paths_config.get('data_dir', 'data/training')
    os.makedirs(training_data_dir, exist_ok=True)
    train_jsonl_path = os.path.join(training_data_dir, 'train.jsonl')

    total_lines = 0
    with open(train_jsonl_path, 'w', encoding='utf-8') as outfile:
        for scenario in scenarios:
            scenario_name = scenario['name']
            scenario_output_dir = os.path.join(output_dir, scenario_name)

            # 查找该场景的所有 samples_*.jsonl 文件
            jsonl_files = glob.glob(os.path.join(scenario_output_dir, 'samples_*.jsonl'))

            for jsonl_file in jsonl_files:
                with open(jsonl_file, 'r', encoding='utf-8') as infile:
                    for line in infile:
                        if line.strip():
                            outfile.write(line)
                            total_lines += 1

    print(f"✓ 合并完成: {total_lines} 条样本")
    print(f"✓ 训练数据文件: {train_jsonl_path}")

    # ── 阶段 6: CoT 格式转换 ──
    print()
    print("=" * 60)
    print("阶段 6: CoT 格式转换")
    print("=" * 60)

    sft_output_dir = paths_config.get('sft_data_dir', 'outputs/sft')
    os.makedirs(sft_output_dir, exist_ok=True)
    sft_train_jsonl_path = os.path.join(sft_output_dir, 'train.jsonl')

    print(f"输入: {train_jsonl_path}")
    print(f"输出: {sft_train_jsonl_path}")
    print()

    # 转换为 SFT 格式
    conversion_stats = convert_to_sft_format(train_jsonl_path, sft_train_jsonl_path)

    print(f"✓ CoT 格式转换完成")
    print(f"  总条数: {conversion_stats['total']}")
    print(f"  成功: {conversion_stats['success']}")
    print(f"  失败: {conversion_stats['failed']}")
    print(f"✓ SFT 训练数据文件: {sft_train_jsonl_path}")
    print()
    print("=" * 60)
    print("数据生成完成")
    print("=" * 60)


if __name__ == '__main__':
    main()
