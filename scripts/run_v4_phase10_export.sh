#!/usr/bin/env bash
set -euo pipefail

ROOT=/home/samuel/TSC_CYCLE
RUN_ROOT=/home/samuel/TSC_CYCLE/runs/v4.0-4B-20260509T184844Z
LLAMA_CPP=/home/samuel/projects/EvoProgTSC/llama.cpp

export LLAMA_CPP_DIR="${LLAMA_CPP}"
export TRITON_PTXAS_PATH="${TRITON_PTXAS_PATH:-/usr/local/cuda/bin/ptxas}"

"${ROOT}/.venv/bin/python" -m tsc_cycle.student.export_gguf \
  --phase9-report "${RUN_ROOT}/phase9_sft_report.json" \
  --run-root "${RUN_ROOT}" \
  --llama-cpp "${LLAMA_CPP}" \
  --merged-dir "${RUN_ROOT}/merged_hf" \
  --fp16-gguf "${RUN_ROOT}/gguf/model.fp16.gguf" \
  --q4-gguf "${RUN_ROOT}/gguf/model.q4_K_M.gguf" \
  --report "${RUN_ROOT}/phase10_export_report.json"
