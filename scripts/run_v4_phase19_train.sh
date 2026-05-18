#!/usr/bin/env bash
set -euo pipefail

ROOT="/home/samuel/TSC_CYCLE"
PY="$ROOT/.venv/bin/python"

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
export TRITON_PTXAS_PATH="${TRITON_PTXAS_PATH:-/usr/local/cuda/bin/ptxas}"

RUN_ROOT="$RUN_ROOT" "$PY" - <<'PY'
import os
from pathlib import Path
from tsc_cycle.student.sft_v42 import check_phase18_handoff, validate_run_root
root = validate_run_root(Path(os.environ["RUN_ROOT"]))
phase18 = check_phase18_handoff(Path("artifacts/v4_2/phase18/reconstruction_report.json"))
if phase18.get("ok") is not True or phase18.get("next_phase_allowed") is not True:
    raise SystemExit("Phase 18 handoff is not green")
manifest = Path("data/v4_2/phase18/tokenized/manifest.json")
if not manifest.exists():
    raise SystemExit(f"missing tokenized manifest: {manifest}")
PY

"$ROOT/scripts/dgx_spark/run_safe.sh" 100G -- "$PY" -m tsc_cycle.student.train \
  --phase v4_2 \
  --mode full \
  --model-name Qwen/Qwen3-4B-Thinking-2507 \
  --tokenized-dir data/v4_2/phase18/tokenized \
  --phase18-report artifacts/v4_2/phase18/reconstruction_report.json \
  --output-root "$RUN_ROOT"

"$PY" -m tsc_cycle.v4_gates.phase19_training validate-report \
  --run-root "$RUN_ROOT" \
  --report-path "$RUN_ROOT/phase19_sft_report.json"
