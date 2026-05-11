#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="/home/samuel/TSC_CYCLE"
PYTHON="/home/samuel/TSC_CYCLE/.venv/bin/python"
REALITY_LOG="/home/samuel/TSC_CYCLE/reality.log"
OUT_LOG="/home/samuel/TSC_CYCLE/reality_test.log"
ARTIFACT_ROOT="/home/samuel/TSC_CYCLE/artifacts/v4/phase12"
GGUF_PATH="/home/samuel/TSC_CYCLE/runs/v4.0-4B-20260509T184844Z/gguf/model.q4_K_M.gguf"
LLAMA_SERVER="/home/samuel/llama.cpp/build/bin/llama-server"
PHASE11_REPORT="/home/samuel/TSC_CYCLE/artifacts/v4/phase11/phase11_gate_report.json"
BACKEND_LABEL="tsc-cycle-v4-q4_K_M"

export PYTHONPATH="${PROJECT_ROOT}:${PYTHONPATH:-}"
cd "${PROJECT_ROOT}"

if [[ ! -x "${PYTHON}" ]]; then
  echo "missing python executable: ${PYTHON}" >&2
  exit 1
fi

if [[ ! -f "${REALITY_LOG}" ]]; then
  echo "missing reality input log: ${REALITY_LOG}" >&2
  exit 1
fi

if [[ ! -f "${GGUF_PATH}" ]]; then
  echo "missing Phase 11 recommended GGUF artifact: ${GGUF_PATH}" >&2
  exit 1
fi

if [[ ! -x "${LLAMA_SERVER}" ]]; then
  echo "missing executable llama-server: ${LLAMA_SERVER}" >&2
  exit 1
fi

"${PYTHON}" - <<'PY'
import json
from pathlib import Path
report_path = Path('/home/samuel/TSC_CYCLE/artifacts/v4/phase11/phase11_gate_report.json')
if not report_path.exists():
    raise SystemExit(f'missing Phase 11 gate report: {report_path}')
report = json.loads(report_path.read_text(encoding='utf-8'))
expected = '/home/samuel/TSC_CYCLE/runs/v4.0-4B-20260509T184844Z/gguf/model.q4_K_M.gguf'
if report.get('ok') is not True:
    raise SystemExit(f'Phase 11 report is not ok: {report.get("fatal_failures")}')
if report.get('next_phase_allowed') is not True:
    raise SystemExit('Phase 11 report does not allow next phase')
if report.get('recommended_artifact') != expected:
    raise SystemExit(f'Phase 11 recommended artifact mismatch: {report.get("recommended_artifact")} != {expected}')
print(f'[PHASE12] Phase 11 GO handoff OK: {report_path}')
PY

mkdir -p "${ARTIFACT_ROOT}"

"${PYTHON}" -m tsc_cycle.v4_gates.phase12_reality_test \
  --reality-log "${REALITY_LOG}" \
  --out-log "${OUT_LOG}" \
  --artifact-root "${ARTIFACT_ROOT}" \
  --gguf-path "${GGUF_PATH}" \
  --llama-server "${LLAMA_SERVER}" \
  --backend-label "${BACKEND_LABEL}" \
  --resume \
  --n-predict 384 \
  --retry-n-predict 768 \
  --timeout-sec 600 \
  --ngl 99 \
  --threads 4 \
  --ctx-size 4096

echo "[PHASE12] complete: ${OUT_LOG}"
