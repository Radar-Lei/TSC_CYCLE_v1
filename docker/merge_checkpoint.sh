#!/usr/bin/env bash
set -euo pipefail

################################################################################
# GRPO Checkpoint 合并脚本 - 在 Docker 容器内合并 LoRA adapter 到基础模型
#
# 功能: 找到最新的 GRPO checkpoint，与 SFT 基础模型合并，输出完整模型
#
# 输入: outputs/grpo/checkpoints/checkpoint-XXXX/ (LoRA adapter)
#       outputs/sft/model/ (SFT 基础模型)
# 输出: outputs/grpo/model/ (合并后的完整模型)
#
# 用法:
#   ./docker/merge_checkpoint.sh                    # 合并最新 checkpoint
#   ./docker/merge_checkpoint.sh --checkpoint checkpoint-5000  # 指定 checkpoint
#   ./docker/merge_checkpoint.sh --output outputs/grpo/model_v2  # 指定输出目录
#
# 后续: 合并后可运行 ./docker/convert_gguf.sh 转换为 GGUF 格式
#
# 注意: 使用 chmod +x docker/merge_checkpoint.sh 设置可执行权限
################################################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

IMAGE_NAME="qwen3-tsc-grpo:latest"
CONTAINER_NAME="merge-checkpoint"
CONTAINER_WORKDIR="/home/samuel/SCU_TSC"

# 默认参数
CHECKPOINT=""
OUTPUT_DIR=""
BASE_MODEL=""

# 解析命令行参数
while [[ $# -gt 0 ]]; do
    case "$1" in
        --checkpoint)
            CHECKPOINT="$2"
            shift 2
            ;;
        --output)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        --base-model)
            BASE_MODEL="$2"
            shift 2
            ;;
        --help|-h)
            echo "用法: $0 [选项]"
            echo ""
            echo "选项:"
            echo "  --checkpoint NAME   指定 checkpoint 名称 (如 checkpoint-5000)"
            echo "  --output DIR        指定输出目录"
            echo "  --base-model DIR    指定基础模型路径"
            echo "  --help, -h          显示此帮助信息"
            echo ""
            echo "默认行为:"
            echo "  - 自动选择最新的 checkpoint"
            echo "  - 输出到 outputs/grpo/model/"
            echo "  - 使用 outputs/sft/model/ 作为基础模型"
            exit 0
            ;;
        *)
            echo "[错误] 未知参数: $1"
            echo "运行 '$0 --help' 查看帮助"
            exit 1
            ;;
    esac
done

echo "=========================================="
echo "GRPO Checkpoint 合并 (Docker)"
echo "=========================================="
echo "[项目目录] ${PROJECT_DIR}"
echo "[Docker 镜像] ${IMAGE_NAME}"
echo ""

# 清理可能残留的同名容器
if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "[清理] 移除已存在的容器: ${CONTAINER_NAME}"
    docker rm -f "${CONTAINER_NAME}" 2>/dev/null || true
fi

# 检查 SFT 基础模型
SFT_MODEL="${PROJECT_DIR}/outputs/sft/model"
if [ ! -f "${SFT_MODEL}/config.json" ]; then
    echo "[错误] SFT 基础模型不存在: outputs/sft/model"
    echo "请先运行 ./docker/sft_train.sh 完成 SFT 训练"
    exit 1
fi
echo "[检查] SFT 基础模型: 存在"

# 检查 checkpoints 目录
CHECKPOINTS_DIR="${PROJECT_DIR}/outputs/grpo/checkpoints"
if [ ! -d "${CHECKPOINTS_DIR}" ]; then
    echo "[错误] Checkpoints 目录不存在: outputs/grpo/checkpoints"
    echo "请先运行 ./docker/grpo_train.sh 进行 GRPO 训练"
    exit 1
fi

# 列出可用的 checkpoints
echo ""
echo "[可用 Checkpoints]"
ls -1 "${CHECKPOINTS_DIR}" | grep -E '^checkpoint-[0-9]+$' | sort -V | while read ckpt; do
    adapter="${CHECKPOINTS_DIR}/${ckpt}/adapter_model.safetensors"
    if [ -f "$adapter" ]; then
        size_mb=$(du -m "$adapter" | cut -f1)
        echo "  - ${ckpt} (${size_mb} MB adapter)"
    fi
done
echo ""

# 构建命令参数
CMD_ARGS=""
if [ -n "$CHECKPOINT" ]; then
    CMD_ARGS="--checkpoint ${CHECKPOINT}"
    echo "[指定] Checkpoint: ${CHECKPOINT}"
else
    echo "[自动] 将选择最新 checkpoint"
fi

if [ -n "$OUTPUT_DIR" ]; then
    CMD_ARGS="${CMD_ARGS} --output ${OUTPUT_DIR}"
    echo "[指定] 输出目录: ${OUTPUT_DIR}"
fi

if [ -n "$BASE_MODEL" ]; then
    CMD_ARGS="${CMD_ARGS} --base-model ${BASE_MODEL}"
    echo "[指定] 基础模型: ${BASE_MODEL}"
fi

echo ""
echo "[开始] 在 Docker 容器中合并模型..."
echo ""

# 创建输出目录（宿主机侧）
mkdir -p "${PROJECT_DIR}/outputs/grpo/model"

# 在 Docker 容器内执行合并
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
    -m src.scripts.merge_checkpoint \
        --config config/config.json \
        ${CMD_ARGS}

echo ""
echo "=========================================="
echo "[完成] Checkpoint 合并完成"
echo "=========================================="
echo "[模型输出] outputs/grpo/model"
echo ""
echo "下一步: 运行以下命令转换为 GGUF 格式"
echo "  ./docker/convert_gguf.sh --model-path outputs/grpo/model"
echo ""
