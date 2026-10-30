#!/usr/bin/env bash
# ==========================================================
# 라즈베리파이 Nearby Scanner 실행 스크립트
# ==========================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== 라즈베리파이 Nearby Scanner 시작 준비 ==="

# 1. 블루투스 상태 점검
if command -v systemctl >/dev/null 2>&1; then
    sudo systemctl start bluetooth || true
fi

# 2. 파이썬 가상환경(venv) 생성 및 활성화
if [ ! -d "venv" ]; then
    echo "[1/3] 파이썬 가상환경(venv) 생성 중..."
    python3 -m venv venv --system-site-packages || {
        echo "python3-venv가 필요합니다: sudo apt-get update && sudo apt-get install -y python3-venv python3-pip"
        exit 1
    }
fi

source venv/bin/activate

# 3. 필수 라이브러리 설치/확인
echo "[2/3] 의존성 패키지 확인 중..."
pip install -q --upgrade pip
pip install -q -r requirements.txt

# 4. 스캐너 실행
echo "[3/3] Nearby Scanner 실행 중..."
python3 nearby_scanner.py
