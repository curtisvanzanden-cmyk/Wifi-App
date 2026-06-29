from wifitester.services.wifi_scanner import (
    parse_linux_iwconfig_output,
    parse_linux_nmcli_output,
    parse_macos_output,
    parse_windows_output,
    percent_to_dbm,
)


WINDOWS_SAMPLE = """
    Name                   : Wi-Fi
    SSID                   : OfficeNet
    BSSID                  : aa:bb:cc:dd:ee:ff
    Signal                 : 85%
    Channel                : 36
"""

LINUX_IWCONFIG_SAMPLE = """
wlan0     IEEE 802.11  ESSID:"HomeWiFi"
          Access Point: 11:22:33:44:55:66
          Signal level=-52 dBm
          Frequency:5.18 GHz (Channel 36)
"""

LINUX_NMCLI_SAMPLE = "*:HomeWiFi:11:22:33:44:55:66:36:78"

MACOS_SAMPLE = """
     agrCtlRSSI: -48
     SSID: CafeWiFi
     BSSID: de:ad:be:ef:00:01
     channel: 11
"""


def test_percent_to_dbm():
    assert percent_to_dbm(100) == -50
    assert percent_to_dbm(80) == -60


def test_parse_windows_output():
    info = parse_windows_output(WINDOWS_SAMPLE)
    assert info is not None
    assert info["ssid"] == "OfficeNet"
    assert info["bssid"] == "aa:bb:cc:dd:ee:ff"
    assert info["rssi"] == -58
    assert info["channel"] == 36


def test_parse_linux_iwconfig_output():
    info = parse_linux_iwconfig_output(LINUX_IWCONFIG_SAMPLE)
    assert info is not None
    assert info["ssid"] == "HomeWiFi"
    assert info["bssid"] == "11:22:33:44:55:66"
    assert info["rssi"] == -52
    assert info["channel"] == 36


def test_parse_linux_iwconfig_quality_format():
    output = "wlan0  Signal level=35/70  ESSID:\"Test\""
    info = parse_linux_iwconfig_output(output)
    assert info is not None
    assert info["ssid"] == "Test"
    assert info["rssi"] == percent_to_dbm(50)


def test_parse_linux_nmcli_output():
    info = parse_linux_nmcli_output(LINUX_NMCLI_SAMPLE)
    assert info is not None
    assert info["ssid"] == "HomeWiFi"
    assert info["bssid"] == "11:22:33:44:55:66"
    assert info["channel"] == 36
    assert info["rssi"] == -61


def test_parse_macos_output():
    info = parse_macos_output(MACOS_SAMPLE)
    assert info is not None
    assert info["ssid"] == "CafeWiFi"
    assert info["bssid"] == "de:ad:be:ef:00:01"
    assert info["rssi"] == -48
    assert info["channel"] == 11
