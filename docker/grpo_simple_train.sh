#!/usr/bin/env bash
set -euo pipefail

################################################################################
# 简化版 GRPO 训练脚本 - 通过 Unsloth Docker 执行无 SUMO reward 的 GRPO 训练
################################################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

IMAGE_NAME="qwen3-tsc-grpo:latest"
CONTAINER_NAME="grpo-simple-train"
CONTAINER_WORKDIR="/home/samuel/SCU_TSC"

echo "=========================================="
echo "简化版 GRPO 训练阶段 (Unsloth Docker)"
echo "=========================================="
echo "[项目目录] ${PROJECT_DIR}"
echo "[Docker 镜像] ${IMAGE_NAME}"
echo ""

if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "[清理] 移除已存在的容器: ${CONTAINER_NAME}"
    docker rm -f "${CONTAINER_NAME}" 2>/dev/null || true
fi

# 解析 --config 参数
CONFIG_FILE="config/config.json"
while [[ $# -gt 0 ]]; do
    case "$1" in
        --config)
            CONFIG_FILE="$2"
            shift 2
            ;;
        *)
            shift
            ;;
    esac
done

# 从配置文件中读取路径
GRPO_OUTPUT=$(python3 -c "import json; c=json.load(open('${PROJECT_DIR}/${CONFIG_FILE}')); print(c['paths'].get('grpo_simple_output', 'outputs/grpo_simple/model'))")
GRPO_CHECKPOINTS=$(python3 -c "import json; c=json.load(open('${PROJECT_DIR}/${CONFIG_FILE}')); print(c['paths'].get('grpo_simple_checkpoints', 'outputs/grpo_simple/checkpoints'))")
SFT_MODEL=$(python3 -c "import json; c=json.load(open('${PROJECT_DIR}/${CONFIG_FILE}')); print(c['training']['grpo_simple']['model']['model_name'])")
GRPO_DATA_DIR=$(python3 -c "import json; c=json.load(open('${PROJECT_DIR}/${CONFIG_FILE}')); print(c['paths'].get('grpo_simple_data_dir', 'outputs/grpo_simple'))")
GRPO_DATA="${PROJECT_DIR}/${GRPO_DATA_DIR}/grpo_train.jsonl"
SFT_MODEL_ABS="${PROJECT_DIR}/${SFT_MODEL}"

mkdir -p "${PROJECT_DIR}/${GRPO_OUTPUT}"
mkdir -p "${PROJECT_DIR}/${GRPO_CHECKPOINTS}"

LOG_FILE="${PROJECT_DIR}/${GRPO_OUTPUT}/../train_$(date +%Y%m%d_%H%M%S).log"
echo "[训练日志] ${LOG_FILE}"

if [ ! -d "${SFT_MODEL_ABS}" ] || [ ! -f "${SFT_MODEL_ABS}/config.json" ]; then
    echo "[错误] SFT 模型不存在: ${SFT_MODEL_ABS}"
    echo "请先完成 SFT 训练"
    exit 1
fi

if [ ! -f "${GRPO_DATA}" ]; then
    echo "[错误] GRPO 训练数据不存在: ${GRPO_DATA}"
    echo "请先运行 ./docker/grpo_simple_data.sh 生成简化版 GRPO 数据"
    exit 1
fi

echo "[前置检查] 配置文件: ${CONFIG_FILE}"
echo "[前置检查] SFT 模型: 存在 (${SFT_MODEL})"
echo "[前置检查] GRPO 数据: $(wc -l < "${GRPO_DATA}") 条记录"
echo ""

echo "[开始] 简化版 GRPO 训练..."
echo "[开始] $(date '+%Y-%m-%d %H:%M:%S')" | tee "${LOG_FILE}"
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
    -m src.grpo_simple.train \
        --config "${CONFIG_FILE}" 2>&1 | tee -a "${LOG_FILE}"

echo ""
echo "=========================================="
echo "[完成] 简化版 GRPO 训练完成"
echo "=========================================="
echo "[模型输出] ${GRPO_OUTPUT}"
echo "[检查点目录] ${GRPO_CHECKPOINTS}"
echo ""
