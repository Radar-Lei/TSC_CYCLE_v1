#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="/home/samuel/TSC_CYCLE"
RUN_ROOT="${PROJECT_ROOT}/runs/v4.0-4B-20260509T184844Z"
EXPORT_REPORT="${RUN_ROOT}/phase10_export_report.json"
MERGED_HF="${RUN_ROOT}/merged_hf"
GGUF="${RUN_ROOT}/gguf/model.fp16.gguf"
PROMPT_FIXTURE="${RUN_ROOT}/gguf/tokenizer_parity_prompts.jsonl"
OUT="${RUN_ROOT}/gguf/tokenizer_parity.json"
PYTHON="${PROJECT_ROOT}/.venv/bin/python"
export PYTHONPATH="${PROJECT_ROOT}:${PYTHONPATH:-}"
cd "${PROJECT_ROOT}"

if [[ -x "/home/samuel/projects/EvoProgTSC/llama.cpp/llama-tokenize" ]]; then
  LLAMA_TOKENIZE="/home/samuel/projects/EvoProgTSC/llama.cpp/llama-tokenize"
elif [[ -x "/home/samuel/projects/EvoProgTSC/llama.cpp/llama-cli" ]]; then
  LLAMA_TOKENIZE="/home/samuel/projects/EvoProgTSC/llama.cpp/llama-cli"
else
  echo "missing llama-tokenize/llama-cli under /home/samuel/projects/EvoProgTSC/llama.cpp" >&2
  exit 1
fi

"${PYTHON}" - <<'PY'
import json
from pathlib import Path
p = Path('/home/samuel/TSC_CYCLE/runs/v4.0-4B-20260509T184844Z/phase10_export_report.json')
d = json.loads(p.read_text(encoding='utf-8'))
assert d.get('ok') is True, d
assert d.get('next_phase_allowed') is True, d
assert Path(d['paths']['merged_hf']).exists(), d
assert Path(d['paths']['gguf_fp16']).exists(), d
print(p)
PY

"${PYTHON}" -m tsc_cycle.v4_gates.phase10_tokenizer_parity \
  --merged-hf "${MERGED_HF}" \
  --gguf "${GGUF}" \
  --llama-tokenize "${LLAMA_TOKENIZE}" \
  --prompt-fixture "${PROMPT_FIXTURE}" \
  --out "${OUT}"
