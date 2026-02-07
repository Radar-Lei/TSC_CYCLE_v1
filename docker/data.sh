#!/usr/bin/env bash
set -euo pipefail

################################################################################
# 数据生成脚本 - 从 SUMO 仿真生成训练数据
#
# 输出: outputs/data/*.jsonl
#       outputs/states/* (仿真状态快照)
#
# 用法:
#   ./docker/data.sh
################################################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

# 切换到项目目录
cd "${PROJECT_DIR}"

# 确保 SUMO_HOME 已设置
if [[ -z "${SUMO_HOME:-}" ]]; then
    echo "[ERROR] SUMO_HOME 未设置" >&2
    exit 1
fi

echo "=========================================="
echo "数据生成阶段"
echo "=========================================="
echo "[项目目录] ${PROJECT_DIR}"
echo "[SUMO_HOME] ${SUMO_HOME}"
echo ""

# 创建输出目录
mkdir -p outputs/data outputs/states

# 调用数据生成脚本
echo "[开始] 生成训练数据..."
python3 -m src.scripts.generate_training_data \
    --config config/config.json \
    --output-dir outputs/data \
    --state-dir outputs/states

echo ""
echo "=========================================="
echo "[完成] 数据生成完成"
echo "=========================================="
echo "[输出目录] outputs/data/"
echo "[状态目录] outputs/states/"
echo ""
