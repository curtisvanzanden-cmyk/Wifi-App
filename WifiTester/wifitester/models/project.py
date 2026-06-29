"""Project and measurement data models."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import numpy as np


@dataclass
class MeasurementPoint:
    """Single measurement point with comprehensive metadata."""

    x: int
    y: int
    rssi: float
    timestamp: str
    ssid: str = ""
    bssid: str = ""
    channel: int = 0
    frequency: float = 0.0
    noise: float = 0.0
    note: str = ""
    link_quality: int = 0
    tx_rate: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(data: dict) -> MeasurementPoint:
        return MeasurementPoint(**data)


@dataclass
class ProjectMetadata:
    """Project-level metadata."""

    name: str
    location: str
    floor: str
    surveyor: str
    created: str
    modified: str
    floorplan_path: str
    calibration: Optional[Tuple[float, str]] = None
    notes: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(data: dict) -> ProjectMetadata:
        calibration = data.get("calibration")
        if calibration and isinstance(calibration, list):
            calibration = tuple(calibration)
        data = dict(data)
        data["calibration"] = calibration
        return ProjectMetadata(**data)


class Project:
    """Complete project container."""

    def __init__(self) -> None:
        now = datetime.now().isoformat()
        self.metadata = ProjectMetadata(
            name="New Project",
            location="",
            floor="",
            surveyor="",
            created=now,
            modified=now,
            floorplan_path="",
        )
        self.measurements: List[MeasurementPoint] = []
        self.access_points: Dict[str, dict] = {}

    def add_measurement(self, point: MeasurementPoint) -> None:
        self.measurements.append(point)
        self.metadata.modified = datetime.now().isoformat()
        self._track_access_point(point)

    def remove_last_measurement(self) -> Optional[MeasurementPoint]:
        if not self.measurements:
            return None
        removed = self.measurements.pop()
        self.metadata.modified = datetime.now().isoformat()
        self.rebuild_access_points()
        return removed

    def clear_measurements(self) -> None:
        self.measurements.clear()
        self.access_points.clear()
        self.metadata.modified = datetime.now().isoformat()

    def rebuild_access_points(self) -> None:
        """Rebuild AP index from current measurements (e.g. after undo)."""
        self.access_points.clear()
        for point in self.measurements:
            self._track_access_point(point)

    def _track_access_point(self, point: MeasurementPoint) -> None:
        if point.bssid and point.bssid not in self.access_points:
            self.access_points[point.bssid] = {
                "ssid": point.ssid,
                "channel": point.channel,
                "frequency": point.frequency,
                "first_seen": point.timestamp,
            }

    def get_statistics(self) -> dict:
        if not self.measurements:
            return {}

        rssi_values = [m.rssi for m in self.measurements]
        return {
            "count": len(self.measurements),
            "min_rssi": min(rssi_values),
            "max_rssi": max(rssi_values),
            "avg_rssi": float(np.mean(rssi_values)),
            "median_rssi": float(np.median(rssi_values)),
            "std_rssi": float(np.std(rssi_values)),
            "dead_zones": len([r for r in rssi_values if r < -80]),
            "good_coverage": len([r for r in rssi_values if r > -60]),
            "unique_aps": len(self.access_points),
            "channels": list({m.channel for m in self.measurements if m.channel}),
        }

    def to_dict(self) -> dict:
        return {
            "metadata": self.metadata.to_dict(),
            "measurements": [m.to_dict() for m in self.measurements],
            "access_points": self.access_points,
        }

    @staticmethod
    def from_dict(data: dict) -> Project:
        project = Project()
        project.metadata = ProjectMetadata.from_dict(data["metadata"])
        project.measurements = [MeasurementPoint.from_dict(m) for m in data["measurements"]]
        project.access_points = data.get("access_points", {})
        return project

    def save_to_file(self, filepath: str) -> None:
        with open(filepath, "w", encoding="utf-8") as handle:
            json.dump(self.to_dict(), handle, indent=2)

    @staticmethod
    def load_from_file(filepath: str) -> Project:
        with open(filepath, encoding="utf-8") as handle:
            data = json.load(handle)
        return Project.from_dict(data)
