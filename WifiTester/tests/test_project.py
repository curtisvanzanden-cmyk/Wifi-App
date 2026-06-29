from wifitester.models.project import MeasurementPoint, Project


def _point(x, y, rssi, bssid="aa:bb:cc:dd:ee:ff", ssid="TestAP"):
    return MeasurementPoint(
        x=x,
        y=y,
        rssi=rssi,
        timestamp="2025-01-01T12:00:00",
        ssid=ssid,
        bssid=bssid,
        channel=6,
    )


def test_undo_rebuilds_access_points():
    project = Project()
    project.add_measurement(_point(1, 1, -50, bssid="aa:bb:cc:dd:ee:01"))
    project.add_measurement(_point(2, 2, -60, bssid="aa:bb:cc:dd:ee:02"))

    assert len(project.access_points) == 2

    project.remove_last_measurement()
    assert len(project.measurements) == 1
    assert len(project.access_points) == 1
    assert "aa:bb:cc:dd:ee:01" in project.access_points


def test_project_round_trip(tmp_path):
    project = Project()
    project.metadata.name = "Round Trip"
    project.add_measurement(_point(10, 20, -55))

    filepath = tmp_path / "test.wifiproj"
    project.save_to_file(str(filepath))
    loaded = Project.load_from_file(str(filepath))

    assert loaded.metadata.name == "Round Trip"
    assert len(loaded.measurements) == 1
    assert loaded.measurements[0].rssi == -55
