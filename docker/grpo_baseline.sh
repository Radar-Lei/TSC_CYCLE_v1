#!/usr/bin/env bash
set -euo pipefail

################################################################################
# GRPO Baseline 预计算脚本 - 通过 Docker 容器执行 baseline 预计算
#
# 输出: outputs/grpo/baseline.json (每个 state_file 的 baseline 性能指标)
#
# 用法:
#   ./docker/grpo_baseline.sh                    # 使用默认配置
#   ./docker/grpo_baseline.sh --workers 8        # 指定并行工作进程数
#
# 注意: 使用 chmod +x docker/grpo_baseline.sh 设置可执行权限
################################################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

IMAGE_NAME="qwen3-tsc-grpo:latest"
CONTAINER_NAME="grpo-baseline"
CONTAINER_WORKDIR="/home/samuel/SCU_TSC"

echo "=========================================="
echo "GRPO Baseline 预计算阶段 (Docker)"
echo "=========================================="
echo "[项目目录] ${PROJECT_DIR}"
echo "[Docker 镜像] ${IMAGE_NAME}"
echo ""

# 清理可能残留的同名容器
if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "[清理] 移除已存在的容器: ${CONTAINER_NAME}"
    docker rm -f "${CONTAINER_NAME}" 2>/dev/null || true
fi

# 创建输出目录（宿主机侧）
mkdir -p "${PROJECT_DIR}/outputs/grpo"

# 通过 Docker 容器执行 baseline 预计算
echo "[开始] GRPO Baseline 预计算..."
docker run --rm \
    --name "${CONTAINER_NAME}" \
    --gpus all \
    --shm-size=32GB \
    --user "$(id -u):$(id -g)" \
    -v "${PROJECT_DIR}:${CONTAINER_WORKDIR}:rw" \
    -w "${CONTAINER_WORKDIR}" \
    -e SUMO_HOME=/usr/share/sumo \
    --entrypoint python3 \
    "${IMAGE_NAME}" \
    -m src.grpo.baseline \
        --config config/config.json \
        --workers 16 \
        "$@"

echo ""
echo "=========================================="
echo "[完成] GRPO Baseline 预计算完成"
echo "=========================================="
echo "[输出文件] outputs/grpo/baseline.json"
echo ""
