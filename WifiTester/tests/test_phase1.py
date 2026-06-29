from wifitester.services.heatmap import can_render_heatmap, image_bounds, MIN_HEATMAP_POINTS
from wifitester.services.sampler import median_rssi
from wifitester.services.settings import DEFAULTS, load_settings, save_settings
from wifitester.ui.signal_style import rssi_to_color


def test_median_rssi():
    assert median_rssi([-50, -52, -48, -51, -49]) == -50.0
    assert median_rssi([]) is None


def test_rssi_to_color_bands():
    assert rssi_to_color(-45) == "#22c55e"
    assert rssi_to_color(-65) == "#eab308"
    assert rssi_to_color(-75) == "#f97316"
    assert rssi_to_color(-85) == "#ef4444"


def test_image_bounds():
    assert image_bounds(800, 600) == (0.0, 800.0, 0.0, 600.0)


def test_can_render_heatmap():
    assert not can_render_heatmap(MIN_HEATMAP_POINTS - 1)
    assert can_render_heatmap(MIN_HEATMAP_POINTS)


def test_settings_round_trip(tmp_path, monkeypatch):
    settings_file = tmp_path / "settings.json"
    monkeypatch.setattr("wifitester.services.settings.SETTINGS_FILE", settings_file)

    save_settings({"onboarding_completed": True, "sample_count": 3})
    loaded = load_settings()
    assert loaded["onboarding_completed"] is True
    assert loaded["sample_count"] == 3
    assert loaded["live_rssi_interval_ms"] == DEFAULTS["live_rssi_interval_ms"]
