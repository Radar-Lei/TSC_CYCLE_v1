#!/usr/bin/env bash
set -euo pipefail

################################################################################
# GRPO 训练脚本 - 强化学习微调（通过 Docker 容器执行）
#
# 输入: 基础模型 (默认: Qwen3-4B-Thinking-2507，跳过 SFT)
#        或 outputs/sft/model/final/ (通过 --sft-adapter 使用 SFT 模型)
# 输出: outputs/grpo/final/ (GRPO 模型)
#
# 用法:
#   ./docker/grpo.sh
#   ./docker/grpo.sh --max-steps 50     # 自定义参数
################################################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

IMAGE_NAME="qwen3-tsc-grpo:latest"
CONTAINER_WORKDIR="/home/samuel/SCU_TSC"

echo "=========================================="
echo "GRPO 训练阶段 (Docker)"
echo "=========================================="
echo "[项目目录] ${PROJECT_DIR}"
echo "[Docker 镜像] ${IMAGE_NAME}"
echo ""

# 创建输出目录（宿主机侧）
mkdir -p "${PROJECT_DIR}/outputs/grpo"

# 通过 Docker 容器执行 GRPO 训练
echo "[开始] GRPO 训练..."
docker run --rm \
    --gpus all \
    --shm-size=32GB \
    --user "$(id -u):$(id -g)" \
    -v "${PROJECT_DIR}:${CONTAINER_WORKDIR}:rw" \
    -w "${CONTAINER_WORKDIR}" \
    -e HF_HOME="${CONTAINER_WORKDIR}/model" \
    -e MODELSCOPE_CACHE="${CONTAINER_WORKDIR}/model" \
    -e UNSLOTH_USE_MODELSCOPE=1 \
    -e SUMO_HOME=/usr/share/sumo \
    --entrypoint python3 \
    "${IMAGE_NAME}" \
    -m src.scripts.train_grpo \
        --config config/config.json \
        --output-dir outputs/grpo \
        "$@"

echo ""
echo "=========================================="
echo "[完成] GRPO 训练完成"
echo "=========================================="
echo "[输出目录] outputs/grpo/"
echo ""
