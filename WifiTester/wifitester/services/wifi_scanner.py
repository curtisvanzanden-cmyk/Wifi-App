"""Cross-platform WiFi signal scanning."""

from __future__ import annotations

import platform
import re
import subprocess
from typing import Dict, Optional


def percent_to_dbm(percent: int) -> int:
    """Convert Windows-style signal percentage to approximate dBm."""
    return round((percent / 2) - 100)


def parse_windows_output(output: str) -> Optional[Dict]:
    info = {"rssi": None, "ssid": "", "bssid": "", "channel": 0}

    for line in output.splitlines():
        line = line.strip()
        if "SSID" in line and "BSSID" not in line:
            info["ssid"] = line.split(":", 1)[1].strip()
        elif "BSSID" in line:
            info["bssid"] = line.split(":", 1)[1].strip()
        elif "Signal" in line:
            percent = int(line.split(":", 1)[1].strip().replace("%", ""))
            info["rssi"] = percent_to_dbm(percent)
        elif "Channel" in line:
            try:
                info["channel"] = int(line.split(":", 1)[1].strip())
            except ValueError:
                pass

    return info if info["rssi"] is not None else None


def parse_linux_iwconfig_output(output: str) -> Optional[Dict]:
    info = {"rssi": None, "ssid": "", "bssid": "", "channel": 0}

    for line in output.splitlines():
        if "ESSID" in line:
            match = re.search(r'ESSID:"([^"]*)"', line)
            if match:
                info["ssid"] = match.group(1)
        if "Access Point" in line:
            match = re.search(r"Access Point: ([0-9A-Fa-f:]+)", line)
            if match:
                info["bssid"] = match.group(1)
        if "Signal level" in line:
            match = re.search(r"Signal level=(-?\d+)\s*dBm", line)
            if match:
                info["rssi"] = int(match.group(1))
            else:
                quality_match = re.search(r"Signal level=(\d+)/(\d+)", line)
                if quality_match:
                    current, maximum = map(int, quality_match.groups())
                    if maximum:
                        info["rssi"] = percent_to_dbm(round((current / maximum) * 100))
        if "Frequency" in line:
            match = re.search(r"Channel (\d+)", line)
            if match:
                info["channel"] = int(match.group(1))

    return info if info["rssi"] is not None else None


def parse_linux_nmcli_output(output: str) -> Optional[Dict]:
    info = {"rssi": None, "ssid": "", "bssid": "", "channel": 0}

    for line in output.splitlines():
        if not line.startswith("*"):
            continue

        parts = line[1:].lstrip(":").split(":")
        if len(parts) < 4:
            continue

        info["ssid"] = parts[0]
        info["bssid"] = ":".join(parts[1:-2])
        info["channel"] = int(parts[-2]) if parts[-2] else 0
        info["rssi"] = percent_to_dbm(int(parts[-1]))
        break

    return info if info["rssi"] is not None else None


def parse_macos_output(output: str) -> Optional[Dict]:
    info = {"rssi": None, "ssid": "", "bssid": "", "channel": 0}

    for line in output.splitlines():
        line = line.strip()
        if "agrCtlRSSI" in line or line.startswith("RSSI"):
            info["rssi"] = int(line.split(":", 1)[1].strip())
        elif "SSID" in line and "BSSID" not in line:
            info["ssid"] = line.split(":", 1)[1].strip()
        elif "BSSID" in line:
            info["bssid"] = line.split(":", 1)[1].strip()
        elif "channel" in line.lower():
            try:
                info["channel"] = int(line.split(":", 1)[1].strip())
            except ValueError:
                pass

    return info if info["rssi"] is not None else None


class WiFiScanner:
    """Enhanced WiFi scanning with detailed network info."""

    @staticmethod
    def get_detailed_info() -> Optional[Dict]:
        os_type = platform.system().lower()

        try:
            if os_type.startswith("win"):
                return WiFiScanner._scan_windows()
            if os_type.startswith("linux"):
                return WiFiScanner._scan_linux()
            if os_type.startswith("darwin"):
                return WiFiScanner._scan_macos()
        except (subprocess.CalledProcessError, FileNotFoundError, OSError) as exc:
            print(f"WiFi scan error: {exc}")

        return None

    @staticmethod
    def _scan_windows() -> Optional[Dict]:
        output = subprocess.check_output(
            ["netsh", "wlan", "show", "interfaces"],
            stderr=subprocess.DEVNULL,
        ).decode(errors="ignore")
        return parse_windows_output(output)

    @staticmethod
    def _scan_linux() -> Optional[Dict]:
        info: Dict = {"rssi": None, "ssid": "", "bssid": "", "channel": 0}

        try:
            iface = WiFiScanner._detect_linux_interface()
            output = subprocess.check_output(
                ["iwconfig", iface],
                stderr=subprocess.DEVNULL,
            ).decode(errors="ignore")
            parsed = parse_linux_iwconfig_output(output)
            if parsed:
                info = parsed
        except (subprocess.CalledProcessError, FileNotFoundError, OSError):
            pass

        if info["rssi"] is None:
            try:
                output = subprocess.check_output(
                    ["nmcli", "-t", "-f", "IN-USE,SSID,BSSID,CHAN,SIGNAL", "device", "wifi"],
                    stderr=subprocess.DEVNULL,
                ).decode(errors="ignore")
                parsed = parse_linux_nmcli_output(output)
                if parsed:
                    info = parsed
            except (subprocess.CalledProcessError, FileNotFoundError, OSError):
                pass

        return info if info["rssi"] is not None else None

    @staticmethod
    def _scan_macos() -> Optional[Dict]:
        airport = (
            "/System/Library/PrivateFrameworks/Apple80211.framework"
            "/Versions/Current/Resources/airport"
        )
        output = subprocess.check_output([airport, "-I"]).decode(errors="ignore")
        return parse_macos_output(output)

    @staticmethod
    def _detect_linux_interface() -> str:
        try:
            output = subprocess.check_output(["iwconfig"], stderr=subprocess.DEVNULL).decode(
                errors="ignore"
            )
            for line in output.splitlines():
                if "IEEE 802.11" in line:
                    return line.split()[0]
        except (subprocess.CalledProcessError, FileNotFoundError, OSError):
            pass
        return "wlan0"
