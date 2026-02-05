#!/bin/bash
set -euo pipefail

# Start Xvfb (virtual X server for SUMO)
export DISPLAY=:99
Xvfb :99 -screen 0 1024x768x24 > /dev/null 2>&1 &
sleep 1  # Wait for Xvfb to start

# Create necessary directories
mkdir -p logs outputs .checkpoints

# Execute command passed to entrypoint
if [[ $# -gt 0 ]]; then
    exec "$@"
fi

# Default to bash if no command provided
exec /bin/bash
