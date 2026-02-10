#!/usr/bin/env bash
set -euo pipefail

################################################################################
# GGUF 转换脚本 - 在 Docker 容器内将 SFT 模型转换为 GGUF 格式
#
# 输入: outputs/sft/model/* (safetensors 格式的完整模型)
# 输出: outputs/sft/model/model.gguf (GGUF 格式模型)
#
# 用法:
#   ./docker/convert_gguf.sh                    # 默认 f16 精度
#   ./docker/convert_gguf.sh --outtype q8_0     # 指定量化类型
#   ./docker/convert_gguf.sh --outtype f32      # 全精度
#
# 支持的 outtype: f32, f16, bf16, q8_0, auto
# 注意: 使用 chmod +x docker/convert_gguf.sh 设置可执行权限
################################################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

IMAGE_NAME="qwen3-tsc-grpo:latest"
CONTAINER_WORKDIR="/home/samuel/SCU_TSC"

# 默认参数
OUTTYPE="f16"

# 解析命令行参数
while [[ $# -gt 0 ]]; do
    case "$1" in
        --outtype)
            OUTTYPE="$2"
            shift 2
            ;;
        *)
            echo "[错误] 未知参数: $1"
            echo "用法: $0 [--outtype f32|f16|bf16|q8_0|auto]"
            exit 1
            ;;
    esac
done

MODEL_DIR="${PROJECT_DIR}/outputs/sft/model"
OUTPUT_FILE="${MODEL_DIR}/model-${OUTTYPE}.gguf"

echo "=========================================="
echo "GGUF 格式转换 (Docker)"
echo "=========================================="
echo "[项目目录] ${PROJECT_DIR}"
echo "[Docker 镜像] ${IMAGE_NAME}"
echo "[模型目录] outputs/sft/model"
echo "[输出文件] outputs/sft/model/model-${OUTTYPE}.gguf"
echo "[输出精度] ${OUTTYPE}"
echo ""

# 检查模型文件是否存在
if [ ! -f "${MODEL_DIR}/config.json" ]; then
    echo "[错误] 模型目录 outputs/sft/model 中未找到 config.json"
    echo "请先运行 sft_train.sh 完成训练"
    exit 1
fi

SAFETENSOR_COUNT=$(find "${MODEL_DIR}" -name "*.safetensors" | wc -l)
if [ "${SAFETENSOR_COUNT}" -eq 0 ]; then
    echo "[错误] 模型目录中未找到 .safetensors 文件"
    exit 1
fi
echo "[模型] 发现 ${SAFETENSOR_COUNT} 个 safetensors 文件"

# 如果输出文件已存在，提示用户
if [ -f "${OUTPUT_FILE}" ]; then
    echo "[警告] 输出文件已存在: model-${OUTTYPE}.gguf"
    read -rp "是否覆盖? (y/N): " CONFIRM
    if [[ ! "${CONFIRM}" =~ ^[Yy]$ ]]; then
        echo "[取消] 用户取消操作"
        exit 0
    fi
fi

echo ""
echo "[步骤 1/3] 在容器内安装 llama-cpp-python (含转换工具)..."

# 在 Docker 容器内执行转换
# 1. 克隆 llama.cpp 并使用其 convert_hf_to_gguf.py 脚本
# 2. 转换模型为 GGUF 格式
docker run --rm \
    --gpus all \
    --shm-size=32GB \
    --user "$(id -u):$(id -g)" \
    -v "${PROJECT_DIR}:${CONTAINER_WORKDIR}:rw" \
    -w "${CONTAINER_WORKDIR}" \
    -e HF_HOME="${CONTAINER_WORKDIR}/.cache/huggingface" \
    --entrypoint bash \
    "${IMAGE_NAME}" \
    -c "
set -euo pipefail

MODEL_PATH='${CONTAINER_WORKDIR}/outputs/sft/model'
OUTPUT_PATH='${CONTAINER_WORKDIR}/outputs/sft/model/model-${OUTTYPE}.gguf'
LLAMA_CPP_DIR='/tmp/llama.cpp'

echo '[步骤 2/3] 克隆 llama.cpp 转换工具...'

# 只克隆必要的文件（shallow clone）
if [ ! -d \"\${LLAMA_CPP_DIR}\" ]; then
    git clone --depth 1 https://github.com/ggml-org/llama.cpp.git \"\${LLAMA_CPP_DIR}\" 2>&1
fi

echo '[依赖] 安装转换脚本依赖...'
pip install -q --break-system-packages gguf numpy sentencepiece protobuf 2>&1

echo ''
echo '[步骤 3/3] 开始转换模型为 GGUF 格式...'
echo '  模型路径: '\${MODEL_PATH}
echo '  输出路径: '\${OUTPUT_PATH}
echo '  输出精度: ${OUTTYPE}'
echo ''

python3 \"\${LLAMA_CPP_DIR}/convert_hf_to_gguf.py\" \\
    \"\${MODEL_PATH}\" \\
    --outfile \"\${OUTPUT_PATH}\" \\
    --outtype \"${OUTTYPE}\"

echo ''
echo '[完成] GGUF 文件大小:' \$(du -h \"\${OUTPUT_PATH}\" | cut -f1)
"

echo ""
echo "=========================================="
echo "[完成] GGUF 转换完成"
echo "=========================================="
echo "[输出文件] ${OUTPUT_FILE}"
if [ -f "${OUTPUT_FILE}" ]; then
    echo "[文件大小] $(du -h "${OUTPUT_FILE}" | cut -f1)"
fi
echo ""
