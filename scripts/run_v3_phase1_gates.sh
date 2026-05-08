#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PY="/home/samuel/TSC_CYCLE/.venv/bin/python"
if [ ! -x "$PY" ]; then
  echo "ERROR: required interpreter missing or not executable: $PY" >&2
  exit 1
fi

# shellcheck source=/dev/null
source scripts/dgx_spark/env.sh
export PYTHONPATH="$ROOT:${PYTHONPATH:-}"

ARTIFACTS="artifacts/v3/phase1"
GGUF_DIR="runs/v3.0-gates/gguf_microconvert"
GGUF_REPORT="$GGUF_DIR/gguf_microconvert.json"
mkdir -p "$ARTIFACTS" "$GGUF_DIR"

echo "=== Phase 1: DGX Spark environment verify ==="
"$PY" scripts/dgx_spark/verify.py

echo "=== Phase 1: run_safe scope check ==="
scripts/dgx_spark/run_safe.sh 100G -- "$PY" -m tsc_cycle.v3_gates.run_safe_scope_check_v3 \
  --out "$ARTIFACTS/run_safe_scope.json"

echo "=== Phase 1: Qwen3.5 env smoke ==="
scripts/dgx_spark/run_safe.sh 100G -- "$PY" -m tsc_cycle.v3_gates.env_smoke_v3 \
  --out "$ARTIFACTS/env_smoke.json"

echo "=== Phase 1: tokenizer audit ==="
"$PY" -m tsc_cycle.v3_gates.tokenizer_audit_v3 \
  --out "$ARTIFACTS/tokenizer_audit.json"

echo "=== Phase 1: GGUF micro-convert ==="
scripts/dgx_spark/run_safe.sh 100G -- "$PY" -m tsc_cycle.v3_gates.gguf_microconvert_v3 \
  --out "$GGUF_DIR"

read -r LLAMA_TOKENIZE TOKENIZER_GGUF < <("$PY" - <<'PY'
import json
from pathlib import Path
report = json.loads(Path("runs/v3.0-gates/gguf_microconvert/gguf_microconvert.json").read_text(encoding="utf-8"))
print(report["llama_tokenize"], report["tokenizer_gguf"])
PY
)

echo "=== Phase 1: tokenizer parity ==="
"$PY" -m tsc_cycle.v3_gates.tokenizer_parity_v3 \
  --llama-tokenize "$LLAMA_TOKENIZE" \
  --gguf "$TOKENIZER_GGUF" \
  --require-gguf \
  --out "$ARTIFACTS/tokenizer_parity.json"

echo "=== Phase 1: memory sweep ==="
scripts/dgx_spark/run_safe.sh 100G -- "$PY" -m tsc_cycle.v3_gates.memory_budget_v3 \
  --model Qwen/Qwen3.5-9B \
  --seqs 1536 2048 2560 3072 4096 \
  --out "$ARTIFACTS/memory_budget.json"

SELECTED_SEQ="$("$PY" - <<'PY'
import json
print(json.load(open("artifacts/v3/phase1/memory_budget.json"))["selected_max_seq"])
PY
)"

echo "=== Phase 1: 100-step dry-run seq=${SELECTED_SEQ} ==="
scripts/dgx_spark/run_safe.sh 100G -- "$PY" -m tsc_cycle.v3_gates.memory_budget_v3 \
  --model Qwen/Qwen3.5-9B \
  --seq "$SELECTED_SEQ" \
  --steps 100 \
  --out "$ARTIFACTS/train_100step.json"

echo "=== Phase 1: fatal gate report ==="
"$PY" -m tsc_cycle.v3_gates.phase1_report \
  --artifacts "$ARTIFACTS" \
  --gguf-report "$GGUF_REPORT" \
  --out "$ARTIFACTS/phase1_gate_report.json"
