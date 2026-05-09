#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="/home/samuel/TSC_CYCLE"
PYTHON="/home/samuel/TSC_CYCLE/.venv/bin/python"

PYTHONPATH="${PROJECT_ROOT}" "${PYTHON}" -m tsc_cycle.v4_gates.dataset_rebuild \
  --phase7-gate-report "/home/samuel/TSC_CYCLE/artifacts/v4/phase7/phase7_gate_report.json" \
  --v1-valid-labeled "/home/samuel/TSC_CYCLE/data/labeled.jsonl" \
  --v3-new-lint-pass-labeled "/home/samuel/TSC_CYCLE/data/v3/phase2/labeled_new.jsonl" \
  --merged-output "/home/samuel/TSC_CYCLE/data/v4/phase8/labeled_merged.jsonl" \
  --split-dir "/home/samuel/TSC_CYCLE/data/v4/phase8/splits" \
  --tokenized-dir "/home/samuel/TSC_CYCLE/data/v4/phase8/tokenized" \
  --artifacts-dir "/home/samuel/TSC_CYCLE/artifacts/v4/phase8" \
  --model-name "Qwen/Qwen3-4B-Thinking-2507" \
  --seed 42 \
  --max-truncation-rate 0.05

PYTHONPATH="${PROJECT_ROOT}" "${PYTHON}" -m tsc_cycle.v4_gates.phase8_report \
  --phase7-gate-report "/home/samuel/TSC_CYCLE/artifacts/v4/phase7/phase7_gate_report.json" \
  --source-manifest "/home/samuel/TSC_CYCLE/artifacts/v4/phase8/source_manifest.json" \
  --cleaning-report "/home/samuel/TSC_CYCLE/artifacts/v4/phase8/cleaning_report.json" \
  --rebuild-report "/home/samuel/TSC_CYCLE/artifacts/v4/phase8/rebuild_report.json" \
  --dataset-card "/home/samuel/TSC_CYCLE/data/dataset_card.md" \
  --out "/home/samuel/TSC_CYCLE/artifacts/v4/phase8/phase8_gate_report.json"
