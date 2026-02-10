#!/usr/bin/env bash
set -euo pipefail

################################################################################
# SFT 测试脚本 - 加载训练好的 SFT 模型，随机抽取多条样本测试推理效果
#
# 用法:
#   ./docker/sft_test.sh [NUM_SAMPLES]
#   默认测试 5 条样本
################################################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

IMAGE_NAME="qwen3-tsc-grpo:latest"
CONTAINER_WORKDIR="/home/samuel/SCU_TSC"
NUM_SAMPLES="${1:-5}"

echo "=========================================="
echo "SFT 推理测试 (Docker)"
echo "=========================================="
echo "[项目目录] ${PROJECT_DIR}"
echo "[Docker 镜像] ${IMAGE_NAME}"
echo "[测试样本数] ${NUM_SAMPLES}"
echo ""

echo "[开始] 加载 SFT 模型并测试推理..."
docker run --rm \
    --gpus all \
    --shm-size=32GB \
    --user "$(id -u):$(id -g)" \
    -v "${PROJECT_DIR}:${CONTAINER_WORKDIR}:rw" \
    -w "${CONTAINER_WORKDIR}" \
    -e HF_HOME="${CONTAINER_WORKDIR}/.cache/huggingface" \
    --entrypoint python3 \
    "${IMAGE_NAME}" \
    src/sft/test_inference.py "${NUM_SAMPLES}"

echo ""
echo "=========================================="
echo "[完成] SFT 推理测试完成"
echo "=========================================="
