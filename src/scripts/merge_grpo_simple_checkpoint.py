#!/usr/bin/env python3
"""合并 grpo_simple checkpoint 为完整模型。

方式：monkey-patch accelerate 的 unhashable set bug，
然后用 PeftModel.from_pretrained 正常加载 checkpoint。
"""

import argparse
import json
import os

import torch
from unsloth import FastLanguageModel


def _patch_accelerate():
    """Fix accelerate bug: unhashable type 'set' in get_balanced_memory."""
    import accelerate.utils.modeling as accel_mod
    original_fn = accel_mod.get_balanced_memory

    def patched_get_balanced_memory(*args, **kwargs):
        import inspect
        sig = inspect.signature(original_fn)
        bound = sig.bind(*args, **kwargs)
        bound.apply_defaults()
        # Fix: no_split_module_classes may be a set containing sets
        nsmc = bound.arguments.get("no_split_module_classes")
        if nsmc is not None and isinstance(nsmc, (set, frozenset)):
            # Flatten: if elements are sets, convert to list of strings
            flat = []
            for item in nsmc:
                if isinstance(item, (set, frozenset)):
                    flat.extend(item)
                else:
                    flat.append(item)
            bound.arguments["no_split_module_classes"] = flat
        return original_fn(*bound.args, **bound.kwargs)

    accel_mod.get_balanced_memory = patched_get_balanced_memory


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", default="outputs/grpo_simple/checkpoints/checkpoint-3000")
    parser.add_argument("--output", default="outputs/grpo_simple/model")
    parser.add_argument("--config", default="config/config.json")
    args = parser.parse_args()

    _patch_accelerate()

    with open(args.config) as f:
        config = json.load(f)

    grpo_cfg = config["training"]["grpo_simple"]["model"]
    base_model = grpo_cfg["model_name"]

    print(f"[加载] base model: {base_model}")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=base_model,
        max_seq_length=grpo_cfg["max_seq_length"],
        dtype=torch.float16,
        load_in_4bit=False,
        max_lora_rank=grpo_cfg["lora_rank"],
        gpu_memory_utilization=grpo_cfg["gpu_memory_utilization"],
    )

    print(f"[加载] LoRA adapter from: {args.checkpoint}")
    from peft import PeftModel
    model = PeftModel.from_pretrained(model, args.checkpoint)
    print("[加载] adapter 加载成功")

    os.makedirs(args.output, exist_ok=True)
    print(f"[合并] merge_and_unload + save to {args.output}")
    merged = model.merge_and_unload()
    merged.save_pretrained(args.output)
    tokenizer.save_pretrained(args.output)

    # 设置自定义 chat template
    from src.grpo_simple.train import setup_chat_template
    tokenizer = setup_chat_template(tokenizer)
    tokenizer.save_pretrained(args.output)

    print(f"[完成] 模型已保存到 {args.output}")


if __name__ == "__main__":
    main()
