#!/usr/bin/env bash
set -euo pipefail

################################################################################
# Docker 构建和运行入口脚本
#
# 职责分层:
#   - run.sh: 从宿主机启动 Docker 容器(构建镜像、检查环境、运行容器)
#   - publish.sh: 容器内执行完整训练流程(数据生成 -> SFT -> GRPO)
#   - entrypoint.sh: 容器初始化(Xvfb、目录创建等)
#
# 调用链:
#   run.sh -> docker build -> docker run -> ENTRYPOINT(entrypoint.sh) -> publish.sh
#
# 用法:
#   ./docker/run.sh [OPTIONS]
#
# 选项:
#   --rebuild          强制重新构建镜像
#   --skip-data        透传给 publish.sh - 跳过数据生成
#   --skip-sft         透传给 publish.sh - 跳过 SFT 训练
#   --skip-grpo        透传给 publish.sh - 跳过 GRPO 训练
#   --force            透传给 publish.sh - 强制重新运行
#   --help             显示帮助信息
################################################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

# 镜像名称
IMAGE_NAME="qwen3-tsc-grpo:latest"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 默认选项
REBUILD=0
PUBLISH_ARGS=()

# 显示帮助信息
show_help() {
    cat << EOF
用法: $0 [OPTIONS]

从宿主机启动 Docker 容器执行完整训练流程。

选项:
  --rebuild          强制重新构建 Docker 镜像
  --skip-data        跳过数据生成阶段 (透传给 publish.sh)
  --skip-sft         跳过 SFT 训练阶段 (透传给 publish.sh)
  --skip-grpo        跳过 GRPO 训练阶段 (透传给 publish.sh)
  --force            强制重新运行所有阶段 (透传给 publish.sh)
  --help             显示此帮助信息

示例:
  $0                          # 运行完整流程
  $0 --rebuild                # 重新构建镜像后运行
  $0 --skip-data              # 跳过数据生成,只运行训练
  $0 --skip-data --skip-sft   # 只运行 GRPO 训练
  $0 --force                  # 忽略检查点,强制重新运行全部

调用链:
  run.sh -> docker build -> docker run -> entrypoint.sh -> publish.sh

详细说明请参阅: docker/README.md
EOF
    exit 0
}

# 解析命令行参数
parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --rebuild)
                REBUILD=1
                shift
                ;;
            --skip-data|--skip-sft|--skip-grpo|--force)
                PUBLISH_ARGS+=("$1")
                shift
                ;;
            --help|-h)
                show_help
                ;;
            *)
                echo -e "${RED}[ERROR] 未知参数: $1${NC}" >&2
                echo "使用 --help 查看用法" >&2
                exit 1
                ;;
        esac
    done
}

# 检查 Docker 是否安装
check_docker() {
    echo -e "${BLUE}[检查]${NC} Docker 环境..."

    # 检查 Docker 命令
    if ! command -v docker &>/dev/null; then
        echo -e "${RED}[ERROR] Docker 未安装${NC}" >&2
        echo "请安装 Docker: https://docs.docker.com/get-docker/" >&2
        exit 1
    fi
    echo -e "${GREEN}  Docker 已安装${NC}"

    # 检查 Docker daemon 是否运行
    if ! docker info &>/dev/null; then
        echo -e "${RED}[ERROR] Docker daemon 未运行${NC}" >&2
        echo "请启动 Docker: sudo systemctl start docker" >&2
        exit 1
    fi
    echo -e "${GREEN}  Docker daemon 运行中${NC}"

    # 检查 GPU 支持 (nvidia-docker 或 --gpus)
    if ! docker run --rm --gpus all nvidia/cuda:12.0.0-base-ubuntu22.04 nvidia-smi &>/dev/null 2>&1; then
        echo -e "${YELLOW}[WARNING] Docker GPU 支持检测失败${NC}" >&2
        echo -e "${YELLOW}         请确保已安装 nvidia-container-toolkit${NC}" >&2
        echo -e "${YELLOW}         继续执行,但可能会在运行时失败...${NC}" >&2
    else
        echo -e "${GREEN}  NVIDIA GPU 支持可用${NC}"
    fi

    echo -e "${GREEN}[检查] Docker 环境正常${NC}"
    echo ""
}

# 检查镜像是否存在
image_exists() {
    docker images --format '{{.Repository}}:{{.Tag}}' | grep -q "^${IMAGE_NAME}$"
}

# 构建 Docker 镜像
build_image() {
    # 检查是否需要构建
    if [[ $REBUILD -eq 0 ]] && image_exists; then
        echo -e "${BLUE}[镜像]${NC} ${IMAGE_NAME} 已存在,跳过构建"
        echo -e "${BLUE}       ${NC}使用 --rebuild 强制重新构建"
        echo ""
        return 0
    fi

    echo -e "${BLUE}[构建]${NC} 开始构建 Docker 镜像: ${IMAGE_NAME}"
    echo ""

    # 获取当前用户 UID 和 GID
    local user_id
    local group_id
    user_id=$(id -u)
    group_id=$(id -g)

    # 构建镜像
    if docker build \
        --build-arg USER_ID="${user_id}" \
        --build-arg GROUP_ID="${group_id}" \
        -t "${IMAGE_NAME}" \
        -f "${PROJECT_DIR}/docker/Dockerfile" \
        "${PROJECT_DIR}"; then
        echo ""
        echo -e "${GREEN}[构建] 镜像构建成功: ${IMAGE_NAME}${NC}"
        echo ""
    else
        echo ""
        echo -e "${RED}[ERROR] 镜像构建失败${NC}" >&2
        echo -e "${RED}        请检查 Dockerfile 和构建日志${NC}" >&2
        exit 1
    fi
}

# 运行容器执行训练
run_container() {
    echo -e "${BLUE}===========================================${NC}"
    echo -e "${GREEN}启动 Docker 容器执行训练流程${NC}"
    echo -e "${BLUE}===========================================${NC}"
    echo -e "${BLUE}[镜像]${NC} ${IMAGE_NAME}"
    echo -e "${BLUE}[项目]${NC} ${PROJECT_DIR}"
    if [[ ${#PUBLISH_ARGS[@]} -gt 0 ]]; then
        echo -e "${BLUE}[参数]${NC} ${PUBLISH_ARGS[*]}"
    fi
    echo -e "${BLUE}===========================================${NC}"
    echo ""

    # 运行容器
    # 注意: 使用当前用户 UID/GID 以匹配文件权限
    docker run --rm \
        --gpus all \
        --shm-size=32GB \
        --user "$(id -u):$(id -g)" \
        -v "${PROJECT_DIR}:/home/samuel/TSC_CYCLE:rw" \
        -w /home/samuel/TSC_CYCLE \
        -e HF_HOME=/home/samuel/TSC_CYCLE/model \
        -e MODELSCOPE_CACHE=/home/samuel/TSC_CYCLE/model \
        -e UNSLOTH_USE_MODELSCOPE=1 \
        -e SUMO_HOME=/usr/share/sumo \
        "${IMAGE_NAME}" \
        ./docker/publish.sh "${PUBLISH_ARGS[@]+"${PUBLISH_ARGS[@]}"}"

    local exit_code=$?

    echo ""
    if [[ $exit_code -eq 0 ]]; then
        echo -e "${GREEN}===========================================${NC}"
        echo -e "${GREEN}Docker 容器执行完成${NC}"
        echo -e "${GREEN}===========================================${NC}"
    else
        echo -e "${RED}===========================================${NC}"
        echo -e "${RED}Docker 容器执行失败 (退出码: $exit_code)${NC}"
        echo -e "${RED}===========================================${NC}"
        exit $exit_code
    fi
}

# 主流程
main() {
    echo ""
    echo -e "${BLUE}===========================================${NC}"
    echo -e "${GREEN}GRPO 交通信号优化 - Docker 运行脚本${NC}"
    echo -e "${BLUE}===========================================${NC}"
    echo ""

    # 解析参数
    parse_args "$@"

    # 检查 Docker 环境
    check_docker

    # 构建镜像 (如果需要)
    build_image

    # 运行容器
    run_container
}

# 执行主流程
main "$@"
