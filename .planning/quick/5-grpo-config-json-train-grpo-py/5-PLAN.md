---
phase: quick-5
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - config/config.json
  - src/scripts/train_grpo.py
  - src/grpo/trainer.py
autonomous: true
---

<objective>
将 GRPOConfig 的所有可配置参数统一到 config.json 中，train_grpo.py 完整读取并传递。
去掉 load_base_model/load_sft_model 中硬编码的 generation_config 值，改由配置驱动。
</objective>

<tasks>

<task type="auto">
  <name>Task 1: 补全 config.json 中的 GRPO 参数 + 新增 generation 段</name>
  <files>config/config.json</files>
  <action>
  将 training.grpo 从当前 5 个参数扩展为完整配置，对齐 GRPOConfig dataclass 的所有字段。
  新增 training.grpo.generation 子段放 generation_config 覆盖参数。

  目标结构:
  ```json
  "grpo": {
    "model_name": "unsloth/Qwen3-4B-Thinking-2507",
    "max_steps": 100,
    "max_epochs": 1,
    "per_device_train_batch_size": 1,
    "num_generations": 4,
    "gradient_accumulation_steps": 4,
    "learning_rate": 5e-6,
    "warmup_ratio": 0.1,
    "lr_scheduler_type": "linear",
    "optim": "adamw_8bit",
    "weight_decay": 0.001,
    "temperature": 0.9,
    "max_prompt_length": 512,
    "max_completion_length": 1024,
    "save_steps": 50,
    "logging_steps": 1,
    "bf16": true,
    "save_total_limit": 3,
    "seed": 3407,
    "lora_r": 32,
    "lora_alpha": 64,
    "max_seq_length": 2048,
    "generation": {
      "max_length": 2048,
      "temperature": 0.9,
      "top_p": 0.95
    }
  }
  ```
  </action>
  <done>config.json 包含 GRPOConfig 所有字段 + generation_config 覆盖参数</done>
</task>

<task type="auto">
  <name>Task 2: train_grpo.py 完整读取 config.json 并构建 GRPOConfig</name>
  <files>src/scripts/train_grpo.py</files>
  <action>
  1. apply_config() 中为每个 GRPOConfig 字段添加 get_nested 读取
  2. 读取 generation 段参数存入 args
  3. main() 中构建 GRPOConfig 时传入全部参数（不再只传 3 个）
  4. 将 generation_config 参数传递给 load_base_model/load_sft_model
  5. 同样将 lora_r, lora_alpha, max_seq_length 传递给模型加载函数
  </action>
  <done>train_grpo.py 从 config.json 读取所有 GRPO 参数并传递</done>
</task>

<task type="auto">
  <name>Task 3: trainer.py 模型加载函数接受 generation_config 参数</name>
  <files>src/grpo/trainer.py</files>
  <action>
  1. load_base_model() 增加 max_seq_length 和 generation_config 参数，去掉硬编码
  2. load_sft_model() 同样增加参数
  3. 更新自测试
  </action>
  <done>generation_config 由外部传入，不再硬编码</done>
</task>

</tasks>

<success_criteria>
- config.json 包含所有 GRPOConfig 字段
- train_grpo.py 从 config.json 完整读取并传递所有参数
- load_base_model/load_sft_model 不再硬编码 generation_config
- 命令行参数仍可覆盖 config.json 值
</success_criteria>
