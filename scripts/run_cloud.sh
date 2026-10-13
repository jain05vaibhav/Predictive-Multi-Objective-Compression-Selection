#!/usr/bin/env bash
# ==============================================================================
# Run Stage 8 Cloud Receiver & Decompression Server
# ==============================================================================

set -euo pipefail

if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
fi

echo "☁️ Starting Stage 8 Cloud Ingestion & Decompression Server on 0.0.0.0:8765..."
python3 -m cloud.receiver
