#!/usr/bin/env bash
set -euo pipefail

################################################################################
# SFT 训练脚本 - 监督微调（通过 Docker 容器执行）
#
# 输入: outputs/sft/train.jsonl
# 输出: outputs/sft/model/final/ (模型权重)
#
# 用法:
#   ./docker/sft.sh
#   ./docker/sft.sh --max-steps 100    # 自定义参数
################################################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

IMAGE_NAME="qwen3-tsc-grpo:latest"
CONTAINER_WORKDIR="/home/samuel/SCU_TSC"

echo "=========================================="
echo "SFT 训练阶段 (Docker)"
echo "=========================================="
echo "[项目目录] ${PROJECT_DIR}"
echo "[Docker 镜像] ${IMAGE_NAME}"
echo ""

# 创建输出目录（宿主机侧）
mkdir -p "${PROJECT_DIR}/outputs/sft/model"

# 通过 Docker 容器执行 SFT 训练
echo "[开始] SFT 训练..."
docker run --rm \
    --gpus all \
    --shm-size=32GB \
    --user "$(id -u):$(id -g)" \
    -v "${PROJECT_DIR}:${CONTAINER_WORKDIR}:rw" \
    -w "${CONTAINER_WORKDIR}" \
    -e HF_HOME="${CONTAINER_WORKDIR}/model" \
    -e MODELSCOPE_CACHE="${CONTAINER_WORKDIR}/model" \
    -e UNSLOTH_USE_MODELSCOPE=1 \
    --entrypoint python3 \
    "${IMAGE_NAME}" \
    -m src.scripts.train_sft \
        --config config/config.json \
        --data-dir outputs/sft \
        --output-dir outputs/sft/model \
        "$@"

echo ""
echo "=========================================="
echo "[完成] SFT 训练完成"
echo "=========================================="
echo "[输出目录] outputs/sft/model/"
echo ""
