#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="/home/samuel/TSC_CYCLE"
RUN_ROOT="/home/samuel/TSC_CYCLE/runs/v4.0-4B-20260509T184844Z"
PHASE11_ROOT="${RUN_ROOT}/eval_phase11"
FROZEN_V1_ROOT="/home/samuel/TSC_CYCLE/runs/20260507T032419Z"
PYTHON="/home/samuel/TSC_CYCLE/.venv/bin/python"
LLAMA_SERVER="/home/samuel/llama.cpp/build/bin/llama-server"
export PYTHONPATH="${PROJECT_ROOT}:${PYTHONPATH:-}"
cd "${PROJECT_ROOT}"

"${PYTHON}" - <<'PY'
import json
from pathlib import Path
report = Path('/home/samuel/TSC_CYCLE/runs/v4.0-4B-20260509T184844Z/phase10_gguf_report.json')
data = json.loads(report.read_text(encoding='utf-8'))
assert data.get('ok') is True, data.get('fatal_failures')
assert data.get('next_phase_allowed') is True, data
assert (data.get('phase11_handoff') or {}).get('allowed') is True, data.get('phase11_handoff')
paths = (data.get('artifact_manifest') or {}).get('paths') or {}
expected = {
    'merged_hf': '/home/samuel/TSC_CYCLE/runs/v4.0-4B-20260509T184844Z/merged_hf',
    'gguf_q4_K_M': '/home/samuel/TSC_CYCLE/runs/v4.0-4B-20260509T184844Z/gguf/model.q4_K_M.gguf',
}
for key, value in expected.items():
    assert paths.get(key) == value, (key, paths.get(key), value)
    assert Path(value).exists(), value
print('[PHASE11] Phase 10 handoff OK:', report)
PY

if [[ ! -x "${LLAMA_SERVER}" ]]; then
  echo "missing executable llama-server: ${LLAMA_SERVER}" >&2
  exit 1
fi

"${PYTHON}" -m tsc_cycle.eval.phase11_matrix \
  --run-root "${RUN_ROOT}" \
  --out-root "${PHASE11_ROOT}" \
  --frozen-v1-root "${FROZEN_V1_ROOT}" \
  --phase10-report "${RUN_ROOT}/phase10_gguf_report.json" \
  --labeled "${PROJECT_ROOT}/data/v4/phase8/labeled_merged.jsonl" \
  --alignment "${PROJECT_ROOT}/data/v4/phase8/splits/v1_ood_alignment.json" \
  --seed 42 \
  --n-id 300 \
  --n-expanded-ood 300

"${PROJECT_ROOT}/scripts/dgx_spark/run_safe.sh" 100G -- "${PYTHON}" -m tsc_cycle.eval.generate_hf \
  --merged-hf "${RUN_ROOT}/merged_hf" \
  --prompts "${PHASE11_ROOT}/eval_prompts.jsonl" \
  --cache-dir "${PHASE11_ROOT}/gen_cache/v4_hf"

"${PYTHON}" -m tsc_cycle.eval.generate_gguf \
  --gguf-path "${RUN_ROOT}/gguf/model.q4_K_M.gguf" \
  --backend-label v4_gguf_q4_k_m \
  --prompts "${PHASE11_ROOT}/eval_prompts.jsonl" \
  --cache-dir "${PHASE11_ROOT}/gen_cache/v4_gguf_q4_k_m" \
  --llama-server "${LLAMA_SERVER}"

echo "[PHASE11] Frozen v1 baseline is read-only evidence only:"
echo "[PHASE11]   prompts: ${FROZEN_V1_ROOT}/eval/eval_prompts.jsonl"
echo "[PHASE11]   per_sample: ${FROZEN_V1_ROOT}/eval/per_sample.jsonl"
echo "[PHASE11]   cache: ${FROZEN_V1_ROOT}/eval/gen_cache/gguf_q4_k_m"
echo "[PHASE11] OK matrix prompts and v4 caches are under ${PHASE11_ROOT}"
