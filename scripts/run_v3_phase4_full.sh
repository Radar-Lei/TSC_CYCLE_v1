#!/bin/bash
set -euo pipefail

ROOT=/home/samuel/TSC_CYCLE
cd "$ROOT"
PY=/home/samuel/TSC_CYCLE/.venv/bin/python
RUN_SAFE="$ROOT/scripts/dgx_spark/run_safe.sh"
RUN_SAFE_CONTRACT="run_safe.sh 100G --"
ENV_SH="$ROOT/scripts/dgx_spark/env.sh"
WANDB_PROJECT="tsc-cycle-v3-9b"
V1_ROOT="$ROOT/runs/20260507T032419Z"
FROZEN_MARKER="$V1_ROOT/FROZEN.md"
PHASE1_REPORT="$ROOT/artifacts/v3/phase1/phase1_gate_report.json"
REBUILD_REPORT="$ROOT/data/splits/v3/rebuild_report.json"
TOKENIZED_DIR="$ROOT/data/tokenized/v3"

usage() {
  echo "Usage: $0 RUN_ROOT" >&2
  echo "RUN_ROOT must be an existing $ROOT/runs/v3.0-9B-* dry-run root with dry_run_report.json green." >&2
}

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

[ "$#" -eq 1 ] || { usage; exit 2; }
RUN_ROOT="$1"
DRY_REPORT="$RUN_ROOT/reports/dry-run/dry_run_report.json"
[ -f "$DRY_REPORT" ] || DRY_REPORT="$RUN_ROOT/dry_run_report.json"
MANIFEST="$RUN_ROOT/sft_manifest.json"

# shellcheck source=/home/samuel/TSC_CYCLE/scripts/dgx_spark/env.sh
source "$ENV_SH"
export WANDB_PROJECT

"$PY" - "$RUN_ROOT" <<'PY'
import sys
from tsc_cycle.student.sft_v3 import validate_run_root
validate_run_root(sys.argv[1])
PY

case "$RUN_ROOT" in
  "$ROOT"/runs/v3.0-9B-*) ;;
  *) fail "RUN_ROOT must be under $ROOT/runs/v3.0-9B-{utc}: $RUN_ROOT" ;;
esac
case "$RUN_ROOT" in
  *[";&|\`$<>"$'\n\r']*) fail "RUN_ROOT contains unsafe shell metacharacters: $RUN_ROOT" ;;
esac
[ -d "$RUN_ROOT" ] || fail "RUN_ROOT must already exist from dry-run: $RUN_ROOT"

require_json_ok "$PHASE1_REPORT"
require_json_ok "$REBUILD_REPORT"
require_file "$TOKENIZED_DIR/train.arrow"
require_file "$TOKENIZED_DIR/val.arrow"
require_file "$TOKENIZED_DIR/ood_val.arrow"
require_file "$DRY_REPORT"

"$PY" - "$DRY_REPORT" <<'PY'
import json
import sys
from pathlib import Path
path = Path(sys.argv[1])
payload = json.loads(path.read_text(encoding="utf-8"))
if payload.get("ok") is not True or payload.get("full_run_allowed") is not True:
    raise SystemExit(f"dry-run report must have ok=true and full_run_allowed=true: {payload.get('fatal_failures')}")
if int(payload.get("sample_count", 0)) != 500:
    raise SystemExit("dry-run report sample_count must be 500")
if float(payload.get("ood_hard_constraint_pass_rate", 0.0)) < 0.95:
    raise SystemExit("dry-run report ood_hard_constraint_pass_rate must be >= 0.95")
if float(payload.get("grad_norm_p99", 999.0)) >= 3.0:
    raise SystemExit("dry-run report grad_norm_p99 must be < 3.0")
PY

[ -d "$V1_ROOT" ] || fail "missing v1.0 root: $V1_ROOT"
"$PY" - "$V1_ROOT" <<'PY'
import sys
from tsc_cycle.student.sft_v3 import ensure_v1_frozen
result = ensure_v1_frozen(sys.argv[1])
if result.get("ok") is not True or result.get("write_bits_removed") is not True:
    raise SystemExit(f"FROZEN.md evidence failed before full-run: {result}")
PY
require_file "$FROZEN_MARKER"
[ ! -w "$FROZEN_MARKER" ] || fail "FROZEN.md must be read-only before full-run: $FROZEN_MARKER"

trainer_cmd=(
  "$PY" -m tsc_cycle.student.train
  --mode full
  --data-dir "$TOKENIZED_DIR"
  --output-root "$RUN_ROOT"
  --model Qwen/Qwen3.5-9B
)

"$RUN_SAFE" 100G -- "${trainer_cmd[@]}"

require_file "$MANIFEST"
"$PY" - "$MANIFEST" <<'PY'
import json
import sys
from pathlib import Path
path = Path(sys.argv[1])
payload = json.loads(path.read_text(encoding="utf-8"))
if payload.get("ok") is not True:
    raise SystemExit(f"full-run manifest is not ok: {payload.get('fatal_failures')}")
if payload.get("mode") != "full":
    raise SystemExit("sft_manifest.json mode must be full")
if payload.get("early_stopping_triggered") is not True or payload.get("stop_reason") != "early_stopping":
    raise SystemExit("full-run manifest must prove early_stopping convergence")
if payload.get("wandb_project") != "tsc-cycle-v3-9b":
    raise SystemExit("full-run manifest wandb project mismatch")
adapter = Path(str(payload.get("adapter_path", "")))
if not adapter.exists():
    raise SystemExit(f"adapter path missing: {adapter}")
PY

"$PY" - "$V1_ROOT" <<'PY'
import sys
from tsc_cycle.student.sft_v3 import ensure_v1_frozen
result = ensure_v1_frozen(sys.argv[1])
if result.get("ok") is not True or result.get("write_bits_removed") is not True:
    raise SystemExit(f"FROZEN.md evidence failed after full-run: {result}")
PY
require_file "$FROZEN_MARKER"
[ ! -w "$FROZEN_MARKER" ] || fail "FROZEN.md must remain read-only after full-run: $FROZEN_MARKER"

echo "full-run gate passed: $MANIFEST"
