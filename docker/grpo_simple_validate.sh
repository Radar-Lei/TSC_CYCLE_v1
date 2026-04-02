#!/usr/bin/env bash
set -euo pipefail

################################################################################
# 简化版 GRPO 模型验证脚本 - 通过 Unsloth Docker 自动验证训练产出模型
################################################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

IMAGE_NAME="qwen3-tsc-grpo:latest"
CONTAINER_NAME="grpo-simple-validate"
CONTAINER_WORKDIR="/home/samuel/SCU_TSC"

NUM_SAMPLES="${1:-100}"

echo "=========================================="
echo "简化版 GRPO 模型验证 (Unsloth Docker)"
echo "=========================================="
echo "[项目目录] ${PROJECT_DIR}"
echo "[Docker 镜像] ${IMAGE_NAME}"
echo "[测试样本数] ${NUM_SAMPLES}"
echo ""

MODEL_DIR="${PROJECT_DIR}/outputs/grpo_simple/model"
if [ ! -f "${MODEL_DIR}/config.json" ]; then
    echo "[错误] 模型不存在: ${MODEL_DIR}"
    echo "请先完成 GRPO 训练"
    exit 1
fi

if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    docker rm -f "${CONTAINER_NAME}" 2>/dev/null || true
fi

echo "[开始] 模型验证..."
docker run --rm \
    --name "${CONTAINER_NAME}" \
    --gpus all \
    --shm-size=32GB \
    --user "$(id -u):$(id -g)" \
    -v "${PROJECT_DIR}:${CONTAINER_WORKDIR}:rw" \
    -w "${CONTAINER_WORKDIR}" \
    -e HF_HOME="${CONTAINER_WORKDIR}/.cache/huggingface" \
    --entrypoint python3 \
    "${IMAGE_NAME}" \
    -m src.grpo_simple.validate \
        --config config/config.json \
        --num-samples "${NUM_SAMPLES}" \
        --output outputs/grpo_simple/validation_result.json

echo ""
echo "=========================================="
echo "[完成] 验证结果: outputs/grpo_simple/validation_result.json"
echo "=========================================="
