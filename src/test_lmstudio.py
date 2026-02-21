#!/usr/bin/env python3
"""
LM Studio 推理测试 - 通过 OpenAI API 调用 LM Studio

使用 OpenAI-compatible API 调用 LM Studio 中加载的模型，
验证 GGUF 模型在 LM Studio 中的输出格式是否正确。

用法:
    python src/test_lmstudio.py [NUM_SAMPLES]
    默认测试 3 条样本

环境变量:
    LLM_API_BASE_URL: LM Studio API 地址 (默认: http://localhost:1234/v1)
                      Docker 内运行使用: http://host.docker.internal:1234/v1
"""

import json
import os
import random
import sys

try:
    import openai
except ImportError:
    print("[错误] 请先安装 openai: pip install openai")
    sys.exit(1)

SYSTEM_PROMPT = (
    "你是交通信号配时优化专家。\n"
    "请认真分析预测得到的下个周期各个相位的交通状态，给出下个周期的配时方案，并给出你的推理过程。\n"
    "将推理过程放在 <start_working_out> 和 <end_working_out> 之间。\n"
    "然后，将你的最终方案放在 <SOLUTION> 和 </SOLUTION> 之间。"
)


def main():
    num_samples = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    data_path = "outputs/sft/sft_train.jsonl"

    # 从环境变量读取 API URL（支持 Docker 内运行）
    api_base_url = os.getenv("LLM_API_BASE_URL", "http://localhost:1234/v1")
    # 可选: 指定模型名；未指定时自动使用第一个已加载模型
    requested_model = os.getenv("LLM_MODEL_NAME", "").strip()
    
    print("=" * 70)
    print("LM Studio 推理测试 (OpenAI API)")
    print("=" * 70)
    print(f"[API] {api_base_url}")
    print(f"[数据] {data_path}")
    print(f"[样本数] {num_samples}")
    print()

    # 初始化 OpenAI 客户端
    client = openai.OpenAI(
        base_url=api_base_url,
        api_key="not-needed"  # LM Studio 不需要 API key
    )

    # 检查已加载模型
    print("[API] 检查已加载模型...")
    try:
        models_resp = client.models.list()
        loaded_model_ids = [m.id for m in getattr(models_resp, "data", []) if getattr(m, "id", None)]
    except Exception as e:
        print(f"[错误] 获取模型列表失败: {e}")
        print("请确认 LM Studio API 服务已开启")
        sys.exit(1)

    if not loaded_model_ids:
        print("[错误] LM Studio 当前没有已加载模型")
        print("请在 LM Studio 中先加载模型，再重试")
        sys.exit(1)

    if requested_model:
        if requested_model not in loaded_model_ids:
            print(f"[错误] 指定模型未加载: {requested_model}")
            print(f"[可用模型] {loaded_model_ids}")
            sys.exit(1)
        model_name = requested_model
    else:
        model_name = loaded_model_ids[0]

    print(f"[模型] 使用: {model_name}")
    print(f"[模型] 已加载: {loaded_model_ids}")
    print()

    # 读取样本
    print("[数据] 加载 SFT 训练数据...")
    try:
        with open(data_path, "r") as f:
            all_samples = [json.loads(line.strip()) for line in f if line.strip()]
    except FileNotFoundError:
        print(f"[错误] 数据文件不存在: {data_path}")
        print("请先运行 SFT 数据生成: ./docker/data.sh")
        sys.exit(1)

    total = len(all_samples)
    print(f"[数据] 共 {total} 条样本")

    num = min(num_samples, total)
    indices = sorted(random.sample(range(total), num))
    print(f"[抽样] 随机选取 {num} 条，行号: {[i + 1 for i in indices]}")
    print()

    # 测试样本
    success_count = 0
    for rank, idx in enumerate(indices, 1):
        sample = all_samples[idx]
        # SFT data format: {"messages": [...]}
        messages_data = sample.get("messages", [])
        user_msg = [m for m in messages_data if m["role"] == "user"]
        if not user_msg:
            print(f"[警告] 样本{idx+1}无用户消息,跳过")
            continue
        user_content = user_msg[0]["content"]

        print("=" * 70)
        print(f"  样本 {rank}/{num} (行号 {idx + 1})")
        print("=" * 70)
        print("[输入摘要]")
        print(user_content[:300] + ("..." if len(user_content) > 300 else ""))
        print()

        # 调用 LM Studio API
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ]

        try:
            print("[API] 调用 LM Studio...")
            response = client.chat.completions.create(
                model=model_name,
                messages=messages,
                max_tokens=512,
                temperature=0.05,
                top_p=0.95,
            )

            generated_text = response.choices[0].message.content
            print("[模型输出]")
            print(generated_text)
            print()

            # 检查标签
            print("[标签检查]")
            has_start = generated_text.count("<start_working_out>")
            has_end = generated_text.count("<end_working_out>")
            has_solution_start = generated_text.count("<SOLUTION>")
            has_solution_end = generated_text.count("</SOLUTION>")
            
            print(f"  '<start_working_out>' 出现: {has_start}")
            print(f"  '<end_working_out>' 出现: {has_end}")
            print(f"  '<SOLUTION>' 出现: {has_solution_start}")
            print(f"  '</SOLUTION>' 出现: {has_solution_end}")

            # 与 test_gguf.py 对齐: 主要检查 end_working_out + SOLUTION 起始标签
            format_ok = (has_end >= 1) and (has_solution_start >= 1)
            print(f"  主格式匹配(与GGUF一致): {'✓ 成功' if format_ok else '✗ 失败'}")

            if has_start == 0:
                print("  提示: 缺少 '<start_working_out>'（LM Studio chat template 预填时可能不返回该标签）")
            if has_solution_end == 0:
                print("  提示: 缺少 '</SOLUTION>'")
            
            if format_ok:
                success_count += 1
            print()

        except openai.APIConnectionError as e:
            print(f"[错误] 无法连接到 LM Studio: {e}")
            print(f"请确认:")
            print(f"  1. LM Studio 正在运行")
            print(f"  2. 已加载模型 (DeepSignal_CyclePlan/model-Q4_K_M.gguf)")
            print(f"  3. API 服务已启动 (默认端口 1234)")
            print()
            continue

        except openai.APITimeoutError as e:
            print(f"[错误] API 超时: {e}")
            print()
            continue

        except Exception as e:
            print(f"[错误] API 调用失败: {e}")
            print()
            continue

    print("=" * 70)
    print(f"[完成] 共测试 {num} 条样本")
    print(f"[结果] 格式正确: {success_count}/{num} ({success_count/num*100:.1f}%)")
    print("=" * 70)

    if success_count < num:
        print()
        print("[提示] 部分样本格式不正确，可能原因:")
        print("  1. 模型未正确训练思考链格式")
        print("  2. chat template 不匹配 (检查 GGUF 内嵌模板)")
        print("  3. 生成参数不合适 (temperature, max_tokens)")


if __name__ == "__main__":
    main()
