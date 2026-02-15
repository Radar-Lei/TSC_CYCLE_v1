# Quick Task 2: 合并最新 GRPO checkpoint 到 model 目录

## 执行摘要

创建了独立的 checkpoint 合并脚本，支持将 GRPO 训练产生的 LoRA adapter checkpoint 与 SFT 基础模型合并，输出完整模型用于 GGUF 转换。

## 创建的文件

### 1. `src/scripts/merge_checkpoint.py`
Python 合并脚本（约 160 行）：
- 自动查找最新 checkpoint（按 step number 排序）
- 加载 SFT 基础模型 + LoRA adapter
- 使用 PEFT merge_and_unload() 合并权重
- 保存完整模型到指定目录

**命令行参数：**
- `--checkpoint NAME` - 指定 checkpoint（默认：最新）
- `--output DIR` - 指定输出目录（默认：outputs/grpo/model）
- `--base-model DIR` - 指定基础模型（默认：从 config 读取）

### 2. `docker/merge_checkpoint.sh`
Docker 包装脚本（约 120 行）：
- 在 Docker 容器中执行 Python 脚本
- 检查 SFT 基础模型和 checkpoints 目录
- 列出所有可用 checkpoints 及大小
- 支持与 Python 脚本相同的命令行参数

## 修改的文件

### `docker/convert_gguf.sh`
扩展以支持 GRPO 模型：
- 新增 `--model-path` 参数指定模型目录
- 更新帮助信息和错误提示
- 默认仍为 SFT 模型（向后兼容）

## 使用方法

```bash
# 1. 合并最新 checkpoint
./docker/merge_checkpoint.sh

# 2. 合并指定 checkpoint
./docker/merge_checkpoint.sh --checkpoint checkpoint-5000

# 3. 转换为 GGUF（合并后）
./docker/convert_gguf.sh --model-path outputs/grpo/model
```

## 技术细节

- Checkpoint 格式：LoRA adapter (`adapter_model.safetensors`, ~252MB)
- 基础模型：`outputs/sft/model`（SFT 训练后的完整模型）
- 合并方法：PEFT `PeftModel.from_pretrained()` + `merge_and_unload()`
- 输出格式：safetensors 完整模型（约 8GB）

## 验证

- [x] `docker/merge_checkpoint.sh` 可执行权限已设置
- [x] 脚本检查 SFT 基础模型存在性
- [x] 脚本检查 checkpoints 目录并列出可用选项
- [x] `convert_gguf.sh` 支持 `--model-path` 参数
