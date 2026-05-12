#!/usr/bin/env bash
set -euo pipefail

ROOT="/home/samuel/TSC_CYCLE"
PY="$ROOT/.venv/bin/python"
ART="$ROOT/artifacts/v4/phase7"

mkdir -p "$ART"

PYTHONPATH="$ROOT" "$PY" -m tsc_cycle.v4_gates.phase7_protocol \
  --out "$ART/protocol_fixture.json"

PYTHONPATH="$ROOT" "$PY" -m tsc_cycle.v4_gates.phase7_baseline \
  --environment-out "$ART/environment.json" \
  --baseline-out "$ART/baseline_readonly.json"

PYTHONPATH="$ROOT" "$PY" -m tsc_cycle.v4_gates.phase7_tokenizer \
  --out "$ART/tokenizer_audit.json"

PYTHONPATH="$ROOT" "$PY" -m tsc_cycle.v4_gates.phase7_report \
  --artifacts "$ART" \
  --out "$ART/phase7_gate_report.json"
