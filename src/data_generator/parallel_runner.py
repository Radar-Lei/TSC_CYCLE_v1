"""
并行仿真调度器

使用 multiprocessing.Pool 并行运行多天的 SUMO 仿真。

主要功能:
- ParallelRunner: 并行仿真调度器
- run_parallel_simulation: 便捷函数
- save_samples_to_jsonl: 保存样本到 JSONL 格式
- generate_metadata: 生成元数据
"""

import os
import json
import glob
from typing import List, Dict, Any
from multiprocessing import Pool, cpu_count
from tqdm import tqdm
from datetime import datetime

from src.data_generator.day_simulator import simulate_day
from src.data_generator.time_period import get_time_period_stats


def save_samples_to_jsonl(samples: List[dict], output_path: str):
    """
    将样本列表保存为 JSONL 格式

    Args:
        samples: 样本列表 (每个样本是 TrainingSample.to_dict() 的结果)
        output_path: 输出文件路径

    Example:
        >>> samples = [
        ...     {'prompt': 'test', 'state_file': '/tmp/state.xml', 'time_period': 'morning_peak'},
        ...     {'prompt': 'test2', 'state_file': '/tmp/state2.xml', 'time_period': 'off_peak'}
        ... ]
        >>> save_samples_to_jsonl(samples, 'data/training/samples.jsonl')
    """
    # 确保输出目录存在
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # 写入 JSONL (每行一个 JSON 对象)
    with open(output_path, 'w', encoding='utf-8') as f:
        for sample in samples:
            json_line = json.dumps(sample, ensure_ascii=False)
            f.write(json_line + '\n')


def generate_metadata(results: dict, config: dict) -> dict:
    """
    生成 metadata.json 内容

    Args:
        results: ParallelRunner.run() 的返回结果
        config: 配置字典

    Returns:
        元数据字典

    Example:
        >>> results = {
        ...     'total_days': 30,
        ...     'successful': 28,
        ...     'failed': 2,
        ...     'total_samples': 9500,
        ...     'samples_by_day': {'2026-01-01': 350, '2026-01-02': 320},
        ...     'samples_by_period': {'morning_peak': 1200, 'evening_peak': 1100, 'off_peak': 7200}
        ... }
        >>> config = {'sim_end': 86400, 'warmup_steps': 300}
        >>> meta = generate_metadata(results, config)
        >>> print(meta['total_samples'])
        9500
    """
    metadata = {
        'generated_at': datetime.now().isoformat(),
        'version': '1.0',
        'total_days': results['total_days'],
        'successful_days': results['successful'],
        'failed_days': results['failed'],
        'total_samples': results['total_samples'],
        'samples_by_day': results['samples_by_day'],
        'samples_by_period': results['samples_by_period'],
        'errors': results.get('errors', []),
        'config': {
            'sim_end': config.get('sim_end', 86400),
            'warmup_steps': config.get('warmup_steps', 300),
            'base_interval': 300,
            'min_interval': 60
        }
    }

    return metadata


class ParallelRunner:
    """
    并行仿真调度器

    使用 multiprocessing.Pool 并行运行多天的 SUMO 仿真。

    Attributes:
        rou_files: 流量文件列表
        config: 配置字典
        num_workers: 并行进程数
    """

    def __init__(
        self,
        rou_files: List[str],
        config: Dict[str, Any],
        num_workers: int = None
    ):
        """
        初始化并行调度器

        Args:
            rou_files: 流量文件列表 (按天)
            config: 配置字典 (传递给 DaySimulator)
            num_workers: 并行进程数 (默认 min(cpu_count(), 8))
        """
        self.rou_files = sorted(rou_files)
        self.config = config
        self.num_workers = num_workers or min(cpu_count(), 8)

        # 确保输出目录存在
        os.makedirs(config['output_dir'], exist_ok=True)
        os.makedirs(config['state_dir'], exist_ok=True)

    def _rebuild_from_existing_jsonl(self) -> Dict[str, Any]:
        """
        从已存在的 .jsonl 文件重建统计信息
        
        Returns:
            统计结果字典
        """
        samples_by_day = {}
        samples_by_period = {'morning_peak': 0, 'evening_peak': 0, 'off_peak': 0}
        total_samples = 0
        
        # 扫描 output_dir 下的所有 samples_*.jsonl 文件
        jsonl_files = glob.glob(os.path.join(self.config['output_dir'], 'samples_*.jsonl'))
        
        for jsonl_file in jsonl_files:
            # 从文件名提取日期
            basename = os.path.basename(jsonl_file)
            if basename.startswith('samples_') and basename.endswith('.jsonl'):
                date = basename[8:-6]  # samples_2026-01-01.jsonl -> 2026-01-01
            else:
                continue
            
            # 统计文件行数和时段分布
            day_count = 0
            with open(jsonl_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        day_count += 1
                        try:
                            sample = json.loads(line)
                            period = sample.get('metadata', {}).get('time_period', 'off_peak')
                            if period in samples_by_period:
                                samples_by_period[period] += 1
                        except json.JSONDecodeError:
                            pass
            
            samples_by_day[date] = day_count
            total_samples += day_count
        
        return {
            "total_days": len(jsonl_files),
            "successful": len(jsonl_files),
            "failed": 0,
            "total_samples": total_samples,
            "samples_by_day": samples_by_day,
            "samples_by_period": samples_by_period,
            "errors": []
        }

    def run(self) -> Dict[str, Any]:
        """
        运行并行仿真

        Returns:
            汇总结果:
            {
                "total_days": int,
                "successful": int,
                "failed": int,
                "total_samples": int,
                "samples_by_day": Dict[str, int],
                "samples_by_period": Dict[str, int],
                "errors": List[str]
            }
        """
        # 1. 准备任务参数
        tasks = []
        for day_idx, rou_file in enumerate(self.rou_files):
            # 检查增量模式: 跳过已存在输出的日期
            if self.config.get('incremental', True):
                # 从文件名提取日期
                rou_basename = os.path.basename(rou_file)
                if '_2026-' in rou_basename:
                    date_part = rou_basename.split('_2026-')[1].split('.rou.xml')[0]
                    date = f'2026-{date_part}'
                    output_file = os.path.join(
                        self.config['output_dir'],
                        f'samples_{date}.jsonl'
                    )
                    if os.path.exists(output_file):
                        print(f"Skipping {date} (already exists)")
                        continue

            tasks.append((day_idx, rou_file, self.config))

        if not tasks:
            print("No tasks to run (all days already processed)")
            # 从已存在的 jsonl 文件重建统计信息并生成 metadata
            existing_results = self._rebuild_from_existing_jsonl()
            if existing_results['total_samples'] > 0:
                metadata = generate_metadata(existing_results, self.config)
                metadata_path = os.path.join(self.config['output_dir'], 'metadata.json')
                with open(metadata_path, 'w', encoding='utf-8') as f:
                    json.dump(metadata, f, ensure_ascii=False, indent=2)
                print(f"从已有数据重建 metadata.json: {existing_results['total_samples']} 条样本")
            return existing_results

        # 2. 使用 multiprocessing.Pool 执行
        print(f"Running {len(tasks)} days with {self.num_workers} workers...")

        all_samples = []
        samples_by_day = {}
        errors = []
        successful = 0
        failed = 0

        with Pool(processes=self.num_workers) as pool:
            # 使用 imap_unordered 处理结果
            for result in tqdm(
                pool.imap_unordered(simulate_day, tasks),
                total=len(tasks),
                desc="Simulating days"
            ):
                if result['status'] == 'success':
                    successful += 1
                    # 收集样本
                    all_samples.extend(result['samples'])
                    samples_by_day[result['date']] = result['sample_count']

                    # 保存每天的数据到 JSONL 文件
                    output_file = os.path.join(
                        self.config['output_dir'],
                        f"samples_{result['date']}.jsonl"
                    )
                    save_samples_to_jsonl(result['samples'], output_file)
                else:
                    failed += 1
                    errors.append(result['error'])

        # 3. 统计各时段样本数
        samples_by_period = get_time_period_stats(all_samples)

        # 4. 保存汇总的 metadata.json
        results = {
            "total_days": len(tasks),
            "successful": successful,
            "failed": failed,
            "total_samples": len(all_samples),
            "samples_by_day": samples_by_day,
            "samples_by_period": samples_by_period,
            "errors": errors
        }

        metadata = generate_metadata(results, self.config)
        metadata_path = os.path.join(self.config['output_dir'], 'metadata.json')
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

        return results


def run_parallel_simulation(
    rou_files: List[str],
    config: Dict[str, Any],
    num_workers: int = None
) -> Dict[str, Any]:
    """
    便捷函数,运行并行仿真

    Args:
        rou_files: 流量文件列表 (List[str]) 或目录路径 (str，向后兼容)
        config: 配置字典
        num_workers: 并行进程数 (默认自动检测)

    Returns:
        汇总结果

    Example:
        >>> config = {
        ...     'sumocfg': 'sumo_simulation/environments/chengdu/chengdu.sumocfg',
        ...     'phase_config_path': 'output/phase_config.json',
        ...     'output_dir': 'data/training',
        ...     'state_dir': 'data/states',
        ...     'warmup_steps': 300,
        ...     'sim_end': 86400
        ... }
        >>> rou_files = ['day1.rou.xml', 'day2.rou.xml']
        >>> results = run_parallel_simulation(rou_files, config, num_workers=4)
        >>> print(results['total_samples'])
        9523
    """
    # 向后兼容: 如果传入的是目录路径,则扫描目录
    if isinstance(rou_files, str):
        rou_dir = rou_files
        rou_files = glob.glob(os.path.join(rou_dir, '*.rou.xml'))
        if not rou_files:
            raise ValueError(f"No .rou.xml files found in {rou_dir}")

    if not rou_files:
        raise ValueError("No .rou.xml files provided")

    # 创建 ParallelRunner 并运行
    runner = ParallelRunner(rou_files, config, num_workers)
    results = runner.run()

    return results
