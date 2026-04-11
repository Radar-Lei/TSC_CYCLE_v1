#!/usr/bin/env bash
set -euo pipefail

################################################################################
# SFT 训练脚本 - 通过 Docker 容器执行 SFT 训练
#
# 用法:
#   ./docker/sft_train.sh                                # 使用默认配置
#   ./docker/sft_train.sh --config config/config_32b.json  # 指定配置文件
################################################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

IMAGE_NAME="qwen3-tsc-grpo:latest"
CONTAINER_NAME="sft-train"
CONTAINER_WORKDIR="/home/samuel/SCU_TSC"

echo "=========================================="
echo "SFT 训练阶段 (Docker)"
echo "=========================================="
echo "[项目目录] ${PROJECT_DIR}"
echo "[Docker 镜像] ${IMAGE_NAME}"
echo ""

# 清理可能残留的同名容器
if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "[清理] 移除已存在的容器: ${CONTAINER_NAME}"
    docker rm -f "${CONTAINER_NAME}" 2>/dev/null || true
fi

# 解析 --config 参数
CONFIG_FILE="config/config.json"
EXTRA_ARGS=()
while [[ $# -gt 0 ]]; do
    case "$1" in
        --config)
            CONFIG_FILE="$2"
            EXTRA_ARGS+=("--config" "$2")
            shift 2
            ;;
        *)
            EXTRA_ARGS+=("$1")
            shift
            ;;
    esac
done

# 从配置文件中读取路径
SFT_OUTPUT=$(python3 -c "import json; c=json.load(open('${PROJECT_DIR}/${CONFIG_FILE}')); print(c['paths'].get('sft_output', 'outputs/sft/model'))")
SFT_DATA_DIR=$(python3 -c "import json; c=json.load(open('${PROJECT_DIR}/${CONFIG_FILE}')); print(c['paths'].get('sft_data_dir', 'outputs/sft'))")

# 创建输出目录（宿主机侧）
mkdir -p "${PROJECT_DIR}/${SFT_OUTPUT}"
mkdir -p "${PROJECT_DIR}/$(dirname "${SFT_OUTPUT}")/checkpoints"

# 确保 SFT 训练数据存在
SFT_DATA="${PROJECT_DIR}/${SFT_DATA_DIR}/sft_train.jsonl"
WORKSPACE="${PROJECT_DIR}/${SFT_DATA_DIR}/think_workspace.jsonl"
SAMPLES="${PROJECT_DIR}/${SFT_DATA_DIR}/sampled_100.jsonl"

if [ ! -f "${SFT_DATA}" ]; then
    echo "[数据] sft_train.jsonl 不存在，正在生成..."
    if [ ! -f "${WORKSPACE}" ] || [ ! -f "${SAMPLES}" ]; then
        echo "[错误] 缺少数据源文件:"
        echo "  - think_workspace.jsonl: $([ -f "${WORKSPACE}" ] && echo '存在' || echo '不存在')"
        echo "  - sampled_100.jsonl: $([ -f "${SAMPLES}" ] && echo '存在' || echo '不存在')"
        echo "请先运行 data.sh 生成数据"
        exit 1
    fi
    python3 -m src.scripts.generate_sft_data assemble \
        --workspace "${WORKSPACE}" \
        --samples "${SAMPLES}" \
        --output "${SFT_DATA}"
    echo "[数据] sft_train.jsonl 生成完成 ($(wc -l < "${SFT_DATA}") 条记录)"
else
    echo "[数据] sft_train.jsonl 已存在 ($(wc -l < "${SFT_DATA}") 条记录)，跳过生成"
fi

echo "[前置检查] 配置文件: ${CONFIG_FILE}"
echo "[前置检查] 模型输出: ${SFT_OUTPUT}"
echo ""

# 通过 Docker 容器执行 SFT 训练
echo "[开始] SFT 训练..."
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
    -m src.sft.train \
        --config "${CONFIG_FILE}"

echo ""
echo "=========================================="
echo "[完成] SFT 训练完成"
echo "=========================================="
echo "[模型输出] ${SFT_OUTPUT}"
echo ""
