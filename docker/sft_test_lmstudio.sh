#!/usr/bin/env bash
set -euo pipefail

################################################################################
# LM Studio API 测试脚本（Docker）
#
# 用法:
#   ./docker/sft_test_lmstudio.sh [NUM_SAMPLES]
#
# 环境变量:
#   LLM_API_BASE_URL   LM Studio OpenAI API 地址
#                      默认: http://host.docker.internal:1234/v1
#   LLM_MODEL_NAME     指定要测试的已加载模型 ID（可选）
#
# 说明:
#   - 复用 benchmark/run_batch.sh 的连接方式
#   - Linux 下自动添加: --add-host=host.docker.internal:host-gateway
################################################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

IMAGE_NAME="qwen3-tsc-grpo:latest"
CONTAINER_NAME="sft-test-lmstudio"
CONTAINER_WORKDIR="/home/samuel/SCU_TSC"
HOST_OS="$(uname -s)"
NUM_SAMPLES="${1:-3}"
LLM_API_BASE_URL="${LLM_API_BASE_URL:-http://host.docker.internal:1234/v1}"
LLM_MODEL_NAME="${LLM_MODEL_NAME:-}"

echo "=========================================="
echo "LM Studio API 测试 (Docker)"
echo "=========================================="
echo "[项目目录] ${PROJECT_DIR}"
echo "[Docker 镜像] ${IMAGE_NAME}"
echo "[API] ${LLM_API_BASE_URL}"
if [[ -n "${LLM_MODEL_NAME}" ]]; then
    echo "[模型] ${LLM_MODEL_NAME}"
fi
echo "[测试样本数] ${NUM_SAMPLES}"
echo ""

if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "[清理] 移除已存在的容器: ${CONTAINER_NAME}"
    docker rm -f "${CONTAINER_NAME}" 2>/dev/null || true
fi

EXTRA_ARGS=()
if [[ "${HOST_OS}" == "Linux" ]]; then
    EXTRA_ARGS+=(--add-host=host.docker.internal:host-gateway)
fi

echo "[检查] 从容器探测 LM Studio API..."
if ! docker run --rm \
    "${EXTRA_ARGS[@]}" \
    "${IMAGE_NAME}" \
    bash -lc "curl -fsS -m 5 '${LLM_API_BASE_URL}/models' >/dev/null"; then
    echo "[错误] 容器内无法连接到 LM Studio API: ${LLM_API_BASE_URL}"
    echo "请确认:"
    echo "  1. LM Studio 已启动并已加载模型"
    echo "  2. LM Studio API 服务已开启 (端口 1234)"
    echo "  3. Linux 下网络接口不是仅 localhost（建议 0.0.0.0）"
    exit 1
fi

echo "[开始] 调用 src/test_lmstudio.py ..."
docker run --rm \
    --name "${CONTAINER_NAME}" \
    --gpus all \
    --user "$(id -u):$(id -g)" \
    -v "${PROJECT_DIR}:${CONTAINER_WORKDIR}:rw" \
    -w "${CONTAINER_WORKDIR}" \
    -e HOME="${CONTAINER_WORKDIR}" \
    -e XDG_CACHE_HOME="${CONTAINER_WORKDIR}/.cache" \
    -e HF_HOME="${CONTAINER_WORKDIR}/.cache/huggingface" \
    -e LLM_API_BASE_URL="${LLM_API_BASE_URL}" \
    -e LLM_MODEL_NAME="${LLM_MODEL_NAME}" \
    "${EXTRA_ARGS[@]}" \
    "${IMAGE_NAME}" \
    python src/test_lmstudio.py "${NUM_SAMPLES}"

echo ""
echo "=========================================="
echo "[完成] LM Studio API 测试完成"
echo "=========================================="
