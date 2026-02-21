#!/usr/bin/env bash
set -euo pipefail

# SUMO Center Entrypoint for TSC_CYCLE Benchmark
# This script initializes the container environment and runs the benchmark

# Set up environment
export PYTHONPATH="${PYTHONPATH:-/srv/client}"
export SUMO_HOME="${SUMO_HOME:-/usr/share/sumo}"
export PATH="${SUMO_HOME}/bin:${PATH}"

# Create necessary directories
mkdir -p /srv/sumo-data/logs /srv/sumo-data/runs /srv/sumo-data/config

# Handle user permissions for mounted volumes
# If USER_ID is set, create a user with that UID and run as that user
if [[ -n "${USER_ID:-}" ]]; then
    GROUP_ID="${GROUP_ID:-${USER_ID}}"

    # Create group if it doesn't exist
    if ! getent group benchmarkgroup >/dev/null 2>&1; then
        groupadd -g "${GROUP_ID}" benchmarkgroup
    fi

    # Create user if it doesn't exist
    if ! id benchmarkuser >/dev/null 2>&1; then
        useradd -u "${USER_ID}" -g "${GROUP_ID}" -m -s /bin/bash benchmarkuser
        # Add user to video group for GUI support
        usermod -aG video benchmarkuser 2>/dev/null || true
    fi

    # Fix permissions on mounted directories
    chown -R "${USER_ID}:${GROUP_ID}" /srv/sumo-data 2>/dev/null || true
    chown -R "${USER_ID}:${GROUP_ID}" /srv/client/TSC_CYCLE 2>/dev/null || true
    chown -R "${USER_ID}:${GROUP_ID}" /srv/client/benchmark/results 2>/dev/null || true

    echo "[entrypoint] Running as benchmarkuser (UID=${USER_ID}, GID=${GROUP_ID})"

    # Use gosu to drop privileges and run the command
    if [[ $# -gt 0 ]]; then
        exec gosu benchmarkuser "$@"
    else
        # Default: keep container running
        echo "[entrypoint] Container ready. Run benchmark with: python -m TSC_CYCLE.benchmark.run_batch --config /srv/client/benchmark/config/batch_config.json"
        exec gosu benchmarkuser tail -f /dev/null
    fi
else
    # No USER_ID set, run as root (legacy behavior)
    if [[ $# -gt 0 ]]; then
        exec "$@"
    else
        echo "[entrypoint] Container ready. Run benchmark with: python -m TSC_CYCLE.benchmark.run_batch --config /srv/client/benchmark/config/batch_config.json"
        exec tail -f /dev/null
    fi
fi
