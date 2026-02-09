#!/usr/bin/env bash
set -euo pipefail

################################################################################
# SFT 交通信号优化 - 训练流程
#
# 每个阶段独立拉起 Docker 容器执行
#
# 流程:
#   all:    数据生成 -> SFT 训练（默认完整流程）
#   单阶段: data / sft
#
# 用法:
#   ./docker/run.sh                 # 默认流程（all: data -> sft）
#   ./docker/run.sh --stage all     # 完整流程（data -> sft）
#   ./docker/run.sh --stage data    # 仅数据生成
#   ./docker/run.sh --stage sft     # 仅 SFT 训练
#
# 说明:
#   - 任一阶段失败则立即停止（set -e）
#   - 所有输出统一到 outputs/ 目录
#   - 每个阶段通过 Docker 容器执行
################################################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

# 切换到项目目录
cd "${PROJECT_DIR}"

# 解析 --stage 参数
STAGE="all"
while [[ $# -gt 0 ]]; do
    case "$1" in
        --stage)
            STAGE="$2"
            shift 2
            ;;
        *)
            echo "[ERROR] 未知参数: $1" >&2
            echo "用法: ./docker/run.sh [--stage data|sft|all]" >&2
            exit 1
            ;;
    esac
done

echo ""
echo "=========================================="
echo "SFT 交通信号优化 - 训练流程"
echo "=========================================="
echo "[项目目录] ${PROJECT_DIR}"
echo "[执行阶段] ${STAGE}"
echo ""

# 记录开始时间
START_TIME=$(date +%s)

# 阶段 1: 数据生成
if [[ "${STAGE}" == "all" || "${STAGE}" == "data" ]]; then
    echo "[阶段 1/2] 数据生成"
    bash "${SCRIPT_DIR}/data.sh"
fi

# 阶段 2: SFT 训练
if [[ "${STAGE}" == "all" || "${STAGE}" == "sft" ]]; then
    echo "[阶段 2/2] SFT 训练"
    bash "${SCRIPT_DIR}/sft.sh"
fi

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
echo "  SFT:  outputs/sft/model/"
echo ""
echo "=========================================="
echo ""
