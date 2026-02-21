#!/bin/bash
set -euo pipefail

# 确保用户的 bashrc 存在（解决基础镜像可能的权限问题）
touch ~/.bashrc 2>/dev/null || true

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
