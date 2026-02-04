#!/usr/bin/env bash
# 清理旧的Docker镜像和容器，确保使用最新的代码

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

CONTAINER_NAME="${CONTAINER_NAME:-qwen3-tsc-grpo}"
IMAGE_NAME="${IMAGE_NAME:-qwen3-tsc-grpo}"

echo "=========================================="
echo "清理旧的Docker镜像和容器"
echo "=========================================="
echo ""

# 停止并删除容器
echo "[1/3] 停止并删除旧容器..."
if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    docker stop "${CONTAINER_NAME}" 2>/dev/null || true
    docker rm "${CONTAINER_NAME}"
    echo "✓ 已删除容器: ${CONTAINER_NAME}"
else
    echo "  未找到容器: ${CONTAINER_NAME} (跳过)"
fi

# 删除旧镜像
echo ""
echo "[2/3] 删除旧镜像..."
if docker images --format '{{.Repository}}:{{.Tag}}' | grep -q "^${IMAGE_NAME}:latest$"; then
    docker rmi "${IMAGE_NAME}:latest"
    echo "✓ 已删除镜像: ${IMAGE_NAME}:latest"
else
    echo "  未找到镜像: ${IMAGE_NAME}:latest (跳过)"
fi

# 显示下一步操作
echo ""
echo "[3/3] 准备就绪"
echo ""
echo "=========================================="
echo "✅ 清理完成！"
echo "=========================================="
echo ""
echo "现在可以运行以下命令重新构建并启动训练："
echo ""
echo "  cd ${PROJECT_DIR}"
echo "  ./docker/publish.sh"
echo ""
echo "这将自动："
echo "  1. 重新构建Docker镜像（包含scikit-learn）"
echo "  2. 启动容器"
echo "  3. 运行完整的训练流程"
echo ""
