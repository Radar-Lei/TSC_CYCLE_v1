---
status: complete
phase: 03-grpo-training
source: [03-01-SUMMARY.md, 03-02-SUMMARY.md]
started: 2026-02-10T10:00:00Z
updated: 2026-02-10T12:30:00Z
---

## Current Test

[testing complete]

## Tests

### 1. GRPO 配置完整性
expected: config/config.json 中包含 training.grpo 配置段，含模型参数、训练超参数（num_generations=4 等）和 reward 子配置（sumo_throughput_weight=0.6, sumo_queue_weight=0.4, exact_score=3.0）。同时包含 paths.grpo_data_dir、paths.grpo_output、paths.grpo_baseline 路径配置。
result: pass

### 2. Baseline 预计算脚本
expected: src/grpo/baseline.py 存在，包含多进程并行处理逻辑（ProcessPoolExecutor），能根据 state_file 去重、将 scenario 名称正确映射到 sumocfg 路径（arterial4x4_* → sumo_simulation/arterial4x4/{scenario}/arterial4x4.sumocfg，chengdu → sumo_simulation/environments/chengdu/chengdu.sumocfg）。
result: pass

### 3. Docker Baseline 入口脚本
expected: docker/grpo_baseline.sh 存在且可执行，遵循 data.sh 脚本模式（Docker 配置、挂载卷等）。
result: pass

### 4. Reward 函数 - L1 格式匹配
expected: src/grpo/rewards.py 包含 match_format_exactly 和 match_format_approximately 两个函数。精确匹配使用正则验证格式，精确匹配给 3.0 分。近似匹配统计标签出现次数，每个正确标签 +0.5，否则 -1.0。
result: pass

### 5. Reward 函数 - L2 约束检查（渐进式评分）
expected: src/grpo/rewards.py 包含 check_constraints 函数，提取 SOLUTION JSON 并验证相位顺序和绿灯时长范围。使用渐进式评分（部分满足给部分分，非二元制）。
result: pass

### 6. Reward 函数 - L3 SUMO 仿真 Reward（门控机制）
expected: src/grpo/rewards.py 包含 sumo_simulation_reward 函数，仅在 L1 格式正确 + L2 约束全满足时才执行 SUMO 仿真。使用 ProcessPoolExecutor 并行运行。Baseline 归一化公式：combined = 0.6 × throughput_ratio + 0.4 × queue_ratio，最终 score = min(combined, 1.0) × 5.0。SUMO 系统错误时 raise error 终止。
result: pass

### 7. Reward 函数 - Think 长度惩罚
expected: src/grpo/rewards.py 包含 think_length_reward 函数，估算 think 内容 token 数（char_count / 2），对 <50 或 >200 token 的思考内容施加惩罚。
result: pass

### 8. Reward 初始化函数
expected: src/grpo/rewards.py 包含 init_rewards(config_path, baseline_path) 函数，加载 config 和 baseline.json 到全局变量缓存。
result: pass

### 9. GRPO 训练脚本 - 模型加载与训练
expected: src/grpo/train.py 存在，加载 SFT 模型（outputs/sft/model），配置 LoRA，使用 GRPOTrainer 传入 5 个 reward 函数，fast_inference=False（无 vLLM），num_generations=4。
result: pass

### 10. GRPO 训练脚本 - 模型保存
expected: src/grpo/train.py 训练完成后合并 LoRA 保存 merged_16bit 模型到 outputs/grpo/model 目录。
result: pass

### 11. Docker GRPO 训练入口脚本
expected: docker/grpo_train.sh 存在且可执行，验证 3 个前置条件（outputs/sft/model 存在、outputs/grpo/grpo_train.jsonl 存在、outputs/grpo/baseline.json 存在），Docker 配置与 sft_train.sh 一致（--gpus all, --shm-size=32GB, SUMO_HOME 环境变量等），执行 python3 -m src.grpo.train。
result: pass

## Summary

total: 11
passed: 11
issues: 0
pending: 0
skipped: 0

## Gaps

[none]
