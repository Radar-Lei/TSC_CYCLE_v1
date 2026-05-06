#!/bin/bash
# Autonomous Phase 3→6 driver. Launched in background (nohup).
# Idempotent — resumes if any phase already partially done.
set -euo pipefail
cd /home/samuel/TSC_CYCLE
set -a; source .env; set +a
source scripts/dgx_spark/env.sh
export PYTHONPATH=.

TS="${TS:-$(date -u +%Y%m%dT%H%M%SZ)}"
RUN_DIR="runs/${TS}"
mkdir -p "$RUN_DIR"
ln -sfn "$TS" runs/latest

echo "=== [$(date -Is)] Pipeline START — TS=$TS ==="

# ─── Phase 3: Teacher Labeling ─────────────────────────────────────────────
LABELED=$(wc -l < data/labeled.jsonl 2>/dev/null || echo 0)
if [ "$LABELED" -lt 2700 ]; then
  echo "=== [$(date -Is)] Phase 3: Teacher Labeling (already $LABELED labeled) ==="
  python -m tsc_cycle.teacher.labeler --workers 10 \
    --cost-out "$RUN_DIR/teacher_cost.json" \
    --reject-stats "$RUN_DIR/teacher_reject_stats.json"
fi

# Validate labeled count
LABELED=$(wc -l < data/labeled.jsonl 2>/dev/null || echo 0)
if [ "$LABELED" -lt 2700 ]; then
  echo "ABORT: only $LABELED labeled samples, need ≥2700"
  exit 1
fi

# ─── Phase 4a: Dataset build ───────────────────────────────────────────────
if [ ! -f data/tokenized/train/data.parquet ]; then
  echo "=== [$(date -Is)] Phase 4a: Dataset build ==="
  python -m tsc_cycle.student.dataset
fi

# ─── Phase 4b: QLoRA SFT ───────────────────────────────────────────────────
ADAPTER_DIR="$RUN_DIR/train/adapter"
if [ ! -d "$ADAPTER_DIR" ]; then
  echo "=== [$(date -Is)] Phase 4b: QLoRA SFT (run_safe.sh wrapped) ==="
  scripts/dgx_spark/run_safe.sh 100G -- python -m tsc_cycle.student.train \
    --output-dir "$RUN_DIR/train"
fi

# ─── Phase 5: Merge + GGUF Export ──────────────────────────────────────────
if [ ! -f "$RUN_DIR/gguf/model.q4_K_M.gguf" ]; then
  echo "=== [$(date -Is)] Phase 5: Merge + GGUF Export ==="
  python -m tsc_cycle.student.export_gguf --adapter "$ADAPTER_DIR" --out "$RUN_DIR"
fi

# ─── Phase 6: Evaluation ───────────────────────────────────────────────────
if [ ! -f "$RUN_DIR/eval/decision.md" ]; then
  echo "=== [$(date -Is)] Phase 6: Evaluation ==="
  python -m tsc_cycle.eval.run_eval \
    --merged-hf "$RUN_DIR/merged_bf16" \
    --gguf-bf16 "$RUN_DIR/gguf/model.bf16.gguf" \
    --gguf-q4   "$RUN_DIR/gguf/model.q4_K_M.gguf" \
    --out-dir   "$RUN_DIR/eval"
fi

echo "=== [$(date -Is)] PIPELINE COMPLETE ==="
echo "Final GGUF (q4_K_M): $RUN_DIR/gguf/model.q4_K_M.gguf"
echo "Decision: $RUN_DIR/eval/decision.md"
