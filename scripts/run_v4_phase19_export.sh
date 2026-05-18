#!/usr/bin/env bash
set -euo pipefail

ROOT="/home/samuel/TSC_CYCLE"
PY="$ROOT/.venv/bin/python"
LLAMA_CPP="${LLAMA_CPP_DIR:-/home/samuel/projects/EvoProgTSC/llama.cpp}"

if [[ $# -gt 1 ]]; then
  printf 'usage: %s [RUN_ROOT]\n' "$0" >&2
  exit 2
fi

RUN_ROOT="${1:-runs/v4.2-4B-$(date -u +%Y%m%dT%H%M%SZ)}"
case "$RUN_ROOT" in
  runs/v4.2-4B-*|*/runs/v4.2-4B-*) ;;
  *) printf 'RUN_ROOT must match runs/v4.2-4B-*\n' >&2; exit 2 ;;
esac
cd "$ROOT"

export LLAMA_CPP_DIR="$LLAMA_CPP"
export TRITON_PTXAS_PATH="${TRITON_PTXAS_PATH:-/usr/local/cuda/bin/ptxas}"

"$PY" -m tsc_cycle.v4_gates.phase19_training validate-report \
  --run-root "$RUN_ROOT" \
  --report-path "$RUN_ROOT/phase19_sft_report.json"

"$ROOT/scripts/dgx_spark/run_safe.sh" 100G -- "$PY" -m tsc_cycle.student.export_gguf \
  --export-phase phase19 \
  --phase19-report "$RUN_ROOT/phase19_sft_report.json" \
  --run-root "$RUN_ROOT" \
  --llama-cpp "$LLAMA_CPP" \
  --merged-dir "$RUN_ROOT/merged_hf" \
  --fp16-gguf "$RUN_ROOT/gguf/model.fp16.gguf" \
  --q4-gguf "$RUN_ROOT/gguf/model.q4_K_M.gguf" \
  --report "$RUN_ROOT/phase19_export_report.json"

"$PY" -m tsc_cycle.v4_gates.phase19_export \
  --run-root "$RUN_ROOT" \
  --report "$RUN_ROOT/phase19_export_report.json" \
  --evaluate-only
