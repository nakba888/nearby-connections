#!/usr/bin/env bash
# ==============================================================================
# Build & Run Google Nearby C++ Discoverer & File Receiver on Raspberry Pi
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== Building Nearby Connections File Receiver ==="

# 1. Setup check
if [ ! -d "google-nearby" ]; then
    echo "google-nearby directory not found. Running setup_rpi_bazel.sh first..."
    chmod +x setup_rpi_bazel.sh
    ./setup_rpi_bazel.sh
fi

# 2. Check and initialize submodules if needed
cd google-nearby
if [ -f ".gitmodules" ]; then
    echo "Updating git submodules..."
    git submodule update --init --recursive || true
fi
cd "$SCRIPT_DIR"

# 3. Copy source to sample directory
TARGET_DIR="google-nearby/connections/samples/rpi_receiver"
mkdir -p "$TARGET_DIR"
cp src/main.cc "$TARGET_DIR/main.cc"
cp src/BUILD "$TARGET_DIR/BUILD"

# 4. Build with Bazel
cd google-nearby
echo "Compiling with Bazel (C++17)..."
bazel build //connections/samples/rpi_receiver:nearby_discoverer --check_visibility=false

# 5. Run binary
mkdir -p "$SCRIPT_DIR/received_files"
cd "$SCRIPT_DIR"
echo "Starting Discoverer & Receiver..."
./google-nearby/bazel-bin/connections/samples/rpi_receiver/nearby_discoverer
