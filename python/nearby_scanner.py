#!/usr/bin/env python3
"""
Nearby Connections BLE Discoverer / Scanner for Raspberry Pi
============================================================
Scans for BLE advertising packets emitted by smartphones using
Google Nearby Connections (UUID: 0xFEF3) or specified Service UUIDs.
Features session tracking, background noise filtering, and clean ASCII logging.
"""

import asyncio
import datetime
import hashlib
import json
import os
import subprocess
import sys
import time
from typing import Dict, List, Optional

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
        "only_nearby_connections_endpoints": True,
        "target_endpoint_ids": [],
        "scan_all_google_nearby": False,
        "custom_service_uuids": [
            "0000fef3-0000-1000-8000-00805f9b34fb"
        ],
        "rssi_threshold": -80,
        "update_interval_seconds": 10,
        "min_log_interval_seconds": 5,
        "rssi_delta_threshold": 8,
        "timeout_seconds": 15,
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


def estimate_distance(rssi: int) -> str:
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
        self.only_nearby_endpoints = config.get("only_nearby_connections_endpoints", True)
        self.target_endpoints: List[str] = [
            ep.upper() for ep in config.get("target_endpoint_ids", [])
        ]
        self.scan_all_google = config.get("scan_all_google_nearby", False)

        self.rssi_threshold = config.get("rssi_threshold", -80)
        self.update_interval = config.get("update_interval_seconds", 10)
        self.min_log_interval = config.get("min_log_interval_seconds", 5)
        self.rssi_delta = config.get("rssi_delta_threshold", 8)
        self.timeout_seconds = config.get("timeout_seconds", 15)

        # Active devices: addr -> session dict
        self.active_devices: Dict[str, dict] = {}
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

        # Bytes 1-3: Service ID Hash (3 bytes)
        payload_hash = raw_data[1:4]
        if payload_hash == self.service_id_hash[:3]:
            info["matched_service_id"] = True

        # Bytes 4-7: 4-byte Endpoint ID
        if len(raw_data) >= 8:
            try:
                candidate = raw_data[4:8].decode("ascii")
                if candidate.isalnum() and len(candidate) == 4:
                    info["endpoint_id"] = candidate
            except Exception:
                pass

        # Fallback scan for 4-char alphanumeric endpoint in the payload
        if not info["endpoint_id"] and len(raw_data) >= 8:
            for offset in range(1, min(10, len(raw_data) - 4)):
                try:
                    candidate = raw_data[offset : offset + 4].decode("ascii")
                    if candidate.isalnum() and len(candidate) == 4 and candidate.isupper():
                        info["endpoint_id"] = candidate
                        break
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

        parsed_info = self.parse_nearby_payload(nearby_service_data) if nearby_service_data else None

        # 3. Noise Filter: Ignore background beacons (earbuds/watches) that are not Nearby Connections
        if is_google_nearby and self.only_nearby_endpoints:
            if not parsed_info or not parsed_info.get("endpoint_id"):
                # No valid Nearby Connections Endpoint ID -> Ignore background noise
                return

        # 4. Target Endpoint ID Filter (if specified in config)
        if self.target_endpoints:
            ep = parsed_info.get("endpoint_id") if parsed_info else None
            if not ep or ep.upper() not in self.target_endpoints:
                return

        device_name = adv.local_name or device.name or "Unknown Device"

        # 5. Session Tracking & Rate Limiting
        is_new_device = addr not in self.active_devices

        if is_new_device:
            # First time seeing this target device: Display full card
            self.active_devices[addr] = {
                "first_seen": now,
                "last_seen": now,
                "last_logged_time": now,
                "last_logged_rssi": rssi,
                "name": device_name,
                "endpoint_id": parsed_info.get("endpoint_id") if parsed_info else None,
                "endpoint_info": parsed_info.get("endpoint_info") if parsed_info else None,
                "packet_count": 1,
            }

            timestamp = datetime.datetime.now().strftime("%H:%M:%S")
            proximity = estimate_distance(rssi)

            print("\n" + "=" * 65)
            print(f"{BOLD}{GREEN}[TARGET PHONE DETECTED] Google Nearby Connections{RESET}")
            print(f"Time: {timestamp} | MAC: {BOLD}{addr}{RESET} | Name: {device_name}")
            print(f"RSSI: {BOLD}{rssi} dBm{RESET} ({proximity})")

            if parsed_info:
                if parsed_info.get("endpoint_id"):
                    print(f"Endpoint ID: {BOLD}{GREEN}{parsed_info['endpoint_id']}{RESET}")
                if parsed_info.get("endpoint_info"):
                    print(f"Endpoint Info: {parsed_info['endpoint_info']}")
                if parsed_info.get("hex"):
                    print(f"Payload Hex: {parsed_info['hex']}")
                if parsed_info.get("matched_service_id"):
                    print(f"[MATCH] {GREEN}Target Service ID matched!{RESET} ({self.service_id})")

            print("=" * 65)

            # Log to file
            log_msg = f"NEW_DEVICE | MAC={addr} | RSSI={rssi} | Name={device_name}"
            if parsed_info and parsed_info.get("endpoint_id"):
                log_msg += f" | Endpoint={parsed_info['endpoint_id']}"
            self.log_event(log_msg)

            # Trigger external command if configured
            cmd = self.config.get("trigger_command", "").strip()
            if cmd:
                try:
                    env = os.environ.copy()
                    env["NEARBY_MAC"] = str(addr)
                    env["NEARBY_RSSI"] = str(rssi)
                    env["NEARBY_NAME"] = str(device_name)
                    if parsed_info and parsed_info.get("endpoint_id"):
                        env["NEARBY_ENDPOINT"] = str(parsed_info["endpoint_id"])
                    subprocess.Popen(cmd, shell=True, env=env)
                except Exception as e:
                    print(f"[WARN] Failed to run trigger command: {e}")

        else:
            # Device already known: update stats
            dev = self.active_devices[addr]
            dev["last_seen"] = now
            dev["packet_count"] += 1
            if parsed_info and parsed_info.get("endpoint_id"):
                dev["endpoint_id"] = parsed_info["endpoint_id"]

            time_since_last_log = now - dev["last_logged_time"]
            rssi_diff = abs(rssi - dev["last_logged_rssi"])

            # Never log faster than min_log_interval (5s)
            # Log only if update_interval elapsed (10s) OR (min_interval elapsed AND RSSI delta >= 8 dBm)
            should_log = (time_since_last_log >= self.update_interval) or (
                time_since_last_log >= self.min_log_interval and rssi_diff >= self.rssi_delta
            )

            if should_log:
                dev["last_logged_time"] = now
                dev["last_logged_rssi"] = rssi
                duration = int(now - dev["first_seen"])
                proximity = estimate_distance(rssi)
                timestamp = datetime.datetime.now().strftime("%H:%M:%S")

                ep_tag = f" (Endpoint: {dev['endpoint_id']})" if dev.get("endpoint_id") else ""
                print(
                    f"[{timestamp}] [TRACKING] MAC: {BOLD}{addr}{RESET}{ep_tag} | "
                    f"RSSI: {BOLD}{rssi} dBm{RESET} ({proximity}) | "
                    f"In range: {duration}s"
                )

    async def cleanup_loop(self):
        """Check for devices that stopped transmitting and notify exit"""
        while True:
            await asyncio.sleep(2)
            now = time.time()
            to_remove = []

            for addr, dev in list(self.active_devices.items()):
                if (now - dev["last_seen"]) > self.timeout_seconds:
                    to_remove.append(addr)
                    duration = int(now - dev["first_seen"])
                    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
                    ep_tag = f" (Endpoint: {dev['endpoint_id']})" if dev.get("endpoint_id") else ""
                    print(
                        f"[{timestamp}] {YELLOW}[DEVICE LEFT]{RESET} MAC: {BOLD}{addr}{RESET}{ep_tag} | "
                        f"Was in range for: {duration}s"
                    )
                    self.log_event(f"DEVICE_LEFT | MAC={addr} | Duration={duration}s")

            for addr in to_remove:
                self.active_devices.pop(addr, None)


async def main():
    config = load_config()
    discoverer = NearbyDiscoverer(config)

    print(f"\n{BOLD}{CYAN}=========================================================={RESET}")
    print(f"{BOLD}{CYAN}   Raspberry Pi Nearby Connections BLE Discoverer{RESET}")
    print(f"{BOLD}{CYAN}=========================================================={RESET}")
    print(f"- Target Service ID: {BOLD}{discoverer.service_id}{RESET}")
    print(f"- Filter Noise: ONLY Nearby Connections Advertisers (Endpoint ID required)")
    print(f"- RSSI Sensitivity Filter: >= {discoverer.rssi_threshold} dBm")
    print(f"- Update Interval: {discoverer.update_interval}s (Min interval: {discoverer.min_log_interval}s)")
    print(f"- Device Departure Timeout: {discoverer.timeout_seconds}s")
    print(f"- Log File: {discoverer.log_file}")
    print("Scanning for target smartphone... (Stop: Ctrl+C)\n")

    scanner = BleakScanner(
        detection_callback=discoverer.handle_detection,
        scanning_mode="active",
    )

    cleanup_task = asyncio.create_task(discoverer.cleanup_loop())

    try:
        await scanner.start()
        while True:
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        pass
    finally:
        cleanup_task.cancel()
        await scanner.stop()
        print(f"\n{YELLOW}Scanner stopped cleanly.{RESET}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Scanner terminated by user.{RESET}")
