#!/usr/bin/env bash
set -euo pipefail

################################################################################
# 完整训练流程 - 支持 data -> grpo (默认) 或 data -> sft -> grpo (完整)
#
# 每个阶段独立拉起 Docker 容器执行
#
# 流程:
#   direct: 数据生成 -> GRPO 训练（跳过 SFT，使用 Qwen3-4B-Thinking-2507）
#   all:    数据生成 -> SFT 训练 -> GRPO 训练（完整流程）
#   单阶段: data / sft / grpo
#
# 用法:
#   ./docker/run.sh                 # 默认流程（direct: data -> grpo）
#   ./docker/run.sh --stage all     # 完整流程（data -> sft -> grpo）
#   ./docker/run.sh --stage sft     # 从 SFT 阶段开始
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
STAGE="direct"
while [[ $# -gt 0 ]]; do
    case "$1" in
        --stage)
            STAGE="$2"
            shift 2
            ;;
        *)
            echo "[ERROR] 未知参数: $1" >&2
            echo "用法: ./docker/run.sh [--stage data|sft|grpo|all|direct]" >&2
            exit 1
            ;;
    esac
done

echo ""
echo "=========================================="
echo "GRPO 交通信号优化 - 完整训练流程"
echo "=========================================="
echo "[项目目录] ${PROJECT_DIR}"
echo "[执行阶段] ${STAGE}"
echo ""

# 记录开始时间
START_TIME=$(date +%s)

# 阶段 1: 数据生成
if [[ "${STAGE}" == "all" || "${STAGE}" == "direct" || "${STAGE}" == "data" ]]; then
    echo "[阶段 1/3] 数据生成"
    bash "${SCRIPT_DIR}/data.sh"
fi

# 阶段 2: SFT 训练 (仅 all 模式)
if [[ "${STAGE}" == "all" || "${STAGE}" == "sft" ]]; then
    echo "[阶段 2/3] SFT 训练"
    bash "${SCRIPT_DIR}/sft.sh"
fi

# 阶段 3: GRPO 训练
if [[ "${STAGE}" == "all" || "${STAGE}" == "direct" || "${STAGE}" == "grpo" ]]; then
    echo "[阶段 3/3] GRPO 训练"
    bash "${SCRIPT_DIR}/grpo.sh"
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
if [[ "${STAGE}" == "all" || "${STAGE}" == "sft" ]]; then
    echo "  SFT:  outputs/sft/model/"
fi
echo "  GRPO: outputs/grpo/"
echo ""
echo "=========================================="
echo ""
