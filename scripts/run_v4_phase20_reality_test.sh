#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="/home/samuel/TSC_CYCLE"
PYTHON="/home/samuel/TSC_CYCLE/.venv/bin/python"
REALITY_LOG="/home/samuel/TSC_CYCLE/reality.log"
ARTIFACT_ROOT="/home/samuel/TSC_CYCLE/artifacts/v4_2/phase20"
OUT_LOG="/home/samuel/TSC_CYCLE/artifacts/v4_2/phase20/reality_test.log"
RUN_ROOT="/home/samuel/TSC_CYCLE/runs/v4.2-4B-20260518T111519Z"
GGUF_PATH="/home/samuel/TSC_CYCLE/runs/v4.2-4B-20260518T111519Z/gguf/model.q4_K_M.gguf"
EVAL_REPORT="/home/samuel/TSC_CYCLE/artifacts/v4_2/phase20/eval_report.json"
LLAMA_SERVER="/home/samuel/llama.cpp/build/bin/llama-server"
BACKEND_LABEL="tsc-cycle-v4.2-q4_K_M"

export PYTHONPATH="${PROJECT_ROOT}:${PYTHONPATH:-}"

if [[ ! -x "${PYTHON}" ]]; then
  echo "missing python executable: ${PYTHON}" >&2
  exit 1
fi

if [[ ! -f "${REALITY_LOG}" ]]; then
  echo "missing reality input log: ${REALITY_LOG}" >&2
  exit 1
fi

if [[ ! -f "${GGUF_PATH}" ]]; then
  echo "missing Phase 20 q4_K_M GGUF artifact: ${GGUF_PATH}" >&2
  exit 1
fi

if [[ ! -x "${LLAMA_SERVER}" ]]; then
  echo "missing executable llama-server: ${LLAMA_SERVER}" >&2
  exit 1
fi

mkdir -p "${ARTIFACT_ROOT}"

"${PYTHON}" -m tsc_cycle.v4_gates.phase20_eval validate-report \
  --run-root "${RUN_ROOT}" \
  --report "${EVAL_REPORT}"

"${PYTHON}" -m tsc_cycle.v4_gates.phase20_reality_test \
  --reality-log "${REALITY_LOG}" \
  --out-log "${OUT_LOG}" \
  --artifact-root "${ARTIFACT_ROOT}" \
  --run-root "${RUN_ROOT}" \
  --eval-report "${EVAL_REPORT}" \
  --gguf-path "${GGUF_PATH}" \
  --llama-server "${LLAMA_SERVER}" \
  --backend-label "${BACKEND_LABEL}" \
  --resume \
  --n-predict 384 \
  --retry-n-predict 768 \
  --timeout-sec 600 \
  --ngl 99 \
  --threads 4 \
  --ctx-size 4096

echo "[PHASE20] complete: ${OUT_LOG}"
