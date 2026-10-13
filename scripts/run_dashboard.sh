#!/usr/bin/env bash
# ==============================================================================
# Run AURA-EDGE Modern React Command Center & API Server
# ==============================================================================

set -euo pipefail

if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
fi

echo "◈ Starting AURA-EDGE React Command Center on http://localhost:5000..."
python -m dashboard.server --port 5000
