#!/usr/bin/env python3
"""
GGUF 推理测试 - 使用 llama-cpp-python
"""

import json
import random
import sys

try:
    from llama_cpp import Llama
except ImportError:
    print("[错误] 请先安装 llama-cpp-python: pip install llama-cpp-python")
    sys.exit(1)

SYSTEM_PROMPT = (
    "你是交通信号配时优化专家。\n"
    "请认真分析预测得到的下个周期各个相位的交通状态，给出下个周期的配时方案，并给出你的推理过程。\n"
    "将推理过程放在 <start_working_out> 和 <end_working_out> 之间。\n"
    "然后，将你的最终方案放在 <SOLUTION> 和 </SOLUTION> 之间。"
)

def main():
    num_samples = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    model_path = "outputs/sft/merged/model-Q4_K_M.gguf"
    data_path = "outputs/sft/sft_train.jsonl"  # 使用 SFT 训练数据

    print(f"[模型] 加载 GGUF 模型: {model_path}")
    print("[注意] GGUF 模型加载需要几秒钟...")

    # 加载 GGUF 模型
    llm = Llama(
        model_path=model_path,
        n_ctx=2048,
        n_gpu_layers=-1,  # 全部加载到 GPU
        verbose=False,
    )
    print("[模型] 加载完成")
    print("[模式] 使用 create_chat_completion - 自动应用 GGUF 内嵌的 chat template")

    # 读取样本
    with open(data_path, "r") as f:
        all_samples = [json.loads(line.strip()) for line in f if line.strip()]

    total = len(all_samples)
    print(f"[数据] 共 {total} 条样本 (来自 {data_path})")

    num = min(num_samples, total)
    indices = sorted(random.sample(range(total), num))
    print(f"[抽样] 随机选取 {num} 条")
    print()

    for rank, idx in enumerate(indices, 1):
        sample = all_samples[idx]
        # SFT data format: {"messages": [...]}
        messages_data = sample.get("messages", [])
        user_msg = [m for m in messages_data if m["role"] == "user"]
        if not user_msg:
            print(f"[警告] 样本{idx+1}无用户消息,跳过")
            continue
        user_content = user_msg[0]["content"]

        # 使用 chat completion API，自动应用 GGUF 内嵌的 chat template
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ]

        print("=" * 70)
        print(f"  样本 {rank}/{num} (行号 {idx + 1})")
        print("=" * 70)
        print("[输入摘要]")
        print(user_content[:300] + ("..." if len(user_content) > 300 else ""))
        print()

        # 生成（使用 chat completion，自动应用 template）
        output = llm.create_chat_completion(
            messages=messages,
            max_tokens=512,
            temperature=0.05,
            top_p=0.95,
        )

        generated_text = output["choices"][0]["message"]["content"]
        print("[模型输出]")
        print(generated_text)
        print()

        # 检查标签
        print("[标签检查]")
        print(f"  '<end_working_out>' 出现: {generated_text.count('<end_working_out>')}")
        print(f"  '<SOLUTION>' 出现: {generated_text.count('<SOLUTION>')}")

    print("=" * 70)
    print(f"[完成] 共测试 {num} 条样本")


if __name__ == "__main__":
    main()
