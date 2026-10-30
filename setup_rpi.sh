#!/usr/bin/env bash
# ==============================================================================
# Raspberry Pi Setup Script for Nearby Discoverer
# ==============================================================================

set -e

echo "=========================================================="
echo "   Raspberry Pi Nearby Connections Setup"
echo "=========================================================="

echo "[1/3] Updating system packages and Bluetooth tools..."
sudo apt-get update
sudo apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    bluetooth \
    bluez \
    libbluetooth-dev

echo "[2/3] Enabling Bluetooth service..."
sudo systemctl enable bluetooth
sudo systemctl start bluetooth

echo "[3/3] Setting up Python virtual environment..."
cd python
if [ ! -d "venv" ]; then
    python3 -m venv venv --system-site-packages
fi

source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo "=========================================================="
echo "Setup completed successfully!"
echo ""
echo "Run scanner now:"
echo "   cd python"
echo "   ./run_scanner.sh"
echo "=========================================================="
