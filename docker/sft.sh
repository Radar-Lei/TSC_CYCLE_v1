#!/usr/bin/env bash
set -euo pipefail

################################################################################
# SFT 训练脚本 - 监督微调
#
# 输入: outputs/data/*.jsonl
# 输出: outputs/sft/final/ (模型权重)
#
# 用法:
#   ./docker/sft.sh
################################################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

# 切换到项目目录
cd "${PROJECT_DIR}"

echo "=========================================="
echo "SFT 训练阶段"
echo "=========================================="
echo "[项目目录] ${PROJECT_DIR}"
echo ""

# 创建输出目录
mkdir -p outputs/sft

# 调用 SFT 训练脚本
echo "[开始] SFT 训练..."
python3 -m src.scripts.train_sft \
    --config config/config.json \
    --output-dir outputs/sft

echo ""
echo "=========================================="
echo "[完成] SFT 训练完成"
echo "=========================================="
echo "[输出目录] outputs/sft/"
echo ""
