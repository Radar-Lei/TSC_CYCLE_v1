#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
ROOT_CAUSE_DIR="${PROJECT_DIR}/outputs/grpo_simple/qwen3-8b/root_cause"
RUNS_DIR="${ROOT_CAUSE_DIR}/runs"
REPORT_DIR="${ROOT_CAUSE_DIR}/report"
CONFIG_PATH="config/config_8b.json"
REUSE_EXISTING="false"
SAMPLE_SIZES=(50 2000 4000)

show_help() {
    cat <<'EOF'
用法:
  bash docker/grpo_simple_root_cause.sh [options]

选项:
  --config PATH           配置文件路径，默认 config/config_8b.json
  --reuse-existing        复用已有 runs 结果，仅补缺失 run 并重建聚合报告
  --root-cause-dir PATH   root cause 产物根目录，默认 outputs/grpo_simple/qwen3-8b/root_cause
  --help                  显示帮助

说明:
  - 固定组织 runs/50、runs/2000、runs/4000 与 report/ 目录
  - 默认按既有 baseline 验证路径生成 summary，再聚合 root cause 报告
  - 如已有结果，可加 --reuse-existing 避免重复跑重型验证
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --config)
            CONFIG_PATH="$2"
            shift 2
            ;;
        --reuse-existing)
            REUSE_EXISTING="true"
            shift
            ;;
        --root-cause-dir)
            ROOT_CAUSE_DIR="$2"
            RUNS_DIR="${ROOT_CAUSE_DIR}/runs"
            REPORT_DIR="${ROOT_CAUSE_DIR}/report"
            shift 2
            ;;
        --help|-h)
            show_help
            exit 0
            ;;
        *)
            echo "[错误] 未知参数: $1"
            show_help
            exit 1
            ;;
    esac
done

mkdir -p "${RUNS_DIR}" "${REPORT_DIR}"

echo "=========================================="
echo "GRPO Simple Root Cause 批处理"
echo "=========================================="
echo "[项目目录] ${PROJECT_DIR}"
echo "[配置文件] ${CONFIG_PATH}"
echo "[产物目录] ${ROOT_CAUSE_DIR}"
echo "[复用已有] ${REUSE_EXISTING}"
echo ""

for size in "${SAMPLE_SIZES[@]}"; do
    RUN_DIR="${RUNS_DIR}/${size}"
    RESULT_JSON="${RUN_DIR}/validation_result.json"
    MANIFEST_JSON="${RUN_DIR}/sample_manifest.json"
    DETAILS_JSON="${RUN_DIR}/details.json"
    FAILURES_JSON="${RUN_DIR}/failure_examples.json"

    mkdir -p "${RUN_DIR}"

    if [[ "${REUSE_EXISTING}" == "true" && -f "${RESULT_JSON}" ]]; then
        echo "[复用] 已存在 run ${size}: ${RESULT_JSON}"
        continue
    fi

    echo "[运行] 生成 ${size} 样本 baseline 验证结果"
    bash "${PROJECT_DIR}/docker/grpo_simple_validate.sh" \
        --config "${CONFIG_PATH}" \
        --num-samples "${size}" \
        --output "${RESULT_JSON}" \
        --sample-manifest-out "${MANIFEST_JSON}" \
        --details-output "${DETAILS_JSON}" \
        --failure-examples-out "${FAILURES_JSON}"
done

RUN_ARGS=()
for size in "${SAMPLE_SIZES[@]}"; do
    RESULT_JSON="${RUNS_DIR}/${size}/validation_result.json"
    if [[ ! -f "${RESULT_JSON}" ]]; then
        echo "[错误] 缺少 run 结果: ${RESULT_JSON}"
        exit 1
    fi
    RUN_ARGS+=(--run "${size}=${RESULT_JSON}")
done

echo "[聚合] 生成 root cause 报告"
python -m src.grpo_simple.root_cause_analysis \
    --config "${PROJECT_DIR}/${CONFIG_PATH}" \
    "${RUN_ARGS[@]}" \
    --json-output "${REPORT_DIR}/root_cause_report.json" \
    --markdown-output "${REPORT_DIR}/root_cause_report.md"

echo ""
echo "=========================================="
echo "[完成] Root cause 产物已生成"
echo "[Runs]   ${RUNS_DIR}"
echo "[Report] ${REPORT_DIR}/root_cause_report.json"
echo "[Report] ${REPORT_DIR}/root_cause_report.md"
echo "=========================================="
