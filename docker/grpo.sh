#!/usr/bin/env bash
set -euo pipefail

################################################################################
# GRPO 训练脚本 - 强化学习微调
#
# 输入: outputs/sft/final/ (SFT 模型)
# 输出: outputs/grpo/final/ (GRPO 模型)
#
# 用法:
#   ./docker/grpo.sh
################################################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

# 切换到项目目录
cd "${PROJECT_DIR}"

echo "=========================================="
echo "GRPO 训练阶段"
echo "=========================================="
echo "[项目目录] ${PROJECT_DIR}"
echo ""

# 创建输出目录
mkdir -p outputs/grpo

# 调用 GRPO 训练脚本
echo "[开始] GRPO 训练..."
python3 -m src.scripts.train_grpo \
    --config config/config.json \
    --output-dir outputs/grpo

echo ""
echo "=========================================="
echo "[完成] GRPO 训练完成"
echo "=========================================="
echo "[输出目录] outputs/grpo/"
echo ""
