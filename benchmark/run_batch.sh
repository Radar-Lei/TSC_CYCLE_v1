#!/usr/bin/env bash
# Batch benchmark runner script for TSC_CYCLE LLM Traffic Signal Cycle Benchmark
# Usage: ./run_batch.sh [config_path]
#
# This script runs the benchmark inside a Docker container that has SUMO installed.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOCKER_DIR="${ROOT_DIR}/docker"

# Container configuration
IMAGE_NAME="${IMAGE_NAME:-tsc-cycle-benchmark}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
CONTAINER_NAME="${CONTAINER_NAME:-tsc-cycle-benchmark}"
PORT="${PORT:-8014}"
CONTAINER_PORT="${CONTAINER_PORT:-8013}"
STOP_EXISTING="${STOP_EXISTING:-1}"
HOST_OS="$(uname -s)"

# TSC_CYCLE specific configuration
# PROJECT_ROOT is the parent directory (TSC_CYCLE project root)
PROJECT_ROOT="$(cd "${ROOT_DIR}/.." && pwd)"
HOST_DATA_DIR="${SUMO_CLIENT_DATA_DIR:-${ROOT_DIR}/.sumo-data}"
HOST_TSC_CYCLE_DIR="${PROJECT_ROOT}"
BENCHMARK_CONFIG="${1:-TSC_CYCLE/benchmark/config/batch_config.json}"

# GUI configuration (set BENCHMARK_GUI=0 to disable)
BENCHMARK_GUI="${BENCHMARK_GUI:-0}"
GUI_BACKEND="${GUI_BACKEND:-xquartz}"

# LLM API configuration (pass through to container)
LLM_API_BASE_URL="${LLM_API_BASE_URL:-http://host.docker.internal:1234/v1}"

echo "============================================================"
echo "TSC_CYCLE BATCH BENCHMARK (Docker)"
echo "============================================================"
echo "Config: ${BENCHMARK_CONFIG}"
echo "Container: ${CONTAINER_NAME}"
echo ""

# Stop existing container if needed
if [[ "${STOP_EXISTING}" == "1" ]]; then
  existing="$(docker ps -a --filter "name=^/${CONTAINER_NAME}$" --format '{{.Names}}' 2>/dev/null || true)"
  if [[ -n "${existing}" ]]; then
    echo "[run_batch] Removing existing container ${CONTAINER_NAME}"
    docker rm -f "${CONTAINER_NAME}" 2>/dev/null || true
  fi
fi

# Build the Docker image
echo "[run_batch] Building ${IMAGE_NAME}:${IMAGE_TAG}"
docker build \
  -f "${DOCKER_DIR}/Dockerfile" \
  -t "${IMAGE_NAME}:${IMAGE_TAG}" \
  "${PROJECT_ROOT}"

# Prepare run arguments
RUN_ARGS=""

# Mount TSC_CYCLE directory
RUN_ARGS+=" -v ${HOST_TSC_CYCLE_DIR}:/srv/client/TSC_CYCLE"

# Mount data directory
mkdir -p "${HOST_DATA_DIR}/config" "${HOST_DATA_DIR}/runs" "${HOST_DATA_DIR}/logs"
RUN_ARGS+=" -v ${HOST_DATA_DIR}:/srv/sumo-data"

# Mount benchmark results directory (for output files)
HOST_RESULTS_DIR="${ROOT_DIR}/results"
mkdir -p "${HOST_RESULTS_DIR}"
RUN_ARGS+=" -v ${HOST_RESULTS_DIR}:/srv/client/benchmark/results"

# Pass LLM API URL (use host.docker.internal for macOS/Windows)
RUN_ARGS+=" -e LLM_API_BASE_URL=${LLM_API_BASE_URL}"

# Add host.docker.internal mapping for Linux
if [[ "${HOST_OS}" == "Linux" ]]; then
  RUN_ARGS+=" --add-host=host.docker.internal:host-gateway"
fi

# macOS GUI configuration
if [[ "${HOST_OS}" == "Darwin" ]]; then
  if [[ "${BENCHMARK_GUI}" == "1" ]]; then
    RUN_ARGS+=" -e SUMO_GUI=1"
    RUN_ARGS+=" -e SUMO_AUTO_START_GUI=1"

    if [[ "${GUI_BACKEND}" == "xquartz" ]]; then
      if open -Ra XQuartz >/dev/null 2>&1; then
        echo "[run_batch] XQuartz detected for GUI mode"
      else
        echo "[run_batch] Warning: XQuartz not found, GUI may not work" >&2
      fi
      RUN_ARGS+=" -e DISPLAY=host.docker.internal:0"
      RUN_ARGS+=" -e QT_X11_NO_MITSHM=1"
      RUN_ARGS+=" -e LIBGL_ALWAYS_INDIRECT=1"
      RUN_ARGS+=" -e LIBGL_ALWAYS_SOFTWARE=1"
    fi
  fi
fi

# Run the container
echo "[run_batch] Starting container ${CONTAINER_NAME}"
docker run \
  -d \
  --name "${CONTAINER_NAME}" \
  -p "${PORT}:${CONTAINER_PORT}" \
  -e USER_ID="$(id -u)" \
  -e GROUP_ID="$(id -g)" \
  ${RUN_ARGS} \
  "${IMAGE_NAME}:${IMAGE_TAG}"

# Wait for container to be ready
echo "[run_batch] Waiting for container to be ready..."
for _ in {1..30}; do
  if docker exec "${CONTAINER_NAME}" test -f /srv/client/.venv/bin/python >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

# Run the benchmark inside the container
echo ""
echo "============================================================"
echo "RUNNING BENCHMARK"
echo "============================================================"

BENCHMARK_PY="/srv/client/.venv/bin/python"
CONTAINER_CONFIG_PATH="/srv/client/${BENCHMARK_CONFIG}"

docker exec -i "${CONTAINER_NAME}" "${BENCHMARK_PY}" -m TSC_CYCLE.benchmark.run_batch --config "${CONTAINER_CONFIG_PATH}" 2>&1

echo ""
echo "[run_batch] Benchmark completed"
echo "[run_batch] Results available in: ${HOST_DATA_DIR}/runs/"
