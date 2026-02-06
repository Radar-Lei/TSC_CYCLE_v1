"""
交叉口级别并行仿真调度器

通过复制 .rou.xml 文件，实现在交叉口级别的真正并行：
- 将交叉口分组，每组交由一个独立的 SUMO 实例处理
- 同一天的不同交叉口可以并行采样
- 完成后合并结果并删除临时文件

主要类:
- IntersectionParallelRunner: 交叉口级别并行调度器
"""

import os
import json
import glob
import shutil
import tempfile
from typing import List, Dict, Any, Tuple
from multiprocessing import Pool, cpu_count
from tqdm import tqdm
from datetime import datetime
from pathlib import Path

from src.data_generator.day_simulator import (
    DaySimulator, 
    create_temp_sumocfg,
    get_simulation_ranges
)
from src.data_generator.traffic_collector import load_phase_config
from src.data_generator.time_period import get_time_period_stats


def split_into_groups(items: List[str], num_groups: int) -> List[List[str]]:
    """
    将列表均匀分成 N 组
    
    Args:
        items: 待分组的列表
        num_groups: 组数
        
    Returns:
        分组后的列表
    """
    if num_groups <= 0:
        return [items]
    
    groups = [[] for _ in range(num_groups)]
    for i, item in enumerate(items):
        groups[i % num_groups].append(item)
    
    # 移除空组
    return [g for g in groups if g]


def simulate_intersection_group(args: tuple) -> Dict[str, Any]:
    """
    仿真单个交叉口组的入口函数
    
    Args:
        args: (task_id, rou_file, config, tl_ids) 元组
              - task_id: 任务 ID (用于端口分配)
              - rou_file: 流量文件路径 (可以是临时副本)
              - config: 配置字典
              - tl_ids: 该任务负责的交叉口 ID 列表
              
    Returns:
        仿真结果字典
    """
    task_id, rou_file, config, tl_ids = args
    
    # 创建修改后的配置，只处理指定的交叉口
    modified_config = config.copy()
    modified_config['target_tl_ids'] = tl_ids
    
    # DaySimulator 已支持 target_tl_ids，直接使用
    simulator = DaySimulator(task_id, rou_file, modified_config)
    result = simulator.run()
    
    return result


class IntersectionParallelRunner:
    """
    交叉口级别并行调度器
    
    将每天的仿真拆分为多个交叉口组，每组独立运行 SUMO 实例。
    通过复制 .rou.xml 文件实现真正的并行。
    """
    
    def __init__(
        self,
        rou_files: List[str],
        config: Dict[str, Any],
        num_workers: int = None,
        intersection_groups: int = None
    ):
        """
        初始化调度器
        
        Args:
            rou_files: 流量文件列表 (按天)
            config: 配置字典
            num_workers: 总并行进程数 (默认 min(cpu_count(), 12))
            intersection_groups: 每天分成多少个交叉口组 (默认等于 num_workers)
        """
        self.rou_files = sorted(rou_files)
        self.config = config
        self.num_workers = num_workers or min(cpu_count(), 12)
        self.intersection_groups = intersection_groups or self.num_workers
        
        # 临时文件目录
        self.temp_dir = tempfile.mkdtemp(prefix='sumo_parallel_')
        
        # 加载相位配置获取交叉口列表
        phase_config = load_phase_config(config['phase_config_path'])
        self.all_tl_ids = list(phase_config.get('traffic_lights', {}).keys())
        
        # 确保输出目录存在
        os.makedirs(config['output_dir'], exist_ok=True)
        os.makedirs(config['state_dir'], exist_ok=True)
    
    def _copy_rou_file(self, rou_file: str, group_id: int) -> str:
        """
        复制流量文件到临时目录
        
        Args:
            rou_file: 原始流量文件路径
            group_id: 组 ID (用于文件名区分)
            
        Returns:
            临时文件路径
        """
        basename = os.path.basename(rou_file)
        name, ext = os.path.splitext(basename)
        temp_name = f"{name}_group{group_id}{ext}"
        temp_path = os.path.join(self.temp_dir, temp_name)
        
        shutil.copy2(rou_file, temp_path)
        return temp_path
    
    def _extract_date_from_rou(self, rou_file: str) -> str:
        """从 rou 文件名提取日期"""
        basename = os.path.basename(rou_file)
        if '_2026-' in basename:
            date_part = basename.split('_2026-')[1].split('.rou.xml')[0]
            return f'2026-{date_part}'
        return 'unknown'
    
    def _check_day_completed(self, date: str) -> bool:
        """检查某天的数据是否已生成完成"""
        output_file = os.path.join(
            self.config['output_dir'],
            f'samples_{date}.jsonl'
        )
        return os.path.exists(output_file)
    
    def run(self) -> Dict[str, Any]:
        """
        运行交叉口级别并行仿真
        
        Returns:
            汇总结果
        """
        try:
            # 1. 划分交叉口组
            tl_groups = split_into_groups(self.all_tl_ids, self.intersection_groups)
            print(f"将 {len(self.all_tl_ids)} 个交叉口分成 {len(tl_groups)} 组")
            for i, group in enumerate(tl_groups):
                print(f"  组 {i}: {len(group)} 个交叉口")
            
            # 2. 准备所有任务
            all_tasks = []
            days_to_process = []
            task_id = 0
            
            for rou_file in self.rou_files:
                date = self._extract_date_from_rou(rou_file)
                
                # 增量模式检查
                if self.config.get('incremental', True):
                    if self._check_day_completed(date):
                        print(f"跳过 {date} (已完成)")
                        continue
                
                days_to_process.append((rou_file, date))
                
                # 为每个交叉口组创建任务
                for group_idx, tl_group in enumerate(tl_groups):
                    # 复制流量文件
                    temp_rou = self._copy_rou_file(rou_file, group_idx)
                    
                    all_tasks.append((
                        task_id,
                        temp_rou,
                        self.config,
                        tl_group
                    ))
                    task_id += 1
            
            if not all_tasks:
                print("所有天数已处理完成")
                return self._rebuild_from_existing()
            
            print(f"\n准备处理 {len(days_to_process)} 天 × {len(tl_groups)} 组 = {len(all_tasks)} 个任务")
            print(f"使用 {self.num_workers} 个并行进程")
            
            # 3. 并行执行
            results_by_date: Dict[str, List[Dict]] = {}
            
            with Pool(processes=self.num_workers) as pool:
                for result in tqdm(
                    pool.imap_unordered(simulate_intersection_group, all_tasks),
                    total=len(all_tasks),
                    desc="处理交叉口组"
                ):
                    date = result['date']
                    if date not in results_by_date:
                        results_by_date[date] = []
                    results_by_date[date].append(result)
            
            # 4. 合并每天的结果
            all_samples = []
            samples_by_day = {}
            errors = []
            successful_days = 0
            failed_days = 0
            
            for date, day_results in results_by_date.items():
                day_samples = []
                day_errors = []
                
                for result in day_results:
                    if result['status'] == 'success':
                        day_samples.extend(result['samples'])
                    else:
                        day_errors.append(result['error'])
                
                if day_errors:
                    errors.extend(day_errors)
                    if not day_samples:
                        failed_days += 1
                        continue
                
                successful_days += 1
                all_samples.extend(day_samples)
                samples_by_day[date] = len(day_samples)
                
                # 保存每天的数据
                output_file = os.path.join(
                    self.config['output_dir'],
                    f'samples_{date}.jsonl'
                )
                self._save_samples_to_jsonl(day_samples, output_file)
            
            # 5. 统计时段分布
            samples_by_period = get_time_period_stats(all_samples)
            
            # 6. 生成 metadata
            results = {
                "total_days": len(days_to_process),
                "successful": successful_days,
                "failed": failed_days,
                "total_samples": len(all_samples),
                "samples_by_day": samples_by_day,
                "samples_by_period": samples_by_period,
                "errors": errors
            }
            
            self._save_metadata(results)
            
            return results
            
        finally:
            # 清理临时目录
            self._cleanup()
    
    def _save_samples_to_jsonl(self, samples: List[dict], output_path: str):
        """保存样本到 JSONL 文件"""
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            for sample in samples:
                json_line = json.dumps(sample, ensure_ascii=False)
                f.write(json_line + '\n')
    
    def _save_metadata(self, results: Dict[str, Any]):
        """保存 metadata.json"""
        metadata = {
            'generated_at': datetime.now().isoformat(),
            'version': '1.0',
            'parallel_mode': 'intersection',
            'total_days': results['total_days'],
            'successful_days': results['successful'],
            'failed_days': results['failed'],
            'total_samples': results['total_samples'],
            'samples_by_day': results['samples_by_day'],
            'samples_by_period': results['samples_by_period'],
            'errors': results.get('errors', []),
            'config': {
                'intersection_groups': self.intersection_groups,
                'num_workers': self.num_workers,
                'warmup_steps': self.config.get('warmup_steps', 300)
            }
        }
        
        metadata_path = os.path.join(self.config['output_dir'], 'metadata.json')
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
    
    def _rebuild_from_existing(self) -> Dict[str, Any]:
        """从已存在的 JSONL 文件重建统计信息"""
        samples_by_day = {}
        samples_by_period = {'morning_peak': 0, 'evening_peak': 0, 'off_peak': 0}
        total_samples = 0
        
        jsonl_files = glob.glob(os.path.join(self.config['output_dir'], 'samples_*.jsonl'))
        
        for jsonl_file in jsonl_files:
            basename = os.path.basename(jsonl_file)
            if basename.startswith('samples_') and basename.endswith('.jsonl'):
                date = basename[8:-6]
            else:
                continue
            
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
    
    def _cleanup(self):
        """清理临时文件"""
        if os.path.exists(self.temp_dir):
            try:
                shutil.rmtree(self.temp_dir)
                print(f"\n已清理临时目录: {self.temp_dir}")
            except Exception as e:
                print(f"\n警告: 清理临时目录失败: {e}")
