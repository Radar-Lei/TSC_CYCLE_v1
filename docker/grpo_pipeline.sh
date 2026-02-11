#!/usr/bin/env bash
set -euo pipefail

################################################################################
# GRPO 端到端训练流水线
#
# 功能: 串联 5 个步骤完成完整的 GRPO 训练流程
#   1. 数据生成: 从 SFT 数据生成 GRPO 训练数据
#   2. 数据过滤: 剔除空交叉口和极低流量样本
#   3. Baseline 计算: 在过滤后的数据上预计算 baseline
#   4. GRPO 训练: 执行强化学习训练
#   5. 结果分析: 分析训练日志，输出关键指标
#
# 用法:
#   ./docker/grpo_pipeline.sh                     # 完整流程
#   ./docker/grpo_pipeline.sh --skip-data         # 跳过数据生成（使用现有数据）
#   ./docker/grpo_pipeline.sh --skip-filter       # 跳过数据过滤
#   ./docker/grpo_pipeline.sh --skip-baseline     # 跳过 baseline 计算
#   ./docker/grpo_pipeline.sh --skip-train        # 跳过训练（仅生成数据）
#   ./docker/grpo_pipeline.sh --skip-analysis     # 跳过结果分析
#
# 注意:
#   - 所有训练参数从 config/config.json 读取
#   - 每步输出独立日志文件到 outputs/grpo/grpo_*.log
#   - 任何步骤失败时流水线立即停止（fail-fast）
#   - 过滤后数据会覆盖原始 grpo_train.jsonl（首次会备份为 _original）
################################################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

IMAGE_NAME="qwen3-tsc-grpo:latest"
CONTAINER_WORKDIR="/home/samuel/SCU_TSC"
LOG_DIR="${PROJECT_DIR}/outputs/grpo"

# 解析参数
SKIP_DATA=false
SKIP_FILTER=false
SKIP_BASELINE=false
SKIP_TRAIN=false
SKIP_ANALYSIS=false

for arg in "$@"; do
    case "$arg" in
        --skip-data)
            SKIP_DATA=true
            ;;
        --skip-filter)
            SKIP_FILTER=true
            ;;
        --skip-baseline)
            SKIP_BASELINE=true
            ;;
        --skip-train)
            SKIP_TRAIN=true
            ;;
        --skip-analysis)
            SKIP_ANALYSIS=true
            ;;
        *)
            echo "未知参数: $arg"
            echo "支持的参数: --skip-data, --skip-filter, --skip-baseline, --skip-train, --skip-analysis"
            exit 1
            ;;
    esac
done

# 创建日志目录
mkdir -p "$LOG_DIR"

# 记录开始时间
START_TIME=$(date +%s)

echo "=========================================="
echo "GRPO 端到端训练流水线"
echo "=========================================="
echo "[项目目录] ${PROJECT_DIR}"
echo "[日志目录] ${LOG_DIR}"
echo ""
echo "[配置] 跳过设置:"
echo "  数据生成: $SKIP_DATA"
echo "  数据过滤: $SKIP_FILTER"
echo "  Baseline: $SKIP_BASELINE"
echo "  训练: $SKIP_TRAIN"
echo "  结果分析: $SKIP_ANALYSIS"
echo ""
echo "开始时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "=========================================="
echo ""

################################################################################
# 步骤 1/5: 数据生成
################################################################################
if [ "$SKIP_DATA" = false ]; then
    echo "[1/5] 生成 GRPO 数据..."
    echo ""

    LOG_FILE="${LOG_DIR}/grpo_generate.log"
    "${SCRIPT_DIR}/grpo_data.sh" 2>&1 | tee "$LOG_FILE"

    echo ""
    echo "[1/5] ✓ 数据生成完成"
    echo ""
else
    echo "[1/5] ⊘ 跳过数据生成"
    echo ""
fi

################################################################################
# 步骤 2/5: 数据过滤
################################################################################
if [ "$SKIP_FILTER" = false ]; then
    echo "[2/5] 过滤数据..."
    echo ""

    LOG_FILE="${LOG_DIR}/grpo_filter.log"
    "${SCRIPT_DIR}/filter_data.sh" --skip-baseline 2>&1 | tee "$LOG_FILE"

    # 数据覆盖逻辑（过滤后数据 -> 原始路径）
    ORIGINAL_FILE="${LOG_DIR}/grpo_train.jsonl"
    FILTERED_FILE="${LOG_DIR}/grpo_train_filtered.jsonl"
    BACKUP_FILE="${LOG_DIR}/grpo_train_original.jsonl"

    if [ -f "$FILTERED_FILE" ]; then
        # 首次备份原始文件
        if [ ! -f "$BACKUP_FILE" ] && [ -f "$ORIGINAL_FILE" ]; then
            echo "[2/5] 备份原始数据: grpo_train.jsonl -> grpo_train_original.jsonl"
            mv "$ORIGINAL_FILE" "$BACKUP_FILE"
        fi

        # 覆盖原始文件
        cp "$FILTERED_FILE" "$ORIGINAL_FILE"

        # 统计样本数
        FILTERED_COUNT=$(wc -l < "$ORIGINAL_FILE")
        if [ -f "$BACKUP_FILE" ]; then
            ORIGINAL_COUNT=$(wc -l < "$BACKUP_FILE")
            echo "[2/5] 数据覆盖完成: 过滤后 $FILTERED_COUNT 条（原始 $ORIGINAL_COUNT 条）"
        else
            echo "[2/5] 数据覆盖完成: 过滤后 $FILTERED_COUNT 条"
        fi
    else
        echo "[2/5] 警告: 未找到过滤输出文件 $FILTERED_FILE"
    fi

    echo ""
    echo "[2/5] ✓ 数据过滤完成"
    echo ""
else
    echo "[2/5] ⊘ 跳过数据过滤"
    echo ""
fi

################################################################################
# 步骤 3/5: Baseline 计算
################################################################################
if [ "$SKIP_BASELINE" = false ]; then
    echo "[3/5] 计算 Baseline..."
    echo ""

    LOG_FILE="${LOG_DIR}/grpo_baseline.log"
    "${SCRIPT_DIR}/grpo_baseline.sh" 2>&1 | tee "$LOG_FILE"

    echo ""
    echo "[3/5] ✓ Baseline 计算完成"
    echo ""
else
    echo "[3/5] ⊘ 跳过 Baseline 计算"
    echo ""
fi

################################################################################
# 训练前检查
################################################################################
if [ "$SKIP_TRAIN" = false ]; then
    echo "[检查] 训练前置条件验证..."
    echo ""

    CHECK_FAILED=false
    CHECK_MESSAGES=()

    # 1. 文件存在性检查
    DATA_FILE="${LOG_DIR}/grpo_train.jsonl"
    BASELINE_FILE="${LOG_DIR}/baseline.json"

    if [ ! -f "$DATA_FILE" ]; then
        CHECK_MESSAGES+=("✗ 训练数据不存在: $DATA_FILE")
        CHECK_FAILED=true
    else
        CHECK_MESSAGES+=("✓ 训练数据存在: $DATA_FILE")
    fi

    if [ ! -f "$BASELINE_FILE" ]; then
        CHECK_MESSAGES+=("✗ Baseline 文件不存在: $BASELINE_FILE")
        CHECK_FAILED=true
    else
        CHECK_MESSAGES+=("✓ Baseline 文件存在: $BASELINE_FILE")
    fi

    # 2. 最少样本数检查
    if [ -f "$DATA_FILE" ]; then
        SAMPLE_COUNT=$(wc -l < "$DATA_FILE")
        MIN_SAMPLES=$(python3 -c "import json; c=json.load(open('${PROJECT_DIR}/config/config.json')); print(c['training']['grpo']['data_filter']['min_samples_threshold'])" 2>/dev/null || echo "1000")

        if [ "$SAMPLE_COUNT" -ge "$MIN_SAMPLES" ]; then
            CHECK_MESSAGES+=("✓ 样本数充足: $SAMPLE_COUNT >= $MIN_SAMPLES")
        else
            CHECK_MESSAGES+=("✗ 样本数不足: $SAMPLE_COUNT < $MIN_SAMPLES")
            CHECK_FAILED=true
        fi
    fi

    # 3. Baseline 完整性检查
    if [ -f "$DATA_FILE" ] && [ -f "$BASELINE_FILE" ]; then
        BASELINE_CHECK=$(python3 -c "
import json
data_scenarios = set()
with open('${DATA_FILE}', 'r') as f:
    for line in f:
        item = json.loads(line)
        data_scenarios.add(item['state_file'])

with open('${BASELINE_FILE}', 'r') as f:
    baseline = json.load(f)
    baseline_scenarios = set(baseline.keys())

missing = data_scenarios - baseline_scenarios
if missing:
    print(f'✗ Baseline 缺失 {len(missing)} 个场景')
    exit(1)
else:
    print(f'✓ Baseline 完整: 覆盖所有 {len(data_scenarios)} 个场景')
" 2>&1)

        CHECK_MESSAGES+=("$BASELINE_CHECK")
        if [[ "$BASELINE_CHECK" == *"✗"* ]]; then
            CHECK_FAILED=true
        fi
    fi

    # 4. Reward 配置合法性检查
    REWARD_CHECK=$(python3 -c "
import json
c = json.load(open('${PROJECT_DIR}/config/config.json'))
r = c['training']['grpo']['reward']
w_sum = r['sumo_throughput_weight'] + r['sumo_queue_weight'] + r['sumo_delay_weight']
if abs(w_sum - 1.0) < 0.001:
    print(f'✓ Reward 权重合法: {w_sum:.3f} ≈ 1.0')
else:
    print(f'✗ Reward 权重非法: {w_sum:.3f} != 1.0')
    exit(1)
" 2>&1)

    CHECK_MESSAGES+=("$REWARD_CHECK")
    if [[ "$REWARD_CHECK" == *"✗"* ]]; then
        CHECK_FAILED=true
    fi

    # 打印所有检查结果
    for msg in "${CHECK_MESSAGES[@]}"; do
        echo "$msg"
    done
    echo ""

    # 如果有检查失败，停止流水线
    if [ "$CHECK_FAILED" = true ]; then
        echo "[检查] ✗ 训练前检查失败，流水线停止"
        exit 1
    else
        echo "[检查] ✓ 所有检查通过"
        echo ""
    fi
fi

################################################################################
# 步骤 4/5: GRPO 训练
################################################################################
if [ "$SKIP_TRAIN" = false ]; then
    echo "[4/5] GRPO 训练..."
    echo ""

    LOG_FILE="${LOG_DIR}/grpo_train.log"
    "${SCRIPT_DIR}/grpo_train.sh" --skip-validate 2>&1 | tee "$LOG_FILE"

    echo ""
    echo "[4/5] ✓ GRPO 训练完成"
    echo ""
else
    echo "[4/5] ⊘ 跳过 GRPO 训练"
    echo ""
fi

################################################################################
# 步骤 5/5: 结果分析
################################################################################
if [ "$SKIP_ANALYSIS" = false ]; then
    echo "[5/5] 分析训练结果..."
    echo ""

    TRAIN_LOG="${LOG_DIR}/grpo_train.log"
    ANALYSIS_OUTPUT="${LOG_DIR}/grpo_analysis.txt"
    LOG_FILE="${LOG_DIR}/grpo_analysis.log"

    if [ ! -f "$TRAIN_LOG" ]; then
        echo "[5/5] 警告: 训练日志不存在，跳过分析"
    else
        # 通过 Docker 容器运行分析脚本
        docker run --rm \
            --name "grpo-analysis" \
            --user "$(id -u):$(id -g)" \
            -v "${PROJECT_DIR}:${CONTAINER_WORKDIR}:rw" \
            -w "${CONTAINER_WORKDIR}" \
            --entrypoint python3 \
            "${IMAGE_NAME}" \
            -m src.scripts.analyze_grpo_training \
            --log "$TRAIN_LOG" \
            --output "$ANALYSIS_OUTPUT" \
            2>&1 | tee "$LOG_FILE"

        echo ""
        echo "[5/5] ✓ 结果分析完成"
        echo ""
    fi
else
    echo "[5/5] ⊘ 跳过结果分析"
    echo ""
fi

################################################################################
# 流水线完成
################################################################################
END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))
MINUTES=$((DURATION / 60))
SECONDS=$((DURATION % 60))

echo "=========================================="
echo "GRPO 流水线完成"
echo "=========================================="
echo "完成时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "总耗时: ${MINUTES}分${SECONDS}秒"
echo ""
echo "[输出文件]"

# 列出主要输出文件
OUTPUT_FILES=(
    "outputs/grpo/grpo_train.jsonl"
    "outputs/grpo/grpo_train_filtered.jsonl"
    "outputs/grpo/grpo_train_rejected.jsonl"
    "outputs/grpo/baseline.json"
    "outputs/grpo/model/"
    "outputs/grpo/grpo_analysis.txt"
)

for file in "${OUTPUT_FILES[@]}"; do
    FULL_PATH="${PROJECT_DIR}/${file}"
    if [ -e "$FULL_PATH" ]; then
        if [ -d "$FULL_PATH" ]; then
            echo "  ✓ $file (目录)"
        else
            SIZE=$(du -h "$FULL_PATH" | cut -f1)
            echo "  ✓ $file ($SIZE)"
        fi
    fi
done

echo ""
echo "[日志文件]"
LOG_FILES=(
    "grpo_generate.log"
    "grpo_filter.log"
    "grpo_baseline.log"
    "grpo_train.log"
    "grpo_analysis.log"
)

for log in "${LOG_FILES[@]}"; do
    LOG_PATH="${LOG_DIR}/${log}"
    if [ -f "$LOG_PATH" ]; then
        SIZE=$(du -h "$LOG_PATH" | cut -f1)
        echo "  ✓ outputs/grpo/${log} ($SIZE)"
    fi
done

echo "=========================================="
