#!/usr/bin/env bash
set -euo pipefail

################################################################################
# SFT 测试脚本 - 加载训练好的 SFT 模型，随机抽取多条样本测试推理效果
#
# 用法:
#   ./docker/sft_test.sh [NUM_SAMPLES]           # PyTorch 模式（默认）
#   ./docker/sft_test.sh --gguf [NUM_SAMPLES]    # GGUF 模式
#   默认测试 5 条样本
#
# 模式说明:
#   - PyTorch 模式: 调用 src/sft/test_inference.py（需要 GPU）
#   - GGUF 模式:    调用 src/test_gguf.py（量化模型，低显存需求）
################################################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

IMAGE_NAME="qwen3-tsc-grpo:latest"
CONTAINER_NAME="sft-test"
CONTAINER_WORKDIR="/home/samuel/SCU_TSC"

# 参数解析
USE_GGUF=false
NUM_SAMPLES=5

while [[ $# -gt 0 ]]; do
    case $1 in
        --gguf)
            USE_GGUF=true
            shift
            ;;
        *)
            NUM_SAMPLES="$1"
            shift
            ;;
    esac
done

# 根据模式选择测试脚本
if [[ "$USE_GGUF" == "true" ]]; then
    TEST_SCRIPT="src/test_gguf.py"
    TEST_MODE="GGUF"
else
    TEST_SCRIPT="src/sft/test_inference.py"
    TEST_MODE="PyTorch"
fi

echo "=========================================="
echo "SFT 推理测试 (Docker)"
echo "=========================================="
echo "[项目目录] ${PROJECT_DIR}"
echo "[Docker 镜像] ${IMAGE_NAME}"
echo "[测试模式] ${TEST_MODE}"
echo "[测试样本数] ${NUM_SAMPLES}"
echo ""

# 清理可能残留的同名容器
if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "[清理] 移除已存在的容器: ${CONTAINER_NAME}"
    docker rm -f "${CONTAINER_NAME}" 2>/dev/null || true
fi

echo "[开始] 加载 SFT 模型并测试推理..."
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
    "${TEST_SCRIPT}" "${NUM_SAMPLES}"

echo ""
echo "=========================================="
echo "[完成] SFT 推理测试完成"
echo "=========================================="
