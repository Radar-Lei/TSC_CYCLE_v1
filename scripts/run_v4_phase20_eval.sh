#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT=/home/samuel/TSC_CYCLE
PYTHON=/home/samuel/TSC_CYCLE/.venv/bin/python
RUN_ROOT=${1:-/home/samuel/TSC_CYCLE/runs/v4.2-4B-20260518T111519Z}
MERGED_HF=/home/samuel/TSC_CYCLE/runs/v4.2-4B-20260518T111519Z/merged_hf
ARTIFACT_ROOT=/home/samuel/TSC_CYCLE/artifacts/v4_2/phase20

case "$RUN_ROOT" in
  runs/v4.2-4B-*|/home/samuel/TSC_CYCLE/runs/v4.2-4B-*) ;;
  *) printf 'RUN_ROOT must match runs/v4.2-4B-*\n' >&2; exit 2 ;;
esac

case "$RUN_ROOT" in
  runs/v4.0-4B-*|*/runs/v4.0-4B-*) printf 'RUN_ROOT must match runs/v4.2-4B-*\n' >&2; exit 2 ;;
esac

export PYTHONPATH="$PROJECT_ROOT${PYTHONPATH:+:$PYTHONPATH}"

"$PYTHON" -m tsc_cycle.v4_gates.phase20_eval build-prompts \
  --run-root /home/samuel/TSC_CYCLE/runs/v4.2-4B-20260518T111519Z \
  --labeled /home/samuel/TSC_CYCLE/data/v4_2/phase18/labeled_calibrated.jsonl \
  --split-index /home/samuel/TSC_CYCLE/data/v4_2/phase18/splits/val.index.jsonl \
  --split-index /home/samuel/TSC_CYCLE/data/v4_2/phase18/splits/ood_val.index.jsonl \
  --out /home/samuel/TSC_CYCLE/artifacts/v4_2/phase20/eval_prompts.jsonl \
  --manifest /home/samuel/TSC_CYCLE/artifacts/v4_2/phase20/eval_prompt_manifest.json

/home/samuel/TSC_CYCLE/scripts/dgx_spark/run_safe.sh 100G -- /home/samuel/TSC_CYCLE/.venv/bin/python -m tsc_cycle.eval.generate_hf \
  --merged-hf /home/samuel/TSC_CYCLE/runs/v4.2-4B-20260518T111519Z/merged_hf \
  --prompts /home/samuel/TSC_CYCLE/artifacts/v4_2/phase20/eval_prompts.jsonl \
  --cache-dir /home/samuel/TSC_CYCLE/artifacts/v4_2/phase20/gen_cache/v4_2_hf \
  --n-predict 384

"$PYTHON" -m tsc_cycle.v4_gates.phase20_eval normalize-outputs \
  --prompts /home/samuel/TSC_CYCLE/artifacts/v4_2/phase20/eval_prompts.jsonl \
  --cache-dir /home/samuel/TSC_CYCLE/artifacts/v4_2/phase20/gen_cache/v4_2_hf \
  --out /home/samuel/TSC_CYCLE/artifacts/v4_2/phase20/eval_outputs.jsonl

"$PYTHON" -m tsc_cycle.v4_gates.phase20_eval evaluate \
  --run-root /home/samuel/TSC_CYCLE/runs/v4.2-4B-20260518T111519Z \
  --outputs /home/samuel/TSC_CYCLE/artifacts/v4_2/phase20/eval_outputs.jsonl \
  --report /home/samuel/TSC_CYCLE/artifacts/v4_2/phase20/eval_report.json
