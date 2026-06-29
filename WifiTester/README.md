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

1. Run the app — a **Getting Started** wizard appears on first launch
2. Enter project details and **load a floorplan** image (PNG/JPG)
3. The map enters **survey mode** automatically — click points to record signal
4. Switch **Map view** to Points, Heatmap, or Overlay in the sidebar
5. **Save Project** to store measurements and metadata (`.wifiproj`)

Projects auto-save every 5 minutes. Unsaved work is written to `~/.config/wifitester/autosave/autosave.wifiproj`.

### Survey workflow

- **Live signal** is shown in the toolbar while you work
- Each click **samples WiFi several times** and stores the median RSSI
- Heatmap view requires at least **3 measurement points**
- Use **Test mode** in the sidebar when WiFi hardware is unavailable

Reopen the wizard anytime via **Help → Getting Started**.

## Development

```bash
pip install -r requirements.txt
pip install pytest
pytest
```

## Project layout

```
WifiTester/
├── main.py
├── wifitester/
│   ├── app.py
│   ├── models/project.py
│   ├── services/
│   │   ├── wifi_scanner.py
│   │   ├── heatmap.py
│   │   ├── sampler.py
│   │   └── settings.py
│   └── ui/
│       ├── signal_style.py
│       └── dialogs/onboarding.py
└── tests/
```
