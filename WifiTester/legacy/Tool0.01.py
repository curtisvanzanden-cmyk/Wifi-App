import os
import csv
import platform
import subprocess
from datetime import datetime
import tkinter as tk
from tkinter import filedialog, messagebox

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
from scipy.interpolate import griddata


# --- Globals ---
click_coords = []
signal_strengths = []
floorplan_path = None
output_csv = "heatmap_data.csv"

fig = None
ax = None


def get_signal_strength() -> int | None:
    """Get WiFi signal strength in dBm, platform-specific."""
    os_type = platform.system().lower()

    try:
        if os_type == "windows":
            output = subprocess.check_output(
                ["netsh", "wlan", "show", "interfaces"], stderr=subprocess.DEVNULL
            ).decode()
            for line in output.splitlines():
                if "Signal" in line:
                    percent = int(line.split(":")[1].strip().replace("%", ""))
                    return round((percent / 2) - 100)

        elif os_type == "linux":
            iface = detect_linux_interface()
            output = subprocess.check_output(
                ["iwconfig", iface], stderr=subprocess.DEVNULL
            ).decode()
            for line in output.splitlines():
                if "Signal level" in line:
                    return int(line.split("Signal level=")[1].split(" dBm")[0])

        elif os_type == "darwin":  # macOS
            airport = (
                "/System/Library/PrivateFrameworks/Apple80211.framework"
                "/Versions/Current/Resources/airport"
            )
            output = subprocess.check_output([airport, "-I"]).decode()
            for line in output.splitlines():
                if "agrCtlRSSI" in line:
                    return int(line.split(":")[1].strip())

    except Exception as e:
        log_msg(f"Error getting signal: {e}", "ERROR")

    return None


def detect_linux_interface() -> str:
    """Detect active WiFi interface on Linux."""
    try:
        output = subprocess.check_output(["iwconfig"], stderr=subprocess.STDOUT).decode()
        for line in output.splitlines():
            if "IEEE 802.11" in line:
                return line.split()[0]
    except Exception:
        pass
    return "wlan0"  # fallback


def onclick(event):
    """Handle clicks on the floorplan plot."""
    if event.xdata is None or event.ydata is None:
        return

    x, y = int(event.xdata), int(event.ydata)
    signal = get_signal_strength()

    if signal is not None:
        click_coords.append((x, y))
        signal_strengths.append(signal)

        ax.plot(x, y, "ro")
        ax.text(x + 5, y, f"{signal} dBm", color="black", fontsize=8)
        fig.canvas.draw()

        log_msg(f"Point added at ({x}, {y}) with {signal} dBm")
    else:
        log_msg("Failed to read WiFi signal strength", "WARN")


def save_data():
    """Save collected points to CSV file."""
    if not click_coords:
        messagebox.showwarning("No Data", "No data to save yet.")
        return

    with open(output_csv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["x", "y", "signal_dBm", "timestamp"])
        for (x, y), s in zip(click_coords, signal_strengths):
            writer.writerow([x, y, s, datetime.now().isoformat()])

    log_msg(f"Data saved to {output_csv}")


def generate_heatmap():
    """Generate WiFi heatmap overlayed on floorplan."""
    if not click_coords:
        messagebox.showwarning("No Data", "No data points recorded.")
        return

    x_coords, y_coords = zip(*click_coords)
    strength = signal_strengths

    xi = np.linspace(min(x_coords), max(x_coords), 200)
    yi = np.linspace(min(y_coords), max(y_coords), 200)
    xi, yi = np.meshgrid(xi, yi)

    try:
        zi = griddata((x_coords, y_coords), strength, (xi, yi), method="cubic")
    except Exception as e:
        log_msg(f"Interpolation failed: {e}", "ERROR")
        return

    fig2, ax2 = plt.subplots(figsize=(10, 8))
    try:
        img = mpimg.imread(floorplan_path)
        ax2.imshow(img, extent=[0, img.shape[1], img.shape[0], 0])
    except FileNotFoundError:
        log_msg(f"Floorplan not found at {floorplan_path}", "ERROR")
        return

    heatmap = ax2.contourf(xi, yi, zi, 15, cmap="RdYlGn", alpha=0.6)
    plt.colorbar(heatmap, ax=ax2, label="Signal Strength (dBm)")
    ax2.set_title("WiFi Heatmap")
    plt.tight_layout()
    plt.show()


def choose_floorplan():
    """Ask user to select a floorplan image file."""
    global floorplan_path
    floorplan_path = filedialog.askopenfilename(
        title="Select Floorplan",
        filetypes=[
            ("PNG Files", "*.png"),
            ("JPEG Files", "*.jpg"),
            ("JPEG Files", "*.jpeg"),
            ("Bitmap Files", "*.bmp"),
            ("All Files", "*.*"),
        ],
    )
    if floorplan_path:
        log_msg(f"Selected floorplan: {floorplan_path}")
    else:
        log_msg("No floorplan selected", "WARN")



def start_mapping():
    """Start floorplan click mapping."""
    global fig, ax

    if not floorplan_path:
        messagebox.showerror("No Floorplan", "Please select a floorplan first.")
        return

    img = mpimg.imread(floorplan_path)
    fig, ax = plt.subplots(figsize=(10, 8))
    ax.imshow(img)
    ax.set_title("Click on the floorplan to record WiFi signal")

    fig.canvas.mpl_connect("button_press_event", onclick)

    log_msg("Click on the map to add points. Close window when done.")
    plt.show()


def log_msg(msg: str, level: str = "INFO"):
    """Log message into Tkinter text box."""
    colors = {"INFO": "black", "WARN": "orange", "ERROR": "red"}
    log_box.insert(tk.END, f"[{level}] {msg}\n", level)
    log_box.see(tk.END)


# --- Tkinter GUI ---
root = tk.Tk()
root.title("WiFi Heatmap Tool")

frame = tk.Frame(root)
frame.pack(padx=10, pady=10)

btn_select = tk.Button(frame, text="Select Floorplan", command=choose_floorplan)
btn_select.grid(row=0, column=0, padx=5, pady=5)

btn_start = tk.Button(frame, text="Start Mapping", command=start_mapping)
btn_start.grid(row=0, column=1, padx=5, pady=5)

btn_save = tk.Button(frame, text="Save Data", command=save_data)
btn_save.grid(row=1, column=0, padx=5, pady=5)

btn_heatmap = tk.Button(frame, text="Generate Heatmap", command=generate_heatmap)
btn_heatmap.grid(row=1, column=1, padx=5, pady=5)

# Log window
log_box = tk.Text(root, height=10, width=60)
log_box.pack(padx=10, pady=10)

for tag, color in {"INFO": "black", "WARN": "orange", "ERROR": "red"}.items():
    log_box.tag_configure(tag, foreground=color)

root.mainloop()
