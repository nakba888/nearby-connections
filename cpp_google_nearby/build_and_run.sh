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

# ==============================================================================
# 4. Patch upstream open-source compilation bugs in google-nearby
# ==============================================================================
echo "Applying upstream compatibility patches..."

# --- Patch 4a: Create missing utf_string_conversions.h stub ---
mkdir -p "$SCRIPT_DIR/google-nearby/sharing/internal/base/strings"
cat << 'HEADER_EOF' > "$SCRIPT_DIR/google-nearby/sharing/internal/base/strings/utf_string_conversions.h"
// Auto-generated stub — upstream google-nearby references this header but
// it is not included in the open-source release.
#pragma once
#include <string>
#include <string_view>
HEADER_EOF

# --- Patch 4b: Fix offline_frames_validator.cc ---
#   Error: nearby::utils::IsStringUtf8 does not exist in the OSS release.
#   Fix:   Replace with a simple inline UTF-8 validator.
VALIDATOR_FILE="$SCRIPT_DIR/google-nearby/connections/implementation/offline_frames_validator.cc"
if [ -f "$VALIDATOR_FILE" ]; then
    # Check if already patched
    if grep -q 'nearby::utils::IsStringUtf8' "$VALIDATOR_FILE"; then
        echo "  Patching offline_frames_validator.cc (IsStringUtf8 fix)..."

        # 1) Comment out the broken include
        sed -i 's|^#include "sharing/internal/base/utf_string_conversions.h"|// PATCHED: #include "sharing/internal/base/utf_string_conversions.h"|' \
            "$VALIDATOR_FILE" 2>/dev/null || true

        # 2) Add a simple inline UTF-8 check function and replace all calls
        #    Insert our helper right after the last #include block
        #    We use a unique guard to avoid double-patching
        if ! grep -q 'NEARBY_PATCH_UTF8_HELPER' "$VALIDATOR_FILE"; then
            sed -i '/^namespace nearby/i \
// --- NEARBY_PATCH_UTF8_HELPER (auto-generated) ---\
namespace nearby { namespace utils {\
inline bool IsStringUtf8(const std::string\& s) {\
  size_t i = 0;\
  while (i < s.size()) {\
    unsigned char c = static_cast<unsigned char>(s[i]);\
    int bytes = 0;\
    if      (c <= 0x7F) { bytes = 1; }\
    else if ((c & 0xE0) == 0xC0) { bytes = 2; }\
    else if ((c & 0xF0) == 0xE0) { bytes = 3; }\
    else if ((c & 0xF8) == 0xF0) { bytes = 4; }\
    else { return false; }\
    if (i + bytes > s.size()) return false;\
    for (int j = 1; j < bytes; ++j) {\
      if ((static_cast<unsigned char>(s[i + j]) & 0xC0) != 0x80) return false;\
    }\
    i += bytes;\
  }\
  return true;\
}\
}}  // namespace nearby::utils\
// --- END NEARBY_PATCH_UTF8_HELPER ---' "$VALIDATOR_FILE" 2>/dev/null || true
        fi
    else
        echo "  offline_frames_validator.cc already patched."
    fi
fi

# --- Patch 4c: Fix any other files that use nearby::utils::IsStringUtf8 ---
for f in $(grep -rl 'nearby::utils::IsStringUtf8' "$SCRIPT_DIR/google-nearby/connections/" 2>/dev/null || true); do
    if [ "$f" != "$VALIDATOR_FILE" ]; then
        if ! grep -q 'NEARBY_PATCH_UTF8_HELPER' "$f"; then
            echo "  Patching additional file: $f"
            sed -i '/^namespace nearby/i \
// --- NEARBY_PATCH_UTF8_HELPER (auto-generated) ---\
namespace nearby { namespace utils {\
inline bool IsStringUtf8(const std::string\& s) {\
  size_t i = 0;\
  while (i < s.size()) {\
    unsigned char c = static_cast<unsigned char>(s[i]);\
    int bytes = 0;\
    if      (c <= 0x7F) { bytes = 1; }\
    else if ((c & 0xE0) == 0xC0) { bytes = 2; }\
    else if ((c & 0xF0) == 0xE0) { bytes = 3; }\
    else if ((c & 0xF8) == 0xF0) { bytes = 4; }\
    else { return false; }\
    if (i + bytes > s.size()) return false;\
    for (int j = 1; j < bytes; ++j) {\
      if ((static_cast<unsigned char>(s[i + j]) & 0xC0) != 0x80) return false;\
    }\
    i += bytes;\
  }\
  return true;\
}\
}}  // namespace nearby::utils\
// --- END NEARBY_PATCH_UTF8_HELPER ---' "$f" 2>/dev/null || true
        fi
    fi
done

# --- Patch 4d: Fix sharing/internal/base/utf_string_conversions.h include guard ---
SHARING_UTF_FILE="$SCRIPT_DIR/google-nearby/sharing/internal/base/utf_string_conversions.h"
if [ -f "$SHARING_UTF_FILE" ]; then
    if grep -q 'sharing/internal/base/strings/utf_string_conversions.h' "$SHARING_UTF_FILE"; then
        echo "  Patching sharing utf_string_conversions.h (missing sub-header)..."
        sed -i 's|#include "sharing/internal/base/strings/utf_string_conversions.h".*|// PATCHED: removed missing sub-header include|' \
            "$SHARING_UTF_FILE" 2>/dev/null || true
    fi
fi

echo "All patches applied."

# ==============================================================================
# 5. Build with Bazel (C++20 & GITHUB_BUILD flag)
# ==============================================================================
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
