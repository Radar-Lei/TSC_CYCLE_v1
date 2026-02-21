---
status: resolved
trigger: "SFT 推理测试脚本 `./docker/sft_test.sh 3` 运行超过 30 分钟仍未结束，预期只需 1-5 分钟"
created: 2026-02-19T13:30:00+08:00
updated: 2026-02-19T17:40:00+08:00
---

## Resolution Summary

### 根本原因
GLM-4.7-Flash 是一个 59GB 的大模型，加载需要 10-15 分钟，而不是推理本身的问题。

### 解决方案
1. **修改训练脚本**：只保存 LoRA adapter（46MB）而不是 merged 完整模型
2. **创建合并脚本**：`src/merge_lora.py` - 用 BF16 加载并合并 LoRA
3. **转换为 GGUF**：17GB Q4_K_M 格式，加载更快

### 修改的文件
- `src/sft/train.py` - 只保存 LoRA adapter
- `src/sft/test_inference.py` - 支持加载基础模型 + LoRA adapter
- `src/merge_lora.py` - 新增，合并 LoRA 并保存
- `src/export_gguf.py` - 新增，导出 GGUF（有环境问题，暂时不用）

### 验证结果
- GGUF 模型（17GB）可以正常推理
- 生成速度约 9.6 tokens/s（CPU）
- 模型正确输出 `[Start thinking]` 推理过程

### 后续建议
1. 在 Docker 镜像中预装 llama.cpp（带 GPU 支持）
2. 或使用 llama-cpp-python 进行 GGUF 推理
3. 保持 LoRA adapter 模式，需要时再合并/导出

## Symptoms
expected: SFT 推理测试 3 个样本应在 1-5 分钟内完成
actual: 运行超过 30 分钟仍未结束，GPU 显存满利用率高
errors: 只显示 `torch_dtype is deprecated! Use dtype instead!` 警告
reproduction: 运行 `./docker/sft_test.sh 3`

## Evidence
- 确认 GLM-4.7-Flash 基础模型 59GB，加载需要 10-15 分钟
- LoRA adapter 只有 46MB
- GGUF Q4_K_M 压缩到 17GB，推理正常
