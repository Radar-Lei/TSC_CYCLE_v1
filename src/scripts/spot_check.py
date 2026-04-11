#!/usr/bin/env python3
"""用用户示例测试模型输出。"""

import json
import torch
from unsloth import FastLanguageModel
from src.grpo_simple.train import setup_chat_template

# 用户提供的测试输入
TEST_PROMPT = [
    {
        "role": "system",
        "content": (
            "你是交通信号配时优化专家。\n"
            "请认真分析预测得到的下个周期各个相位的交通状态，给出下个周期的配时方案，并给出你的推理过程。\n"
            "将推理过程放在 <start_working_out> 和 <end_working_out> 之间。\n"
            "然后,将你的最终方案放在 <SOLUTION> 和 </SOLUTION> 之间。"
        ),
    },
    {
        "role": "user",
        "content": """【cycle_predict_input_json】{
  "prediction": {
    "as_of": "2026-03-25 12:46:57",
    "phase_waits": [
      {
        "phase_id": 1,
        "pred_wait": 8.46,
        "pred_saturation": 0.1763,
        "min_green": 45,
        "max_green": 80,
        "capacity": 48
      },
      {
        "phase_id": 2,
        "pred_wait": 5.63,
        "pred_saturation": 0.1407,
        "min_green": 20,
        "max_green": 45,
        "capacity": 40
      },
      {
        "phase_id": 3,
        "pred_wait": 7.62,
        "pred_saturation": 0.2309,
        "min_green": 45,
        "max_green": 80,
        "capacity": 33
      },
      {
        "phase_id": 4,
        "pred_wait": 14.85,
        "pred_saturation": 0.4641,
        "min_green": 20,
        "max_green": 45,
        "capacity": 32
      }
    ]
  }
}【/cycle_predict_input_json】
任务(必须完成):
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
2) 数组元素必须为对象:{"phase_id": <int>, "final": <int>};不允许输出其它字段。""",
    },
]


def main():
    print("[加载] 模型...")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name="outputs/grpo_simple/model",
        max_seq_length=2048,
        dtype=torch.float16,
        load_in_4bit=False,
    )
    model.eval()
    tokenizer = setup_chat_template(tokenizer)

    rendered = tokenizer.apply_chat_template(
        TEST_PROMPT, tokenize=False, add_generation_prompt=True
    )
    input_ids = tokenizer.encode(rendered, return_tensors="pt").to(model.device)
    prompt_len = input_ids.shape[-1]

    print(f"[推理] prompt tokens: {prompt_len}")

    with torch.no_grad():
        outputs = model.generate(
            input_ids=input_ids,
            max_new_tokens=1024,
            temperature=0.1,
            top_p=0.95,
            do_sample=True,
        )

    generated_ids = outputs[0][prompt_len:]
    decoded = tokenizer.decode(generated_ids, skip_special_tokens=True)
    completion = "<start_working_out>" + decoded

    print("\n" + "=" * 60)
    print("[模型输出]")
    print("=" * 60)
    print(completion)
    print("=" * 60)

    # 验证约束
    import re
    sol_match = re.search(r"<SOLUTION>(.*?)</SOLUTION>", completion, re.DOTALL)
    if sol_match:
        try:
            solution = json.loads(sol_match.group(1))
            print("\n[解析结果]")
            print(json.dumps(solution, indent=2, ensure_ascii=False))

            constraints = [
                {"phase_id": 1, "min": 45, "max": 80},
                {"phase_id": 2, "min": 20, "max": 45},
                {"phase_id": 3, "min": 45, "max": 80},
                {"phase_id": 4, "min": 20, "max": 45},
            ]

            all_pass = True
            for c, s in zip(constraints, solution):
                final = s.get("final", s.get(str(c["phase_id"])))
                in_range = c["min"] <= final <= c["max"] if isinstance(final, int) else False
                status = "✅" if in_range else "❌"
                print(f"  Phase {c['phase_id']}: final={final}, range=[{c['min']},{c['max']}] {status}")
                if not in_range:
                    all_pass = False

            print(f"\n[约束检查] {'PASS ✅' if all_pass else 'FAIL ❌'}")
        except json.JSONDecodeError as e:
            print(f"\n[JSON 解析失败] {e}")
    else:
        print("\n[未找到 <SOLUTION> 标签]")


if __name__ == "__main__":
    main()
