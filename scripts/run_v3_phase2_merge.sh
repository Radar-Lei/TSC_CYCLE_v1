#!/usr/bin/env bash
set -euo pipefail

cd /home/samuel/TSC_CYCLE

PYTHON=/home/samuel/TSC_CYCLE/.venv/bin/python

if ! git diff --quiet -- data/labeled.jsonl; then
  echo "ERROR: data/labeled.jsonl has uncommitted changes before merge; refusing to continue." >&2
  exit 1
fi

"${PYTHON}" -m tsc_cycle.v3_gates.phase2_datagen_report \
  --old-labeled data/labeled.jsonl \
  --new-labeled data/v3/phase2/labeled_new.jsonl \
  --rejected data/v3/phase2/rejected_new.jsonl \
  --datagen-manifest data/v3/phase2/datagen_manifest.json \
  --merged-out data/v3/phase2/labeled_merged.jsonl \
  --report-out data/v3/phase2/merge_report.json \
  --min-new-valid 6000 \
  --min-merged-valid 9000 \
  --labeler-model gpt-5.5 \
  --labeler-effort high \
  --workers-max 10

if ! git diff --quiet -- data/labeled.jsonl; then
  echo "ERROR: data/labeled.jsonl changed after merge; refusing to continue." >&2
  exit 1
fi
