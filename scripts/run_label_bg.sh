#!/bin/bash
set -euo pipefail
cd /home/samuel/TSC_CYCLE
set -a; source .env; set +a
source scripts/dgx_spark/env.sh
export PYTHONPATH=.
python -m tsc_cycle.teacher.labeler --workers 10 \
  --cost-out runs/p3_full_cost.json \
  --reject-stats runs/p3_full_reject.json \
  >> runs/p3_full.log 2>&1
