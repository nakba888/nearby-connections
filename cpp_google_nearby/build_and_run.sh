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

# 4. Patch upstream open-source include bug in google-nearby
echo "Applying upstream compatibility patches..."
mkdir -p "$SCRIPT_DIR/google-nearby/sharing/internal/base/strings"
if [ ! -f "$SCRIPT_DIR/google-nearby/sharing/internal/base/strings/utf_string_conversions.h" ]; then
    cat << 'EOF' > "$SCRIPT_DIR/google-nearby/sharing/internal/base/strings/utf_string_conversions.h"
#pragma once
#include <string>
#include <string_view>
EOF
fi

if [ -f "$SCRIPT_DIR/google-nearby/connections/implementation/offline_frames_validator.cc" ]; then
    sed -i 's|#include "sharing/internal/base/utf_string_conversions.h"|// #include "sharing/internal/base/utf_string_conversions.h"|g' \
        "$SCRIPT_DIR/google-nearby/connections/implementation/offline_frames_validator.cc" || true
fi

# 5. Build with Bazel (C++20 & GITHUB_BUILD flag)
cd google-nearby

if command -v clang >/dev/null 2>&1; then
    export CC=clang
    export CXX=clang++
fi

echo "Compiling with Bazel (C++20)..."
bazel build //connections/samples/rpi_receiver:nearby_discoverer \
    --check_visibility=false \
    --cxxopt='-std=c++20' \
    --host_cxxopt='-std=c++20' \
    --cxxopt='-DGITHUB_BUILD' \
    --copt='-DGITHUB_BUILD'

# 6. Run binary
mkdir -p "$SCRIPT_DIR/received_files"
cd "$SCRIPT_DIR"
echo "Starting Discoverer & Receiver..."
./google-nearby/bazel-bin/connections/samples/rpi_receiver/nearby_discoverer
