#!/usr/bin/env python3
"""SFT inference test - randomly sample from train.jsonl and show model output."""

import json
import random
import sys

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

# Build special tokens dynamically to avoid tooling issues
_IM_END = "<" + "|im_end|" + ">"
_EOF_TOK = "<" + "|endoftext|" + ">"

SYSTEM_PROMPT = (
    "你是交通信号配时优化专家。\n"
    "请认真分析预测得到的下个周期各个相位的交通状态，给出下个周期的配时方案，并给出你的推理过程。\n"
    "将推理过程放在 <start_working_out> 和 <" + "end_working_out> 之间。\n"
    "然后，将你的最终方案放在 <SOLUTION> 和 <" + "/SOLUTION> 之间。"
)

TASK_SUFFIX = (
    "\n任务(必须完成):\n"
    "主要基于 prediction.phase_waits 的 pred_saturation(已计算),"
    "在满足硬约束前提下输出下一周期各相位最终绿灯时间 final(单位:秒)。\n\n"
    "字段说明(仅说明含义):\n"
    "- prediction.phase_waits[*].min_green / max_green:秒。\n"
    "- prediction.phase_waits[*].pred_saturation:预测饱和度(pred_wait / capacity)。\n"
    "- prediction.phase_waits[*].capacity:相位容量(车辆容纳数)。\n\n"
    "硬约束(必须满足):\n"
    "1) 相位顺序固定:严格按 prediction.phase_waits 的顺序输出;不可跳相、不可重排。\n"
    "2) 每相位约束:final 必须满足 prediction.phase_waits[*].min_green <= final <= "
    "prediction.phase_waits[*].max_green。\n"
    "3) final 必须为整数秒。\n\n"
    "提示(非硬约束):\n"
    "- capacity 仅供参考,最终决策以 pred_saturation 为主。\n\n"
    "输出格式:\n"
    '1) JSON 顶层必须是数组(list);数组长度必须等于 prediction.phase_waits 的长度。\n'
    '2) 数组元素必须为对象:{"phase_id": <int>, "final": <int>};不允许输出其它字段。'
)


def clean_generated_text(text, tokenizer):
    """Remove trailing special tokens from generated text."""
    for tok in [tokenizer.eos_token, _IM_END, _EOF_TOK]:
        if tok and text.endswith(tok):
            text = text[: -len(tok)].rstrip()
    return text


def main():
    num_samples = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    model_path = "outputs/sft/model"
    data_path = "outputs/sft/sft_train.jsonl"

    print("[模型] 加载 SFT 模型:", model_path)
    tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(
        model_path,
        torch_dtype=torch.bfloat16,
        device_map="auto",
        trust_remote_code=True,
    )
    model.eval()

    # Read all samples
    with open(data_path, "r") as f:
        all_samples = [json.loads(line.strip()) for line in f if line.strip()]

    total = len(all_samples)
    print(f"[数据] 共 {total} 条样本 (来自 {data_path})")

    num = min(num_samples, total)
    indices = sorted(random.sample(range(total), num))
    print(f"[抽样] 随机选取 {num} 条，行号: {[i + 1 for i in indices]}")
    print()

    for rank, idx in enumerate(indices, 1):
        sample = all_samples[idx]
        # SFT data format: {"messages": [...]}
        messages = sample.get("messages", [])
        # Extract user message
        user_msg = [m for m in messages if m["role"] == "user"]
        if not user_msg:
            print(f"[警告] 样本{idx+1}无用户消息,跳过")
            continue
        user_content = user_msg[0]["content"]

        input_messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ]

        text = tokenizer.apply_chat_template(
            input_messages, tokenize=False, add_generation_prompt=True
        )
        inputs = tokenizer(text, return_tensors="pt").to(model.device)

        print("==" * 70)
        print(f"  样本 {rank}/{num} (行号 {idx + 1})")
        print("=" * 70)
        # Show a short summary of the input
        print("[输入摘要]")
        print(user_content[:500] + ("..." if len(user_content) > 500 else ""))
        print()

        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=512,
                temperature=0.05,
                top_p=0.95,
                do_sample=True,
            )

        generated_ids = outputs[0][inputs["input_ids"].shape[1] :]
        generated_text = tokenizer.decode(generated_ids, skip_special_tokens=False)
        generated_text = clean_generated_text(generated_text, tokenizer)

        think_tag = "<" + "start_working_out>"
        print("[模型输出]")
        print(think_tag + generated_text)
        print()

        # 检查标签
        print("[标签检查]")
        print(f"  '<end_working_out>' 出现: {generated_text.count('<end_working_out>')}")
        print(f"  '<SOLUTION>' 出现: {generated_text.count('<SOLUTION>')}")
        print(f"  '</SOLUTION>' 出现: {generated_text.count('</SOLUTION>')}")

        # 检查格式匹配
        import re
        match_format = re.compile(r"<end_working_out>.*?<SOLUTION>(.+?)</SOLUTION>\s*$", flags=re.DOTALL)
        match_result = match_format.search(generated_text)
        print(f"  格式匹配: {'✓ 成功' if match_result else '✗ 失败'}")
        print()

    print("=" * 70)
    print(f"[完成] 共测试 {num} 条样本")
    print("=" * 70)


if __name__ == "__main__":
    main()
