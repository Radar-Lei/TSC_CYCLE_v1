#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="/home/samuel/TSC_CYCLE"
RUN_ROOT="${PROJECT_ROOT}/runs/v4.0-4B-20260509T184844Z"
GGUF_DIR="${RUN_ROOT}/gguf"
PYTHON="${PROJECT_ROOT}/.venv/bin/python"
LLAMA_SERVER="/home/samuel/llama.cpp/build/bin/llama-server"
export PYTHONPATH="${PROJECT_ROOT}:${PYTHONPATH:-}"
cd "${PROJECT_ROOT}"

"${PYTHON}" - <<'PY'
import json
from pathlib import Path
root = Path('/home/samuel/TSC_CYCLE/runs/v4.0-4B-20260509T184844Z')
for rel in ['phase10_export_report.json', 'gguf/tokenizer_parity.json']:
    p = root / rel
    d = json.loads(p.read_text(encoding='utf-8'))
    assert d.get('ok') is True, (p, d.get('fatal_failures'))
print(root)
PY

if [[ ! -x "${LLAMA_SERVER}" ]]; then
  echo "missing executable llama-server: ${LLAMA_SERVER}" >&2
  exit 1
fi

"${PYTHON}" -m tsc_cycle.student.parity \
  --merged-hf "${RUN_ROOT}/merged_hf" \
  --gguf-bf16 "${GGUF_DIR}/model.fp16.gguf" \
  --gguf-q4 "${GGUF_DIR}/model.q4_K_M.gguf" \
  --prompts "${GGUF_DIR}/tokenizer_parity_prompts.jsonl" \
  --hf-out "${GGUF_DIR}/parity_hf.json" \
  --bf16-out "${GGUF_DIR}/parity_gguf_fp16.json" \
  --q4-out "${GGUF_DIR}/parity_gguf_q4.json" \
  --report "${GGUF_DIR}/parity_report.json" \
  --llama-server "${LLAMA_SERVER}" \
  --n-predict 256 \
  --timeout-sec 600

"${PYTHON}" -m tsc_cycle.v4_gates.phase10_report \
  --run-root "${RUN_ROOT}" \
  --out "${RUN_ROOT}/phase10_gguf_report.json"
