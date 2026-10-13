#!/usr/bin/env bash
# ==============================================================================
# Raspberry Pi 3B+ Automated Hardware Setup Script
#
# Configures system packages, camera interfaces, GPIO sensor libraries,
# and Python virtual environment for the autonomous compression controller.
# ==============================================================================

set -euo pipefail

echo "=================================================================="
echo "🍓 Setting up Raspberry Pi 3B+ Autonomous Compression Node"
echo "=================================================================="

# 1. Update OS package repositories
echo "\n[Step 1/5] Updating apt repositories..."
sudo apt-get update -y

# 2. Install hardware interfaces, GPIO, camera, and vcgencmd binaries
echo "\n[Step 2/5] Installing native libraries and hardware packages..."
sudo apt-get install -y \
    python3-pip \
    python3-venv \
    libraspberrypi-bin \
    libgpiod2 \
    python3-picamera2 \
    python3-opencv \
    i2c-tools \
    wireless-tools \
    iproute2

# 3. Create python virtual environment with system site-packages (for picamera2)
echo "\n[Step 3/5] Initializing Python virtual environment (.venv)..."
if [ ! -d ".venv" ]; then
    python3 -m venv --system-site-packages .venv
fi

# 4. Activate venv and install edge requirements
echo "\n[Step 4/5] Installing edge python dependencies..."
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install adafruit-circuitpython-dht

# 5. Enable hardware camera in raspi-config
echo "\n[Step 5/5] Configuring camera & hardware permissions..."
sudo usermod -a -G video,gpio "$USER" 2>/dev/null || true

echo "\n=================================================================="
echo "✅ Raspberry Pi setup complete!"
echo ""
echo "Hardware Wiring Check:"
echo "  - DHT22 VCC  -> 3.3V (Pin 1)"
echo "  - DHT22 DATA -> GPIO4 (Pin 7) [+ 10k pull-up to 3.3V]"
echo "  - DHT22 GND  -> GND (Pin 9)"
echo "  - CSI Camera -> 15-Pin Ribbon CSI Port"
echo ""
echo "To run the autonomous edge pipeline:"
echo "  ./scripts/run_edge.sh --cloud-host <YOUR_LAPTOP_IP>"
echo "=================================================================="
