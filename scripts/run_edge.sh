#!/usr/bin/env bash
# ==============================================================================
# Run Autonomous Edge Controller Pipeline on Raspberry Pi
# ==============================================================================

set -euo pipefail

# Activate virtual environment if present
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
fi

CLOUD_HOST="${1:-}"

if [ -n "$CLOUD_HOST" ]; then
    echo "🍓 Starting Edge Pipeline transmitting to Cloud: ${CLOUD_HOST}:8765..."
    python3 -m edge.main_loop --cloud-host "$CLOUD_HOST" --cloud-port 8765
else
    echo "🍓 Starting Edge Pipeline in standalone local mode..."
    python3 -m edge.main_loop
fi
