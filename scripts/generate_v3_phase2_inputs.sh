#!/usr/bin/env bash
set -euo pipefail

ROOT="/home/samuel/TSC_CYCLE"
PYTHON="/home/samuel/TSC_CYCLE/.venv/bin/python"

"${PYTHON}" -m tsc_cycle.sample_inputs \
  --v3-phase2 \
  --prior "${ROOT}/data/dist_prior.json" \
  --exclude-labeled "${ROOT}/data/labeled.jsonl" \
  --per-sample "${ROOT}/runs/20260507T032419Z/eval/per_sample.jsonl" \
  --out-dir "${ROOT}/data/v3/phase2" \
  --same-dist 5250 \
  --ood 1500 \
  --targeted 750 \
  --seed 42
