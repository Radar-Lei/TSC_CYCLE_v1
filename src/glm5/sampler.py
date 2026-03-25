"""从 train.jsonl 分层抽样训练数据，确保交叉口和饱和度分布均衡

按 (tl_id, 饱和度桶) 组合分层，每层按比例抽样并保证至少 1 个样本，
最终精确输出 n 条训练数据。支持固定 seed 可重复抽样。
"""

import argparse
import json
import os
import random
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


def _saturation_bucket(sample_dict: dict) -> str:
    """计算样本的平均饱和度并分桶

    Args:
        sample_dict: 训练样本字典，包含 prediction.phase_waits

    Returns:
        "low" (avg < 0.3), "med" (0.3 <= avg < 0.7), "high" (avg >= 0.7)
    """
    phase_waits = sample_dict["prediction"]["phase_waits"]
    if not phase_waits:
        return "low"
    avg_sat = sum(pw["pred_saturation"] for pw in phase_waits) / len(phase_waits)
    if avg_sat < 0.3:
        return "low"
    elif avg_sat < 0.7:
        return "med"
    else:
        return "high"


@dataclass
class SamplingStats:
    """抽样统计信息

    Attributes:
        total_source: 数据源总量
        total_sampled: 抽样总量
        tl_id_counts: 每个 tl_id 的采样数
        bucket_counts: low/med/high 各多少
    """

    total_source: int = 0
    total_sampled: int = 0
    tl_id_counts: Dict[str, int] = field(default_factory=dict)
    bucket_counts: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "total_source": self.total_source,
            "total_sampled": self.total_sampled,
            "tl_id_counts": self.tl_id_counts,
            "bucket_counts": self.bucket_counts,
        }

    def print_summary(self) -> None:
        """打印抽样摘要"""
        print(f"[采样] 总量: {self.total_sampled}/{self.total_source}")
        bucket_str = ", ".join(
            f"{k}={v}" for k, v in sorted(self.bucket_counts.items())
        )
        print(f"[采样] 饱和度分布: {bucket_str}")
        total_tl = len(self.tl_id_counts)
        source_tl = len(set(self.tl_id_counts.keys()))
        print(f"[采样] 交叉口覆盖: {source_tl}/{total_tl}")


class StratifiedSampler:
    """分层抽样器

    按 (tl_id, 饱和度桶) 组合分层，每层按比例抽样。
    使用固定 seed 保证可重复性。
    """

    def __init__(self, seed: int = 42):
        self.seed = seed

    def load_data(self, jsonl_path: str) -> List[dict]:
        """逐行读取 jsonl 文件

        Args:
            jsonl_path: jsonl 文件路径

        Returns:
            训练样本字典列表
        """
        data = []
        with open(jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    data.append(json.loads(line))
        print(f"[采样] 加载 {len(data)} 条数据")
        return data

    def sample(
        self, data: List[dict], n: int = 5000
    ) -> Tuple[List[dict], SamplingStats]:
        """分层抽样

        策略:
        1. 按 (tl_id, bucket) 组合分组
        2. 每组按比例分配配额，至少 1 个
        3. 不足配额的组取全部
        4. 总数多退少补

        Args:
            data: 训练样本字典列表
            n: 目标抽样数量

        Returns:
            (抽样结果列表, 统计信息)
        """
        rng = random.Random(self.seed)

        # 1. 按 (tl_id, bucket) 分组
        groups: Dict[Tuple[str, str], List[dict]] = defaultdict(list)
        for item in data:
            tl_id = item["metadata"]["tl_id"]
            bucket = _saturation_bucket(item)
            groups[(tl_id, bucket)].append(item)

        # 2. 计算每组配额
        total = len(data)
        quotas: Dict[Tuple[str, str], int] = {}
        for key, group in groups.items():
            quotas[key] = max(1, round(n * len(group) / total))

        # 3. 按配额抽样
        sampled = []
        sampled_set = set()  # 用 index 追踪已选中的样本

        # 建立全局 index 映射
        item_to_idx = {id(item): idx for idx, item in enumerate(data)}

        for key in sorted(groups.keys()):  # 排序保证确定性
            group = groups[key]
            quota = quotas[key]
            if len(group) <= quota:
                chosen = group[:]
            else:
                chosen = rng.sample(group, quota)
            sampled.extend(chosen)
            for item in chosen:
                sampled_set.add(item_to_idx[id(item)])

        # 4. 调整到精确 n 条
        if len(sampled) > n:
            # 随机去掉多余的
            rng.shuffle(sampled)
            sampled = sampled[:n]
        elif len(sampled) < n:
            # 从未选中的样本中随机补充
            remaining = [
                item for idx, item in enumerate(data) if idx not in sampled_set
            ]
            need = n - len(sampled)
            if need <= len(remaining):
                extra = rng.sample(remaining, need)
            else:
                extra = remaining
            sampled.extend(extra)

        # 5. 计算统计信息
        tl_id_counts: Dict[str, int] = defaultdict(int)
        bucket_counts: Dict[str, int] = defaultdict(int)
        for item in sampled:
            tl_id = item["metadata"]["tl_id"]
            bucket = _saturation_bucket(item)
            tl_id_counts[tl_id] += 1
            bucket_counts[bucket] += 1

        stats = SamplingStats(
            total_source=total,
            total_sampled=len(sampled),
            tl_id_counts=dict(tl_id_counts),
            bucket_counts=dict(bucket_counts),
        )

        return sampled, stats


def sample_training_data(
    input_path: str,
    n: int = 5000,
    output_path: Optional[str] = None,
    seed: int = 42,
) -> Tuple[List[dict], SamplingStats]:
    """便捷函数: 加载数据、分层抽样、可选输出到文件

    Args:
        input_path: train.jsonl 文件路径
        n: 目标抽样数量
        output_path: 输出 jsonl 路径 (None 则不写文件)
        seed: 随机种子

    Returns:
        (抽样结果列表, 统计信息)
    """
    sampler = StratifiedSampler(seed=seed)
    data = sampler.load_data(input_path)
    sampled, stats = sampler.sample(data, n=n)

    if output_path is not None:
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            for item in sampled:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
        print(f"[采样] 已写入 {output_path}")

    stats.print_summary()
    return sampled, stats


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="从 train.jsonl 分层抽样训练数据")
    parser.add_argument(
        "--input",
        default="outputs/data/train.jsonl",
        help="输入 jsonl 文件路径",
    )
    parser.add_argument(
        "--output",
        default="outputs/glm5/sampled_5000.jsonl",
        help="输出 jsonl 文件路径",
    )
    parser.add_argument("--n", type=int, default=5000, help="抽样数量")
    parser.add_argument("--seed", type=int, default=42, help="随机种子")
    args = parser.parse_args()

    sample_training_data(
        input_path=args.input,
        n=args.n,
        output_path=args.output,
        seed=args.seed,
    )
