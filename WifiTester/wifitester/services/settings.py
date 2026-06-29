"""Application settings persistence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SETTINGS_DIR = Path.home() / ".config" / "wifitester"
SETTINGS_FILE = SETTINGS_DIR / "settings.json"

DEFAULTS: dict[str, Any] = {
    "onboarding_completed": False,
    "sample_count": 5,
    "sample_interval_ms": 300,
    "live_rssi_interval_ms": 500,
}


def load_settings() -> dict[str, Any]:
    if not SETTINGS_FILE.exists():
        return dict(DEFAULTS)

    try:
        with open(SETTINGS_FILE, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return dict(DEFAULTS)

    merged = dict(DEFAULTS)
    merged.update(data)
    return merged


def save_settings(settings: dict[str, Any]) -> None:
    SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
    merged = dict(DEFAULTS)
    merged.update(settings)
    with open(SETTINGS_FILE, "w", encoding="utf-8") as handle:
        json.dump(merged, handle, indent=2)
