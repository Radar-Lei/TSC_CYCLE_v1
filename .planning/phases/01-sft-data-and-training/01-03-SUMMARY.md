---
phase: 01-sft-data-and-training
plan: 03
subsystem: sft-training-pipeline
tags: [sft, training, unsloth, lora, docker]
dependency_graph:
  requires: [01-02-sft-data-assembly]
  provides: [sft-training-pipeline]
  affects: [01-04-sft-execution]
tech_stack:
  added: [unsloth, trl, datasets]
  patterns: [lora-finetuning, chat-template, merged-model-save]
key_files:
  created:
    - src/sft/__init__.py
    - src/sft/train.py
    - docker/sft_train.sh
  modified: []
decisions:
  - 使用 unsloth 的 FastLanguageModel 加载 Qwen3-4B-Base 进行 LoRA 微调
  - Chat template 使用 <think><solution> 标签格式（重复开标签作为关闭标签）
  - 训练后合并 LoRA 保存为 merged_16bit 完整模型到 outputs/sft/model
  - Docker 脚本遵循 data.sh 模式确保环境一致性
metrics:
  duration: 217s
  tasks_completed: 2
  files_created: 3
  lines_added: 308
  completed_date: 2026-02-09T12:44:44Z
---

# Phase 01 Plan 03: SFT 训练流水线 Summary

**一句话:** 创建完整的 SFT 训练流水线（Docker shell + Python 训练脚本），使用 unsloth 对 Qwen3-4B-Base 进行 LoRA 微调并合并保存。

## 完成的工作

### Task 1: 创建 SFT Python 训练脚本
- 创建 `src/sft/__init__.py` 和 `src/sft/train.py`（253 行）
- 实现完整的 SFT 训练流程：
  1. **配置加载**: 从 `config/config.json` 读取所有超参数（training.sft 部分）和路径（paths 部分）
  2. **模型加载**: 使用 unsloth 的 `FastLanguageModel.from_pretrained` 加载 Qwen3-4B-Base
  3. **LoRA 配置**: 使用 `get_peft_model` 配置 LoRA（rank=32, alpha=64, target_modules=7个）
  4. **Chat Template**: 自定义模板支持 `<think>...<think><solution>...<solution>` 格式
  5. **数据加载**: 从 `outputs/sft/sft_train.jsonl` 加载数据，过滤超过 max_seq_length/2 的样本
  6. **训练**: 使用 `SFTTrainer` 和 `SFTConfig` 执行训练
  7. **模型保存**: 使用 `save_pretrained_merged` 合并 LoRA 保存为 merged_16bit 格式

**关键实现细节:**
```python
# Chat template 设置（适配项目标签格式）
reasoning_start = "<think>"
reasoning_end = "<think>"  # 项目约定：开标签重复作为关闭标签
solution_start = "<solution>"
solution_end = "<solution>"

# 模型保存（合并 LoRA）
model.save_pretrained_merged(
    output_path,
    tokenizer,
    save_method="merged_16bit",
)
```

**提交:** `44dc096` - feat(01-03): create SFT training script

### Task 2: 创建 Docker SFT 训练 shell 脚本
- 创建 `docker/sft_train.sh`（55 行，可执行）
- 严格遵循 `docker/data.sh` 的运行模式：
  - 使用相同的 IMAGE_NAME: `qwen3-tsc-grpo:latest`
  - 使用相同的 Docker 配置: `--gpus all`, `--shm-size=32GB`, `--user`
  - 使用相同的挂载方式: `-v "${PROJECT_DIR}:${CONTAINER_WORKDIR}:rw"`
  - 使用相同的环境变量: `-e SUMO_HOME=/usr/share/sumo`
- 创建输出目录: `outputs/sft/model` 和 `outputs/sft/checkpoints`
- 通过 Docker 容器调用: `python3 -m src.sft.train --config config/config.json`
- 支持传递额外参数: `"$@"`

**脚本结构:**
```bash
#!/usr/bin/env bash
set -euo pipefail

# 目录设置
SCRIPT_DIR + PROJECT_DIR
IMAGE_NAME="qwen3-tsc-grpo:latest"
CONTAINER_WORKDIR="/home/samuel/SCU_TSC"

# Docker run
docker run --rm \
    --gpus all \
    --shm-size=32GB \
    --user "$(id -u):$(id -g)" \
    -v "${PROJECT_DIR}:${CONTAINER_WORKDIR}:rw" \
    -w "${CONTAINER_WORKDIR}" \
    -e SUMO_HOME=/usr/share/sumo \
    --entrypoint python3 \
    "${IMAGE_NAME}" \
    -m src.sft.train \
        --config config/config.json \
        "$@"
```

**提交:** `d42925c` - feat(01-03): create Docker SFT training shell script

## 输出文件

### src/sft/train.py (253 行)
完整的 SFT 训练脚本，包含：
- `load_config()`: 配置加载
- `setup_model()`: 模型和 LoRA 设置
- `setup_chat_template()`: 自定义 chat template
- `load_sft_data()`: 数据加载和过滤
- `train_model()`: SFTTrainer 训练
- `save_model()`: 合并 LoRA 并保存

### docker/sft_train.sh (55 行)
Docker 容器执行脚本，遵循 data.sh 模式，支持：
- GPU 加速（--gpus all）
- 大共享内存（--shm-size=32GB）
- 用户权限一致性
- 项目目录挂载

## Deviations from Plan

无偏差 - 计划执行完全按预期进行。

## 验证

执行计划中的验证步骤:

1. **Shell 脚本语法验证:**
```bash
bash -n docker/sft_train.sh && echo "Syntax OK"
```
结果: **Syntax OK** ✓

2. **Python 脚本语法验证:**
```bash
python3 -c "import ast; ast.parse(open('src/sft/train.py').read()); print('Syntax OK')"
```
结果: **Syntax OK** ✓

3. **关键组件检查:**
```bash
grep "FastLanguageModel\|SFTTrainer\|save_pretrained_merged" src/sft/train.py
```
结果: **所有关键组件存在** ✓

4. **配置引用检查:**
```bash
grep "training.sft" src/sft/train.py
```
结果: **config.json 配置项被正确引用** ✓

5. **结构一致性检查:**
```bash
# 对比 sft_train.sh 和 data.sh 的关键配置
grep -E "(IMAGE_NAME|--gpus all|--shm-size|--user)" docker/sft_train.sh
```
结果: **与 data.sh 结构完全一致** ✓

## Self-Check

检查关键文件是否存在:
```bash
[ -f "src/sft/__init__.py" ] && echo "FOUND: src/sft/__init__.py" || echo "MISSING"
[ -f "src/sft/train.py" ] && echo "FOUND: src/sft/train.py" || echo "MISSING"
[ -f "docker/sft_train.sh" ] && echo "FOUND: docker/sft_train.sh" || echo "MISSING"
```

检查提交是否存在:
```bash
git log --oneline --all | grep -q "44dc096" && echo "FOUND: 44dc096 (Task 1)"
git log --oneline --all | grep -q "d42925c" && echo "FOUND: d42925c (Task 2)"
```

所有检查项目:
- [x] src/sft/__init__.py 存在
- [x] src/sft/train.py 存在（253 行）
- [x] docker/sft_train.sh 存在且可执行
- [x] 提交 44dc096 存在（Task 1）
- [x] 提交 d42925c 存在（Task 2）

## Self-Check: PASSED

所有文件和提交均已验证存在。

## 技术实现细节

### 1. LoRA 配置
```python
model = FastLanguageModel.get_peft_model(
    model,
    r=32,  # LoRA rank
    target_modules=[
        "q_proj", "k_proj", "v_proj", "o_proj",
        "gate_proj", "up_proj", "down_proj"
    ],
    lora_alpha=64,  # 2 * rank 加速训练
    use_gradient_checkpointing="unsloth",
    random_state=3407,
)
```

### 2. Chat Template 格式
系统提示词: "你是交通信号配时优化专家。"

模板特点:
- 使用重复开标签作为关闭标签（`<think>...<think>`）
- `add_generation_prompt` 自动添加 `<think>` 引导模型开始推理
- 支持 system/user/assistant 三种角色

### 3. 数据过滤策略
参考 qwen3_(4b)_grpo.py 第 146-149 行：
- 过滤掉 tokenized 长度超过 `max_seq_length/2` 的样本
- 避免训练过程中因序列过长导致显存不足
- 保留合理长度样本确保训练稳定性

### 4. 模型保存方式
选择 `merged_16bit` 方法:
- 合并 LoRA 权重到基础模型
- 保存为 float16 格式（平衡精度和大小）
- 可直接用于推理，无需额外加载 LoRA adapter

## 下一步

继续执行 Phase 1 Plan 04: SFT 模型训练执行与验证。
