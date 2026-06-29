# WiFi Heatmap Pro

WiFi site survey tool for mapping signal strength on floorplans and generating coverage heatmaps.

## Requirements

- Python 3.10+
- Tkinter (usually included with Python)
- WiFi tools for your platform:
  - **Windows:** `netsh`
  - **Linux:** `iwconfig` or `nmcli`
  - **macOS:** built-in `airport` utility

## Install

```bash
cd WifiTester
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Run

```bash
python main.py
```

Or:

```bash
python -m wifitester
```

## Quick start

1. **File → New Project** (or use the default project)
2. **Select Floorplan** and choose an image (PNG/JPG)
3. **Start Measuring** and click points on the map
4. **Generate Heatmap** to visualize coverage
5. **Save Project** to store measurements and metadata (`.wifiproj`)

Projects auto-save every 5 minutes. Unsaved work is written to `~/.config/wifitester/autosave/autosave.wifiproj`.

## Test mode

Enable **Test Mode (Simulate)** in the sidebar to add measurements without live WiFi hardware.

## Development

```bash
pip install -r requirements.txt
pip install pytest
pytest
```

## Project layout

```
WifiTester/
├── main.py                 # Application entry point
├── wifitester/
│   ├── app.py              # Tkinter UI
│   ├── models/project.py   # Project and measurement models
│   └── services/
│       ├── wifi_scanner.py # Cross-platform WiFi scanning
│       └── heatmap.py      # Heatmap interpolation and rendering
├── tests/
└── legacy/                 # Earlier prototype scripts
```

## Legacy scripts

Older prototypes (`Tool.py`, `Tool0.01.py`, `tool0.02.py`) are in `legacy/` for reference. Use `main.py` for all new work.
