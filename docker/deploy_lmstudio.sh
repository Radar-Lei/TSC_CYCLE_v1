#!/usr/bin/env bash
set -euo pipefail

################################################################################
# 部署 GGUF 到 LM Studio 模型目录
#
# 将训练好的 GGUF 模型符号链接到 LM Studio 模型目录，
# 以便在 LM Studio 中加载和测试。
#
# 用法:
#   ./docker/deploy_lmstudio.sh                # 部署 Q4_K_M (默认)
#   ./docker/deploy_lmstudio.sh --quantization f16  # 部署 f16
#   ./docker/deploy_lmstudio.sh --quantization Q8_0 # 部署 Q8_0
#
# 要求:
#   - GGUF 模型已生成 (运行 ./docker/convert_gguf.sh)
#   - LM Studio 模型目录存在
################################################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

# 默认参数
QUANTIZATION="Q4_K_M"
MODEL_NAME="DeepSignal_CyclePlan"

# 解析命令行参数
while [[ $# -gt 0 ]]; do
    case "$1" in
        --quantization)
            QUANTIZATION="$2"
            shift 2
            ;;
        --help|-h)
            echo "用法: $0 [选项]"
            echo ""
            echo "选项:"
            echo "  --quantization TYPE  量化类型 (默认: Q4_K_M)"
            echo "  --help, -h           显示此帮助信息"
            echo ""
            echo "示例:"
            echo "  $0                          # 部署 Q4_K_M (默认)"
            echo "  $0 --quantization f16       # 部署 f16"
            echo "  $0 --quantization Q8_0      # 部署 Q8_0"
            exit 0
            ;;
        *)
            echo "[错误] 未知参数: $1"
            echo "用法: $0 [--quantization TYPE]"
            echo "运行 '$0 --help' 查看详细帮助"
            exit 1
            ;;
    esac
done

echo "=========================================="
echo "部署 GGUF 到 LM Studio"
echo "=========================================="
echo "[项目目录] ${PROJECT_DIR}"
echo "[量化类型] ${QUANTIZATION}"
echo "[模型名称] ${MODEL_NAME}"
echo ""

# 检查源文件
SOURCE_FILE="${PROJECT_DIR}/outputs/sft/merged/model-${QUANTIZATION}.gguf"
if [ ! -f "${SOURCE_FILE}" ]; then
    echo "[错误] GGUF 文件不存在: ${SOURCE_FILE}"
    echo ""
    echo "请先运行:"
    echo "  1. ./docker/sft_train.sh               # 训练 SFT 模型"
    echo "  2. 在 Docker 内运行 merge_lora.py      # 合并 LoRA adapter"
    echo "  3. ./docker/convert_gguf.sh --model-path outputs/sft/merged --outtype ${QUANTIZATION}"
    exit 1
fi

echo "[源文件] ${SOURCE_FILE}"
echo "[文件大小] $(du -h "${SOURCE_FILE}" | cut -f1)"

# 检查 LM Studio 目录
LMSTUDIO_DIR="${HOME}/.lmstudio/models"
if [ ! -d "${LMSTUDIO_DIR}" ]; then
    echo "[错误] LM Studio 模型目录不存在: ${LMSTUDIO_DIR}"
    echo "请先安装 LM Studio"
    exit 1
fi

# 创建目标目录
TARGET_DIR="${LMSTUDIO_DIR}/DeepSignal/${MODEL_NAME}"
mkdir -p "${TARGET_DIR}"
echo "[目标目录] ${TARGET_DIR}"

# 创建符号链接
TARGET_FILE="${TARGET_DIR}/model-${QUANTIZATION}.gguf"

# 如果已存在，先删除
if [ -e "${TARGET_FILE}" ] || [ -L "${TARGET_FILE}" ]; then
    echo "[清理] 删除已存在的文件/链接: ${TARGET_FILE}"
    rm -f "${TARGET_FILE}"
fi

echo "[链接] 创建符号链接..."
ln -sf "${SOURCE_FILE}" "${TARGET_FILE}"

# 验证链接
if [ -L "${TARGET_FILE}" ] && [ -e "${TARGET_FILE}" ]; then
    echo "[成功] 符号链接已创建"
    echo ""
    echo "=========================================="
    echo "[完成] GGUF 已部署到 LM Studio"
    echo "=========================================="
    echo "[模型路径] DeepSignal/${MODEL_NAME}/model-${QUANTIZATION}.gguf"
    echo ""
    echo "下一步:"
    echo "  1. 打开 LM Studio"
    echo "  2. 在 'My Models' 中找到 DeepSignal/${MODEL_NAME}"
    echo "  3. 加载 model-${QUANTIZATION}.gguf"
    echo "  4. 测试模型:"
    echo "     - 手动在 LM Studio Chat 中测试"
    echo "     - 或运行: python src/test_lmstudio.py"
    echo ""
else
    echo "[错误] 符号链接创建失败"
    exit 1
fi
