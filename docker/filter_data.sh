#!/usr/bin/env bash
set -euo pipefail

################################################################################
# GRPO 数据过滤 + Baseline 重算 - 通过 Docker 容器执行
#
# 功能:
#   1. 过滤数据: 从 grpo_train.jsonl 中剔除空交叉口和极低流量样本
#   2. Baseline 重算: 在过滤后的数据上重新计算 baseline.json
#
# 输出:
#   - outputs/grpo/grpo_train_filtered.jsonl (保留样本)
#   - outputs/grpo/grpo_train_rejected.jsonl (剔除样本)
#   - outputs/grpo/grpo_train_filter_report.txt (统计报告)
#   - outputs/grpo/baseline.json (过滤后数据的 baseline)
#
# 用法:
#   ./docker/filter_data.sh                           # 使用默认配置
#   ./docker/filter_data.sh --threshold 0.2           # 覆盖阈值
#   ./docker/filter_data.sh --skip-baseline            # 跳过 baseline 重算
#
# 注意: 使用 chmod +x docker/filter_data.sh 设置可执行权限
################################################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

IMAGE_NAME="qwen3-tsc-grpo:latest"
CONTAINER_WORKDIR="/home/samuel/SCU_TSC"

echo "=========================================="
echo "GRPO 数据过滤 + Baseline 重算 (Docker)"
echo "=========================================="
echo "[项目目录] ${PROJECT_DIR}"
echo "[Docker 镜像] ${IMAGE_NAME}"
echo ""

# 解析参数 - 检查是否有 --skip-baseline 标志
SKIP_BASELINE=false
FILTER_ARGS=()

for arg in "$@"; do
    if [ "$arg" == "--skip-baseline" ]; then
        SKIP_BASELINE=true
    else
        FILTER_ARGS+=("$arg")
    fi
done

# 创建输出目录（宿主机侧）
mkdir -p "${PROJECT_DIR}/outputs/grpo"

# ============================================================
# 步骤 1: 数据过滤
# ============================================================
CONTAINER_NAME_FILTER="grpo-filter"

echo "[步骤 1/2] 数据过滤..."
echo "[容器名] ${CONTAINER_NAME_FILTER}"

# 清理可能残留的同名容器
if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME_FILTER}$"; then
    echo "[清理] 移除已存在的容器: ${CONTAINER_NAME_FILTER}"
    docker rm -f "${CONTAINER_NAME_FILTER}" 2>/dev/null || true
fi

docker run --rm \
    --name "${CONTAINER_NAME_FILTER}" \
    --gpus all \
    --shm-size=32GB \
    --user "$(id -u):$(id -g)" \
    -v "${PROJECT_DIR}:${CONTAINER_WORKDIR}:rw" \
    -w "${CONTAINER_WORKDIR}" \
    -e SUMO_HOME=/usr/share/sumo \
    --entrypoint python3 \
    "${IMAGE_NAME}" \
    -m src.scripts.filter_grpo_data \
        --config config/config.json \
        "${FILTER_ARGS[@]}"

echo ""
echo "[完成] 数据过滤完成"
echo ""

# ============================================================
# 步骤 2: Baseline 重算（可选）
# ============================================================
if [ "$SKIP_BASELINE" = true ]; then
    echo "[跳过] Baseline 重算已跳过 (--skip-baseline)"
    echo ""
else
    CONTAINER_NAME_BASELINE="grpo-baseline-filtered"

    echo "[步骤 2/2] Baseline 重算 (使用过滤后数据)..."
    echo "[容器名] ${CONTAINER_NAME_BASELINE}"

    # 清理可能残留的同名容器
    if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME_BASELINE}$"; then
        echo "[清理] 移除已存在的容器: ${CONTAINER_NAME_BASELINE}"
        docker rm -f "${CONTAINER_NAME_BASELINE}" 2>/dev/null || true
    fi

    # 使用过滤后的数据重新计算 baseline
    docker run --rm \
        --name "${CONTAINER_NAME_BASELINE}" \
        --gpus all \
        --shm-size=32GB \
        --user "$(id -u):$(id -g)" \
        -v "${PROJECT_DIR}:${CONTAINER_WORKDIR}:rw" \
        -w "${CONTAINER_WORKDIR}" \
        -e SUMO_HOME=/usr/share/sumo \
        --entrypoint python3 \
        "${IMAGE_NAME}" \
        -m src.grpo.baseline \
            --config config/config.json \
            --input outputs/grpo/grpo_train_filtered.jsonl \
            --output outputs/grpo/baseline.json \
            --workers 16

    echo ""
    echo "[完成] Baseline 重算完成"
    echo ""
fi

echo "=========================================="
echo "[完成] 数据过滤 + Baseline 重算完成"
echo "=========================================="
echo "[输出文件]"
echo "  - 保留样本: outputs/grpo/grpo_train_filtered.jsonl"
echo "  - 剔除样本: outputs/grpo/grpo_train_rejected.jsonl"
echo "  - 统计报告: outputs/grpo/grpo_train_filter_report.txt"
if [ "$SKIP_BASELINE" = false ]; then
    echo "  - Baseline: outputs/grpo/baseline.json (基于过滤后数据)"
fi
echo ""
