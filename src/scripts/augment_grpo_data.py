#!/usr/bin/env python3
"""
GRPO 训练数据增强：

1. 对原始数据做多样化变换（重映射 phase_id、扰动 min/max_green 范围）
2. 生成全新合成样本（覆盖训练数据中缺失的参数空间）

输出格式与 generate_grpo_simple_data.py 一致，可直接作为 grpo_train.jsonl 使用。
"""

import argparse
import json
import random
import re
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List


SYSTEM_PROMPT = (
    "你是交通信号配时优化专家。\n"
    "请认真分析预测得到的下个周期各个相位的交通状态，给出下个周期的配时方案，并给出你的推理过程。\n"
    "将推理过程放在 <start_working_out> 和 <end_working_out> 之间。\n"
    "然后，将你的最终方案放在 <SOLUTION> 和 </SOLUTION> 之间。"
)

TASK_TEMPLATE = """任务(必须完成):
主要基于 prediction.phase_waits 的 pred_saturation(已计算),在满足硬约束前提下输出下一周期各相位最终绿灯时间 final(单位:秒)。

字段说明(仅说明含义):
- prediction.phase_waits[*].min_green / max_green:秒。
- prediction.phase_waits[*].pred_wait:预测等待车辆数。
- prediction.phase_waits[*].pred_saturation:预测饱和度(pred_wait / capacity)。
- prediction.phase_waits[*].capacity:相位容量(车辆容纳数)。

硬约束(必须满足):
1) 相位顺序固定:严格按 prediction.phase_waits 的顺序输出;不可跳相、不可重排。
2) 每相位约束:final 必须满足 prediction.phase_waits[*].min_green ≤ final ≤ prediction.phase_waits[*].max_green。
3) final 必须为整数秒。

提示(非硬约束):
- capacity 仅供参考,最终决策以 pred_saturation 为主。

输出格式:
1) JSON 顶层必须是数组(list);数组长度必须等于 prediction.phase_waits 的长度。
2) 数组元素必须为对象:{"phase_id": <int>, "final": <int>};不允许输出其它字段。"""


# ═══════════════════════════════════════════════════════════════
# Part 1: 原始数据多样化变换
# ═══════════════════════════════════════════════════════════════

def inject_pred_wait(sample: Dict[str, Any]) -> Dict[str, Any]:
    """给原始样本的 prompt 注入 pred_wait 字段（= pred_saturation * capacity）。"""
    new_sample = deepcopy(sample)
    user_msg = new_sample["prompt"][1]["content"]

    json_match = re.search(
        r'【cycle_predict_input_json】(.*?)【/cycle_predict_input_json】',
        user_msg, re.DOTALL,
    )
    if not json_match:
        return new_sample

    try:
        pred_dict = json.loads(json_match.group(1))
    except json.JSONDecodeError:
        return new_sample

    for pw in pred_dict["prediction"]["phase_waits"]:
        if "pred_wait" not in pw:
            sat = pw.get("pred_saturation", 0.0)
            cap = pw.get("capacity", 30)
            pw["pred_wait"] = round(sat * cap, 2)

    new_json = json.dumps(pred_dict, ensure_ascii=False, indent=2)
    new_user = f"【cycle_predict_input_json】{new_json}【/cycle_predict_input_json】\n{TASK_TEMPLATE}"
    new_sample["prompt"][1]["content"] = new_user
    return new_sample


# Phase ID 重映射模板：将原始偶数 ID 映射到新的 ID 空间
REMAP_TEMPLATES = [
    # 连续整数起始
    {0: 1, 2: 2, 4: 3, 6: 4, 8: 5},
    {0: 1, 2: 2, 4: 3},
    {0: 2, 2: 3, 4: 4, 6: 5, 8: 6},
    {0: 3, 2: 4, 4: 5, 6: 6, 8: 7},
    # 奇数 ID
    {0: 1, 2: 3, 4: 5, 6: 7, 8: 9},
    {0: 1, 2: 3, 4: 5},
    {0: 3, 2: 5, 4: 7},
    # 高 ID
    {0: 5, 2: 6, 4: 7, 6: 8, 8: 9},
    {0: 10, 2: 11, 4: 12, 6: 13, 8: 14},
    # 保持原始但偏移
    {0: 0, 2: 1, 4: 2, 6: 3, 8: 4},
]


def perturb_green_range(min_green: int, max_green: int) -> tuple:
    """扰动 min/max_green，扩展训练数据中从未出现的范围。"""
    strategy = random.random()

    if strategy < 0.3:
        # 提高 min_green（训练数据只到 34，扩展到 60）
        new_min = random.randint(max(min_green, 20), 60)
        new_max = new_min + random.randint(15, 60)
        new_max = min(new_max, 150)
    elif strategy < 0.5:
        # 压缩区间（训练数据区间一般很大 50-90s）
        mid = (min_green + max_green) // 2
        half_range = random.randint(5, 15)
        new_min = max(5, mid - half_range)
        new_max = mid + half_range
    elif strategy < 0.7:
        # 降低 max_green（训练数据 55-120，扩展到 30-55）
        new_min = random.randint(5, 25)
        new_max = random.randint(30, 55)
    else:
        # 原始范围上做小幅扰动 ±30%
        delta_min = int(min_green * random.uniform(-0.3, 0.3))
        delta_max = int(max_green * random.uniform(-0.3, 0.3))
        new_min = max(5, min_green + delta_min)
        new_max = max(new_min + 10, max_green + delta_max)
        new_max = min(new_max, 150)

    return new_min, new_max


def perturb_saturation(pred_saturation: float) -> float:
    """扰动饱和度，确保覆盖全范围。"""
    strategy = random.random()

    if strategy < 0.2:
        # 完全随机
        return round(random.uniform(0.0, 2.0), 4)
    elif strategy < 0.4:
        # 反转：低变高，高变低
        inverted = max(0.0, 1.0 - pred_saturation + random.uniform(-0.2, 0.2))
        return round(inverted, 4)
    else:
        # 原始值 ± 扰动
        delta = random.uniform(-0.3, 0.3)
        return round(max(0.0, pred_saturation + delta), 4)


def diversify_original_sample(sample: Dict[str, Any]) -> Dict[str, Any]:
    """对一条原始 GRPO 样本做多样化变换。"""
    new_sample = deepcopy(sample)
    user_msg = new_sample["prompt"][1]["content"]

    # 从 prompt 中提取 prediction JSON
    json_match = re.search(
        r'【cycle_predict_input_json】(.*?)【/cycle_predict_input_json】',
        user_msg, re.DOTALL,
    )
    if not json_match:
        return new_sample

    try:
        pred_dict = json.loads(json_match.group(1))
    except json.JSONDecodeError:
        return new_sample

    phase_waits = pred_dict["prediction"]["phase_waits"]

    # 选择一个重映射模板
    remap = random.choice(REMAP_TEMPLATES)

    new_phase_waits = []
    for pw in phase_waits:
        old_id = pw["phase_id"]
        new_id = remap.get(old_id, old_id + random.randint(1, 5))

        new_min, new_max = perturb_green_range(pw["min_green"], pw["max_green"])
        new_sat = perturb_saturation(pw["pred_saturation"])
        new_cap = max(15, pw["capacity"] + random.randint(-10, 15))
        new_wait = round(new_sat * new_cap, 2)

        new_phase_waits.append({
            "phase_id": new_id,
            "pred_wait": new_wait,
            "pred_saturation": new_sat,
            "min_green": new_min,
            "max_green": new_max,
            "capacity": new_cap,
        })

    # 重建 prediction JSON
    new_pred = {
        "prediction": {
            "as_of": pred_dict["prediction"]["as_of"],
            "phase_waits": new_phase_waits,
        }
    }
    new_json = json.dumps(new_pred, ensure_ascii=False, indent=2)
    new_user = f"【cycle_predict_input_json】{new_json}【/cycle_predict_input_json】\n{TASK_TEMPLATE}"

    new_sample["prompt"][1]["content"] = new_user
    new_sample["metadata"]["source"] = "diversified_original"

    return new_sample


def diversify_originals(
    original_path: str, num_variants: int, seed: int
) -> List[Dict[str, Any]]:
    """从原始数据中随机抽样并做多样化变换。"""
    random.seed(seed)

    originals = []
    with open(original_path, "r", encoding="utf-8") as f:
        for line in f:
            originals.append(json.loads(line.strip()))

    # 随机抽样做变换
    indices = [random.randint(0, len(originals) - 1) for _ in range(num_variants)]
    variants = []
    for idx in indices:
        variant = diversify_original_sample(originals[idx])
        variants.append(variant)

    return variants


# ═══════════════════════════════════════════════════════════════
# Part 2: 全新合成样本生成
# ═══════════════════════════════════════════════════════════════

PHASE_ID_TEMPLATES = [
    [1, 2, 3, 4], [1, 2, 3], [1, 2, 3, 4, 5], [1, 2, 3, 4, 5, 6],
    [2, 3, 4, 5], [3, 4, 5, 6],
    [1, 3, 5], [1, 3, 5, 7], [1, 3],
    [0, 1, 2, 3], [1, 2, 4, 6], [0, 1, 3, 5],
    [2, 4, 6, 8], [1, 4, 7], [0, 3, 6],
    [0, 1, 2, 3], [0, 2, 4, 6],
    [1, 2], [3, 4], [1, 4], [2, 5],
    [0, 1, 2, 3, 4, 5], [1, 2, 3, 4, 5, 6],
    [5, 6, 7, 8], [0, 2, 4], [0, 4, 6], [0, 4, 8], [0, 6, 8],
]


def random_timestamp() -> str:
    base = datetime(2026, 1, 1)
    offset = timedelta(
        days=random.randint(0, 365), hours=random.randint(6, 22),
        minutes=random.randint(0, 59), seconds=random.randint(0, 59),
    )
    return (base + offset).strftime("%Y-%m-%d %H:%M:%S")


def random_phase_wait(phase_id: int) -> Dict[str, Any]:
    min_green = random.randint(5, 60)
    max_green = min_green + random.randint(10, 80)
    max_green = min(max_green, 150)
    capacity = random.randint(15, 60)

    r = random.random()
    if r < 0.25:
        pred_saturation = round(random.uniform(0.0, 0.2), 4)
    elif r < 0.50:
        pred_saturation = round(random.uniform(0.2, 0.6), 4)
    elif r < 0.80:
        pred_saturation = round(random.uniform(0.6, 1.0), 4)
    else:
        pred_saturation = round(random.uniform(1.0, 2.5), 4)

    pred_wait = round(pred_saturation * capacity, 2)

    return {
        "phase_id": phase_id,
        "pred_wait": pred_wait,
        "pred_saturation": pred_saturation,
        "min_green": min_green,
        "max_green": max_green,
        "capacity": capacity,
    }


def generate_synthetic_sample(phase_ids: List[int]) -> Dict[str, Any]:
    timestamp = random_timestamp()
    phase_waits = [random_phase_wait(pid) for pid in phase_ids]

    prediction_dict = {"prediction": {"as_of": timestamp, "phase_waits": phase_waits}}
    prediction_json = json.dumps(prediction_dict, ensure_ascii=False, indent=2)
    user_content = f"【cycle_predict_input_json】{prediction_json}【/cycle_predict_input_json】\n{TASK_TEMPLATE}"

    prompt = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]
    metadata = {
        "state_file": "synthetic",
        "source": "synthetic",
        "tl_id": f"synthetic_{random.randint(1, 200)}",
        "sim_time": random.uniform(0, 86400),
        "date": timestamp[:10],
        "cycle_count": random.randint(1, 100),
    }
    return {"prompt": prompt, "metadata": metadata}


def generate_synthetics(num_samples: int, seed: int) -> List[Dict[str, Any]]:
    random.seed(seed + 1000)
    samples = []
    for _ in range(num_samples):
        phase_ids = random.choice(PHASE_ID_TEMPLATES)
        samples.append(generate_synthetic_sample(phase_ids))
    return samples


# ═══════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Augment GRPO training data")
    parser.add_argument("--original", default="outputs/grpo_simple/grpo_train_original.jsonl",
                        help="原始 GRPO 数据路径")
    parser.add_argument("--output", default="outputs/grpo_simple/grpo_train.jsonl",
                        help="最终合并输出路径")
    parser.add_argument("--num-diversified", type=int, default=8000,
                        help="从原始数据变换生成的样本数")
    parser.add_argument("--num-synthetic", type=int, default=5000,
                        help="全新合成样本数")
    parser.add_argument("--seed", type=int, default=42, help="随机种子")
    args = parser.parse_args()

    original_path = Path(args.original)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 读取原始数据，并注入 pred_wait 字段
    originals = []
    with original_path.open("r", encoding="utf-8") as f:
        for line in f:
            originals.append(json.loads(line.strip()))
    print(f"[原始数据] {len(originals)} 条")

    print("[原始数据] 注入 pred_wait 字段...")
    originals = [inject_pred_wait(s) for s in originals]

    # Part 1: 原始数据多样化变换
    print(f"[多样化变换] 从原始数据生成 {args.num_diversified} 条变体...")
    diversified = diversify_originals(args.original, args.num_diversified, args.seed)
    print(f"[多样化变换] 完成: {len(diversified)} 条")

    # Part 2: 全新合成
    print(f"[合成数据] 生成 {args.num_synthetic} 条全新样本...")
    synthetics = generate_synthetics(args.num_synthetic, args.seed)
    print(f"[合成数据] 完成: {len(synthetics)} 条")

    # 合并：原始 + 变体 + 合成
    all_samples = originals + diversified + synthetics
    random.seed(args.seed + 999)
    random.shuffle(all_samples)

    with output_path.open("w", encoding="utf-8") as f:
        for sample in all_samples:
            f.write(json.dumps(sample, ensure_ascii=False) + "\n")

    total = len(all_samples)
    print(f"\n[最终输出] {output_path}")
    print(f"  原始:     {len(originals)}")
    print(f"  多样化:   {len(diversified)}")
    print(f"  合成:     {len(synthetics)}")
    print(f"  总计:     {total}")

    # 统计 phase_id 分布
    phase_counts: Dict[int, int] = {}
    for s in all_samples:
        user_msg = s["prompt"][1]["content"]
        for m in re.finditer(r'"phase_id":\s*(\d+)', user_msg):
            pid = int(m.group(1))
            phase_counts[pid] = phase_counts.get(pid, 0) + 1
    print(f"  Phase ID 分布: {dict(sorted(phase_counts.items()))}")


if __name__ == "__main__":
    main()
