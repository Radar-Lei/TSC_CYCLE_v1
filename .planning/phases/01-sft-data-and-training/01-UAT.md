---
status: testing
phase: 01-sft-data-and-training
source: [01-01-SUMMARY.md, 01-02-SUMMARY.md, 01-03-SUMMARY.md]
started: 2026-02-09T13:00:00Z
updated: 2026-02-09T13:00:00Z
---

## Current Test
<!-- OVERWRITE each test - shows where we are -->

number: 1
name: 样本抽取脚本可运行
expected: |
  运行 `python3 -m src.scripts.sample_selector --input outputs/data/train.jsonl --output /tmp/test_sample.jsonl --count 100 --seed 42` 成功执行，生成 100 行 JSONL 文件，终端打印分布统计信息。
awaiting: user response

## Tests

### 1. 样本抽取脚本可运行
expected: 运行 `python3 -m src.scripts.sample_selector --input outputs/data/train.jsonl --output /tmp/test_sample.jsonl --count 100 --seed 42` 成功执行，生成 100 行 JSONL 文件，终端打印分布统计信息。
result: [pending]

### 2. 抽取样本覆盖性
expected: `outputs/sft/sampled_100.jsonl` 包含 100 条数据，覆盖全部 34 个 tl_id，覆盖两个场景(arterial4x4_10, chengdu)，覆盖不同饱和度区间(zero/low/medium/high)。
result: [pending]

### 3. SFT 数据 messages 格式
expected: `outputs/sft/sft_train.jsonl` 每条数据包含 messages 数组，含 3 个元素：role=system、role=user、role=assistant。共 100 条数据。
result: [pending]

### 4. SFT 数据标签格式
expected: `sft_train.jsonl` 中每条 assistant content 匹配 `<think>...<think><solution>[...}<solution>` 格式，即使用重复开标签作为关闭标签。
result: [pending]

### 5. SFT 数据约束校验
expected: 所有 100 条数据中 solution 的每个 final 值都满足 `min_green <= final <= max_green` 硬约束，无任何违反。
result: [pending]

### 6. SFT 训练脚本完整性
expected: `src/sft/train.py` 语法正确，包含 FastLanguageModel、SFTTrainer、save_pretrained_merged 等关键组件，支持从 config/config.json 读取配置。
result: [pending]

### 7. Docker 训练脚本一致性
expected: `docker/sft_train.sh` bash 语法正确，与 `docker/data.sh` 使用相同的 IMAGE_NAME、--gpus all、--shm-size=32GB、--user 配置。
result: [pending]

## Summary

total: 7
passed: 0
issues: 0
pending: 7
skipped: 0

## Gaps

[none yet]
