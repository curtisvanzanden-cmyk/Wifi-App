"""WiFi signal sampling utilities."""

from __future__ import annotations

from statistics import median
from typing import Iterable, Optional


def median_rssi(readings: Iterable[float]) -> Optional[float]:
    values = [float(value) for value in readings]
    if not values:
        return None
    return float(median(values))
