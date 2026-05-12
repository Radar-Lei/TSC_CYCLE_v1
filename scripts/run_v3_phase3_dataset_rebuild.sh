#!/usr/bin/env bash
set -euo pipefail

cd /home/samuel/TSC_CYCLE

PYTHON=/home/samuel/TSC_CYCLE/.venv/bin/python

if [[ ! -x "${PYTHON}" ]]; then
  echo "ERROR: missing project python at ${PYTHON}" >&2
  exit 1
fi

for path in \
  data/v3/phase2/labeled_merged.jsonl \
  data/v3/phase2/merge_report.json \
  artifacts/v3/phase1/memory_budget.json \
  artifacts/v3/phase1/tokenizer_audit.json; do
  if [[ ! -f "${path}" ]]; then
    echo "ERROR: missing required Phase 3 input: ${path}" >&2
    exit 1
  fi
done

if ! git diff --quiet -- data/labeled.jsonl; then
  echo "ERROR: data/labeled.jsonl has uncommitted changes before Phase 3 rebuild; refusing to continue." >&2
  exit 1
fi

"${PYTHON}" -m tsc_cycle.v3_gates.dataset_rebuild_v3 \
  --merged-jsonl data/v3/phase2/labeled_merged.jsonl \
  --phase2-report data/v3/phase2/merge_report.json \
  --memory-budget artifacts/v3/phase1/memory_budget.json \
  --tokenizer-audit artifacts/v3/phase1/tokenizer_audit.json \
  --splits-dir data/splits/v3 \
  --tokenized-dir data/tokenized/v3 \
  --report-out data/splits/v3/rebuild_report.json \
  --seed 42 \
  --expected-train 7601 \
  --expected-val 950 \
  --expected-ood-val 950 \
  --max-truncation-rate 0.05

if ! git diff --quiet -- data/labeled.jsonl; then
  echo "ERROR: data/labeled.jsonl changed after Phase 3 rebuild; refusing to continue." >&2
  exit 1
fi
