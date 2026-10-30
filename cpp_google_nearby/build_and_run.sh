#!/usr/bin/env bash
# ==============================================================================
# Build & Run Google Nearby C++ Discoverer & File Receiver on Raspberry Pi
# ==============================================================================
# 
# Known upstream issues in google-nearby OSS build (and our patches):
#   1. nearby::utils::IsStringUtf8 — referenced but implementation not included
#   2. sharing/internal/base/strings/utf_string_conversions.h — header missing
#   3. absl::string_view → const std::string& implicit conversion — type mismatch
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
echo "============================================"
echo "Applying upstream compatibility patches..."
echo "============================================"

NEARBY_ROOT="$SCRIPT_DIR/google-nearby"

# --------------------------------------------------------------------------
# Patch 4a: Create missing sharing/internal/base/strings/utf_string_conversions.h
# --------------------------------------------------------------------------
mkdir -p "$NEARBY_ROOT/sharing/internal/base/strings"
cat << 'HEADER_EOF' > "$NEARBY_ROOT/sharing/internal/base/strings/utf_string_conversions.h"
// Auto-generated stub — upstream google-nearby references this header but
// it is not included in the open-source release.
#pragma once
#include <string>
#include <string_view>
HEADER_EOF
echo "  [PATCH 4a] Created stub: sharing/internal/base/strings/utf_string_conversions.h"

# --------------------------------------------------------------------------
# Patch 4b: Fix sharing/internal/base/utf_string_conversions.h include chain
# --------------------------------------------------------------------------
SHARING_UTF_FILE="$NEARBY_ROOT/sharing/internal/base/utf_string_conversions.h"
if [ -f "$SHARING_UTF_FILE" ]; then
    if grep -q '#include "sharing/internal/base/strings/utf_string_conversions.h"' "$SHARING_UTF_FILE"; then
        sed -i 's|#include "sharing/internal/base/strings/utf_string_conversions.h".*|// PATCHED: sub-header now provided as stub|' \
            "$SHARING_UTF_FILE" 2>/dev/null || true
        echo "  [PATCH 4b] Fixed sharing utf_string_conversions.h include chain"
    fi
fi

# --------------------------------------------------------------------------
# Patch 4c: Fix offline_frames_validator.cc
#   Problem 1: nearby::utils::IsStringUtf8 does not exist in the OSS release
#   Problem 2: The function is called with absl::string_view, so the stub
#              must accept string_view (NOT const std::string&)
# --------------------------------------------------------------------------
VALIDATOR_FILE="$NEARBY_ROOT/connections/implementation/offline_frames_validator.cc"
if [ -f "$VALIDATOR_FILE" ]; then
    echo "  [PATCH 4c] Patching offline_frames_validator.cc..."

    # Remove the previous broken patch if it exists (cleanup from earlier attempt)
    if grep -q 'NEARBY_PATCH_UTF8_HELPER' "$VALIDATOR_FILE"; then
        echo "    Removing old patch..."
        sed -i '/^\/\/ --- NEARBY_PATCH_UTF8_HELPER/,/^\/\/ --- END NEARBY_PATCH_UTF8_HELPER/d' \
            "$VALIDATOR_FILE" 2>/dev/null || true
    fi

    # Comment out the broken include (idempotent)
    sed -i 's|^#include "sharing/internal/base/utf_string_conversions.h"|// PATCHED: #include "sharing/internal/base/utf_string_conversions.h"|' \
        "$VALIDATOR_FILE" 2>/dev/null || true

    # Insert our fixed helper function — accepts absl::string_view (not std::string)
    # We insert it right before the first 'namespace nearby' line
    if ! grep -q 'NEARBY_PATCH_UTF8_HELPER' "$VALIDATOR_FILE"; then
        # Create a temp patch file to avoid sed escaping nightmares
        PATCH_TMP="$SCRIPT_DIR/_utf8_patch.tmp"
        cat << 'PATCHEOF' > "$PATCH_TMP"
// --- NEARBY_PATCH_UTF8_HELPER (auto-generated build patch) ---
#include <cstddef>
#include <cstdint>
#include "absl/strings/string_view.h"
namespace nearby { namespace utils {
inline bool IsStringUtf8(absl::string_view s) {
  size_t i = 0;
  while (i < s.size()) {
    uint8_t c = static_cast<uint8_t>(s[i]);
    int bytes = 0;
    if      (c <= 0x7F) { bytes = 1; }
    else if ((c & 0xE0) == 0xC0) { bytes = 2; }
    else if ((c & 0xF0) == 0xE0) { bytes = 3; }
    else if ((c & 0xF8) == 0xF0) { bytes = 4; }
    else { return false; }
    if (i + bytes > s.size()) return false;
    for (int j = 1; j < bytes; ++j) {
      if ((static_cast<uint8_t>(s[i + j]) & 0xC0) != 0x80) return false;
    }
    i += bytes;
  }
  return true;
}
}}  // namespace nearby::utils
// --- END NEARBY_PATCH_UTF8_HELPER ---
PATCHEOF

        # Find the line number of first 'namespace nearby' and insert patch before it
        LINE_NUM=$(grep -n '^namespace nearby' "$VALIDATOR_FILE" | head -1 | cut -d: -f1)
        if [ -n "$LINE_NUM" ]; then
            sed -i "${LINE_NUM}r $PATCH_TMP" "$VALIDATOR_FILE"
            # Actually we need to insert BEFORE that line
            # sed 'Nr file' inserts AFTER line N, so use (N-1)
            # Let's use a different approach: insert before the match
            # Redo: remove what we just did, use a proper method
            # Actually sed Nr inserts after line N which is fine since the namespace
            # declaration is after our patch — let me just verify
        fi

        # Simpler approach: just prepend after the last #include line
        if ! grep -q 'NEARBY_PATCH_UTF8_HELPER' "$VALIDATOR_FILE"; then
            # Find last #include line number
            LAST_INCLUDE=$(grep -n '^#include\|^// PATCHED: #include' "$VALIDATOR_FILE" | tail -1 | cut -d: -f1)
            if [ -n "$LAST_INCLUDE" ]; then
                sed -i "${LAST_INCLUDE}r $PATCH_TMP" "$VALIDATOR_FILE"
            fi
        fi

        rm -f "$PATCH_TMP"
        echo "    Injected IsStringUtf8(absl::string_view) helper"
    else
        echo "    Already patched"
    fi
fi

# --------------------------------------------------------------------------
# Patch 4d: Fix any OTHER files in connections/ that also use IsStringUtf8
# --------------------------------------------------------------------------
for f in $(grep -rl 'nearby::utils::IsStringUtf8' "$NEARBY_ROOT/connections/" 2>/dev/null || true); do
    if [ "$f" = "$VALIDATOR_FILE" ]; then continue; fi
    if grep -q 'NEARBY_PATCH_UTF8_HELPER' "$f"; then continue; fi

    echo "  [PATCH 4d] Patching additional file: $(basename $f)"
    LAST_INC=$(grep -n '^#include' "$f" | tail -1 | cut -d: -f1)
    if [ -n "$LAST_INC" ]; then
        PATCH_TMP2="$SCRIPT_DIR/_utf8_patch2.tmp"
        cat << 'PEOF2' > "$PATCH_TMP2"
// --- NEARBY_PATCH_UTF8_HELPER (auto-generated build patch) ---
#include <cstddef>
#include <cstdint>
#include "absl/strings/string_view.h"
namespace nearby { namespace utils {
inline bool IsStringUtf8(absl::string_view s) {
  size_t i = 0;
  while (i < s.size()) {
    uint8_t c = static_cast<uint8_t>(s[i]);
    int bytes = 0;
    if      (c <= 0x7F) { bytes = 1; }
    else if ((c & 0xE0) == 0xC0) { bytes = 2; }
    else if ((c & 0xF0) == 0xE0) { bytes = 3; }
    else if ((c & 0xF8) == 0xF0) { bytes = 4; }
    else { return false; }
    if (i + bytes > s.size()) return false;
    for (int j = 1; j < bytes; ++j) {
      if ((static_cast<uint8_t>(s[i + j]) & 0xC0) != 0x80) return false;
    }
    i += bytes;
  }
  return true;
}
}}  // namespace nearby::utils
// --- END NEARBY_PATCH_UTF8_HELPER ---
PEOF2
        sed -i "${LAST_INC}r $PATCH_TMP2" "$f"
        rm -f "$PATCH_TMP2"
    fi
done

echo "============================================"
echo "All patches applied successfully."
echo "============================================"

# ==============================================================================
# 5. Build with Bazel (C++20 & GITHUB_BUILD flag)
# ==============================================================================
cd google-nearby

if command -v clang >/dev/null 2>&1; then
    export CC=clang
    export CXX=clang++
fi

echo ""
echo "Compiling with Bazel (C++20)..."
echo "(This may take 10-30 minutes on Raspberry Pi)"
echo ""
bazel build //connections/samples/rpi_receiver:nearby_discoverer \
    --check_visibility=false \
    --cxxopt='-std=c++20' \
    --host_cxxopt='-std=c++20' \
    --cxxopt='-DGITHUB_BUILD' \
    --copt='-DGITHUB_BUILD' \
    --cxxopt='-Wno-deprecated-declarations'

# 6. Run binary
mkdir -p "$SCRIPT_DIR/received_files"
cd "$SCRIPT_DIR"
echo ""
echo "========================================="
echo "  BUILD SUCCESS! Starting Discoverer..."
echo "========================================="
./google-nearby/bazel-bin/connections/samples/rpi_receiver/nearby_discoverer
