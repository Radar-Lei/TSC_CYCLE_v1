#!/usr/bin/env bash
set -euo pipefail

################################################################################
# GRPO 交通信号周期优化 - 一键运行完整训练流程
#
# 完整流程: 数据生成 -> SFT 训练 -> GRPO 训练
#
# 用法:
#   ./docker/publish.sh [OPTIONS]
#
# 选项:
#   --skip-data      跳过数据生成阶段
#   --skip-sft       跳过 SFT 训练阶段
#   --skip-grpo      跳过 GRPO 训练阶段
#   --force          强制重新运行所有阶段(清除检查点)
#   --help           显示帮助信息
#
# 配置:
#   config/config.json - 训练参数配置文件
################################################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 默认选项
SKIP_DATA=0
SKIP_SFT=0
SKIP_GRPO=0
FORCE_ALL=0

# 解析命令行参数
parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --skip-data)
                SKIP_DATA=1
                shift
                ;;
            --skip-sft)
                SKIP_SFT=1
                shift
                ;;
            --skip-grpo)
                SKIP_GRPO=1
                shift
                ;;
            --force)
                FORCE_ALL=1
                shift
                ;;
            --help)
                echo "用法: $0 [OPTIONS]"
                echo ""
                echo "选项:"
                echo "  --skip-data      跳过数据生成阶段"
                echo "  --skip-sft       跳过 SFT 训练阶段"
                echo "  --skip-grpo      跳过 GRPO 训练阶段"
                echo "  --force          强制重新运行所有阶段"
                echo "  --help           显示此帮助信息"
                exit 0
                ;;
            *)
                echo -e "${RED}[ERROR] 未知参数: $1${NC}" >&2
                echo "使用 --help 查看用法" >&2
                exit 1
                ;;
        esac
    done
}

# 加载函数库
source "${SCRIPT_DIR}/lib/checkpoint.sh"
source "${SCRIPT_DIR}/lib/logging.sh"
source "${SCRIPT_DIR}/lib/summary.sh"

# 依赖检查
check_dependencies() {
    local errors=0

    echo -e "${BLUE}[检查]${NC} 正在检查系统依赖..."

    # 检查 GPU
    if ! command -v nvidia-smi &>/dev/null; then
        echo -e "${RED}[ERROR] nvidia-smi 未找到 (GPU 不可用)${NC}" >&2
        ((errors++))
    else
        if ! nvidia-smi &>/dev/null; then
            echo -e "${RED}[ERROR] nvidia-smi 失败 (驱动问题)${NC}" >&2
            ((errors++))
        else
            local gpu_count
            gpu_count=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | wc -l)
            echo -e "${GREEN}✓ CUDA 可用 ($gpu_count GPUs)${NC}"
        fi
    fi

    # 检查 SUMO
    if [[ -z "${SUMO_HOME:-}" ]]; then
        echo -e "${RED}[ERROR] SUMO_HOME 未设置${NC}" >&2
        ((errors++))
    elif [[ ! -d "$SUMO_HOME" ]]; then
        echo -e "${RED}[ERROR] SUMO_HOME 目录不存在: $SUMO_HOME${NC}" >&2
        ((errors++))
    elif ! command -v sumo &>/dev/null; then
        echo -e "${RED}[ERROR] sumo 命令未找到 (检查 PATH)${NC}" >&2
        ((errors++))
    else
        echo -e "${GREEN}✓ SUMO 可用 (SUMO_HOME=$SUMO_HOME)${NC}"
    fi

    # 检查磁盘空间 (至少 10GB)
    local available_gb
    available_gb=$(df --output=avail -BG "${PROJECT_DIR}" 2>/dev/null | tail -1 | tr -d 'G' | xargs)
    if [[ $available_gb -lt 10 ]]; then
        echo -e "${RED}[ERROR] 磁盘空间不足: ${available_gb}GB (需要 10GB)${NC}" >&2
        ((errors++))
    else
        echo -e "${GREEN}✓ 磁盘空间: ${available_gb}GB 可用${NC}"
    fi

    # 检查 Python 包
    local required_packages=("torch" "transformers" "unsloth" "trl")
    local missing_count=0
    for pkg in "${required_packages[@]}"; do
        if ! python3 -c "import $pkg" 2>/dev/null; then
            echo -e "${RED}✗ Python 包缺失: $pkg${NC}" >&2
            ((missing_count++))
        fi
    done

    if [[ $missing_count -eq 0 ]]; then
        echo -e "${GREEN}✓ 所有 Python 包可用${NC}"
    else
        ((errors++))
    fi

    if [[ $errors -gt 0 ]]; then
        echo ""
        echo -e "${RED}依赖检查失败 ($errors 个错误)${NC}" >&2
        return 1
    fi

    echo -e "${GREEN}✓ 所有依赖检查通过${NC}"
    return 0
}

# 加载 JSON 配置
load_json_config() {
    local config_file="${PROJECT_DIR}/config/config.json"

    if [[ ! -f "$config_file" ]]; then
        echo -e "${YELLOW}[WARNING] 配置文件不存在: $config_file${NC}" >&2
        echo -e "${YELLOW}[WARNING] 使用默认配置${NC}" >&2
        return
    fi

    # 使用 jq 读取配置 (如果可用)
    if command -v jq &>/dev/null; then
        echo -e "${BLUE}[配置]${NC} 从 config.json 读取配置"

        # 读取关键配置 (使用 // 提供默认值)
        export PARALLEL_WORKERS=$(jq -r '.simulation.parallel_workers // 4' "$config_file")
        export WARMUP_STEPS=$(jq -r '.simulation.warmup_steps // 300' "$config_file")
        export DATA_DIR=$(jq -r '.paths.data_dir // "data/training"' "$config_file")
        export SFT_OUTPUT=$(jq -r '.paths.sft_output // "outputs/sft"' "$config_file")
        export GRPO_OUTPUT=$(jq -r '.paths.grpo_output // "outputs/grpo"' "$config_file")
        # 读取 time_ranges (JSON 数组转换为字符串)
        export TIME_RANGES=$(jq -c '.simulation.time_ranges // []' "$config_file")
    else
        echo -e "${YELLOW}[WARNING] jq 未安装,使用默认配置${NC}" >&2
        export PARALLEL_WORKERS=4
        export WARMUP_STEPS=300
        export DATA_DIR="data/training"
        export SFT_OUTPUT="outputs/sft"
        export GRPO_OUTPUT="outputs/grpo"
        export TIME_RANGES="[]"
    fi
}

# 数据生成阶段
stage_data_generation() {
    local stage_name="data"

    # 检查 --skip-data 参数
    if [[ $SKIP_DATA -eq 1 ]]; then
        echo -e "${YELLOW}[SKIP] 用户指定跳过数据生成阶段${NC}"
        return 0
    fi

    # 智能检测已完成
    if check_stage_completed "$stage_name"; then
        echo -e "${YELLOW}[SKIP] 数据生成已完成,跳过此阶段${NC}"
        show_stage_summary "$stage_name"
        return 0
    fi

    echo -e "${BLUE}[阶段 1/3]${NC} 数据生成"
    log_stage_start "$stage_name"

    # 写入开始检查点
    write_checkpoint "$stage_name" "running"

    # 执行数据生成
    if run_with_logging "$stage_name" \
        python3 -m src.scripts.generate_training_data \
            --workers "$PARALLEL_WORKERS" \
            --warmup-steps "$WARMUP_STEPS" \
            --output-dir "outputs/data" \
            --time-ranges "$TIME_RANGES"
    then
        # 成功
        write_checkpoint "$stage_name" "success"
        log_stage_end "$stage_name" 0
        show_stage_summary "$stage_name"
        return 0
    else
        # 失败
        local exit_code=$?
        write_checkpoint "$stage_name" "failed"
        log_stage_end "$stage_name" $exit_code
        log_error "数据生成失败,退出码: $exit_code"
        return 1
    fi
}

# SFT 训练阶段
stage_sft_training() {
    local stage_name="sft"

    # 检查 --skip-sft 参数
    if [[ $SKIP_SFT -eq 1 ]]; then
        echo -e "${YELLOW}[SKIP] 用户指定跳过 SFT 训练阶段${NC}"
        return 0
    fi

    # 智能检测已完成
    if check_stage_completed "$stage_name"; then
        echo -e "${YELLOW}[SKIP] SFT 训练已完成,跳过此阶段${NC}"
        show_stage_summary "$stage_name"
        return 0
    fi

    echo -e "${BLUE}[阶段 2/3]${NC} SFT 训练"
    log_stage_start "$stage_name"

    # 写入开始检查点
    write_checkpoint "$stage_name" "running"

    # 执行 SFT 训练
    if run_with_logging "$stage_name" \
        python3 -m src.scripts.train_sft \
            --config config/config.json \
            --output-dir "$SFT_OUTPUT"
    then
        # 成功
        write_checkpoint "$stage_name" "success"
        log_stage_end "$stage_name" 0
        show_stage_summary "$stage_name"
        return 0
    else
        # 失败
        local exit_code=$?
        write_checkpoint "$stage_name" "failed"
        log_stage_end "$stage_name" $exit_code
        log_error "SFT 训练失败,退出码: $exit_code"
        return 1
    fi
}

# GRPO 训练阶段
stage_grpo_training() {
    local stage_name="grpo"

    # 检查 --skip-grpo 参数
    if [[ $SKIP_GRPO -eq 1 ]]; then
        echo -e "${YELLOW}[SKIP] 用户指定跳过 GRPO 训练阶段${NC}"
        return 0
    fi

    # 智能检测已完成
    if check_stage_completed "$stage_name"; then
        echo -e "${YELLOW}[SKIP] GRPO 训练已完成,跳过此阶段${NC}"
        show_stage_summary "$stage_name"
        return 0
    fi

    echo -e "${BLUE}[阶段 3/3]${NC} GRPO 训练"
    log_stage_start "$stage_name"

    # 写入开始检查点
    write_checkpoint "$stage_name" "running"

    # 执行 GRPO 训练
    if run_with_logging "$stage_name" \
        python3 -m src.scripts.train_grpo \
            --config config/config.json \
            --output-dir "$GRPO_OUTPUT"
    then
        # 成功
        write_checkpoint "$stage_name" "success"
        log_stage_end "$stage_name" 0
        show_stage_summary "$stage_name"
        return 0
    else
        # 失败
        local exit_code=$?
        write_checkpoint "$stage_name" "failed"
        log_stage_end "$stage_name" $exit_code
        log_error "GRPO 训练失败,退出码: $exit_code"
        return 1
    fi
}

# 主流程
main() {
    local start_time
    start_time=$(date +%s)

    # 解析参数
    parse_args "$@"

    # 初始化日志系统
    init_logging

    # 显示配置
    echo ""
    echo -e "${BLUE}==========================================${NC}"
    echo -e "${GREEN}GRPO 交通信号周期优化 - 完整训练流程${NC}"
    echo -e "${BLUE}==========================================${NC}"
    echo -e "${BLUE}[项目目录]${NC} ${PROJECT_DIR}"
    echo -e "${BLUE}[并行数]${NC} ${PARALLEL_WORKERS:-auto}"
    echo -e "${BLUE}[预热步数]${NC} ${WARMUP_STEPS:-auto}"
    echo -e "${BLUE}[数据目录]${NC} ${DATA_DIR:-default}"
    echo -e "${BLUE}[SFT 输出]${NC} ${SFT_OUTPUT:-default}"
    echo -e "${BLUE}[GRPO 输出]${NC} ${GRPO_OUTPUT:-default}"
    echo -e "${BLUE}==========================================${NC}"
    echo ""

    # 强制模式: 清除检查点
    if [[ $FORCE_ALL -eq 1 ]]; then
        echo -e "${YELLOW}[FORCE] 强制重新运行,清除所有检查点${NC}"
        clear_checkpoint "data"
        clear_checkpoint "sft"
        clear_checkpoint "grpo"
        echo ""
    fi

    # 依赖检查
    if ! check_dependencies; then
        echo -e "${RED}[ERROR] 依赖检查失败,终止执行${NC}" >&2
        exit 1
    fi
    echo ""

    # 加载配置
    load_json_config
    echo ""

    # 执行三个阶段
    log_info "开始训练流程"

    stage_data_generation || exit 1
    stage_sft_training || exit 1
    stage_grpo_training || exit 1

    # 计算总时长
    local end_time
    end_time=$(date +%s)
    local total_duration=$((end_time - start_time))

    # 显示最终摘要
    show_final_summary $total_duration

    echo -e "${GREEN}✓ 训练流程完成!${NC}"
    echo ""
}

# 执行主流程
main "$@"
