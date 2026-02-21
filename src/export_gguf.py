#!/usr/bin/env python3
"""
合并 LoRA adapter 并导出 GGUF 格式
"""

import os
import argparse

def main():
    parser = argparse.ArgumentParser(description="导出 SFT 模型为 GGUF 格式")
    parser.add_argument("--adapter_path", type=str, default="outputs/sft/model", help="LoRA adapter 路径")
    parser.add_argument("--base_model", type=str, default="unsloth/GLM-4.7-Flash", help="基础模型路径")
    parser.add_argument("--output_path", type=str, default="outputs/sft/gguf", help="GGUF 输出路径")
    parser.add_argument("--quantization", type=str, default="q4_k_m", help="量化方法 (q4_k_m, q8_0, f16)")
    args = parser.parse_args()

    print(f"[导出 GGUF] 合并 LoRA 并导出 {args.quantization} 格式")
    print(f"  基础模型: {args.base_model}")
    print(f"  LoRA adapter: {args.adapter_path}")
    print(f"  输出路径: {args.output_path}")

    from unsloth import FastLanguageModel

    # 加载基础模型（4bit 量化加速）
    print("[加载] 加载基础模型...")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=args.base_model,
        max_seq_length=2048,
        load_in_4bit=True,
        trust_remote_code=True,
    )

    # 加载 LoRA adapter
    print("[加载] 加载 LoRA adapter...")
    from peft import PeftModel
    model = PeftModel.from_pretrained(model, args.adapter_path)

    # 合并 LoRA 到基础模型
    print("[合并] 合并 LoRA adapter...")
    model = model.merge_and_unload()

    # 最小化修改 chat template：将 GLM 原生 <think> 替换为项目标签
    # 保留其余 GLM 原生格式，确保与 SFT 训练一致
    print("[模板] 替换思考标签 (think -> start_working_out)...")
    if tokenizer.chat_template:
        tokenizer.chat_template = (
            tokenizer.chat_template
            .replace("<think>", "<start_working_out>")
            .replace("</think>", "<end_working_out>")
        )

    # 导出 GGUF
    os.makedirs(args.output_path, exist_ok=True)
    print(f"[导出] 保存 GGUF ({args.quantization})...")
    model.save_pretrained_gguf(
        args.output_path,
        tokenizer,
        quantization_method=args.quantization,
    )

    print(f"[完成] GGUF 已保存到 {args.output_path}")


if __name__ == "__main__":
    main()
