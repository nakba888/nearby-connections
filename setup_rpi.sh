#!/usr/bin/env bash
# ==============================================================================
# 라즈베리파이 원클릭 환경 구성 스크립트 (Python Discoverer 중심)
# ==============================================================================

set -e

echo "=========================================================="
echo "   라즈베리파이 Nearby Connections 환경 설정"
echo "=========================================================="

echo "[1/3] 시스템 패키지 및 블루투스 도구 점검..."
sudo apt-get update
sudo apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    bluetooth \
    bluez \
    libbluetooth-dev

echo "[2/3] 블루투스 서비스 활성화..."
sudo systemctl enable bluetooth
sudo systemctl start bluetooth

echo "[3/3] 파이썬 스캐너 가상환경 설정..."
cd python
if [ ! -d "venv" ]; then
    python3 -m venv venv --system-site-packages
fi

source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo "=========================================================="
echo "🎉 모든 준비가 완료되었습니다!"
echo ""
echo "▶ 지금 바로 스캐너 실행하기:"
echo "   cd python"
echo "   ./run_scanner.sh"
echo "=========================================================="
