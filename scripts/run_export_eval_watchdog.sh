#!/bin/bash
# Watchdog: wait for training adapter, then run P5 export + P6 eval.
set -euo pipefail
cd /home/samuel/TSC_CYCLE
set -a; source .env; set +a
source scripts/dgx_spark/env.sh
export PYTHONPATH=.

TS="${TS:-20260506T212001Z}"
RUN_DIR="runs/${TS}"
ADAPTER_DIR="$RUN_DIR/train/adapter"

echo "[$(date -Is)] watchdog: waiting for $ADAPTER_DIR ..."
while [ ! -d "$ADAPTER_DIR" ] || [ ! -f "$ADAPTER_DIR/adapter_model.safetensors" ]; do
  sleep 60
  # Stop if training process died without producing adapter
  if ! pgrep -f "tsc_cycle.student.train" > /dev/null; then
    sleep 30
    if [ ! -f "$ADAPTER_DIR/adapter_model.safetensors" ]; then
      echo "[$(date -Is)] ABORT: train process died without saving adapter"
      exit 1
    fi
  fi
done
echo "[$(date -Is)] adapter ready: $ADAPTER_DIR"

# Phase 5: merge + GGUF export
if [ ! -f "$RUN_DIR/gguf/model.q4_K_M.gguf" ]; then
  echo "[$(date -Is)] Phase 5: merge + GGUF export"
  python -m tsc_cycle.student.export_gguf --adapter "$ADAPTER_DIR" --out "$RUN_DIR"
fi

# Phase 5 parity check (20 OOD prompts)
if [ ! -f "$RUN_DIR/parity.json" ]; then
  echo "[$(date -Is)] Phase 5 parity check"
  python -m tsc_cycle.eval.parity \
    --merged-hf "$RUN_DIR/merged_bf16" \
    --gguf-bf16 "$RUN_DIR/gguf/model.bf16.gguf" \
    --gguf-q4   "$RUN_DIR/gguf/model.q4_K_M.gguf" \
    --out "$RUN_DIR/parity.json" || true
fi

# Phase 6: full evaluation
if [ ! -f "$RUN_DIR/eval/decision.md" ]; then
  echo "[$(date -Is)] Phase 6: full eval"
  python -m tsc_cycle.eval.run_eval \
    --merged-hf "$RUN_DIR/merged_bf16" \
    --gguf-bf16 "$RUN_DIR/gguf/model.bf16.gguf" \
    --gguf-q4   "$RUN_DIR/gguf/model.q4_K_M.gguf" \
    --out-dir   "$RUN_DIR/eval"
fi

echo "[$(date -Is)] PIPELINE COMPLETE"
echo "Final GGUF (q4_K_M): $RUN_DIR/gguf/model.q4_K_M.gguf"
echo "Decision: $RUN_DIR/eval/decision.md"
