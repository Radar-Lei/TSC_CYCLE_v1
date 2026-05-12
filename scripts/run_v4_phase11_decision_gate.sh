#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="/home/samuel/TSC_CYCLE"
PYTHON="$PROJECT_ROOT/.venv/bin/python"
PHASE11_ROOT="$PROJECT_ROOT/runs/v4.0-4B-20260509T184844Z/eval_phase11"
METRICS="$PHASE11_ROOT/metrics.json"
PHASE10_REPORT="$PROJECT_ROOT/runs/v4.0-4B-20260509T184844Z/phase10_gguf_report.json"
DECISION_MD="$PHASE11_ROOT/decision.md"
GATE_REPORT="$PROJECT_ROOT/artifacts/v4/phase11/phase11_gate_report.json"

mkdir -p "$PROJECT_ROOT/artifacts/v4/phase11"

set +e
"$PYTHON" -m tsc_cycle.eval.phase11_decision \
  --metrics "$METRICS" \
  --phase10-report "$PHASE10_REPORT" \
  --out-decision "$DECISION_MD"
DECISION_STATUS=$?

"$PYTHON" -m tsc_cycle.v4_gates.phase11_eval_report \
  --metrics "$METRICS" \
  --phase10-report "$PHASE10_REPORT" \
  --matrix-manifest "$PHASE11_ROOT/matrix_manifest.json" \
  --decision-md "$DECISION_MD" \
  --report-md "$PHASE11_ROOT/report.md" \
  --per-sample "$PHASE11_ROOT/per_sample.jsonl" \
  --frozen-v1-per-sample "$PROJECT_ROOT/runs/20260507T032419Z/eval/per_sample.jsonl" \
  --out "$GATE_REPORT"
REPORT_STATUS=$?
set -e

if [ "$REPORT_STATUS" -ne 0 ]; then
  echo "[PHASE11-DECISION] fail-closed report written: $GATE_REPORT" >&2
  exit "$REPORT_STATUS"
fi

exit "$DECISION_STATUS"
