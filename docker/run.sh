#!/usr/bin/env bash
set -euo pipefail

################################################################################
# 交通信号优化 - 数据生成流程
#
# 通过 Docker 容器执行数据生成
#
# 用法:
#   ./docker/run.sh                 # 执行数据生成
#
# 说明:
#   - 失败则立即停止（set -e）
#   - 所有输出统一到 outputs/ 目录
#   - 通过 Docker 容器执行
################################################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

# 切换到项目目录
cd "${PROJECT_DIR}"

echo ""
echo "=========================================="
echo "交通信号优化 - 数据生成流程"
echo "=========================================="
echo "[项目目录] ${PROJECT_DIR}"
echo ""

# 记录开始时间
START_TIME=$(date +%s)

# 数据生成
echo "[阶段] 数据生成"
bash "${SCRIPT_DIR}/data.sh" "$@"

# 计算总时长
END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))
HOURS=$((DURATION / 3600))
MINUTES=$(((DURATION % 3600) / 60))
SECONDS=$((DURATION % 60))

echo ""
echo "=========================================="
echo "数据生成完成"
echo "=========================================="
printf "[总耗时] %02d:%02d:%02d\n" $HOURS $MINUTES $SECONDS
echo ""
echo "[输出目录]"
echo "  数据: outputs/data/"
echo ""
echo "=========================================="
echo ""
