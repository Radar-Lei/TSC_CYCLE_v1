#!/usr/bin/env bash
set -euo pipefail

ROOT="/home/samuel/TSC_CYCLE"
PY="$ROOT/.venv/bin/python"

if [[ $# -gt 1 ]]; then
  printf 'usage: %s [RUN_ROOT]\n' "$0" >&2
  exit 2
fi

RUN_ROOT="${1:-runs/v4.0-4B-$(date -u +%Y%m%dT%H%M%SZ)}"
case "$RUN_ROOT" in
  runs/v4.0-4B-*|*/runs/v4.0-4B-*) ;;
  *) printf 'RUN_ROOT must match runs/v4.0-4B-*\n' >&2; exit 2 ;;
esac
cd "$ROOT"

"$PY" - <<PY
import json
from pathlib import Path
from tsc_cycle.student.sft_v4 import check_phase8_handoff, validate_run_root
root = validate_run_root(Path("$RUN_ROOT"))
smoke = root / "reports" / "smoke" / "pretrain_smoke_report.json"
if not smoke.exists():
    raise SystemExit(f"missing smoke report: {smoke}")
payload = json.loads(smoke.read_text(encoding="utf-8"))
if payload.get("ok") is not True or payload.get("full_train_allowed") is not True:
    raise SystemExit("Phase 9 smoke report is not green")
phase8 = check_phase8_handoff(Path("artifacts/v4/phase8/phase8_gate_report.json"))
if phase8.get("ok") is not True or phase8.get("next_phase_allowed") is not True:
    raise SystemExit("Phase 8 handoff is not green")
PY

"$ROOT/scripts/dgx_spark/run_safe.sh" 100G -- "$PY" -m tsc_cycle.student.train \
  --phase v4 \
  --mode full \
  --model-name Qwen/Qwen3-4B-Thinking-2507 \
  --tokenized-dir data/v4/phase8/tokenized \
  --phase8-gate-report artifacts/v4/phase8/phase8_gate_report.json \
  --output-root "$RUN_ROOT"

"$PY" - <<PY
import json
from pathlib import Path
root = Path("$RUN_ROOT")
report = root / "training_report.json"
if not report.exists():
    raise SystemExit(f"missing training report: {report}")
payload = json.loads(report.read_text(encoding="utf-8"))
adapter = Path(payload.get("adapter_path", root / "adapter"))
required = {"loss_curve", "duration_seconds", "vram_peak_gb", "adapter_sha256", "data_manifest_sha256"}
missing = sorted(key for key in required if key not in payload)
if payload.get("ok") is not True or missing:
    raise SystemExit(f"bad training report: missing={missing} ok={payload.get('ok')}")
if not (adapter / "adapter_model.safetensors").exists() or not (adapter / "adapter_config.json").exists():
    raise SystemExit(f"missing adapter files under {adapter}")
print(report)
PY
