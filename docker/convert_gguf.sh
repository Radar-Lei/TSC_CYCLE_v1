#!/usr/bin/env bash
set -euo pipefail

################################################################################
# GGUF 转换脚本 - 在 Docker 容器内将模型转换为 GGUF 格式
#
# 输入: outputs/{sft,grpo}/model/* (safetensors 格式的完整模型)
# 输出: {model_dir}/model-{outtype}.gguf (GGUF 格式模型)
#
# 用法:
#   ./docker/convert_gguf.sh                         # SFT 模型，f16 精度
#   ./docker/convert_gguf.sh --model-path outputs/grpo/model  # GRPO 模型
#   ./docker/convert_gguf.sh --outtype q8_0         # 8-bit 量化
#   ./docker/convert_gguf.sh --outtype q4_k_m       # 4-bit K-quant 中等（推荐）
#   ./docker/convert_gguf.sh --outtype f32          # 全精度
#
# 支持的 outtype:
#   - 直接转换: f32, f16, bf16, q8_0, auto
#   - 二次量化 (需要 llama-quantize):
#     Q4_0, Q4_1, Q4_K_S, Q4_K_M, Q5_0, Q5_1, Q5_K_S, Q5_K_M,
#     Q6_K, Q8_0, IQ4_NL, IQ4_XS, IQ3_M, IQ3_S, IQ3_XXS
#
# 注意: 使用 chmod +x docker/convert_gguf.sh 设置可执行权限
################################################################################

# 二次量化类型列表（需要先用 f16 转换，再用 llama-quantize 量化）
QUANT_TYPES=(
    "Q4_0" "Q4_1" "Q4_K_S" "Q4_K_M"
    "Q5_0" "Q5_1" "Q5_K_S" "Q5_K_M"
    "Q6_K" "Q8_0"
    "IQ4_NL" "IQ4_XS" "IQ3_M" "IQ3_S" "IQ3_XXS"
)

# 检查是否为二次量化类型
is_quant_type() {
    local check_type="$1"
    for t in "${QUANT_TYPES[@]}"; do
        if [[ "$t" == "$check_type" ]]; then
            return 0
        fi
    done
    return 1
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

IMAGE_NAME="qwen3-tsc-grpo:latest"
CONTAINER_NAME="convert-gguf"
CONTAINER_WORKDIR="/home/samuel/SCU_TSC"

# 默认参数
OUTTYPE="f16"
OUTTYPE_NORM="F16"
MODEL_PATH=""

# 解析命令行参数
while [[ $# -gt 0 ]]; do
    case "$1" in
        --outtype)
            OUTTYPE="$2"
            shift 2
            ;;
        --model-path)
            MODEL_PATH="$2"
            shift 2
            ;;
        --help|-h)
            echo "用法: $0 [选项]"
            echo ""
            echo "选项:"
            echo "  --model-path DIR    模型目录路径 (默认: outputs/grpo/model)"
            echo "  --outtype TYPE      输出精度 (默认: f16)"
            echo "  --help, -h          显示此帮助信息"
            echo ""
            echo "直接转换类型 (convert_hf_to_gguf.py 支持):"
            echo "  f32, f16, bf16, q8_0, auto"
            echo ""
            echo "二次量化类型 (使用 llama-quantize，推荐 Q4_K_M):"
            echo "  Q4_0, Q4_1, Q4_K_S, Q4_K_M  (4-bit 系列)"
            echo "  Q5_0, Q5_1, Q5_K_S, Q5_K_M  (5-bit 系列)"
            echo "  Q6_K, Q8_0                  (6-bit, 8-bit)"
            echo "  IQ4_NL, IQ4_XS, IQ3_M, IQ3_S, IQ3_XXS  (importance 量化)"
            echo ""
            echo "示例:"
            echo "  $0                                    # SFT 模型，f16 精度"
            echo "  $0 --model-path outputs/grpo/model    # GRPO 模型"
            echo "  $0 --outtype q8_0                     # 8-bit 量化"
            echo "  $0 --outtype Q4_K_M                   # 4-bit K-quant（推荐）"
            echo "  $0 --outtype Q5_K_M                   # 5-bit K-quant（更高质量）"
            exit 0
            ;;
        *)
            echo "[错误] 未知参数: $1"
            echo "用法: $0 [--model-path DIR] [--outtype TYPE]"
            echo "运行 '$0 --help' 查看支持的类型"
            exit 1
            ;;
    esac
done

# 设置模型目录
if [ -z "$MODEL_PATH" ]; then
    MODEL_PATH="outputs/grpo/model"
fi

# 转换为绝对路径
if [[ "$MODEL_PATH" != /* ]]; then
    MODEL_DIR="${PROJECT_DIR}/${MODEL_PATH}"
else
    MODEL_DIR="$MODEL_PATH"
fi

# 标准化 outtype（用于量化类型判断与 llama-quantize 参数）
OUTTYPE_NORM="$(printf '%s' "$OUTTYPE" | tr '[:lower:]' '[:upper:]')"

# 获取相对路径用于显示
MODEL_REL_PATH="${MODEL_DIR#${PROJECT_DIR}/}"
OUTPUT_FILE="${MODEL_DIR}/model-${OUTTYPE}.gguf"

# 判断是否需要二次量化
NEEDS_QUANT=false
if is_quant_type "$OUTTYPE_NORM"; then
    NEEDS_QUANT=true
    INTERMEDIATE_FILE="${MODEL_DIR}/model-f16.gguf"
fi

echo "=========================================="
echo "GGUF 格式转换 (Docker)"
echo "=========================================="
echo "[项目目录] ${PROJECT_DIR}"
echo "[Docker 镜像] ${IMAGE_NAME}"
echo "[模型目录] ${MODEL_REL_PATH}"
echo "[输出文件] ${MODEL_REL_PATH}/model-${OUTTYPE}.gguf"
echo "[输出精度] ${OUTTYPE}"
if [ "$NEEDS_QUANT" = true ]; then
    echo "[量化模式] 二次量化 (f16 -> ${OUTTYPE})"
fi
echo ""

# 清理可能残留的同名容器
if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "[清理] 移除已存在的容器: ${CONTAINER_NAME}"
    docker rm -f "${CONTAINER_NAME}" 2>/dev/null || true
fi

# 检查模型文件是否存在
if [ ! -f "${MODEL_DIR}/config.json" ]; then
    echo "[错误] 模型目录 ${MODEL_REL_PATH} 中未找到 config.json"
    echo "请先运行训练脚本:"
    echo "  - SFT: ./docker/sft_train.sh"
    echo "  - GRPO: ./docker/merge_checkpoint.sh"
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

# 设置总步骤数
if [ "$NEEDS_QUANT" = true ]; then
    TOTAL_STEPS=4
else
    TOTAL_STEPS=3
fi

echo ""
echo "[步骤 1/${TOTAL_STEPS}] 准备在容器内转换..."

# 在 Docker 容器内执行转换
# 1. 克隆 llama.cpp 并使用其 convert_hf_to_gguf.py 脚本
# 2. 转换模型为 GGUF 格式
# 3. 如果需要二次量化，编译并运行 llama-quantize
docker run --rm \
    --name "${CONTAINER_NAME}" \
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

MODEL_PATH='${CONTAINER_WORKDIR}/${MODEL_REL_PATH}'
OUTPUT_PATH='${CONTAINER_WORKDIR}/${MODEL_REL_PATH}/model-${OUTTYPE}.gguf'
LLAMA_CPP_DIR='/tmp/llama.cpp'
NEEDS_QUANT='${NEEDS_QUANT}'
OUTTYPE='${OUTTYPE}'
OUTTYPE_NORM='${OUTTYPE_NORM}'

echo '[步骤 2/${TOTAL_STEPS}] 克隆 llama.cpp...'

# 克隆 llama.cpp（shallow clone）
if [ ! -d \"\${LLAMA_CPP_DIR}\" ]; then
    git clone --depth 1 https://github.com/ggml-org/llama.cpp.git \"\${LLAMA_CPP_DIR}\" 2>&1
fi

echo '[依赖] 安装转换脚本依赖...'
pip install -q --break-system-packages gguf numpy sentencepiece protobuf 2>&1

# 如果需要二次量化，先转换为 f16
if [ \"\${NEEDS_QUANT}\" = 'true' ]; then
    INTERMEDIATE_PATH='${CONTAINER_WORKDIR}/${MODEL_REL_PATH}/model-f16.gguf'
    echo ''
    echo '[步骤 3/${TOTAL_STEPS}] 先转换为 f16 GGUF 格式...'
    echo '  模型路径: '\${MODEL_PATH}
    echo '  中间文件: '\${INTERMEDIATE_PATH}
    echo '  输出精度: f16'
    echo ''

    python3 \"\${LLAMA_CPP_DIR}/convert_hf_to_gguf.py\" \\
        \"\${MODEL_PATH}\" \\
        --outfile \"\${INTERMEDIATE_PATH}\" \\
        --outtype f16

    echo ''
    echo '[中间文件] f16 GGUF 大小:' \$(du -h \"\${INTERMEDIATE_PATH}\" | cut -f1)

    # 编译 llama-quantize
    echo ''
    echo '[步骤 4/${TOTAL_STEPS}] 编译 llama-quantize 工具...'
    cd \"\${LLAMA_CPP_DIR}\"
    cmake -B build -DCMAKE_BUILD_TYPE=Release 2>&1 | tail -5
    cmake --build build --config Release -j\$(nproc) --target llama-quantize 2>&1 | tail -10

    # 执行量化
    echo ''
    echo '[量化] 执行二次量化: f16 -> '\${OUTTYPE_NORM}
    echo '  输入文件: '\${INTERMEDIATE_PATH}
    echo '  输出文件: '\${OUTPUT_PATH}
    echo '  量化类型: '\${OUTTYPE_NORM}
    echo ''

    \"\${LLAMA_CPP_DIR}/build/bin/llama-quantize\" \"\${INTERMEDIATE_PATH}\" \"\${OUTPUT_PATH}\" \"\${OUTTYPE_NORM}\"

    # 删除中间文件
    echo ''
    echo '[清理] 删除中间文件...'
    rm -f \"\${INTERMEDIATE_PATH}\"

else
    # 直接转换
    echo ''
    echo '[步骤 3/${TOTAL_STEPS}] 开始转换模型为 GGUF 格式...'
    echo '  模型路径: '\${MODEL_PATH}
    echo '  输出路径: '\${OUTPUT_PATH}
    echo '  输出精度: '\${OUTTYPE}
    echo ''

    python3 \"\${LLAMA_CPP_DIR}/convert_hf_to_gguf.py\" \\
        \"\${MODEL_PATH}\" \\
        --outfile \"\${OUTPUT_PATH}\" \\
        --outtype \"\${OUTTYPE}\"
fi

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
