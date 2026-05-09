#!/bin/bash
set -euo pipefail

ROOT=/home/samuel/TSC_CYCLE
PY=/home/samuel/TSC_CYCLE/.venv/bin/python
RUN_SAFE="$ROOT/scripts/dgx_spark/run_safe.sh"
ENV_SH="$ROOT/scripts/dgx_spark/env.sh"
UTC="${RUN_UTC:-$(date -u +%Y%m%dT%H%M%SZ)}"
RUN_ROOT="${RUN_ROOT:-$ROOT/runs/v3.0-9B-${UTC}}"
WANDB_PROJECT="tsc-cycle-v3-9b"
V1_ROOT="$ROOT/runs/20260507T032419Z"
FROZEN_MARKER="$V1_ROOT/FROZEN.md"
PHASE1_REPORT="$ROOT/artifacts/v3/phase1/phase1_gate_report.json"
REBUILD_REPORT="$ROOT/data/splits/v3/rebuild_report.json"
TOKENIZED_DIR="$ROOT/data/tokenized/v3"
MERGED_JSONL="$ROOT/data/v3/phase2/labeled_merged.jsonl"
OOD_INDEX="$ROOT/data/splits/v3/ood_val.index.jsonl"
GRAD_GATE="$RUN_ROOT/reports/dry-run/grad_gate.json"
DRY_REPORT="$RUN_ROOT/reports/dry-run/dry_run_report.json"
EVIDENCE_JSONL="$RUN_ROOT/reports/dry-run/dry_run_ood_generations.jsonl"

# shellcheck source=/home/samuel/TSC_CYCLE/scripts/dgx_spark/env.sh
source "$ENV_SH"
export WANDB_PROJECT

fail() {
  echo "ERROR: $*" >&2
  exit 1
}

require_file() {
  local path="$1"
  [ -f "$path" ] || fail "missing required file: $path"
}

require_json_ok() {
  local path="$1"
  require_file "$path"
  "$PY" - "$path" <<'PY'
import json
import sys
from pathlib import Path
path = Path(sys.argv[1])
payload = json.loads(path.read_text(encoding="utf-8"))
if payload.get("ok") is not True:
    raise SystemExit(f"{path} must have ok=true")
PY
}

case "$RUN_ROOT" in
  "$ROOT"/runs/v3.0-9B-*) ;;
  *) fail "RUN_ROOT must be under $ROOT/runs/v3.0-9B-{utc}: $RUN_ROOT" ;;
esac
case "$RUN_ROOT" in
  *[";&|\`$<>"$'\n\r']*) fail "RUN_ROOT contains unsafe shell metacharacters: $RUN_ROOT" ;;
esac

require_json_ok "$PHASE1_REPORT"
require_json_ok "$REBUILD_REPORT"
require_file "$TOKENIZED_DIR/train.arrow"
require_file "$TOKENIZED_DIR/val.arrow"
require_file "$TOKENIZED_DIR/ood_val.arrow"
require_file "$MERGED_JSONL"
require_file "$OOD_INDEX"
[ -d "$V1_ROOT" ] || fail "missing v1.0 root: $V1_ROOT"

"$PY" - "$V1_ROOT" <<'PY'
import sys
from tsc_cycle.student.sft_v3 import ensure_v1_frozen
result = ensure_v1_frozen(sys.argv[1])
if result.get("ok") is not True or result.get("write_bits_removed") is not True:
    raise SystemExit(f"FROZEN.md evidence failed before dry-run: {result}")
PY
require_file "$FROZEN_MARKER"
[ ! -w "$FROZEN_MARKER" ] || fail "FROZEN.md must be read-only before dry-run: $FROZEN_MARKER"

mkdir -p "$RUN_ROOT/reports/dry-run"
start_epoch=$(date +%s)

trainer_cmd=(
  "$PY" -m tsc_cycle.student.train
  --mode dry-run
  --data-dir "$TOKENIZED_DIR"
  --output-root "$RUN_ROOT"
  --max-steps 200
)

"$ROOT/scripts/dgx_spark/run_safe.sh" 100G -- "${trainer_cmd[@]}"

end_epoch=$(date +%s)
elapsed_seconds=$((end_epoch - start_epoch))
if [ "$elapsed_seconds" -gt 3600 ]; then
  fail "dry-run exceeded 3600 seconds: ${elapsed_seconds}"
fi

require_file "$GRAD_GATE"

"$PY" -m tsc_cycle.v3_gates.sft_dry_run_v3 \
  --run-root "$RUN_ROOT" \
  --grad-gate "$GRAD_GATE" \
  --adapter-path "$RUN_ROOT/adapter" \
  --merged-jsonl "$MERGED_JSONL" \
  --ood-index "$OOD_INDEX" \
  --evidence-out "$EVIDENCE_JSONL" \
  --report-out "$DRY_REPORT" \
  --elapsed-seconds "$elapsed_seconds" \
  --sample-count 500

"$PY" - "$DRY_REPORT" <<'PY'
import json
import sys
from pathlib import Path
path = Path(sys.argv[1])
payload = json.loads(path.read_text(encoding="utf-8"))
if payload.get("ok") is not True or payload.get("full_run_allowed") is not True:
    raise SystemExit(f"dry-run gate failed: {payload.get('fatal_failures')}")
if int(payload.get("sample_count", 0)) != 500:
    raise SystemExit("dry-run report sample_count must be 500")
if float(payload.get("elapsed_seconds", 10**9)) > 3600:
    raise SystemExit("dry-run report elapsed_seconds exceeds 3600")
PY

"$PY" - "$V1_ROOT" <<'PY'
import sys
from tsc_cycle.student.sft_v3 import ensure_v1_frozen
result = ensure_v1_frozen(sys.argv[1])
if result.get("ok") is not True or result.get("write_bits_removed") is not True:
    raise SystemExit(f"FROZEN.md evidence failed after dry-run: {result}")
PY
require_file "$FROZEN_MARKER"
[ ! -w "$FROZEN_MARKER" ] || fail "FROZEN.md must remain read-only after dry-run: $FROZEN_MARKER"

echo "dry-run gate passed: $DRY_REPORT"
