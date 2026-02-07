#!/usr/bin/env bash
set -euo pipefail

################################################################################
# 完整训练流程 - 串联执行 data -> sft -> grpo
#
# 流程:
#   1. 数据生成 (data.sh)
#   2. SFT 训练 (sft.sh)
#   3. GRPO 训练 (grpo.sh)
#
# 用法:
#   ./docker/run.sh
#
# 说明:
#   - 任一阶段失败则立即停止（set -e）
#   - 所有输出统一到 outputs/ 目录
################################################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

# 切换到项目目录
cd "${PROJECT_DIR}"

echo ""
echo "=========================================="
echo "GRPO 交通信号优化 - 完整训练流程"
echo "=========================================="
echo "[项目目录] ${PROJECT_DIR}"
echo ""

# 记录开始时间
START_TIME=$(date +%s)

# 阶段 1: 数据生成
echo "[阶段 1/3] 数据生成"
bash "${SCRIPT_DIR}/data.sh"

# 阶段 2: SFT 训练
echo "[阶段 2/3] SFT 训练"
bash "${SCRIPT_DIR}/sft.sh"

# 阶段 3: GRPO 训练
echo "[阶段 3/3] GRPO 训练"
bash "${SCRIPT_DIR}/grpo.sh"

# 计算总时长
END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))
HOURS=$((DURATION / 3600))
MINUTES=$(((DURATION % 3600) / 60))
SECONDS=$((DURATION % 60))

echo ""
echo "=========================================="
echo "训练流程完成"
echo "=========================================="
printf "[总耗时] %02d:%02d:%02d\n" $HOURS $MINUTES $SECONDS
echo ""
echo "[输出目录]"
echo "  数据: outputs/data/"
echo "  SFT:  outputs/sft/"
echo "  GRPO: outputs/grpo/"
echo ""
echo "=========================================="
echo ""
