# Quick Task 2: 合并最新 GRPO checkpoint 到 model 目录

## 任务描述

创建一个独立的 shell 脚本 `docker/merge_checkpoint.sh`，用于：
1. 找到 `outputs/grpo/checkpoints/` 中最新的 checkpoint
2. 加载 SFT 基础模型 + LoRA adapter
3. 合并并保存到 `outputs/grpo/model/`
4. 使后续能用 `docker/convert_gguf.sh` 转换为 GGUF

## 技术方案

### 依赖关系
- GRPO checkpoint 是 LoRA adapter 格式（`adapter_model.safetensors`）
- 需要加载 SFT 模型 (`outputs/sft/model`) 作为基础模型
- 使用 unsloth 的 `FastLanguageModel.from_pretrained()` + `model.save_pretrained_merged()`

### 文件结构
```
outputs/grpo/
├── checkpoints/
│   ├── checkpoint-2000/
│   ├── checkpoint-3000/
│   ├── checkpoint-4000/
│   ├── checkpoint-5000/
│   └── checkpoint-6000/  ← 最新
└── model/  ← 输出目录
```

### 实现步骤

#### Task 1: 创建合并 Python 脚本 `src/scripts/merge_checkpoint.py`
- 加载 SFT 基础模型
- 找到最新 checkpoint
- 加载 LoRA adapter
- 合并并保存为完整模型

#### Task 2: 创建 Docker 包装脚本 `docker/merge_checkpoint.sh`
- 在 Docker 容器中执行 Python 脚本
- 支持命令行参数指定 checkpoint（可选，默认最新）
- 包含进度打印和错误处理

## 验收标准
- [ ] `docker/merge_checkpoint.sh` 可执行
- [ ] 默认合并最新 checkpoint 到 `outputs/grpo/model/`
- [ ] 支持 `--checkpoint <name>` 指定特定 checkpoint
- [ ] 输出模型与 `convert_gguf.sh` 兼容
