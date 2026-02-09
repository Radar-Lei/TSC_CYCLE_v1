#!/usr/bin/env bash
set -euo pipefail

################################################################################
# 数据生成脚本 - 从 SUMO 仿真生成训练数据（通过 Docker 容器执行）
#
# 输出: outputs/data/*.jsonl
#       outputs/states/* (仿真状态快照)
#
# 用法:
#   ./docker/data.sh                                    # 全部场景
#   ./docker/data.sh --scenarios arterial4x4_1,chengdu  # 指定场景
################################################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

IMAGE_NAME="qwen3-tsc-grpo:latest"
CONTAINER_WORKDIR="/home/samuel/SCU_TSC"

echo "=========================================="
echo "数据生成阶段 (Docker)"
echo "=========================================="
echo "[项目目录] ${PROJECT_DIR}"
echo "[Docker 镜像] ${IMAGE_NAME}"
echo ""

# 创建输出目录（宿主机侧）
mkdir -p "${PROJECT_DIR}/outputs/data" "${PROJECT_DIR}/outputs/states"

# 通过 Docker 容器执行数据生成
echo "[开始] 生成训练数据..."
docker run --rm \
    --gpus all \
    --shm-size=32GB \
    --user "$(id -u):$(id -g)" \
    -v "${PROJECT_DIR}:${CONTAINER_WORKDIR}:rw" \
    -w "${CONTAINER_WORKDIR}" \
    -e SUMO_HOME=/usr/share/sumo \
    --entrypoint python3 \
    "${IMAGE_NAME}" \
    -m src.scripts.generate_training_data \
        --config config/config.json \
        --output-dir outputs/data \
        --state-dir outputs/states \
        "$@"

echo ""
echo "=========================================="
echo "[完成] 数据生成完成"
echo "=========================================="
echo "[输出目录] outputs/data/"
echo "[状态目录] outputs/states/"
echo ""
