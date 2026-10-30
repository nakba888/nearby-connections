#!/usr/bin/env python3
"""
Nearby Connections BLE Discoverer / Scanner for Raspberry Pi
============================================================
이 스크립트는 라즈베리파이(또는 PC)에서 BLE 스캐너를 실행하여
스마트폰이 Google Nearby Connections (UUID: 0xFEF3) 또는
지정한 Service UUID로 송출(Advertising)하는 신호를 감지(Discover)합니다.
"""

import asyncio
import datetime
import hashlib
import json
import os
import subprocess
import sys
import time
from typing import Dict, Optional

try:
    from bleak import BleakScanner
    from bleak.backends.device import BLEDevice
    from bleak.backends.scanner import AdvertisementData
except ImportError:
    print("\n[오류] 'bleak' 패키지가 설치되지 않았습니다.")
    print("다음 명령어로 설치 후 다시 실행해주세요:")
    print("    pip install -r requirements.txt\n")
    sys.exit(1)

# Google 16-bit UUID for Nearby Connections / Fast Pair
GOOGLE_NEARBY_UUID_16 = "0000fef3-0000-1000-8000-00805f9b34fb"
SHORT_FEF3 = "fef3"

# ANSI 컬러 코드
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RED = "\033[91m"
MAGENTA = "\033[95m"


def load_config(config_path: str = "config.json") -> dict:
    default_config = {
        "service_id": "com.example.nearby.detector",
        "scan_all_google_nearby": True,
        "custom_service_uuids": [
            "0000fef3-0000-1000-8000-00805f9b34fb",
            "12345678-1234-5678-1234-56789abcdef0",
        ],
        "rssi_threshold": -85,
        "detection_cooldown_seconds": 3,
        "log_to_file": True,
        "log_file": "detections.log",
        "trigger_command": "",
    }
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                default_config.update(cfg)
        except Exception as e:
            print(f"[경고] 설정 파일 로드 실패({e}), 기본 설정을 사용합니다.")
    return default_config


def compute_service_id_hash(service_id: str) -> bytes:
    """Nearby Connections 표준: Service ID 문자열의 SHA-256 해시값 (첫 3~4바이트)"""
    sha = hashlib.sha256()
    sha.update(service_id.encode("utf-8"))
    return sha.digest()


def estimate_distance(rssi: int, tx_power: int = -59) -> str:
    """RSSI 신호 세기를 바탕으로 대략적인 근접도 표시"""
    if rssi >= -60:
        return f"{GREEN}매우 가까움 (1m 이내){RESET}"
    elif rssi >= -75:
        return f"{YELLOW}근접 (1~3m 내외){RESET}"
    elif rssi >= -85:
        return f"{CYAN}보통 (3~7m 내외){RESET}"
    else:
        return f"{MAGENTA}먼 거리 (7m 이상){RESET}"


class NearbyDiscoverer:
    def __init__(self, config: dict):
        self.config = config
        self.service_id = config.get("service_id", "com.example.nearby.detector")
        self.service_id_hash = compute_service_id_hash(self.service_id)
        self.rssi_threshold = config.get("rssi_threshold", -85)
        self.cooldown = config.get("detection_cooldown_seconds", 3)
        self.last_seen: Dict[str, float] = {}
        self.log_file = config.get("log_file", "detections.log")
        self.log_to_file = config.get("log_to_file", True)

        # 타겟 UUID 정규화
        self.custom_uuids = [
            u.lower() for u in config.get("custom_service_uuids", [])
        ]

    def log_event(self, text: str):
        if not self.log_to_file:
            return
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(f"[{timestamp}] {text}\n")
        except Exception as e:
            print(f"[오류] 로그 저장 실패: {e}")

    def parse_nearby_payload(self, raw_data: bytes) -> dict:
        """Nearby Connections 0xFEF3 Service Data 파싱 시도"""
        info = {
            "hex": raw_data.hex(),
            "matched_service_id": False,
            "endpoint_id": None,
            "endpoint_info": None,
        }

        if len(raw_data) < 4:
            return info

        # 첫 바이트: 헤더/버전/타입
        # 바이트 1~3: Service ID Hash (3 bytes)
        payload_hash = raw_data[1:4]
        if payload_hash == self.service_id_hash[:3]:
            info["matched_service_id"] = True

        # 바이트 4~7: 4바이트 Endpoint ID (알파뉴메릭)
        if len(raw_data) >= 8:
            try:
                endpoint_id_candidate = raw_data[4:8].decode("ascii")
                if endpoint_id_candidate.isalnum():
                    info["endpoint_id"] = endpoint_id_candidate
            except Exception:
                pass

        # 남은 바이트에서 UTF-8 텍스트(기기 이름 또는 전달 정보) 추출 시도
        if len(raw_data) > 8:
            try:
                # 텍스트 추출 (출력 가능한 글자 위주)
                text = raw_data[8:].decode("utf-8", errors="ignore").strip()
                printable = "".join(c for c in text if c.isprintable())
                if len(printable) >= 2:
                    info["endpoint_info"] = printable
            except Exception:
                pass

        return info

    def handle_detection(self, device: BLEDevice, adv: AdvertisementData):
        rssi = adv.rssi
        if rssi < self.rssi_threshold:
            return

        now = time.time()
        addr = device.address
        if addr in self.last_seen and (now - self.last_seen[addr]) < self.cooldown:
            return

        # 1. Google Nearby UUID (0xFEF3) 확인
        is_google_nearby = False
        nearby_service_data: Optional[bytes] = None

        # service_data 딕셔너리 키 검사
        for uuid_key, data in adv.service_data.items():
            uuid_str = str(uuid_key).lower()
            if SHORT_FEF3 in uuid_str or uuid_str == GOOGLE_NEARBY_UUID_16:
                is_google_nearby = True
                nearby_service_data = data
                break

        # service_uuids 리스트 검사
        for s_uuid in adv.service_uuids:
            s_uuid_lower = s_uuid.lower()
            if SHORT_FEF3 in s_uuid_lower or s_uuid_lower == GOOGLE_NEARBY_UUID_16:
                is_google_nearby = True
                break

        # 2. 커스텀 UUID 매칭 확인 (nRF Connect 등 수동 테스트용)
        is_custom_matched = False
        matched_custom_uuid = ""
        for c_uuid in self.custom_uuids:
            for s_uuid in adv.service_uuids:
                if c_uuid in s_uuid.lower():
                    is_custom_matched = True
                    matched_custom_uuid = c_uuid
                    break
            if is_custom_matched:
                break

        # 둘 다 아니면 무시
        if not is_google_nearby and not is_custom_matched:
            return

        # 3. 신호 해석
        self.last_seen[addr] = now
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")

        device_name = adv.local_name or device.name or "알 수 없는 기기"
        proximity = estimate_distance(rssi)

        print("\n" + "=" * 65)
        if is_google_nearby:
            print(f"{BOLD}{GREEN}📡 [Google Nearby Connections 신호 감지!]{RESET}")
        else:
            print(f"{BOLD}{CYAN}📡 [커스텀 BLE 서비스 신호 감지!]{RESET} (UUID: {matched_custom_uuid})")
        print(f"⏰ 시간: {timestamp} | 📍 MAC: {BOLD}{addr}{RESET} | 🏷 이름: {device_name}")
        print(f"📶 신호세기(RSSI): {BOLD}{rssi} dBm{RESET} ({proximity})")

        parsed_info = None
        if nearby_service_data:
            parsed_info = self.parse_nearby_payload(nearby_service_data)
            print(f"📦 Service Data Hex: {parsed_info['hex']}")
            if parsed_info["matched_service_id"]:
                print(f"🎯 {GREEN}설정한 Service ID와 정확히 일치합니다!{RESET} ({self.service_id})")
            if parsed_info["endpoint_id"]:
                print(f"🔑 Endpoint ID: {parsed_info['endpoint_id']}")
            if parsed_info["endpoint_info"]:
                print(f"📝 Endpoint Info: {parsed_info['endpoint_info']}")
        elif adv.manufacturer_data:
            mfg_hex = " ".join(f"{k}: {v.hex()}" for k, v in adv.manufacturer_data.items())
            print(f"🏭 Manufacturer Data: {mfg_hex}")

        print("=" * 65)

        # 로그 기록
        log_msg = f"DETECTED | MAC={addr} | RSSI={rssi} | Name={device_name}"
        if parsed_info and parsed_info.get("hex"):
            log_msg += f" | Payload={parsed_info['hex']}"
        self.log_event(log_msg)

        # 외부 트리거 실행 (설정된 경우)
        cmd = self.config.get("trigger_command", "").strip()
        if cmd:
            try:
                env = os.environ.copy()
                env["NEARBY_MAC"] = str(addr)
                env["NEARBY_RSSI"] = str(rssi)
                env["NEARBY_NAME"] = str(device_name)
                subprocess.Popen(cmd, shell=True, env=env)
            except Exception as e:
                print(f"[경고] 트리거 명령어 실행 실패: {e}")


async def main():
    config = load_config()
    discoverer = NearbyDiscoverer(config)

    print(f"\n{BOLD}{CYAN}=========================================================={RESET}")
    print(f"{BOLD}{CYAN}   라즈베리파이 Nearby Connections BLE 탐색기 (Discoverer){RESET}")
    print(f"{BOLD}{CYAN}=========================================================={RESET}")
    print(f"• 설정된 Service ID: {BOLD}{discoverer.service_id}{RESET}")
    print(f"• Service ID Hash(Prefix): {discoverer.service_id_hash[:3].hex().upper()}")
    print(f"• RSSI 감도 필터: {discoverer.rssi_threshold} dBm 이상")
    print(f"• 로그 파일: {discoverer.log_file}")
    print("스마트폰의 Advertising 신호를 실시간 스캔 중입니다... (종료: Ctrl+C)\n")

    scanner = BleakScanner(
        detection_callback=discoverer.handle_detection,
        scanning_mode="active",
    )

    try:
        await scanner.start()
        while True:
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        pass
    finally:
        await scanner.stop()
        print(f"\n{YELLOW}스캐너가 안전하게 종료되었습니다.{RESET}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n{YELLOW}프로그램을 종료합니다.{RESET}")
