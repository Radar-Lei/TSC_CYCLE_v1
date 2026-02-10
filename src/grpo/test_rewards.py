#!/usr/bin/env python3
"""快速测试 reward 函数的格式匹配能力"""

import json
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.grpo.rewards import (
    init_rewards,
    match_format_exactly,
    match_format_approximately,
    check_constraints,
    think_length_reward,
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

def main():
    # 初始化 rewards（需要配置文件）
    config_path = "config/config.json"
    baseline_path = "outputs/grpo/baseline.json"

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
    print("测试完成")
    print("="*70)

if __name__ == "__main__":
    main()
