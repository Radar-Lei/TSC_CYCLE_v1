#!/usr/bin/env bash
set -euo pipefail

################################################################################
# GRPO 数据生成脚本 - 从 train.jsonl 转换为 GRPO 训练格式（通过 Docker 容器执行）
#
# 输入: outputs/data/train.jsonl
# 输出: outputs/grpo/grpo_train.jsonl
#
# 用法:
#   ./docker/grpo_data.sh
#   ./docker/grpo_data.sh --input outputs/data/train.jsonl --output outputs/grpo/grpo_train.jsonl
################################################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

IMAGE_NAME="qwen3-tsc-grpo:latest"
CONTAINER_WORKDIR="/home/samuel/SCU_TSC"

echo "=========================================="
echo "GRPO 数据生成阶段 (Docker)"
echo "=========================================="
echo "[项目目录] ${PROJECT_DIR}"
echo "[Docker 镜像] ${IMAGE_NAME}"
echo ""

# 创建输出目录（宿主机侧）
mkdir -p "${PROJECT_DIR}/outputs/grpo"

# 通过 Docker 容器执行 GRPO 数据生成
echo "[开始] 生成 GRPO 训练数据..."
docker run --rm \
    --gpus all \
    --shm-size=32GB \
    --user "$(id -u):$(id -g)" \
    -v "${PROJECT_DIR}:${CONTAINER_WORKDIR}:rw" \
    -w "${CONTAINER_WORKDIR}" \
    -e SUMO_HOME=/usr/share/sumo \
    --entrypoint python3 \
    "${IMAGE_NAME}" \
    -m src.scripts.generate_grpo_data \
        "$@"

echo ""
echo "=========================================="
echo "[完成] GRPO 数据生成完成"
echo "=========================================="
echo "[输出文件] outputs/grpo/grpo_train.jsonl"
echo ""
