#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
MEMORY_MAX="${1:-100G}"

if [ "${2:-}" = "--" ]; then
    shift 2
else
    echo "Usage: $0 [MemoryMax] -- <command> [args...]"
    exit 2
fi

# shellcheck source=/dev/null
source "$PROJECT_DIR/scripts/dgx_spark/env.sh"

free_gb=$(awk '/MemAvailable/ {printf "%.0f", $2/1024/1024}' /proc/meminfo)
if [ "$free_gb" -lt 60 ]; then
    echo "ERROR: only ${free_gb}GB MemAvailable; clean up before training."
    exit 1
fi

exec sudo systemd-run --scope \
    --uid="$(id -un)" \
    --gid="$(id -gn)" \
    --expand-environment=no \
    -p "MemoryMax=$MEMORY_MAX" \
    -p MemorySwapMax=0 \
    --same-dir \
    --setenv="CUDA_HOME=$CUDA_HOME" \
    --setenv="PATH=$PATH" \
    --setenv="LD_LIBRARY_PATH=$LD_LIBRARY_PATH" \
    --setenv="TORCH_CUDA_ARCH_LIST=$TORCH_CUDA_ARCH_LIST" \
    --setenv="TRITON_PTXAS_PATH=$TRITON_PTXAS_PATH" \
    --setenv="PYTORCH_ALLOC_CONF=$PYTORCH_ALLOC_CONF" \
    bash -c 'echo 500 > /proc/self/oom_score_adj 2>/dev/null || true; exec "$@"' \
    dgx-spark-training \
    "$@"
