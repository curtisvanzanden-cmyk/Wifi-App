import subprocess
import sys
import time
import platform
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from datetime import datetime
import numpy as np
import csv
import os

# --- Configuration ---
REFRESH_INTERVAL = 1000  # in ms
MAX_HISTORY = 300  # Keep last 300 seconds (5 minutes)
ENABLE_LOGGING = True
LOG_FILENAME = f"wifi_signal_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

# ----------------------

def detect_linux_interface():
    try:
        output = subprocess.check_output(['iwconfig'], stderr=subprocess.STDOUT).decode()
        for line in output.split('\n'):
            if 'IEEE 802.11' in line:
                return line.split()[0]
    except Exception:
        return 'wlan0'  # fallback
    return None

def get_wifi_info():
    os_type = platform.system().lower()
    info = {
        "signal": None,
        "ssid": "Unknown",
        "bssid": "Unknown",
        "freq": "Unknown",
        "bitrate": "Unknown"
    }

    if os_type == 'windows':
        try:
            output = subprocess.check_output(['netsh', 'wlan', 'show', 'interfaces']).decode()
            for line in output.split('\n'):
                if 'Signal' in line:
                    percent = int(line.split(':')[1].strip().replace('%', ''))
                    info['signal'] = (percent / 2) - 100  # Convert to dBm approx
                elif 'SSID' in line and 'BSSID' not in line:
                    info['ssid'] = line.split(':')[1].strip()
                elif 'BSSID' in line:
                    info['bssid'] = line.split(':')[1].strip()
                elif 'Radio type' in line:
                    info['freq'] = line.split(':')[1].strip()
                elif 'Receive rate' in line:
                    info['bitrate'] = line.split(':')[1].strip() + " Mbps"
        except Exception as e:
            print(f"[Windows] Error fetching WiFi info: {e}")

    elif os_type == 'linux':
        iface = detect_linux_interface()
        try:
            iwconfig = subprocess.check_output(['iwconfig', iface]).decode()
            for line in iwconfig.split('\n'):
                if 'Signal level' in line:
                    parts = line.split("Signal level=")
                    if len(parts) > 1:
                        info['signal'] = int(parts[1].split(' dBm')[0])
                if 'ESSID' in line:
                    info['ssid'] = line.split('ESSID:')[1].strip().replace('"', '')
                if 'Access Point' in line:
                    info['bssid'] = line.split('Access Point:')[1].strip()
                if 'Frequency' in line:
                    info['freq'] = line.split('Frequency:')[1].split()[0] + " GHz"
                if 'Bit Rate' in line:
                    info['bitrate'] = line.split('Bit Rate=')[1].split()[0] + " Mbps"
        except Exception as e:
            print(f"[Linux] Error fetching WiFi info: {e}")

    elif os_type == 'darwin':
        try:
            airport = '/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport'
            output = subprocess.check_output([airport, '-I']).decode()
            for line in output.split('\n'):
                if 'agrCtlRSSI' in line:
                    info['signal'] = int(line.split(':')[1].strip())
                elif 'SSID' in line and 'BSSID' not in line:
                    info['ssid'] = line.split(':')[1].strip()
                elif 'BSSID' in line:
                    info['bssid'] = line.split(':')[1].strip()
                elif 'lastTxRate' in line:
                    info['bitrate'] = line.split(':')[1].strip() + " Mbps"
                elif 'channel' in line:
                    freq = line.split(':')[1].strip()
                    info['freq'] = f"Channel {freq}"
        except Exception as e:
            print(f"[macOS] Error fetching WiFi info: {e}")

    return info

def get_color(strength):
    if strength is None:
        return 'gray'
    if strength >= -50:
        return 'green'
    elif strength >= -70:
        return 'yellow'
    else:
        return 'red'

def write_log(timestamp, info):
    if not ENABLE_LOGGING:
        return
    header = ['timestamp', 'signal_dBm', 'SSID', 'BSSID', 'frequency', 'bitrate']
    write_header = not os.path.exists(LOG_FILENAME)
    with open(LOG_FILENAME, 'a', newline='') as f:
        writer = csv.writer(f)
        if write_header:
            writer.writerow(header)
        writer.writerow([timestamp, info['signal'], info['ssid'], info['bssid'], info['freq'], info['bitrate']])

def main():
    print("🔧 WiFi Signal Monitor Pro")
    print("Press Ctrl+C or close the window to exit.")
    print("Logging is", "enabled" if ENABLE_LOGGING else "disabled")
    print()

    signal_history = []
    timestamps = []

    fig, (ax_bar, ax_line) = plt.subplots(2, 1, figsize=(10, 8))
    fig.suptitle("WiFi Signal Strength Monitor", fontsize=16, fontweight='bold')

    # Bar Chart (Current Strength)
    ax_bar.set_xlim(0, 1)
    ax_bar.set_ylim(-100, -30)
    ax_bar.set_ylabel('Signal Strength (dBm)')
    ax_bar.set_xticks([])
    bar = ax_bar.bar(0.5, -100, width=0.6, color='gray')
    bar_text = ax_bar.text(0.5, -95, "N/A", ha='center', va='center', fontsize=14, fontweight='bold')

    # Line Chart (History)
    ax_line.set_ylim(-100, -30)
    ax_line.set_ylabel('Signal (dBm)')
    ax_line.set_xlabel('Time (HH:MM:SS)')
    ax_line.grid(True)
    line, = ax_line.plot([], [], color='blue', label='Signal dBm')
    ax_line.legend()

    info_box = ax_line.text(0.01, 0.98, "", transform=ax_line.transAxes,
                            ha='left', va='top', fontsize=10, bbox=dict(facecolor='white', alpha=0.7))

    def update(frame):
        wifi_info = get_wifi_info()
        timestamp = datetime.now().strftime("%H:%M:%S")
        signal = wifi_info['signal']

        if signal is not None:
            # Update history
            signal_history.append(signal)
            timestamps.append(timestamp)
            if len(signal_history) > MAX_HISTORY:
                signal_history.pop(0)
                timestamps.pop(0)

            # Update bar
            bar[0].set_height(signal)
            bar[0].set_color(get_color(signal))
            bar_text.set_text(f"{signal} dBm")
        else:
            bar[0].set_height(-100)
            bar[0].set_color('gray')
            bar_text.set_text("N/A")

        # Update line chart
        line.set_data(range(len(signal_history)), signal_history)
        ax_line.set_xlim(0, len(signal_history) if len(signal_history) > 10 else 10)
        ax_line.set_xticks(np.linspace(0, len(timestamps)-1, num=min(10, len(timestamps)), dtype=int))
        ax_line.set_xticklabels([timestamps[i] for i in np.linspace(0, len(timestamps)-1, num=min(10, len(timestamps)), dtype=int)])

        # Update info box
        info_str = f"SSID: {wifi_info['ssid']}\nBSSID: {wifi_info['bssid']}\nFreq: {wifi_info['freq']}\nBitrate: {wifi_info['bitrate']}"
        info_box.set_text(info_str)

        # Log data
        write_log(datetime.now().isoformat(), wifi_info)

        return bar, line, bar_text, info_box

    ani = FuncAnimation(fig, update, interval=REFRESH_INTERVAL)
    plt.tight_layout(rect=[0, 0, 1, 0.95])
    plt.show()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nExiting WiFi Monitor Pro...")
        sys.exit(0)
