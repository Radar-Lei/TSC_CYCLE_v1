#!/usr/bin/env bash
set -euo pipefail

cd /home/samuel/TSC_CYCLE

if [[ -z "${OPENAI_API_KEY:-}" ]]; then
  printf 'ERROR: OPENAI_API_KEY is not set; export it before running Phase 2 smoke labeling.\n' >&2
  exit 2
fi

git diff --quiet -- data/labeled.jsonl

/home/samuel/TSC_CYCLE/.venv/bin/python -m tsc_cycle.teacher.labeler \
  --input-files data/v3/phase2/inputs_all.jsonl \
  --exclude-labeled data/labeled.jsonl \
  --labeled data/v3/phase2/labeled_new.smoke.jsonl \
  --rejected data/v3/phase2/rejected_new.smoke.jsonl \
  --cache-dir raw_responses/v3_phase2_smoke \
  --workers 5 \
  --limit 50 \
  --model gpt-5.5 \
  --effort high

git diff --quiet -- data/labeled.jsonl
