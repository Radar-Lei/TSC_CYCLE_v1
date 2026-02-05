"""手工示例生成器

生成 SFT 训练所需的手工示例数据,按复杂度分层:
- 简单场景 (50 条): 2-3 相位,单一明显瓶颈,直接推理
- 中等场景 (30 条): 3-4 相位,多个中等拥堵,需要权衡
- 复杂场景 (20 条): 4+ 相位,边界约束,需要完整推理链
"""

import json
import random
from typing import Any


# 系统提示词 (参考 sample_prompt_result.md)
SYSTEM_PROMPT = """你是交通信号配时优化专家。
【cycle_predict_input_json】{input_json}【/cycle_predict_input_json】

任务(必须完成):
主要基于 prediction.phase_waits 的 pred_saturation(已计算),在满足硬约束前提下输出下一周期各相位最终绿灯时间 final(单位:秒)。

字段说明(仅说明含义):
- prediction.phase_waits[*].min_green / max_green: 秒。
- prediction.phase_waits[*].pred_saturation: 预测饱和度(pred_wait / capacity)。
- prediction.phase_waits[*].capacity: 相位容量(车辆容纳数)。

硬约束(必须满足):
1) 相位顺序固定: 严格按 prediction.phase_waits 的顺序输出;不可跳相、不可重排。
2) 每相位约束: final 必须满足 prediction.phase_waits[*].min_green ≤ final ≤ prediction.phase_waits[*].max_green。
3) final 必须为整数秒。

提示(非硬约束):
- capacity 仅供参考,最终决策以 pred_saturation 为主。

输出要求(必须严格遵守):
1) 必须输出思考过程,并用 <think>...</think> 包裹(内容可简短,但必须有)。
2) 思考过程后必须输出最终 JSON。
3) JSON 顶层必须是数组(list);数组长度必须等于 prediction.phase_waits 的长度。
4) 数组元素必须为对象: {{"phase_id": <int>, "final": <int>}};不允许输出其它字段。
5) phase_id 必须与 prediction.phase_waits 中对应项一致,且顺序必须与 prediction.phase_waits 完全一致。"""


def generate_simple_examples(n: int = 50) -> list[dict[str, Any]]:
    """生成简单场景示例

    特点:
    - 2-3 个相位
    - 单一明显瓶颈 (一个相位饱和度 > 1.0,其他 < 0.3)
    - 直接推理: 增加瓶颈相位,减少空闲相位
    """
    examples = []

    for i in range(n):
        num_phases = random.choice([2, 3])
        bottleneck_idx = random.randint(0, num_phases - 1)

        phases = []
        for j in range(num_phases):
            min_green = random.randint(20, 30)
            max_green = random.randint(40, 60)
            capacity = random.randint(30, 50)

            if j == bottleneck_idx:
                # 瓶颈相位: 饱和度 1.5-2.5
                saturation = round(random.uniform(1.5, 2.5), 4)
                final = max_green  # 使用最大绿灯时间
            else:
                # 空闲相位: 饱和度 0.0-0.3
                saturation = round(random.uniform(0.0, 0.3), 4)
                final = min_green  # 使用最小绿灯时间

            phases.append({
                "phase_id": j + 1,
                "pred_saturation": saturation,
                "min_green": min_green,
                "max_green": max_green,
                "capacity": capacity,
                "final": final,
            })

        # 构造思考过程
        bottleneck = phases[bottleneck_idx]
        think = f"""观察到相位 {bottleneck['phase_id']} 饱和度最高({bottleneck['pred_saturation']}),存在明显拥堵。
其他相位饱和度较低,可以适当减少绿灯时间。
决定将相位 {bottleneck['phase_id']} 调整到最大绿灯时间 {bottleneck['max_green']}s,其他相位使用最小绿灯时间。"""

        # 构造输入 JSON
        input_json = {
            "prediction": {
                "as_of": "2026-01-28 13:12:15",
                "phase_waits": [
                    {k: v for k, v in p.items() if k != "final"}
                    for p in phases
                ],
            }
        }

        # 构造输出
        output = f"<think>{think}</think>" + json.dumps(
            [{"phase_id": p["phase_id"], "final": p["final"]} for p in phases],
            ensure_ascii=False,
        )

        examples.append({
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT.replace("{input_json}", json.dumps(input_json, ensure_ascii=False))},
                {"role": "user", "content": ""},
                {"role": "assistant", "content": output},
            ]
        })

    return examples


def generate_medium_examples(n: int = 30) -> list[dict[str, Any]]:
    """生成中等场景示例

    特点:
    - 3-4 个相位
    - 多个中等拥堵 (饱和度 0.6-1.2)
    - 需要权衡: 根据饱和度比例分配绿灯时间
    """
    examples = []

    for i in range(n):
        num_phases = random.choice([3, 4])

        phases = []
        for j in range(num_phases):
            min_green = random.randint(20, 30)
            max_green = random.randint(40, 60)
            capacity = random.randint(30, 50)

            # 中等拥堵: 饱和度 0.6-1.2
            saturation = round(random.uniform(0.6, 1.2), 4)

            # 根据饱和度分配绿灯时间
            if saturation > 1.0:
                final = max_green
            elif saturation > 0.8:
                final = min((min_green + max_green) // 2 + 5, max_green)
            else:
                final = max((min_green + max_green) // 2 - 5, min_green)

            phases.append({
                "phase_id": j + 1,
                "pred_saturation": saturation,
                "min_green": min_green,
                "max_green": max_green,
                "capacity": capacity,
                "final": final,
            })

        # 构造思考过程
        sorted_phases = sorted(phases, key=lambda p: p["pred_saturation"], reverse=True)
        think = f"""观察各相位饱和度:"""
        for p in phases:
            think += f"\n- 相位 {p['phase_id']}: {p['pred_saturation']}"

        think += f"\n\n相位 {sorted_phases[0]['phase_id']} 饱和度最高,需要优先保证绿灯时间。"
        think += f"\n相位 {sorted_phases[-1]['phase_id']} 饱和度最低,可以适当减少绿灯时间。"
        think += f"\n根据饱和度比例平衡各相位绿灯时间。"

        # 构造输入 JSON
        input_json = {
            "prediction": {
                "as_of": "2026-01-28 13:12:15",
                "phase_waits": [
                    {k: v for k, v in p.items() if k != "final"}
                    for p in phases
                ],
            }
        }

        # 构造输出
        output = f"<think>{think}</think>" + json.dumps(
            [{"phase_id": p["phase_id"], "final": p["final"]} for p in phases],
            ensure_ascii=False,
        )

        examples.append({
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT.replace("{input_json}", json.dumps(input_json, ensure_ascii=False))},
                {"role": "user", "content": ""},
                {"role": "assistant", "content": output},
            ]
        })

    return examples


def generate_complex_examples(n: int = 20) -> list[dict[str, Any]]:
    """生成复杂场景示例

    特点:
    - 4-5 个相位
    - 边界约束情况 (已达 max_green 但仍拥堵,或接近 min_green)
    - 需要完整推理链: 解释约束限制
    """
    examples = []

    for i in range(n):
        num_phases = random.choice([4, 5])

        phases = []
        for j in range(num_phases):
            min_green = random.randint(15, 25)
            max_green = random.randint(35, 50)
            capacity = random.randint(25, 45)

            saturation = round(random.uniform(0.2, 2.0), 4)

            # 考虑边界约束
            if saturation > 1.5:
                final = max_green
            elif saturation > 0.9:
                final = min((min_green + max_green) // 2 + 8, max_green)
            elif saturation > 0.5:
                final = (min_green + max_green) // 2
            else:
                final = min_green

            phases.append({
                "phase_id": j + 1,
                "pred_saturation": saturation,
                "min_green": min_green,
                "max_green": max_green,
                "capacity": capacity,
                "final": final,
            })

        # 构造思考过程 (更详细的推理链)
        sorted_phases = sorted(phases, key=lambda p: p["pred_saturation"], reverse=True)
        think = f"""分析各相位状态:"""
        for p in phases:
            think += f"\n- 相位 {p['phase_id']}: 饱和度 {p['pred_saturation']}, 约束 [{p['min_green']}, {p['max_green']}]s"

        think += f"\n\n步骤 1: 识别瓶颈"
        think += f"\n相位 {sorted_phases[0]['phase_id']} 饱和度最高 ({sorted_phases[0]['pred_saturation']})"

        if sorted_phases[0]['pred_saturation'] > 1.5:
            think += f",已严重拥堵,需使用最大绿灯时间 {sorted_phases[0]['max_green']}s。"
        else:
            think += f",需适当增加绿灯时间。"

        think += f"\n\n步骤 2: 检查约束"
        for p in phases:
            if p['pred_saturation'] > 1.0 and p['final'] == p['max_green']:
                think += f"\n相位 {p['phase_id']} 已达约束上限,无法继续增加。"

        think += f"\n\n步骤 3: 平衡分配"
        think += f"\n根据饱和度比例,在约束范围内优化各相位绿灯时间。"

        # 构造输入 JSON
        input_json = {
            "prediction": {
                "as_of": "2026-01-28 13:12:15",
                "phase_waits": [
                    {k: v for k, v in p.items() if k != "final"}
                    for p in phases
                ],
            }
        }

        # 构造输出
        output = f"<think>{think}</think>" + json.dumps(
            [{"phase_id": p["phase_id"], "final": p["final"]} for p in phases],
            ensure_ascii=False,
        )

        examples.append({
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT.replace("{input_json}", json.dumps(input_json, ensure_ascii=False))},
                {"role": "user", "content": ""},
                {"role": "assistant", "content": output},
            ]
        })

    return examples


def generate_examples() -> list[dict[str, Any]]:
    """生成所有示例并打乱顺序

    Returns:
        包含所有示例的列表
    """
    print("生成简单场景示例...")
    simple = generate_simple_examples(50)
    print(f"  完成: {len(simple)} 条")

    print("生成中等场景示例...")
    medium = generate_medium_examples(30)
    print(f"  完成: {len(medium)} 条")

    print("生成复杂场景示例...")
    complex_examples = generate_complex_examples(20)
    print(f"  完成: {len(complex_examples)} 条")

    # 合并并打乱
    all_examples = simple + medium + complex_examples
    random.shuffle(all_examples)

    print(f"\n总计生成 {len(all_examples)} 条示例")
    return all_examples


if __name__ == "__main__":
    import os

    # 设置随机种子保证可复现
    random.seed(3407)

    # 生成示例
    examples = generate_examples()

    # 分割训练集和验证集
    train_size = 80
    train_examples = examples[:train_size]
    dev_examples = examples[train_size:]

    # 保存训练集
    train_path = "data/sft/train.jsonl"
    with open(train_path, "w", encoding="utf-8") as f:
        for ex in train_examples:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")
    print(f"\n训练集已保存: {train_path} ({len(train_examples)} 条)")

    # 保存验证集
    dev_path = "data/sft/dev.jsonl"
    with open(dev_path, "w", encoding="utf-8") as f:
        for ex in dev_examples:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")
    print(f"验证集已保存: {dev_path} ({len(dev_examples)} 条)")

    # 打印统计信息
    print("\n=== 数据集统计 ===")
    print(f"训练集: {len(train_examples)} 条")
    print(f"验证集: {len(dev_examples)} 条")
    print(f"总计: {len(examples)} 条")

    # 显示第一条示例
    print("\n=== 示例预览 (第 1 条) ===")
    first = train_examples[0]
    print(f"System prompt (前 200 字符):")
    print(first["messages"][0]["content"][:200] + "...")
    print(f"\nAssistant output (前 300 字符):")
    print(first["messages"][2]["content"][:300] + "...")

    print("\n✅ 示例生成完成!")
