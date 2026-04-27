#!/usr/bin/env bash
set -euo pipefail

################################################################################
# 简化版 GRPO 模型验证脚本 - 通过 Unsloth Docker 自动验证训练产出模型
################################################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

IMAGE_NAME="qwen3-tsc-grpo:latest"
CONTAINER_NAME="grpo-simple-validate"
CONTAINER_WORKDIR="/home/samuel/SCU_TSC"
DEFAULT_CONFIG="config/config_8b.json"
DEFAULT_MODEL_DIR="${PROJECT_DIR}/outputs/grpo_simple/qwen3-8b/model"
DEFAULT_OUTPUT="outputs/grpo_simple/qwen3-8b/validation_result.json"

show_help() {
    cat <<'EOF'
用法:
  bash docker/grpo_simple_validate.sh [num_samples]
  bash docker/grpo_simple_validate.sh [options]

选项:
  --num-samples N              测试样本数
  --config PATH                验证配置文件路径，默认 config/config_8b.json
  --output PATH                summary JSON 输出路径
  --sample-manifest-out PATH   sample manifest 输出路径
  --details-output PATH        detail JSON/JSONL 输出路径
  --failure-examples-out PATH  failure examples 输出路径
  --seed N                     随机种子
  --sample-mode MODE           抽样模式
  --help                       显示帮助

说明:
  - 保持兼容: 只传一个数字参数时，视为 num_samples
  - 其余参数会原样透传给 python -m src.grpo_simple.validate
EOF
}

NUM_SAMPLES="100"
CONFIG_PATH="${DEFAULT_CONFIG}"
OUTPUT_PATH="${DEFAULT_OUTPUT}"
PY_ARGS=()
POSITIONAL_NUM_SAMPLES_SET="false"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --help|-h)
            show_help
            exit 0
            ;;
        --num-samples)
            NUM_SAMPLES="$2"
            PY_ARGS+=("$1" "$2")
            shift 2
            ;;
        --config)
            CONFIG_PATH="$2"
            PY_ARGS+=("$1" "$2")
            shift 2
            ;;
        --output)
            OUTPUT_PATH="$2"
            PY_ARGS+=("$1" "$2")
            shift 2
            ;;
        --sample-manifest-out|--details-output|--failure-examples-out|--seed|--sample-mode)
            PY_ARGS+=("$1" "$2")
            shift 2
            ;;
        -* )
            PY_ARGS+=("$1")
            shift
            ;;
        *)
            if [[ "${POSITIONAL_NUM_SAMPLES_SET}" == "false" ]]; then
                NUM_SAMPLES="$1"
                POSITIONAL_NUM_SAMPLES_SET="true"
            else
                PY_ARGS+=("$1")
            fi
            shift
            ;;
    esac
done

if [[ ! " ${PY_ARGS[*]} " =~ " --num-samples " ]]; then
    PY_ARGS=(--num-samples "${NUM_SAMPLES}" "${PY_ARGS[@]}")
fi
if [[ ! " ${PY_ARGS[*]} " =~ " --config " ]]; then
    PY_ARGS=(--config "${CONFIG_PATH}" "${PY_ARGS[@]}")
fi
if [[ ! " ${PY_ARGS[*]} " =~ " --output " ]]; then
    PY_ARGS=(--output "${OUTPUT_PATH}" "${PY_ARGS[@]}")
fi

echo "=========================================="
echo "简化版 GRPO 模型验证 (Unsloth Docker)"
echo "=========================================="
echo "[项目目录] ${PROJECT_DIR}"
echo "[Docker 镜像] ${IMAGE_NAME}"
echo "[配置文件] ${CONFIG_PATH}"
echo "[模型目录] ${DEFAULT_MODEL_DIR}"
echo "[测试样本数] ${NUM_SAMPLES}"
echo "[结果输出] ${OUTPUT_PATH}"
echo ""

if [ ! -f "${DEFAULT_MODEL_DIR}/config.json" ]; then
    echo "[错误] 模型不存在: ${DEFAULT_MODEL_DIR}"
    echo "请先完成 GRPO 训练"
    exit 1
fi

if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    docker rm -f "${CONTAINER_NAME}" 2>/dev/null || true
fi

echo "[开始] 模型验证..."
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
    -m src.grpo_simple.validate \
    "${PY_ARGS[@]}"

echo ""
echo "=========================================="
echo "[完成] 验证结果: ${OUTPUT_PATH}"
echo "=========================================="
