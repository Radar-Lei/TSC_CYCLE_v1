#!/bin/bash
# Sequential driver for phases 3 → 4 → 5 → 6.
#
# Usage:
#   export OPENAI_API_KEY=sk-...
#   bash scripts/run_pipeline.sh
#
# Each phase is idempotent and resumable.
set -euo pipefail

# shellcheck source=/dev/null
source scripts/dgx_spark/env.sh
export PYTHONPATH="$(pwd):${PYTHONPATH:-}"

TS="${TS:-$(date -u +%Y%m%dT%H%M%SZ)}"
RUN_DIR="runs/${TS}"
mkdir -p "$RUN_DIR"
ln -sfn "$TS" runs/latest

# ─── Phase 3: Teacher Labeling ─────────────────────────────────────────────
if [ ! -f data/labeled.jsonl ] || [ "$(wc -l < data/labeled.jsonl)" -lt 2700 ]; then
  echo "=== Phase 3: Teacher Labeling ==="
  if [ -z "${OPENAI_API_KEY:-}" ]; then
    echo "ERROR: OPENAI_API_KEY not set." >&2
    exit 1
  fi

  # 50-sample smoke first
  if [ ! -f "$RUN_DIR/teacher_smoke.json" ]; then
    echo "--- 50-sample smoke ---"
    python -m tsc_cycle.teacher.labeler --limit 50 \
      --cost-out "$RUN_DIR/teacher_smoke_cost.json" \
      --reject-stats "$RUN_DIR/teacher_smoke_reject.json"
    cp "$RUN_DIR/teacher_smoke_cost.json" "$RUN_DIR/teacher_smoke.json"
  fi

  echo "--- full labeling ---"
  python -m tsc_cycle.teacher.labeler --workers 10 \
    --cost-out "$RUN_DIR/teacher_cost.json" \
    --reject-stats "$RUN_DIR/teacher_reject_stats.json"
fi

# ─── Phase 4: Dataset build + QLoRA SFT ─────────────────────────────────────
if [ ! -f data/tokenized/train/data.parquet ]; then
  echo "=== Phase 4a: Dataset build ==="
  python -m tsc_cycle.student.dataset
fi

ADAPTER_DIR="$RUN_DIR/train/adapter"
if [ ! -d "$ADAPTER_DIR" ]; then
  echo "=== Phase 4b: QLoRA SFT (run_safe.sh wrapper) ==="
  scripts/dgx_spark/run_safe.sh 100G -- python -m tsc_cycle.student.train \
    --output-dir "$RUN_DIR/train"
fi

# ─── Phase 5: Merge + GGUF Export ───────────────────────────────────────────
if [ ! -f "$RUN_DIR/gguf/model.q4_K_M.gguf" ]; then
  echo "=== Phase 5: Merge + GGUF Export ==="
  python -m tsc_cycle.student.export_gguf --adapter "$ADAPTER_DIR" --out "$RUN_DIR"
fi

# Optional: parity test
if [ ! -f "$RUN_DIR/parity.json" ]; then
  echo "--- Parity check (20 OOD prompts) ---"
  python -m tsc_cycle.eval.parity \
    --merged-hf "$RUN_DIR/merged_bf16" \
    --gguf-bf16 "$RUN_DIR/gguf/model.bf16.gguf" \
    --gguf-q4   "$RUN_DIR/gguf/model.q4_K_M.gguf" \
    --out "$RUN_DIR/parity.json"
fi

# ─── Phase 6: Evaluation Suite ──────────────────────────────────────────────
if [ ! -f "$RUN_DIR/eval/decision.md" ]; then
  echo "=== Phase 6: Evaluation Suite ==="
  python -m tsc_cycle.eval.run_eval \
    --merged-hf "$RUN_DIR/merged_bf16" \
    --gguf-bf16 "$RUN_DIR/gguf/model.bf16.gguf" \
    --gguf-q4   "$RUN_DIR/gguf/model.q4_K_M.gguf" \
    --out-dir   "$RUN_DIR/eval"
fi

echo
echo "=== ALL PHASES COMPLETE ==="
echo "Final GGUF (q4_K_M): $RUN_DIR/gguf/model.q4_K_M.gguf"
echo "Decision: $RUN_DIR/eval/decision.md"
echo "Report:   $RUN_DIR/eval/report.md"
