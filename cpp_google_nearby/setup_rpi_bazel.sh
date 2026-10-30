#!/usr/bin/env bash
# ==============================================================================
# 라즈베리파이 Google Nearby C++ 빌드 환경 구축 스크립트
# ==============================================================================

set -e

echo "=== 라즈베리파이 Google Nearby C++ 개발 환경 설치 ==="

# 1. 필수 시스템 라이브러리 및 빌드 도구 설치
echo "[1/4] APT 패키지 업데이트 및 빌드 툴체인 설치..."
sudo apt-get update
sudo apt-get install -y \
    build-essential \
    clang \
    cmake \
    ninja-build \
    git \
    curl \
    pkg-config \
    libbluetooth-dev \
    libssl-dev \
    libglib2.0-dev

# 2. 스왑(Swap) 메모리 점검 (C++ 빌드 시 메모리 부족 방지)
TOTAL_RAM_MB=$(free -m | awk '/^Mem:/{print $2}')
echo "현재 라즈베리파이 RAM: ${TOTAL_RAM_MB}MB"
if [ "$TOTAL_RAM_MB" -lt 3500 ]; then
    echo "⚠️ RAM이 4GB 미만인 기기에서는 C++ 대규모 빌드 시 Out of Memory가 발생할 수 있습니다."
    echo "   스왑(Swap) 파일 확장을 권장합니다 (dphys-swapfile)."
fi

# 3. Bazelisk (Bazel 자동 버전 관리자) 설치
echo "[2/4] Bazelisk (Bazel) 설치..."
ARCH=$(uname -m)
BAZELISK_BIN="/usr/local/bin/bazel"

if ! command -v bazel >/dev/null 2>&1; then
    if [ "$ARCH" = "aarch64" ]; then
        BAZEL_URL="https://github.com/bazelbuild/bazelisk/releases/latest/download/bazelisk-linux-arm64"
    elif [ "$ARCH" = "armv7l" ]; then
        BAZEL_URL="https://github.com/bazelbuild/bazelisk/releases/latest/download/bazelisk-linux-armhf"
    else
        BAZEL_URL="https://github.com/bazelbuild/bazelisk/releases/latest/download/bazelisk-linux-amd64"
    fi

    echo "Downloading Bazelisk for $ARCH..."
    sudo curl -Lo "$BAZELISK_BIN" "$BAZEL_URL"
    sudo chmod +x "$BAZELISK_BIN"
    echo "Bazelisk 설치 완료: $(bazel --version || true)"
else
    echo "Bazel이 이미 설치되어 있습니다: $(bazel --version || true)"
fi

# 4. Google Nearby 공식 저장소 클론 (없는 경우)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -d "google-nearby" ]; then
    echo "[3/4] Google Nearby 오픈소스 저장소 클론 중..."
    git clone --depth 1 https://github.com/google/nearby.git google-nearby
else
    echo "google-nearby 저장소가 이미 존재합니다."
fi

echo "[4/4] 설치 완료!"
echo "빌드 방법은 cpp_google_nearby/README.md를 참고하세요."
