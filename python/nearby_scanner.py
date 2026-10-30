#!/usr/bin/env python3
"""
Nearby Connections BLE Discoverer / Scanner for Raspberry Pi
============================================================
Scans for BLE advertising packets emitted by smartphones using
Google Nearby Connections (UUID: 0xFEF3) or specified Service UUIDs.
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
    print("\n[ERROR] 'bleak' package is not installed.")
    print("Please install dependencies:")
    print("    pip install -r requirements.txt\n")
    sys.exit(1)

# Google 16-bit UUID for Nearby Connections / Fast Pair
GOOGLE_NEARBY_UUID_16 = "0000fef3-0000-1000-8000-00805f9b34fb"
SHORT_FEF3 = "fef3"

# ANSI Color Codes
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RED = "\033[91m"
MAGENTA = "\033[95m"


def load_config(config_path: str = "config.json") -> dict:
    default_config = {
        "service_id": "com.atec.mobility.k.hero.nearby.connections.SERVICE_ID",
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
            print(f"[WARN] Failed to load config ({e}). Using defaults.")
    return default_config


def compute_service_id_hash(service_id: str) -> bytes:
    """Nearby Connections standard: SHA-256 hash of Service ID string (first 3-4 bytes)"""
    sha = hashlib.sha256()
    sha.update(service_id.encode("utf-8"))
    return sha.digest()


def estimate_distance(rssi: int, tx_power: int = -59) -> str:
    """Rough distance estimate based on RSSI"""
    if rssi >= -60:
        return f"{GREEN}Immediate (< 1m){RESET}"
    elif rssi >= -75:
        return f"{YELLOW}Near (1-3m){RESET}"
    elif rssi >= -85:
        return f"{CYAN}Normal (3-7m){RESET}"
    else:
        return f"{MAGENTA}Far (> 7m){RESET}"


class NearbyDiscoverer:
    def __init__(self, config: dict):
        self.config = config
        self.service_id = config.get(
            "service_id", "com.atec.mobility.k.hero.nearby.connections.SERVICE_ID"
        )
        self.service_id_hash = compute_service_id_hash(self.service_id)
        self.rssi_threshold = config.get("rssi_threshold", -85)
        self.cooldown = config.get("detection_cooldown_seconds", 3)
        self.last_seen: Dict[str, float] = {}
        self.log_file = config.get("log_file", "detections.log")
        self.log_to_file = config.get("log_to_file", True)

        # Normalize target UUIDs
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
            print(f"[ERROR] Failed to write log: {e}")

    def parse_nearby_payload(self, raw_data: bytes) -> dict:
        """Parse Nearby Connections 0xFEF3 Service Data"""
        info = {
            "hex": raw_data.hex(),
            "matched_service_id": False,
            "endpoint_id": None,
            "endpoint_info": None,
        }

        if len(raw_data) < 4:
            return info

        # Byte 0: Header / Version / Type
        # Bytes 1-3: Service ID Hash (3 bytes)
        payload_hash = raw_data[1:4]
        if payload_hash == self.service_id_hash[:3]:
            info["matched_service_id"] = True

        # Bytes 4-7: 4-byte Endpoint ID
        if len(raw_data) >= 8:
            try:
                endpoint_id_candidate = raw_data[4:8].decode("ascii")
                if endpoint_id_candidate.isalnum():
                    info["endpoint_id"] = endpoint_id_candidate
            except Exception:
                pass

        # Remaining bytes: Endpoint Info
        if len(raw_data) > 8:
            try:
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

        # 1. Check Google Nearby UUID (0xFEF3)
        is_google_nearby = False
        nearby_service_data: Optional[bytes] = None

        for uuid_key, data in adv.service_data.items():
            uuid_str = str(uuid_key).lower()
            if SHORT_FEF3 in uuid_str or uuid_str == GOOGLE_NEARBY_UUID_16:
                is_google_nearby = True
                nearby_service_data = data
                break

        for s_uuid in adv.service_uuids:
            s_uuid_lower = s_uuid.lower()
            if SHORT_FEF3 in s_uuid_lower or s_uuid_lower == GOOGLE_NEARBY_UUID_16:
                is_google_nearby = True
                break

        # 2. Check Custom UUID match
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

        if not is_google_nearby and not is_custom_matched:
            return

        # 3. Format detection output
        self.last_seen[addr] = now
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        device_name = adv.local_name or device.name or "Unknown Device"
        proximity = estimate_distance(rssi)

        print("\n" + "=" * 65)
        if is_google_nearby:
            print(f"{BOLD}{GREEN}[DETECTED] Google Nearby Connections Signal{RESET}")
        else:
            print(f"{BOLD}{CYAN}[DETECTED] Custom BLE Service Signal{RESET} (UUID: {matched_custom_uuid})")

        print(f"Time: {timestamp} | MAC: {BOLD}{addr}{RESET} | Name: {device_name}")
        print(f"RSSI: {BOLD}{rssi} dBm{RESET} ({proximity})")

        parsed_info = None
        if nearby_service_data:
            parsed_info = self.parse_nearby_payload(nearby_service_data)
            print(f"Service Data Hex: {parsed_info['hex']}")
            if parsed_info["matched_service_id"]:
                print(f"[MATCH] {GREEN}Target Service ID Matched!{RESET} ({self.service_id})")
            if parsed_info["endpoint_id"]:
                print(f"Endpoint ID: {parsed_info['endpoint_id']}")
            if parsed_info["endpoint_info"]:
                print(f"Endpoint Info: {parsed_info['endpoint_info']}")
        elif adv.manufacturer_data:
            mfg_hex = " ".join(f"{k}: {v.hex()}" for k, v in adv.manufacturer_data.items())
            print(f"Manufacturer Data: {mfg_hex}")

        print("=" * 65)

        # Log event
        log_msg = f"DETECTED | MAC={addr} | RSSI={rssi} | Name={device_name}"
        if parsed_info and parsed_info.get("hex"):
            log_msg += f" | Payload={parsed_info['hex']}"
        self.log_event(log_msg)

        # Trigger external command if configured
        cmd = self.config.get("trigger_command", "").strip()
        if cmd:
            try:
                env = os.environ.copy()
                env["NEARBY_MAC"] = str(addr)
                env["NEARBY_RSSI"] = str(rssi)
                env["NEARBY_NAME"] = str(device_name)
                subprocess.Popen(cmd, shell=True, env=env)
            except Exception as e:
                print(f"[WARN] Failed to run trigger command: {e}")


async def main():
    config = load_config()
    discoverer = NearbyDiscoverer(config)

    print(f"\n{BOLD}{CYAN}=========================================================={RESET}")
    print(f"{BOLD}{CYAN}   Raspberry Pi Nearby Connections BLE Discoverer{RESET}")
    print(f"{BOLD}{CYAN}=========================================================={RESET}")
    print(f"- Target Service ID: {BOLD}{discoverer.service_id}{RESET}")
    print(f"- Service ID Hash Prefix: {discoverer.service_id_hash[:3].hex().upper()}")
    print(f"- RSSI Sensitivity Filter: >= {discoverer.rssi_threshold} dBm")
    print(f"- Log File: {discoverer.log_file}")
    print("Scanning for smartphone advertising packets... (Stop: Ctrl+C)\n")

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
        print(f"\n{YELLOW}Scanner stopped cleanly.{RESET}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Scanner terminated by user.{RESET}")
