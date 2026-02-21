#!/usr/bin/env python3
"""
合并 LoRA adapter 并保存为 merged 模型
"""

import os
import argparse

def main():
    parser = argparse.ArgumentParser(description="合并 LoRA adapter 并保存")
    parser.add_argument("--adapter_path", type=str, default="outputs/sft/model", help="LoRA adapter 路径")
    parser.add_argument("--base_model", type=str, default="unsloth/GLM-4.7-Flash", help="基础模型路径")
    parser.add_argument("--output_path", type=str, default="outputs/sft/merged", help="输出路径")
    args = parser.parse_args()

    print(f"[合并 LoRA] 合并 LoRA adapter 到基础模型")
    print(f"  基础模型: {args.base_model}")
    print(f"  LoRA adapter: {args.adapter_path}")
    print(f"  输出路径: {args.output_path}")

    from unsloth import FastLanguageModel

    # 加载基础模型（BF16，不用 4bit 量化，以便后续 GGUF 转换）
    print("[加载] 加载基础模型（BF16）...")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=args.base_model,
        max_seq_length=2048,
        load_in_4bit=False,  # 使用 BF16，以便 GGUF 转换
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
    # 确保 merged 模型的 tokenizer 与 SFT 训练一致
    print("[模板] 替换思考标签 (think -> start_working_out)...")
    if tokenizer.chat_template:
        tokenizer.chat_template = (
            tokenizer.chat_template
            .replace("<think>", "<start_working_out>")
            .replace("</think>", "<end_working_out>")
        )

    # 保存 merged 模型
    os.makedirs(args.output_path, exist_ok=True)
    print(f"[保存] 保存 merged 模型到 {args.output_path}...")
    model.save_pretrained(args.output_path)
    tokenizer.save_pretrained(args.output_path)

    print(f"[完成] Merged 模型已保存到 {args.output_path}")


if __name__ == "__main__":
    main()
