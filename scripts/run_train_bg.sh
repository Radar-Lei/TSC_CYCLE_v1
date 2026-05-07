#!/bin/bash
# Phase 4b training driver — bypasses sudo systemd-run.
# Manually applies OOM protection (oom_score_adj) since systemd-run is unavailable.
set -euo pipefail
cd /home/samuel/TSC_CYCLE
set -a; source .env; set +a
source scripts/dgx_spark/env.sh
export PYTHONPATH=.

TS="${TS:-$(cat runs/.current_ts 2>/dev/null | cut -d= -f2 || date -u +%Y%m%dT%H%M%SZ)}"
RUN_DIR="runs/${TS}"
mkdir -p "$RUN_DIR/train"

# OOM protection (no sudo): make this process kill-first if memory pressure
echo 500 > /proc/self/oom_score_adj 2>/dev/null || true

# Verify swap off
if [ "$(awk '/SwapTotal/{print $2}' /proc/meminfo)" -gt 0 ]; then
  echo "ERROR: swap is enabled. Disable with 'sudo swapoff -a' first."
  exit 1
fi

# Verify enough free memory (need 60GB+)
FREE_GB=$(awk '/MemAvailable/{printf "%.0f", $2/1024/1024}' /proc/meminfo)
if [ "$FREE_GB" -lt 60 ]; then
  echo "ERROR: only ${FREE_GB}GB MemAvailable; need ≥60GB."
  exit 1
fi
echo "[$(date -Is)] starting train: ${FREE_GB}GB free, swap off, oom_score_adj=500"

# Smaller per-device batch (bs=1, grad_accum=32) — same effective batch (32)
# but ~4x lower peak activation memory. Previous bs=4 runs OOM-died at step 1.
exec python -m tsc_cycle.student.train \
  --output-dir "$RUN_DIR/train" \
  --batch-size 1 \
  --grad-accum 32
