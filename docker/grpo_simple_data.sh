#!/usr/bin/env bash
set -euo pipefail

################################################################################
# 简化版 GRPO 数据生成脚本 - 通过 Unsloth Docker 从原始 train.jsonl 生成 prompt 数据
################################################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

IMAGE_NAME="qwen3-tsc-grpo:latest"
CONTAINER_NAME="grpo-simple-data"
CONTAINER_WORKDIR="/home/samuel/SCU_TSC"

echo "=========================================="
echo "简化版 GRPO 数据生成 (Unsloth Docker)"
echo "=========================================="
echo "[项目目录] ${PROJECT_DIR}"
echo "[Docker 镜像] ${IMAGE_NAME}"
echo ""

if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    docker rm -f "${CONTAINER_NAME}" 2>/dev/null || true
fi

docker run --rm \
    --name "${CONTAINER_NAME}" \
    --gpus all \
    --shm-size=32GB \
    --user "$(id -u):$(id -g)" \
    -v "${PROJECT_DIR}:${CONTAINER_WORKDIR}:rw" \
    -w "${CONTAINER_WORKDIR}" \
    -e SUMO_HOME=/usr/share/sumo \
    -e HF_HOME="${CONTAINER_WORKDIR}/.cache/huggingface" \
    --entrypoint python3 \
    "${IMAGE_NAME}" \
    -m src.scripts.generate_grpo_simple_data \
        --input outputs/data/train.jsonl \
        --output outputs/grpo_simple/grpo_train.jsonl

echo ""
echo "[完成] outputs/grpo_simple/grpo_train.jsonl"
