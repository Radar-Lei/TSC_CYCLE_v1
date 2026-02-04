#!/usr/bin/env bash
set -euo pipefail

################################################################################
# GRPO信控模型训练 - 一键运行脚本
#
# 完整流程：依赖检查 -> GRPO数据生成 -> SFT数据生成 -> SFT训练 -> GRPO训练
#
# 用法:
#   ./docker/publish.sh
#
# 配置参数（优先级从高到低）：
#   1. 环境变量 (PARALLEL_OVERRIDE, EXTEND_SECONDS_OVERRIDE, WARMUP_STEPS_OVERRIDE)
#   2. YAML配置文件 (config/training_config.yaml)
#   3. 默认值
#
# 环境变量：
#   CONFIG_FILE              - 配置文件路径 (默认: config/training_config.yaml)
#   PARALLEL_OVERRIDE        - 并行进程数 (默认: 从配置文件读取 simulation.sumo.max_workers)
#   EXTEND_SECONDS_OVERRIDE  - 决策延长秒数 (默认: 从配置文件读取 simulation.sumo.extend_seconds)
#   WARMUP_STEPS_OVERRIDE    - 预热步数 (默认: 从配置文件读取 simulation.sumo.warmup_steps)
#   SCENARIOS                - 场景列表，逗号分隔 (默认: 空=所有场景)
################################################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

# 获取当前用户信息（用于文件权限）
HOST_UID="$(id -u)"
HOST_GID="$(id -g)"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 容器配置
CONTAINER_NAME="${CONTAINER_NAME:-qwen3-tsc-grpo}"
IMAGE_NAME="${IMAGE_NAME:-qwen3-tsc-grpo}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
DOCKERFILE="${DOCKERFILE:-${SCRIPT_DIR}/Dockerfile}"
CONTAINER_WORKDIR="/home/samuel/SCU_TSC"
DOCKER_NO_CACHE="${DOCKER_NO_CACHE:-0}"
DOCKER_PULL="${DOCKER_PULL:-0}"

# 目录配置
HOST_MODEL_DIR="${HOST_MODEL_DIR:-${PROJECT_DIR}/model}"
HOST_DATA_DIR="${HOST_DATA_DIR:-${PROJECT_DIR}/data}"

# GRPO生成配置 - 从YAML配置文件读取
CONFIG_FILE="${CONFIG_FILE:-${PROJECT_DIR}/config/training_config.yaml}"
READ_CONFIG_SCRIPT="${PROJECT_DIR}/config/read_config.py"

SCENARIOS="${SCENARIOS:-}"
PARALLEL="${PARALLEL_OVERRIDE:-auto}"
EXTEND_SECONDS="${EXTEND_SECONDS_OVERRIDE:-auto}"
WARMUP_STEPS="${WARMUP_STEPS_OVERRIDE:-auto}"
DRY_RUN="${DRY_RUN:-0}"
FORCE_REGEN_GRPO="${FORCE_REGEN_GRPO:-0}"
FORCE_REGEN_SFT_DATA="${FORCE_REGEN_SFT_DATA:-0}"
FORCE_RETRAIN_SFT="${FORCE_RETRAIN_SFT:-0}"

# 日志
LOG_FILE="${PROJECT_DIR}/.docker_run.log"

################################################################################
# 辅助函数
################################################################################

# 依赖检查函数
check_dependencies() {
  local errors=0

  echo -e "${BLUE}[检查]${NC} 正在检查系统依赖..."

  # 检查CUDA
  if ! command -v nvidia-smi &>/dev/null && [[ ! -d "/usr/local/cuda" ]]; then
    echo -e "${RED}[ERROR] 依赖检查失败: CUDA不可用${NC}" >&2
    echo "请确保NVIDIA驱动和CUDA已安装" >&2
    ((errors++))
  fi

  # 检查SUMO
  if ! command -v sumo &>/dev/null && [[ -z "${SUMO_HOME:-}" ]]; then
    echo -e "${RED}[ERROR] 依赖检查失败: SUMO未安装${NC}" >&2
    echo "请安装SUMO或设置SUMO_HOME环境变量" >&2
    ((errors++))
  fi

  # 检查Python包
  local missing_packages=()

  python -c "import torch" 2>/dev/null || missing_packages+=("torch")
  python -c "import transformers" 2>/dev/null || missing_packages+=("transformers")
  python -c "import unsloth" 2>/dev/null || missing_packages+=("unsloth")
  python -c "import trl" 2>/dev/null || missing_packages+=("trl")

  if [[ ${#missing_packages[@]} -gt 0 ]]; then
    echo -e "${RED}[ERROR] 依赖检查失败: 缺少Python包${NC}" >&2
    echo "缺少的包: ${missing_packages[*]}" >&2
    ((errors++))
  fi

  if [[ $errors -gt 0 ]]; then
    echo "" >&2
    echo -e "${RED}请确保所有依赖已安装后再运行此脚本${NC}" >&2
    exit 1
  fi

  echo -e "${GREEN}[检查]${NC} 所有依赖检查通过 ✓"
  echo ""
}

# Spinner动画函数
showSpinner() {
  local pid=$1
  local message=$2
  local delay=0.1
  local spinstr='|/-\'

  while [ "$(ps a | awk '{print $1}' | grep $pid)" ]; do
    local temp=${spinstr#?}
    printf " [%c] %s..." "$spinstr" "$message"
    local spinstr=$temp${spinstr%"$temp"}
    sleep $delay
    printf "\r"
  done
  printf " \r"
}

# 清理已有容器
if [[ "${STOP_EXISTING:-1}" == "1" ]]; then
  existing="$(docker ps -a --filter "name=^/${CONTAINER_NAME}$" --format '{{.Names}}' 2>/dev/null || true)"
  if [[ -n "${existing}" ]]; then
    echo "[publish] removing existing container ${CONTAINER_NAME}"
    docker rm -f "${CONTAINER_NAME}" 2>/dev/null || true
  fi
fi

# 检查GPU
echo "[publish] checking GPU availability..."
if ! command -v nvidia-smi &>/dev/null; then
  echo "[publish] warning: nvidia-smi not found, GPU may not be available"
fi

# 构建镜像
echo "[publish] building image ${IMAGE_NAME}:${IMAGE_TAG} from ${DOCKERFILE}"
DOCKER_BUILD_ARGS=()
if [[ "${DOCKER_NO_CACHE}" == "1" ]]; then
  DOCKER_BUILD_ARGS+=(--no-cache)
fi
if [[ "${DOCKER_PULL}" == "1" ]]; then
  DOCKER_BUILD_ARGS+=(--pull)
fi
docker build \
  "${DOCKER_BUILD_ARGS[@]}" \
  --build-arg "USER_ID=${HOST_UID}" \
  --build-arg "GROUP_ID=${HOST_GID}" \
  -t "${IMAGE_NAME}:${IMAGE_TAG}" \
  -f "${DOCKERFILE}" \
  "${SCRIPT_DIR}/.."

# 创建目录
mkdir -p "${HOST_MODEL_DIR}"
mkdir -p "${HOST_DATA_DIR}"

echo ""
echo -e "${BLUE}==========================================${NC}"
echo -e "${GREEN}GRPO信控模型训练 - 完整流程${NC}"
echo -e "${BLUE}==========================================${NC}"
echo -e "${BLUE}[容器]${NC} ${CONTAINER_NAME}"
echo -e "${BLUE}[镜像]${NC} ${IMAGE_NAME}:${IMAGE_TAG}"
echo -e "${BLUE}[并行]${NC} ${PARALLEL}"
echo -e "${BLUE}[延长秒数]${NC} ${EXTEND_SECONDS}"
echo -e "${BLUE}[预热步数]${NC} ${WARMUP_STEPS}"
echo -e "${BLUE}[场景]${NC} ${SCENARIOS:-all}"
echo -e "${BLUE}[日志]${NC} ${LOG_FILE}"
echo -e "${BLUE}==========================================${NC}"
echo ""

# 运行完整流程
echo -e "${BLUE}[开始]${NC} $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

docker run \
  --gpus all \
  --name "${CONTAINER_NAME}" \
  --shm-size=32GB \
  --ulimit memlock=-1 \
  --ulimit stack=67108864 \
  --entrypoint /usr/bin/bash \
  -v "${HOST_MODEL_DIR}:/home/samuel/SCU_TSC/model:rw" \
  -v "${HOST_DATA_DIR}:/home/samuel/SCU_TSC/data:rw" \
  -v "${PROJECT_DIR}:${CONTAINER_WORKDIR}:rw" \
  -w "${CONTAINER_WORKDIR}" \
  -e HF_HOME=/home/samuel/SCU_TSC/model \
  -e MODELSCOPE_CACHE=/home/samuel/SCU_TSC/model \
  -e UNSLOTH_USE_MODELSCOPE=1 \
  -e UNSLOTH_VLLM_STANDBY=1 \
  -e SUMO_HOME=/usr/share/sumo \
  -e CONFIG_FILE="${CONFIG_FILE}" \
  -e PARALLEL_OVERRIDE="${PARALLEL_OVERRIDE:-}" \
  -e EXTEND_SECONDS_OVERRIDE="${EXTEND_SECONDS_OVERRIDE:-}" \
  -e WARMUP_STEPS_OVERRIDE="${WARMUP_STEPS_OVERRIDE:-}" \
  -e SCENARIOS="${SCENARIOS}" \
  -e DRY_RUN="${DRY_RUN}" \
  -e FORCE_REGEN_GRPO="${FORCE_REGEN_GRPO}" \
  -e FORCE_REGEN_SFT_DATA="${FORCE_REGEN_SFT_DATA}" \
  -e FORCE_RETRAIN_SFT="${FORCE_RETRAIN_SFT}" \
  "${IMAGE_NAME}:${IMAGE_TAG}" \
  -c "
set -e
cd ${CONTAINER_WORKDIR}

CONFIG_FILE=\"\${CONFIG_FILE:-config/training_config.yaml}\"
if [[ ! -f \"\${CONFIG_FILE}\" ]]; then
  CONFIG_FILE=\"config/training_config.yaml\"
fi

PARALLEL=\"\${PARALLEL_OVERRIDE:-\$(python3 config/read_config.py --config \"\${CONFIG_FILE}\" --key simulation.sumo.max_workers --default 4 2>/dev/null || echo 4)}\"
EXTEND_SECONDS=\"\${EXTEND_SECONDS_OVERRIDE:-\$(python3 config/read_config.py --config \"\${CONFIG_FILE}\" --key simulation.sumo.extend_seconds --default 5 2>/dev/null || echo 5)}\"
WARMUP_STEPS=\"\${WARMUP_STEPS_OVERRIDE:-\$(python3 config/read_config.py --config \"\${CONFIG_FILE}\" --key simulation.sumo.warmup_steps --default 300 2>/dev/null || echo 300)}\"

GRPO_DATA_DIR=\"\$(python3 config/read_config.py --config \"\${CONFIG_FILE}\" --key paths.grpo_dataset_dir --default data/grpo_datasets 2>/dev/null || echo data/grpo_datasets)\"
SFT_DATA_DIR=\"\$(python3 config/read_config.py --config \"\${CONFIG_FILE}\" --key paths.sft_dataset_dir --default data/sft_datasets 2>/dev/null || echo data/sft_datasets)\"
SCENARIOS_DIR=\"\$(python3 config/read_config.py --config \"\${CONFIG_FILE}\" --key simulation.scenarios.scenarios_dir --default sumo_simulation/environments 2>/dev/null || echo sumo_simulation/environments)\"
MIN_GREEN_OFFSET_RANGE=\"\$(python3 config/read_config.py --config \"\${CONFIG_FILE}\" --key simulation.sumo.min_green_offset_range --default 2.0 2>/dev/null || echo 2.0)\"
MAX_GREEN_OFFSET_RANGE=\"\$(python3 config/read_config.py --config \"\${CONFIG_FILE}\" --key simulation.sumo.max_green_offset_range --default 5.0 2>/dev/null || echo 5.0)\"
SFT_DATA_FILE=\"\${SFT_DATA_DIR%/}/sft_dataset.json\"
SFT_MODEL_DIR=\"\$(python3 config/read_config.py --config \"\${CONFIG_FILE}\" --key paths.sft_model_dir --default model/sft_model 2>/dev/null || echo model/sft_model)\"
GRPO_MODEL_DIR=\"\$(python3 config/read_config.py --config \"\${CONFIG_FILE}\" --key paths.grpo_model_dir --default model/grpo_model 2>/dev/null || echo model/grpo_model)\"

export GRPO_DATA_DIR SFT_DATA_DIR SFT_DATA_FILE SFT_MODEL_DIR GRPO_MODEL_DIR

echo -e \"\\033[0;34m[配置]\\033[0m CONFIG_FILE=\${CONFIG_FILE}\"
echo -e \"\\033[0;34m[配置]\\033[0m max_workers(PARALLEL)=\${PARALLEL}, extend_seconds=\${EXTEND_SECONDS}, warmup_steps=\${WARMUP_STEPS}\"
echo -e \"\\033[0;34m[配置]\\033[0m GRPO_DATA_DIR=\${GRPO_DATA_DIR}\"
echo -e \"\\033[0;34m[配置]\\033[0m SFT_DATA_FILE=\${SFT_DATA_FILE}\"
echo -e \"\\033[0;34m[配置]\\033[0m SCENARIOS_DIR=\${SCENARIOS_DIR}\"
echo -e \"\\033[0;34m[配置]\\033[0m green_offset_range=[\${MIN_GREEN_OFFSET_RANGE}, \${MAX_GREEN_OFFSET_RANGE}]\"
echo -e \"\\033[0;34m[配置]\\033[0m SFT_MODEL_DIR=\${SFT_MODEL_DIR}\"
echo -e \"\\033[0;34m[配置]\\033[0m GRPO_MODEL_DIR=\${GRPO_MODEL_DIR}\"
echo ''

if [[ \"\${DRY_RUN:-0}\" == \"1\" ]]; then
  echo -e \"\\033[0;33m[DRY_RUN]\\033[0m 仅回显配置并退出\"
  exit 0
fi

# 容器内依赖检查
echo -e '\033[0;34m[检查]\033[0m 正在检查容器内依赖...'

# 检查CUDA
if ! command -v nvidia-smi &>/dev/null && [[ ! -d '/usr/local/cuda' ]]; then
    echo -e '\033[0;31m[ERROR] 依赖检查失败: CUDA不可用\033[0m' >&2
    exit 1
fi

# 检查SUMO
if ! command -v sumo &>/dev/null && [[ -z \"\${SUMO_HOME:-}\" ]]; then
    echo -e '\033[0;31m[ERROR] 依赖检查失败: SUMO未安装\033[0m' >&2
    exit 1
fi

# 检查Python包
if ! python -c 'import torch' 2>/dev/null; then
    echo -e '\033[0;31m[ERROR] 依赖检查失败: torch未安装\033[0m' >&2
    exit 1
fi

if ! python -c 'import transformers' 2>/dev/null; then
    echo -e '\033[0;31m[ERROR] 依赖检查失败: transformers未安装\033[0m' >&2
    exit 1
fi

if ! python -c 'import unsloth' 2>/dev/null; then
    echo -e '\033[0;31m[ERROR] 依赖检查失败: unsloth未安装\033[0m' >&2
    exit 1
fi

if ! python -c 'import trl' 2>/dev/null; then
    echo -e '\033[0;31m[ERROR] 依赖检查失败: trl未安装\033[0m' >&2
    exit 1
fi

echo -e '\033[0;32m✓ 所有依赖检查通过\033[0m'
echo ''

# 记录开始时间
START_TIME=\$(date +%s)
START_DATE=\$(date '+%Y-%m-%d')

# Step 0: 数据验证（仅当数据已存在时验证，首次运行则跳过）
VALIDATION_START=\$(date +%s)
echo -e '\033[0;34m[Step 0/5]\033[0m 验证数据...'

# 检查数据是否已存在（用于判断是首次运行还是增量训练）
GRPO_DATA_EXISTS=false
SFT_DATA_EXISTS=false
SFT_MODEL_EXISTS=false
SFT_DATA_JSONL=\"\${SFT_DATA_DIR%/}/sft_dataset.jsonl\"

# 检查GRPO数据目录
if [[ -d \"\${GRPO_DATA_DIR}\" ]]; then
    GRPO_JSON_COUNT=\$(find \"\${GRPO_DATA_DIR}\" -mindepth 2 -maxdepth 2 -type f -name 'grpo_dataset.json' 2>/dev/null | wc -l)
    if [[ "\${GRPO_JSON_COUNT}" -gt 0 ]]; then
        GRPO_DATA_EXISTS=true
    fi
fi

if [[ -n \"\${SCENARIOS:-}\" ]]; then
    IFS=',' read -ra SCEN_LIST <<< \"\${SCENARIOS}\"
    for scen in \"\${SCEN_LIST[@]}\"; do
        scen=\"\${scen#\"\${scen%%[![:space:]]*}\"}\"
        scen=\"\${scen%\"\${scen##*[![:space:]]}\"}\"
        if [[ -n \"\${scen}\" ]] && [[ ! -f \"\${GRPO_DATA_DIR%/}/\${scen}/grpo_dataset.json\" ]]; then
            GRPO_DATA_EXISTS=false
            break
        fi
    done
fi

# 检查SFT数据文件
if [[ -s \"\${SFT_DATA_FILE}\" ]] && [[ -s \"\${SFT_DATA_JSONL}\" ]]; then
    SFT_DATA_EXISTS=true
fi

if [[ -f \"\${SFT_MODEL_DIR%/}/adapter_model.safetensors\" ]] && [[ -d \"\${SFT_MODEL_DIR%/}/merged\" ]]; then
    SFT_MODEL_EXISTS=true
fi

if [[ \"\${FORCE_REGEN_GRPO:-0}\" == \"1\" ]]; then
    GRPO_DATA_EXISTS=false
fi
if [[ \"\${FORCE_REGEN_SFT_DATA:-0}\" == \"1\" ]]; then
    SFT_DATA_EXISTS=false
fi
if [[ \"\${FORCE_RETRAIN_SFT:-0}\" == \"1\" ]]; then
    SFT_MODEL_EXISTS=false
fi

if [[ "\$GRPO_DATA_EXISTS" == "true" ]] || [[ "\$SFT_DATA_EXISTS" == "true" ]]; then
    # 数据已存在，执行验证（用于增量训练场景）
    echo '检测到已有数据，执行数据验证...'
    if (
        set -e
        python -m grpo.validate_data --verbose
    ); then
        VALIDATION_END=\$(date +%s)
        VALIDATION_DURATION=\$((VALIDATION_END - VALIDATION_START))
        echo -e '\033[0;32m✓ 数据验证通过 (\${VALIDATION_DURATION}秒)\033[0m'
    else
        echo -e '\033[0;31m[ERROR] 数据验证失败，终止训练\033[0m' >&2
        echo '请修复数据问题后重试' >&2
        exit 1
    fi
else
    # 首次运行，数据尚未生成，跳过验证
    echo '首次运行：数据尚未生成，跳过数据验证'
    echo -e '\033[0;33m[INFO] 数据将在Step 1/2中生成\033[0m'
    VALIDATION_DURATION=0
fi

echo ''
echo -e '\033[0;34m[Step 1/5]\033[0m 生成GRPO数据集...'
if [[ \"\${GRPO_DATA_EXISTS}\" == \"true\" ]]; then
    echo -e '\033[0;33m[SKIP]\033[0m 检测到已有GRPO数据集，跳过生成'
    echo -e '\033[0;32m✓ Step 1/5 完成\033[0m'
else
    if (
        set -e
        if [[ -n \"\${SCENARIOS:-}\" ]]; then
            python -m grpo.generate_grpo_dataset --scenarios \"\${SCENARIOS}\" --parallel \"\${PARALLEL}\" --extend-seconds \"\${EXTEND_SECONDS}\" --warmup-steps \"\${WARMUP_STEPS}\" --output-dir \"\${GRPO_DATA_DIR}\" --scenarios-dir \"\${SCENARIOS_DIR}\" --min-green-offset \"\${MIN_GREEN_OFFSET_RANGE}\" --max-green-offset \"\${MAX_GREEN_OFFSET_RANGE}\"
        else
            python -m grpo.generate_grpo_dataset --all --parallel \"\${PARALLEL}\" --extend-seconds \"\${EXTEND_SECONDS}\" --warmup-steps \"\${WARMUP_STEPS}\" --output-dir \"\${GRPO_DATA_DIR}\" --scenarios-dir \"\${SCENARIOS_DIR}\" --min-green-offset \"\${MIN_GREEN_OFFSET_RANGE}\" --max-green-offset \"\${MAX_GREEN_OFFSET_RANGE}\"
        fi
    ); then
        echo -e '\033[0;32m✓ Step 1/5 完成\033[0m'
    else
        echo -e '\033[0;31m[ERROR] Step 1/5 失败: GRPO数据生成\033[0m' >&2
        echo '请查看日志: ${LOG_FILE}' >&2
        exit 1
    fi
fi

echo ''
echo -e '\033[0;34m[Step 2/5]\033[0m 生成SFT数据集...'
if [[ \"\${SFT_DATA_EXISTS}\" == \"true\" ]]; then
    echo -e '\033[0;33m[SKIP]\033[0m 检测到已有SFT数据集，跳过生成'
    echo -e '\033[0;32m✓ Step 2/5 完成\033[0m'
else
    if (
        python -m grpo.generate_sft_dataset --grpo-dir \"\${GRPO_DATA_DIR}\" --output-dir \"\${SFT_DATA_DIR}\"
    ); then
        echo -e '\033[0;32m✓ Step 2/5 完成\033[0m'
    else
        echo -e '\033[0;31m[ERROR] Step 2/5 失败: SFT数据生成\033[0m' >&2
        echo '请查看日志: ${LOG_FILE}' >&2
        exit 1
    fi
fi

echo ''
echo -e '\033[0;34m[Step 3/5]\033[0m SFT训练...'
if [[ \"\${SFT_MODEL_EXISTS}\" == \"true\" ]]; then
    echo -e '\033[0;33m[SKIP]\033[0m 检测到已有SFT模型，跳过训练'
    echo -e '\033[0;32m✓ Step 3/5 完成\033[0m'
else
    if (
        python -m grpo.sft_training --config \"\${CONFIG_FILE}\"
    ); then
        echo -e '\033[0;32m✓ Step 3/5 完成\033[0m'
    else
        echo -e '\033[0;31m[ERROR] Step 3/5 失败: SFT训练\033[0m' >&2
        echo '请查看日志: ${LOG_FILE}' >&2
        exit 1
    fi
fi

echo ''
echo -e '\033[0;34m[Step 4/5]\033[0m GRPO训练...'
if (
    python -m grpo.training --config \"\${CONFIG_FILE}\"
); then
    echo -e '\033[0;32m✓ Step 4/5 完成\033[0m'
else
    echo -e '\033[0;31m[ERROR] Step 4/5 失败: GRPO训练\033[0m' >&2
    echo '请查看日志: ${LOG_FILE}' >&2
    exit 1
fi

# 计算训练时间
END_TIME=\$(date +%s)
DURATION=\$((END_TIME - START_TIME))
HOURS=\$((DURATION / 3600))
MINUTES=\$(((DURATION % 3600) / 60))
SECONDS=\$((DURATION % 60))
DURATION_STR=\$(printf '%02d:%02d:%02d' \$HOURS \$MINUTES \$SECONDS)

# 收集数据集大小
GRPO_DATASET_SIZE=\$(python -c 'import os, glob, json; d=os.environ.get(\"GRPO_DATA_DIR\", \"\"); files=glob.glob(os.path.join(d, \"*\", \"grpo_dataset.json\")); print(sum(len(json.load(open(p, \"r\", encoding=\"utf-8\"))) for p in files))' 2>/dev/null || echo 0)

SFT_DATASET_SIZE=\$(python -c 'import os, json; p=os.environ.get(\"SFT_DATA_FILE\", \"\"); print(len(json.load(open(p, \"r\", encoding=\"utf-8\"))) if p and os.path.isfile(p) else 0)' 2>/dev/null || echo 0)

# 输出训练摘要
echo ''
echo '=========================================='
echo -e '\033[0;32m训练完成！\033[0m'
echo '=========================================='
echo '数据验证: ✓ 通过 ('\${VALIDATION_DURATION}'秒)'
echo \"训练时间: \${DURATION_STR}\"
echo \"GRPO数据集: \${GRPO_DATASET_SIZE} 条\"
echo \"SFT数据集: \${SFT_DATASET_SIZE} 条\"
echo \"SFT模型: \${SFT_MODEL_DIR}\"
echo \"GRPO模型: \${GRPO_MODEL_DIR}\"
echo '=========================================='
" 2>&1 | tee "${LOG_FILE}"; EXIT_CODE=${PIPESTATUS[0]}

echo ""
if [[ ${EXIT_CODE} -eq 0 ]]; then
  echo -e "${GREEN}✓ 训练完成！${NC}"
else
  echo -e "${RED}✗ 训练失败 (退出码: ${EXIT_CODE})${NC}"
fi
echo -e "${BLUE}[结束]${NC} $(date '+%Y-%m-%d %H:%M:%S')"
echo -e "${BLUE}[日志]${NC} ${LOG_FILE}"
echo ""

if [[ -f "${LOG_FILE}" && -s "${LOG_FILE}" ]]; then
  echo "=========================================="
  echo "最后50行日志"
  echo "=========================================="
  tail -50 "${LOG_FILE}"
fi

# 清理容器
echo ""
echo -e "${BLUE}[清理]${NC} 移除容器 ${CONTAINER_NAME}..."
docker rm -f "${CONTAINER_NAME}" 2>/dev/null || true

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}脚本执行完毕${NC}"
echo -e "${GREEN}========================================${NC}"
