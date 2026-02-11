#!/usr/bin/env bash
set -euo pipefail

################################################################################
# GRPO 训练脚本 - 通过 Docker 容器执行 GRPO 强化学习训练
#
# 前置条件:
#   - outputs/sft/model/ 存在 (SFT 训练后的模型)
#   - outputs/grpo/grpo_train.jsonl 存在 (GRPO 训练数据)
#   - outputs/grpo/baseline.json 存在 (基准仿真结果)
#
# 输出: outputs/grpo/model/* (GRPO 训练后的完整模型)
#       outputs/grpo/checkpoints/* (训练过程中的检查点)
#
# 用法:
#   ./docker/grpo_train.sh
#   ./docker/grpo_train.sh --config custom.json
#   ./docker/grpo_train.sh --skip-validate  # 跳过 reward 验证
################################################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

IMAGE_NAME="qwen3-tsc-grpo:latest"
CONTAINER_NAME="grpo-train"
CONTAINER_WORKDIR="/home/samuel/SCU_TSC"

# 解析参数
SKIP_VALIDATE=false
TRAIN_ARGS=()
for arg in "$@"; do
    if [ "$arg" = "--skip-validate" ]; then
        SKIP_VALIDATE=true
    else
        TRAIN_ARGS+=("$arg")
    fi
done

echo "=========================================="
echo "GRPO 训练阶段 (Docker)"
echo "=========================================="
echo "[项目目录] ${PROJECT_DIR}"
echo "[Docker 镜像] ${IMAGE_NAME}"
echo ""

# 清理可能残留的同名容器
if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "[清理] 移除已存在的容器: ${CONTAINER_NAME}"
    docker rm -f "${CONTAINER_NAME}" 2>/dev/null || true
fi

# 创建输出目录
mkdir -p "${PROJECT_DIR}/outputs/grpo/model"
mkdir -p "${PROJECT_DIR}/outputs/grpo/checkpoints"

# 日志文件
LOG_FILE="${PROJECT_DIR}/outputs/grpo/train_$(date +%Y%m%d_%H%M%S).log"
echo "[训练日志] ${LOG_FILE}"

# 验证前置条件
SFT_MODEL="${PROJECT_DIR}/outputs/sft/model"
GRPO_DATA="${PROJECT_DIR}/outputs/grpo/grpo_train.jsonl"
BASELINE="${PROJECT_DIR}/outputs/grpo/baseline.json"

if [ ! -d "${SFT_MODEL}" ] || [ ! -f "${SFT_MODEL}/config.json" ]; then
    echo "[错误] SFT 模型不存在: ${SFT_MODEL}"
    echo "请先运行 ./docker/sft_train.sh"
    exit 1
fi

if [ ! -f "${GRPO_DATA}" ]; then
    echo "[错误] GRPO 训练数据不存在: ${GRPO_DATA}"
    echo "请先运行 GRPO 数据生成脚本"
    exit 1
fi

if [ ! -f "${BASELINE}" ]; then
    echo "[错误] 基准仿真结果不存在: ${BASELINE}"
    echo "请先运行 ./docker/grpo_baseline.sh"
    exit 1
fi

echo "[前置检查] SFT 模型: 存在"
echo "[前置检查] GRPO 数据: $(wc -l < "${GRPO_DATA}") 条记录"
echo "[前置检查] 基准结果: 存在"
echo ""

# Reward 分布验证
if [ "$SKIP_VALIDATE" = "false" ]; then
    echo ""
    echo "[验证] 运行 reward 分布验证..."
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
        -m src.grpo.test_rewards \
            --sumo-validate \
            --sample-size 50

    VALIDATE_EXIT=$?
    if [ ${VALIDATE_EXIT} -ne 0 ]; then
        echo ""
        echo "[错误] Reward 分布验证未通过！"
        echo "请检查 reward 公式和 baseline 配置。"
        echo "如需跳过验证，使用 --skip-validate 参数。"
        exit 1
    fi
    echo "[验证] Reward 分布验证通过"
    echo ""
else
    echo ""
    echo "[跳过] Reward 分布验证（--skip-validate）"
    echo ""
fi

# 通过 Docker 容器执行 GRPO 训练
echo "[开始] GRPO 训练..."
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
    -m src.grpo.train \
        --config config/config.json \
        "${TRAIN_ARGS[@]}" 2>&1 | tee -a "${LOG_FILE}"

echo ""
echo "=========================================="
echo "[完成] GRPO 训练完成"
echo "=========================================="
echo "[模型输出] outputs/grpo/model"
echo "[检查点目录] outputs/grpo/checkpoints"
echo ""
