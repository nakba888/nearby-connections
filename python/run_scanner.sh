#!/usr/bin/env bash
# ==========================================================
# Raspberry Pi Nearby Scanner Runner Script
# ==========================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== Preparing Raspberry Pi Nearby Scanner ==="

# 1. Check and start Bluetooth service
if command -v systemctl >/dev/null 2>&1; then
    sudo systemctl start bluetooth || true
fi

# 2. Virtual environment setup
if [ ! -d "venv" ]; then
    echo "[1/3] Creating Python venv..."
    python3 -m venv venv --system-site-packages || {
        echo "python3-venv is required: sudo apt-get update && sudo apt-get install -y python3-venv python3-pip"
        exit 1
    }
fi

source venv/bin/activate

# 3. Check and install dependencies
echo "[2/3] Checking dependencies..."
pip install -q --upgrade pip
pip install -q -r requirements.txt

# 4. Run Scanner
echo "[3/3] Starting Nearby Scanner..."
python3 nearby_scanner.py
