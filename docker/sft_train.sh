#!/usr/bin/env bash
set -euo pipefail

################################################################################
# SFT 训练脚本 - 通过 Docker 容器执行 SFT 训练
#
# 输出: outputs/sft/model/* (训练后的完整模型)
#       outputs/sft/checkpoints/* (训练过程中的检查点)
#
# 用法:
#   ./docker/sft_train.sh                    # 使用默认配置
#   ./docker/sft_train.sh --config custom.json  # 指定配置文件
#
# 注意: 使用 chmod +x docker/sft_train.sh 设置可执行权限
################################################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

IMAGE_NAME="qwen3-tsc-grpo:latest"
CONTAINER_WORKDIR="/home/samuel/SCU_TSC"

echo "=========================================="
echo "SFT 训练阶段 (Docker)"
echo "=========================================="
echo "[项目目录] ${PROJECT_DIR}"
echo "[Docker 镜像] ${IMAGE_NAME}"
echo ""

# 创建输出目录（宿主机侧）
mkdir -p "${PROJECT_DIR}/outputs/sft/model"
mkdir -p "${PROJECT_DIR}/outputs/sft/checkpoints"

# 确保 SFT 训练数据存在
SFT_DATA="${PROJECT_DIR}/outputs/sft/sft_train.jsonl"
WORKSPACE="${PROJECT_DIR}/outputs/sft/think_workspace.jsonl"
SAMPLES="${PROJECT_DIR}/outputs/sft/sampled_100.jsonl"

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
echo ""

# 通过 Docker 容器执行 SFT 训练
echo "[开始] SFT 训练..."
docker run --rm \
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
        --config config/config.json \
        "$@"

echo ""
echo "=========================================="
echo "[完成] SFT 训练完成"
echo "=========================================="
echo "[模型输出] outputs/sft/model"
echo "[检查点目录] outputs/sft/checkpoints"
echo ""
