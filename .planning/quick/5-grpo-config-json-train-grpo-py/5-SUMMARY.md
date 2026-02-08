# Quick Task 5 Summary

## Task
GRPO 所有参数统一到 config.json，train_grpo.py 完整读取并传递

## Changes

### 1. config/config.json
- `training.grpo` 从 5 个参数扩展为完整配置（~25 项）
- 新增参数：max_epochs, per_device_train_batch_size, warmup_ratio, lr_scheduler_type, optim, weight_decay, temperature, max_prompt_length, max_completion_length, save_steps, logging_steps, bf16, save_total_limit, seed, lora_r, lora_alpha, max_seq_length
- 新增 `training.grpo.generation` 子段：max_length, temperature, top_p（控制模型 generation_config 覆盖值）

### 2. src/scripts/train_grpo.py
- `apply_config()` 完整读取 config.json 中所有 GRPO 参数
- 所有参数通过 `GRPOConfig(...)` 构造函数传入（原来只传 3 个）
- `generation_config` 字典从 config.json 读取并传递给 `load_base_model/load_sft_model`
- `lora_r`, `lora_alpha`, `max_seq_length` 同样从 config.json 读取并传递
- 配置打印扩展为 11 项（含 generation_config）

### 3. src/grpo/trainer.py
- `load_base_model()` 新增 `max_seq_length` 和 `generation_config` 参数
- `load_sft_model()` 新增 `max_seq_length` 和 `generation_config` 参数
- 两个函数不再硬编码 generation_config 值，全部由外部传入

## Commit
cb9d28f
