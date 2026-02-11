#!/usr/bin/env python3
"""快速测试 reward 函数的格式匹配能力和 SUMO 分布验证"""

import argparse
import json
import os
import random
import re
import statistics
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.grpo.rewards import (
    init_rewards,
    match_format_exactly,
    match_format_approximately,
    check_constraints,
    think_length_reward,
    sumo_simulation_reward,
)

# 模拟 completion 格式（模型实际生成的格式，不含 <start_working_out> 前缀）
test_completions = [
    # 格式正确的例子
    [{
        "content": "我分析了各相位的饱和度情况。phase 0 饱和度 1.2，需要最大绿灯时间。phase 2 饱和度 0.6，可以适当分配。<end_working_out><SOLUTION>[{\"phase_id\": 0, \"final\": 119}, {\"phase_id\": 2, \"final\": 67}]</SOLUTION>"
    }],
    # 格式错误：缺少 <end_working_out>
    [{
        "content": "我分析了情况<SOLUTION>[{\"phase_id\": 0, \"final\": 119}]</SOLUTION>"
    }],
    # 格式错误：缺少 <SOLUTION>
    [{
        "content": "我分析了情况<end_working_out>[{\"phase_id\": 0, \"final\": 119}]"
    }],
    # 格式正确但有换行
    [{
        "content": "分析：phase 0 高饱和度<end_working_out>\n\n<SOLUTION>[{\"phase_id\": 0, \"final\": 100}]</SOLUTION>"
    }],
]

# 模拟 prompt（用于 check_constraints）
test_prompts = [
    [
        {"role": "system", "content": "系统提示"},
        {"role": "user", "content": """
{
  "prediction": {
    "phase_waits": [
      {"phase_id": 0, "pred_saturation": 1.2, "min_green": 21, "max_green": 119, "capacity": 60},
      {"phase_id": 2, "pred_saturation": 0.6, "min_green": 18, "max_green": 111, "capacity": 45}
    ]
  }
}
"""}
    ],
    [{"role": "system", "content": "系统提示"}, {"role": "user", "content": "无效 prompt"}],
    [{"role": "system", "content": "系统提示"}, {"role": "user", "content": "无效 prompt"}],
    [
        {"role": "system", "content": "系统提示"},
        {"role": "user", "content": """
{
  "prediction": {
    "phase_waits": [
      {"phase_id": 0, "pred_saturation": 1.0, "min_green": 10, "max_green": 100, "capacity": 30}
    ]
  }
}
"""}
    ],
]


def validate_sumo_distribution(config_path: str, sample_size: int = 100):
    """从 grpo_train.jsonl 分层抽样并验证 SUMO reward 分布。

    Args:
        config_path: 配置文件路径
        sample_size: 抽样数量

    Returns:
        scores: SUMO reward 分数列表
    """
    # 加载配置
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)

    grpo_data_dir = config["paths"]["grpo_data_dir"]
    grpo_train_path = os.path.join(grpo_data_dir, "grpo_train.jsonl")

    if not os.path.exists(grpo_train_path):
        raise FileNotFoundError(f"GRPO 训练数据不存在: {grpo_train_path}")

    # 读取所有样本并按 scenario 分组
    print(f"[加载] 从 {grpo_train_path} 读取数据...")
    samples_by_scenario = {}

    with open(grpo_train_path, 'r', encoding='utf-8') as f:
        for line in f:
            sample = json.loads(line)
            # 从 state_file 解析 scenario (例如 "outputs/states/arterial4x4_10/..." -> "arterial4x4_10")
            state_file = sample["metadata"]["state_file"]
            scenario = state_file.split('/')[2]

            if scenario not in samples_by_scenario:
                samples_by_scenario[scenario] = []
            samples_by_scenario[scenario].append(sample)

    total_samples = sum(len(samples) for samples in samples_by_scenario.values())
    print(f"[统计] 共 {total_samples} 条样本，{len(samples_by_scenario)} 个场景")

    # 分层抽样
    selected_samples = []
    for scenario, samples in samples_by_scenario.items():
        # 按比例抽样
        scenario_sample_size = max(1, int(sample_size * len(samples) / total_samples))
        if len(samples) <= scenario_sample_size:
            selected_samples.extend(samples)
        else:
            selected_samples.extend(random.sample(samples, scenario_sample_size))

    # 如果抽样不足，随机补充
    if len(selected_samples) < sample_size:
        all_samples = [s for samples in samples_by_scenario.values() for s in samples]
        remaining = sample_size - len(selected_samples)
        additional = random.sample([s for s in all_samples if s not in selected_samples],
                                  min(remaining, len(all_samples) - len(selected_samples)))
        selected_samples.extend(additional)

    # 如果超出，随机移除
    if len(selected_samples) > sample_size:
        selected_samples = random.sample(selected_samples, sample_size)

    print(f"[抽样] 选择 {len(selected_samples)} 条样本进行验证")

    # 对每条样本构造满足约束的 completion 并调用 sumo_simulation_reward
    prompts = []
    completions = []
    state_files = []
    tl_ids = []

    print("[构造] 生成满足约束的测试 completion...")
    for sample in selected_samples:
        prompt = sample["prompt"]
        metadata = sample["metadata"]

        # 解析 phase_waits
        prompt_content = prompt[-1]["content"]
        phase_waits_match = re.search(r'"phase_waits"\s*:\s*(\[.*?\])', prompt_content, re.DOTALL)
        if not phase_waits_match:
            print(f"[警告] 无法解析 phase_waits，跳过样本")
            continue

        phase_waits = json.loads(phase_waits_match.group(1))

        # 构造 completion：使用 min_green 作为 final 值（保证满足 L2 约束）
        phases = [{"phase_id": p["phase_id"], "final": p["min_green"]} for p in phase_waits]
        completion_text = f"<end_working_out><SOLUTION>{json.dumps(phases)}</SOLUTION>"

        prompts.append(prompt)
        completions.append([{"content": completion_text}])
        state_files.append(metadata["state_file"])
        tl_ids.append(metadata["tl_id"])

    if len(completions) == 0:
        raise ValueError("没有有效样本可用于验证")

    print(f"[仿真] 运行 {len(completions)} 个 SUMO 仿真...")
    # 调用 sumo_simulation_reward
    scores = sumo_simulation_reward(
        prompts=prompts,
        completions=completions,
        state_file=state_files,
        tl_id=tl_ids
    )

    return scores


def print_distribution_stats(scores):
    """打印分布统计信息。

    Args:
        scores: SUMO reward 分数列表
    """
    n = len(scores)

    # 基本统计
    mean = statistics.mean(scores)
    std = statistics.stdev(scores) if n > 1 else 0.0
    min_score = min(scores)
    max_score = max(scores)

    # 分位数（手动计算）
    sorted_scores = sorted(scores)

    def percentile(data, p):
        """计算分位数"""
        k = (len(data) - 1) * p
        f = int(k)
        c = int(k) + 1
        if c >= len(data):
            return data[-1]
        d0 = data[f] * (c - k)
        d1 = data[c] * (k - f)
        return d0 + d1

    p10 = percentile(sorted_scores, 0.10)
    p25 = percentile(sorted_scores, 0.25)
    p50 = percentile(sorted_scores, 0.50)
    p75 = percentile(sorted_scores, 0.75)
    p90 = percentile(sorted_scores, 0.90)

    # 唯一值数量
    unique_count = len(set(scores))

    # 负分/零分比例
    negative_count = sum(1 for s in scores if s < 0)
    zero_count = sum(1 for s in scores if s == 0)
    negative_ratio = negative_count / n * 100
    zero_ratio = zero_count / n * 100

    # 输出
    print("")
    print("=" * 42)
    print("========== SUMO Reward 分布验证 ==========")
    print("=" * 42)
    print(f"样本数:   {n}")
    print(f"均值:     {mean:.3f}")
    print(f"标准差:   {std:.3f}")
    print(f"最小值:   {min_score:.3f}")
    print(f"最大值:   {max_score:.3f}")
    print(f"分位数:")
    print(f"  10%: {p10:.3f}")
    print(f"  25%: {p25:.3f}")
    print(f"  50%: {p50:.3f}")
    print(f"  75%: {p75:.3f}")
    print(f"  90%: {p90:.3f}")
    print(f"唯一值数量: {unique_count}")
    print(f"负分比例: {negative_ratio:.1f}%")
    print(f"零分比例: {zero_ratio:.1f}%")
    print("=" * 42)


def check_distribution_quality(scores):
    """检查分布质量是否满足要求。

    Args:
        scores: SUMO reward 分数列表

    Returns:
        (passed, reasons): 是否通过和原因列表
    """
    n = len(scores)
    passed = True
    reasons = []

    # 检查 1: 标准差下界
    std = statistics.stdev(scores) if n > 1 else 0.0
    if std < 0.5:
        passed = False
        reasons.append(f"标准差过低 ({std:.3f} < 0.5)，区分度不够")

    # 检查 2: 唯一值数量下界
    unique_count = len(set(scores))
    threshold = n * 0.3
    if unique_count < threshold:
        passed = False
        reasons.append(f"唯一值数量过低 ({unique_count} < {threshold:.0f})，分布不够连续")

    # 检查 3: 非零比例
    non_zero_count = sum(1 for s in scores if s != 0)
    non_zero_ratio = non_zero_count / n
    if non_zero_ratio < 0.5:
        passed = False
        reasons.append(f"非零比例过低 ({non_zero_ratio*100:.1f}% < 50%)，太多零分")

    return passed, reasons


def run_format_tests(config_path, baseline_path):
    """运行现有的格式测试（保持向后兼容）"""
    print("[初始化] 加载 reward 配置...")
    init_rewards(config_path, baseline_path)

    print("\n" + "="*70)
    print("测试 match_format_exactly")
    print("="*70)

    scores = match_format_exactly(test_completions)
    for i, (completion, score) in enumerate(zip(test_completions, scores)):
        print(f"\n测试 {i+1}:")
        print(f"  内容: {completion[0]['content'][:100]}...")
        print(f"  分数: {score}")

    print("\n" + "="*70)
    print("测试 match_format_approximately")
    print("="*70)

    scores = match_format_approximately(test_completions)
    for i, (completion, score) in enumerate(zip(test_completions, scores)):
        print(f"\n测试 {i+1}:")
        print(f"  分数: {score}")

    print("\n" + "="*70)
    print("测试 check_constraints")
    print("="*70)

    scores = check_constraints(test_prompts, test_completions)
    for i, (prompt, completion, score) in enumerate(zip(test_prompts, test_completions, scores)):
        print(f"\n测试 {i+1}:")
        print(f"  分数: {score}")

    print("\n" + "="*70)
    print("测试 think_length_reward")
    print("="*70)

    scores = think_length_reward(test_completions)
    for i, (completion, score) in enumerate(zip(test_completions, scores)):
        think_content = completion[0]['content'].split("<end_working_out>")[0] if "<end_working_out>" in completion[0]['content'] else "N/A"
        print(f"\n测试 {i+1}:")
        print(f"  思考长度: {len(think_content)} 字符")
        print(f"  估计 tokens: {len(think_content) / 2}")
        print(f"  分数: {score}")

    print("\n" + "="*70)
    print("格式测试完成")
    print("="*70)


def main():
    parser = argparse.ArgumentParser(description="测试 reward 函数和验证 SUMO 分布")
    parser.add_argument("--sumo-validate", action="store_true",
                       help="运行 SUMO 分布验证（需要 SUMO 环境）")
    parser.add_argument("--sample-size", type=int, default=100,
                       help="验证样本数量（默认 100）")
    parser.add_argument("--config", type=str, default="config/config.json",
                       help="配置文件路径（默认 config/config.json）")

    args = parser.parse_args()

    config_path = args.config

    # 从 config 读取 baseline_path
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    baseline_path = os.path.join(config["paths"]["grpo_data_dir"], "baseline.json")

    if args.sumo_validate:
        # SUMO 验证模式
        print("="*70)
        print("SUMO Reward 分布验证模式")
        print("="*70)

        # 初始化 rewards
        print("[初始化] 加载 reward 配置和 baseline...")
        init_rewards(config_path, baseline_path)

        # 运行格式测试
        print("\n[格式测试] 先运行格式测试确保基本功能正常...")
        run_format_tests(config_path, baseline_path)

        # 运行 SUMO 分布验证
        print("\n[SUMO 验证] 开始分布验证...")
        scores = validate_sumo_distribution(config_path, args.sample_size)

        # 输出统计
        print_distribution_stats(scores)

        # 检查质量
        passed, reasons = check_distribution_quality(scores)

        if not passed:
            print("\n" + "\033[91m" + "="*42)
            print("警告: SUMO Reward 分布验证未通过!")
            print("="*42 + "\033[0m")
            for reason in reasons:
                print(f"  - {reason}")
            print("\n请检查 reward 公式和 baseline 配置。")
            sys.exit(1)
        else:
            print("\n" + "\033[92m" + "="*42)
            print("✓ SUMO Reward 分布验证通过")
            print("="*42 + "\033[0m")
    else:
        # 只运行格式测试（向后兼容）
        run_format_tests(config_path, baseline_path)


if __name__ == "__main__":
    main()
