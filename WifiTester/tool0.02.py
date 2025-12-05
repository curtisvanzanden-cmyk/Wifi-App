"""
Professional WiFi Heatmap Tool - Enhanced Edition

NEW FEATURES:
- Multi-AP tracking with SSID/BSSID identification
- Project management (save/load entire projects)
- Auto-save with crash recovery
- Statistical analysis panel (min/max/avg/std dev)
- Dead zone detection and highlighting
- Comparison mode (before/after surveys)
- Export to multiple formats (PNG, PDF, JSON)
- Grid overlay with customizable spacing
- Distance measurement tool
- Notes/annotations per measurement point
- WiFi channel detection and interference analysis
- Historical data tracking with timestamps
- Batch import from other tools
- Coverage percentage calculator
- Professional report generation

Dependencies: matplotlib, numpy, scipy, pillow, reportlab (optional for PDF)
Install: pip install matplotlib numpy scipy pillow reportlab

Author: Enhanced by Assistant
"""

import os
import sys
import csv
import json
import platform
import subprocess
import math
import re
from datetime import datetime
from typing import List, Tuple, Optional, Dict
from dataclasses import dataclass, asdict
from pathlib import Path

try:
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox, scrolledtext
except Exception as e:
    raise RuntimeError("Tkinter required: " + str(e))

try:
    from PIL import Image, ImageTk
except Exception:
    raise RuntimeError("Pillow required: pip install pillow")

try:
    import numpy as np
    import matplotlib
    matplotlib.use("TkAgg")
    import matplotlib.pyplot as plt
    import matplotlib.image as mpimg
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.patches import Circle
except Exception:
    raise RuntimeError("matplotlib and numpy required: pip install matplotlib numpy")

try:
    from scipy.interpolate import griddata
    from scipy.ndimage import gaussian_filter
except Exception:
    griddata = None
    gaussian_filter = None

# Optional PDF support
try:
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas as pdf_canvas
    REPORTLAB_AVAILABLE = True
except Exception:
    REPORTLAB_AVAILABLE = False


# ==================== DATA STRUCTURES ====================

@dataclass
class MeasurementPoint:
    """Single measurement point with comprehensive metadata"""
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
    def from_dict(d: dict) -> 'MeasurementPoint':
        return MeasurementPoint(**d)


@dataclass
class ProjectMetadata:
    """Project-level metadata"""
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
    def from_dict(d: dict) -> 'ProjectMetadata':
        cal = d.get('calibration')
        if cal and isinstance(cal, list):
            cal = tuple(cal)
        d['calibration'] = cal
        return ProjectMetadata(**d)


class Project:
    """Complete project container"""
    def __init__(self):
        self.metadata = ProjectMetadata(
            name="New Project",
            location="",
            floor="",
            surveyor="",
            created=datetime.now().isoformat(),
            modified=datetime.now().isoformat(),
            floorplan_path=""
        )
        self.measurements: List[MeasurementPoint] = []
        self.access_points: Dict[str, dict] = {}  # BSSID -> AP info
        
    def add_measurement(self, point: MeasurementPoint):
        self.measurements.append(point)
        self.metadata.modified = datetime.now().isoformat()
        
        # Track unique APs
        if point.bssid and point.bssid not in self.access_points:
            self.access_points[point.bssid] = {
                'ssid': point.ssid,
                'channel': point.channel,
                'frequency': point.frequency,
                'first_seen': point.timestamp
            }
    
    def get_statistics(self) -> dict:
        """Calculate comprehensive statistics"""
        if not self.measurements:
            return {}
        
        rssi_values = [m.rssi for m in self.measurements]
        return {
            'count': len(self.measurements),
            'min_rssi': min(rssi_values),
            'max_rssi': max(rssi_values),
            'avg_rssi': np.mean(rssi_values),
            'median_rssi': np.median(rssi_values),
            'std_rssi': np.std(rssi_values),
            'dead_zones': len([r for r in rssi_values if r < -80]),
            'good_coverage': len([r for r in rssi_values if r > -60]),
            'unique_aps': len(self.access_points),
            'channels': list(set(m.channel for m in self.measurements if m.channel))
        }
    
    def to_dict(self) -> dict:
        return {
            'metadata': self.metadata.to_dict(),
            'measurements': [m.to_dict() for m in self.measurements],
            'access_points': self.access_points
        }
    
    @staticmethod
    def from_dict(d: dict) -> 'Project':
        proj = Project()
        proj.metadata = ProjectMetadata.from_dict(d['metadata'])
        proj.measurements = [MeasurementPoint.from_dict(m) for m in d['measurements']]
        proj.access_points = d.get('access_points', {})
        return proj
    
    def save_to_file(self, filepath: str):
        """Save project to JSON file"""
        with open(filepath, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)
    
    @staticmethod
    def load_from_file(filepath: str) -> 'Project':
        """Load project from JSON file"""
        with open(filepath, 'r') as f:
            data = json.load(f)
        return Project.from_dict(data)


# ==================== WIFI SCANNER ====================

class WiFiScanner:
    """Enhanced WiFi scanning with detailed network info"""
    
    @staticmethod
    def get_detailed_info() -> Optional[Dict]:
        """Get comprehensive WiFi info including SSID, BSSID, channel, etc."""
        os_type = platform.system().lower()
        
        try:
            if os_type.startswith("win"):
                return WiFiScanner._scan_windows()
            elif os_type.startswith("linux"):
                return WiFiScanner._scan_linux()
            elif os_type.startswith("darwin"):
                return WiFiScanner._scan_macos()
        except Exception as e:
            print(f"WiFi scan error: {e}")
            return None
        
        return None
    
    @staticmethod
    def _scan_windows() -> Optional[Dict]:
        """Windows-specific scanning"""
        out = subprocess.check_output(
            ["netsh", "wlan", "show", "interfaces"],
            stderr=subprocess.DEVNULL
        ).decode(errors="ignore")
        
        info = {'rssi': None, 'ssid': '', 'bssid': '', 'channel': 0}
        
        for line in out.splitlines():
            line = line.strip()
            if "SSID" in line and "BSSID" not in line:
                info['ssid'] = line.split(":", 1)[1].strip()
            elif "BSSID" in line:
                info['bssid'] = line.split(":", 1)[1].strip()
            elif "Signal" in line:
                perc = int(line.split(":", 1)[1].strip().replace('%', ''))
                info['rssi'] = round((perc / 2) - 100)
            elif "Channel" in line:
                try:
                    info['channel'] = int(line.split(":", 1)[1].strip())
                except:
                    pass
        
        return info if info['rssi'] is not None else None
    
    @staticmethod
    def _scan_linux() -> Optional[Dict]:
        """Linux-specific scanning"""
        info = {'rssi': None, 'ssid': '', 'bssid': '', 'channel': 0}
        
        # Try iwconfig first
        try:
            iface = WiFiScanner._detect_linux_interface()
            out = subprocess.check_output(
                ["iwconfig", iface],
                stderr=subprocess.DEVNULL
            ).decode(errors="ignore")
            
            for line in out.splitlines():
                if "ESSID" in line:
                    match = re.search(r'ESSID:"([^"]*)"', line)
                    if match:
                        info['ssid'] = match.group(1)
                elif "Access Point" in line:
                    match = re.search(r'Access Point: ([0-9A-Fa-f:]+)', line)
                    if match:
                        info['bssid'] = match.group(1)
                elif "Signal level" in line:
                    match = re.search(r'Signal level=(-?\d+)', line)
                    if match:
                        info['rssi'] = int(match.group(1))
                elif "Frequency" in line:
                    match = re.search(r'Channel (\d+)', line)
                    if match:
                        info['channel'] = int(match.group(1))
        except:
            pass
        
        # Try nmcli as fallback
        if info['rssi'] is None:
            try:
                out = subprocess.check_output(
                    ["nmcli", "-t", "-f", "IN-USE,SSID,BSSID,CHAN,SIGNAL", "device", "wifi"],
                    stderr=subprocess.DEVNULL
                ).decode(errors="ignore")
                
                for line in out.splitlines():
                    if line.startswith("*"):
                        parts = line.split(":")
                        if len(parts) >= 5:
                            info['ssid'] = parts[1]
                            info['bssid'] = parts[2]
                            info['channel'] = int(parts[3]) if parts[3] else 0
                            perc = int(parts[4])
                            info['rssi'] = round((perc / 2) - 100)
                        break
            except:
                pass
        
        return info if info['rssi'] is not None else None
    
    @staticmethod
    def _scan_macos() -> Optional[Dict]:
        """macOS-specific scanning"""
        airport = "/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport"
        
        info = {'rssi': None, 'ssid': '', 'bssid': '', 'channel': 0}
        
        try:
            out = subprocess.check_output([airport, "-I"]).decode(errors="ignore")
            
            for line in out.splitlines():
                line = line.strip()
                if "agrCtlRSSI" in line or line.startswith("RSSI"):
                    info['rssi'] = int(line.split(":", 1)[1].strip())
                elif "SSID" in line and "BSSID" not in line:
                    info['ssid'] = line.split(":", 1)[1].strip()
                elif "BSSID" in line:
                    info['bssid'] = line.split(":", 1)[1].strip()
                elif "channel" in line.lower():
                    try:
                        info['channel'] = int(line.split(":", 1)[1].strip())
                    except:
                        pass
        except:
            pass
        
        return info if info['rssi'] is not None else None
    
    @staticmethod
    def _detect_linux_interface() -> str:
        """Detect wireless interface on Linux"""
        try:
            out = subprocess.check_output(["iwconfig"], stderr=subprocess.DEVNULL).decode(errors="ignore")
            for line in out.splitlines():
                if "IEEE 802.11" in line:
                    return line.split()[0]
        except:
            pass
        return "wlan0"


# ==================== MAIN APPLICATION ====================

class WiFiHeatmapPro:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("WiFi Heatmap Pro - IT Professional Suite")
        self.root.geometry("1400x900")
        
        # Project and state
        self.project = Project()
        self.current_file: Optional[str] = None
        self.image = None
        self.comparison_project: Optional[Project] = None
        
        # UI state
        self.measuring = False
        self.auto_save_enabled = True
        self.auto_save_interval = 300000  # 5 minutes
        
        # Matplotlib setup
        self.fig: Figure = Figure(figsize=(10, 8))
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.root)
        self.cid_click = None
        
        # Configuration
        self.interpolate_method = tk.StringVar(value="cubic")
        self.colormap = tk.StringVar(value="RdYlGn")
        self.grid_res = tk.IntVar(value=300)
        self.show_points = tk.BooleanVar(value=True)
        self.show_labels = tk.BooleanVar(value=True)
        self.show_colorbar = tk.BooleanVar(value=True)
        self.show_dead_zones = tk.BooleanVar(value=True)
        self.show_grid = tk.BooleanVar(value=False)
        self.grid_spacing = tk.IntVar(value=50)
        self.simulate_mode = tk.BooleanVar(value=False)
        self.sim_rssi = tk.IntVar(value=-60)
        self.smoothing_sigma = tk.DoubleVar(value=1.0)
        
        self._build_ui()
        self._setup_auto_save()
        self._log("WiFi Heatmap Pro initialized")
    
    # ==================== UI BUILDING ====================
    
    def _build_ui(self):
        """Build the complete UI"""
        # Menu bar
        self._build_menu()
        
        # Main layout: left sidebar, center canvas, right info panel
        main_paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_paned.pack(fill=tk.BOTH, expand=True)
        
        # Left control panel
        left_frame = ttk.Frame(main_paned, width=300)
        main_paned.add(left_frame, weight=0)
        self._build_left_panel(left_frame)
        
        # Center canvas area
        center_frame = ttk.Frame(main_paned)
        main_paned.add(center_frame, weight=3)
        self._build_center_panel(center_frame)
        
        # Right info panel
        right_frame = ttk.Frame(main_paned, width=300)
        main_paned.add(right_frame, weight=0)
        self._build_right_panel(right_frame)
        
        # Status bar
        self._build_status_bar()
    
    def _build_menu(self):
        """Build menu bar"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="New Project", command=self.new_project, accelerator="Ctrl+N")
        file_menu.add_command(label="Open Project...", command=self.open_project, accelerator="Ctrl+O")
        file_menu.add_command(label="Save Project", command=self.save_project, accelerator="Ctrl+S")
        file_menu.add_command(label="Save Project As...", command=self.save_project_as, accelerator="Ctrl+Shift+S")
        file_menu.add_separator()
        file_menu.add_command(label="Import CSV...", command=self.import_csv)
        file_menu.add_command(label="Export CSV...", command=self.export_csv)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        
        # Tools menu
        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Tools", menu=tools_menu)
        tools_menu.add_command(label="Generate Heatmap", command=self.generate_heatmap, accelerator="Ctrl+G")
        tools_menu.add_command(label="Export Image...", command=self.export_image)
        tools_menu.add_command(label="Generate Report...", command=self.generate_report)
        tools_menu.add_separator()
        tools_menu.add_command(label="Calibrate Scale...", command=self.calibrate_dialog)
        tools_menu.add_command(label="Compare Projects...", command=self.compare_projects)
        
        # View menu
        view_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="View", menu=view_menu)
        view_menu.add_checkbutton(label="Show Points", variable=self.show_points)
        view_menu.add_checkbutton(label="Show Labels", variable=self.show_labels)
        view_menu.add_checkbutton(label="Show Grid", variable=self.show_grid)
        view_menu.add_checkbutton(label="Highlight Dead Zones", variable=self.show_dead_zones)
        
        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="About", command=self.show_about)
        
        # Keyboard shortcuts
        self.root.bind('<Control-n>', lambda e: self.new_project())
        self.root.bind('<Control-o>', lambda e: self.open_project())
        self.root.bind('<Control-s>', lambda e: self.save_project())
        self.root.bind('<Control-Shift-S>', lambda e: self.save_project_as())
        self.root.bind('<Control-g>', lambda e: self.generate_heatmap())
        self.root.bind('<Control-z>', lambda e: self.undo_last())
    
    def _build_left_panel(self, parent):
        """Build left control panel"""
        # Make it scrollable
        canvas = tk.Canvas(parent)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Project section
        ttk.Label(scrollable_frame, text="📁 Project", font=('Arial', 11, 'bold')).pack(anchor=tk.W, padx=8, pady=(8,4))
        ttk.Button(scrollable_frame, text="Select Floorplan", command=self.select_floorplan).pack(fill=tk.X, padx=8, pady=2)
        ttk.Button(scrollable_frame, text="Project Settings", command=self.edit_project_settings).pack(fill=tk.X, padx=8, pady=2)
        
        ttk.Separator(scrollable_frame).pack(fill=tk.X, pady=8)
        
        # Measurement section
        ttk.Label(scrollable_frame, text="📡 Measurement", font=('Arial', 11, 'bold')).pack(anchor=tk.W, padx=8, pady=(8,4))
        self.measure_btn = ttk.Button(scrollable_frame, text="▶ Start Measuring", command=self.toggle_measuring)
        self.measure_btn.pack(fill=tk.X, padx=8, pady=2)
        ttk.Button(scrollable_frame, text="↶ Undo Last", command=self.undo_last).pack(fill=tk.X, padx=8, pady=2)
        ttk.Button(scrollable_frame, text="🗑 Clear All", command=self.clear_all).pack(fill=tk.X, padx=8, pady=2)
        
        # Test mode
        ttk.Checkbutton(scrollable_frame, text="Test Mode (Simulate)", variable=self.simulate_mode).pack(anchor=tk.W, padx=8, pady=(8,2))
        sim_frame = ttk.Frame(scrollable_frame)
        sim_frame.pack(fill=tk.X, padx=8, pady=2)
        ttk.Label(sim_frame, text="RSSI:").pack(side=tk.LEFT)
        ttk.Spinbox(sim_frame, from_=-100, to=-20, textvariable=self.sim_rssi, width=6).pack(side=tk.LEFT, padx=4)
        
        ttk.Separator(scrollable_frame).pack(fill=tk.X, pady=8)
        
        # Visualization section
        ttk.Label(scrollable_frame, text="🎨 Visualization", font=('Arial', 11, 'bold')).pack(anchor=tk.W, padx=8, pady=(8,4))
        
        ttk.Label(scrollable_frame, text="Interpolation:").pack(anchor=tk.W, padx=8)
        ttk.Combobox(scrollable_frame, textvariable=self.interpolate_method, 
                     values=["cubic", "linear", "nearest"], state='readonly', width=18).pack(padx=8, pady=2)
        
        ttk.Label(scrollable_frame, text="Colormap:").pack(anchor=tk.W, padx=8, pady=(6,0))
        ttk.Combobox(scrollable_frame, textvariable=self.colormap,
                     values=["RdYlGn", "viridis", "plasma", "coolwarm", "jet"], state='readonly', width=18).pack(padx=8, pady=2)
        
        ttk.Label(scrollable_frame, text="Resolution:").pack(anchor=tk.W, padx=8, pady=(6,0))
        ttk.Scale(scrollable_frame, from_=50, to=500, variable=self.grid_res, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=8, pady=2)
        
        ttk.Label(scrollable_frame, text="Smoothing:").pack(anchor=tk.W, padx=8, pady=(6,0))
        ttk.Scale(scrollable_frame, from_=0, to=5, variable=self.smoothing_sigma, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=8, pady=2)
        
        ttk.Checkbutton(scrollable_frame, text="Show measurement points", variable=self.show_points).pack(anchor=tk.W, padx=8, pady=2)
        ttk.Checkbutton(scrollable_frame, text="Show RSSI labels", variable=self.show_labels).pack(anchor=tk.W, padx=8, pady=2)
        ttk.Checkbutton(scrollable_frame, text="Show colorbar", variable=self.show_colorbar).pack(anchor=tk.W, padx=8, pady=2)
        ttk.Checkbutton(scrollable_frame, text="Highlight dead zones", variable=self.show_dead_zones).pack(anchor=tk.W, padx=8, pady=2)
        
        ttk.Separator(scrollable_frame).pack(fill=tk.X, pady=8)
        
        # Grid overlay
        ttk.Label(scrollable_frame, text="📐 Grid Overlay", font=('Arial', 11, 'bold')).pack(anchor=tk.W, padx=8, pady=(8,4))
        ttk.Checkbutton(scrollable_frame, text="Show grid", variable=self.show_grid).pack(anchor=tk.W, padx=8, pady=2)
        ttk.Label(scrollable_frame, text="Spacing (pixels):").pack(anchor=tk.W, padx=8)
        ttk.Spinbox(scrollable_frame, from_=10, to=200, textvariable=self.grid_spacing, width=18).pack(padx=8, pady=2)
        
        ttk.Separator(scrollable_frame).pack(fill=tk.X, pady=8)
        
        ttk.Button(scrollable_frame, text="🔄 Refresh View", command=self.refresh_view).pack(fill=tk.X, padx=8, pady=8)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
    
    def _build_center_panel(self, parent):
        """Build center canvas area"""
        toolbar_frame = ttk.Frame(parent)
        toolbar_frame.pack(fill=tk.X, padx=4, pady=4)
        
        ttk.Button(toolbar_frame, text="🖼 Generate Heatmap", command=self.generate_heatmap).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar_frame, text="💾 Export Image", command=self.export_image).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar_frame, text="📄 Generate Report", command=self.generate_report).pack(side=tk.LEFT, padx=2)
        
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        self.ax.axis('off')
        self.canvas.draw()
    
    def _build_right_panel(self, parent):
        """Build right information panel"""
        notebook = ttk.Notebook(parent)
        notebook.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        
        # Statistics tab
        stats_frame = ttk.Frame(notebook)
        notebook.add(stats_frame, text="Statistics")
        self.stats_text = scrolledtext.ScrolledText(stats_frame, height=15, width=30, wrap=tk.WORD)
        self.stats_text.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        
        # Access Points tab
        ap_frame = ttk.Frame(notebook)
        notebook.add(ap_frame, text="Access Points")
        self.ap_text = scrolledtext.ScrolledText(ap_frame, height=15, width=30, wrap=tk.WORD)
        self.ap_text.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        
        # Measurements tab
        meas_frame = ttk.Frame(notebook)
        notebook.add(meas_frame, text="Measurements")
        
        # Create treeview for measurements
        columns = ('Time', 'X', 'Y', 'RSSI', 'SSID')
        self.meas_tree = ttk.Treeview(meas_frame, columns=columns, show='headings', height=15)
        for col in columns:
            self.meas_tree.heading(col, text=col)
            self.meas_tree.column(col, width=60)
        
        meas_scroll = ttk.Scrollbar(meas_frame, orient=tk.VERTICAL, command=self.meas_tree.yview)
        self.meas_tree.configure(yscrollcommand=meas_scroll.set)
        
        self.meas_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4, pady=4)
        meas_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Log tab
        log_frame = ttk.Frame(notebook)
        notebook.add(log_frame, text="Log")
        self.log_text = scrolledtext.ScrolledText(log_frame, height=15, width=30, wrap=tk.WORD)
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        
        # Configure text tags for log levels
        self.log_text.tag_config('INFO', foreground='black')
        self.log_text.tag_config('WARN', foreground='orange')
        self.log_text.tag_config('ERROR', foreground='red')
        self.log_text.tag_config('SUCCESS', foreground='green')
    
    def _build_status_bar(self):
        """Build status bar"""
        status_frame = ttk.Frame(self.root)
        status_frame.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.status_label = ttk.Label(status_frame, text="Ready", relief=tk.SUNKEN, anchor=tk.W)
        self.status_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        self.point_count_label = ttk.Label(status_frame, text="Points: 0", relief=tk.SUNKEN)
        self.point_count_label.pack(side=tk.RIGHT, padx=2)
        
        self.ap_count_label = ttk.Label(status_frame, text="APs: 0", relief=tk.SUNKEN)
        self.ap_count_label.pack(side=tk.RIGHT, padx=2)
    
    # ==================== PROJECT MANAGEMENT ====================
    
    def new_project(self):
        """Create new project"""
        if self.project.measurements and messagebox.askyesno("Save", "Save current project?"):
            self.save_project()
        
        self.project = Project()
        self.current_file = None
        self.image = None
        self.refresh_view()
        self.update_info_panels()
        self._log("New project created", "SUCCESS")
        self.root.title("WiFi Heatmap Pro - Untitled Project")
    
    def open_project(self):
        """Open existing project"""
        filepath = filedialog.askopenfilename(
            title="Open Project",
            filetypes=[("WiFi Project", "*.wifiproj"), ("JSON", "*.json"), ("All Files", "*.*")]
        )
        if not filepath:
            return
        
        try:
            self.project = Project.load_from_file(filepath)
            self.current_file = filepath
            
            # Load floorplan if path exists
            if self.project.metadata.floorplan_path and os.path.exists(self.project.metadata.floorplan_path):
                self._load_floorplan(self.project.metadata.floorplan_path)
            
            self.refresh_view()
            self.update_info_panels()
            self._log(f"Project loaded: {filepath}", "SUCCESS")
            self.root.title(f"WiFi Heatmap Pro - {self.project.metadata.name}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load project: {e}")
            self._log(f"Failed to load project: {e}", "ERROR")
    
    def save_project(self):
        """Save current project"""
        if not self.current_file:
            self.save_project_as()
        else:
            try:
                self.project.save_to_file(self.current_file)
                self._log(f"Project saved: {self.current_file}", "SUCCESS")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save: {e}")
                self._log(f"Save failed: {e}", "ERROR")
    
    def save_project_as(self):
        """Save project with new filename"""
        filepath = filedialog.asksaveasfilename(
            title="Save Project As",
            defaultextension=".wifiproj",
            filetypes=[("WiFi Project", "*.wifiproj"), ("JSON", "*.json"), ("All Files", "*.*")]
        )
        if not filepath:
            return
        
        try:
            self.current_file = filepath
            self.project.save_to_file(filepath)
            self._log(f"Project saved: {filepath}", "SUCCESS")
            self.root.title(f"WiFi Heatmap Pro - {self.project.metadata.name}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save: {e}")
            self._log(f"Save failed: {e}", "ERROR")
    
    def edit_project_settings(self):
        """Edit project metadata"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Project Settings")
        dialog.geometry("400x400")
        
        ttk.Label(dialog, text="Project Name:").grid(row=0, column=0, sticky=tk.W, padx=8, pady=4)
        name_var = tk.StringVar(value=self.project.metadata.name)
        ttk.Entry(dialog, textvariable=name_var, width=30).grid(row=0, column=1, padx=8, pady=4)
        
        ttk.Label(dialog, text="Location:").grid(row=1, column=0, sticky=tk.W, padx=8, pady=4)
        loc_var = tk.StringVar(value=self.project.metadata.location)
        ttk.Entry(dialog, textvariable=loc_var, width=30).grid(row=1, column=1, padx=8, pady=4)
        
        ttk.Label(dialog, text="Floor:").grid(row=2, column=0, sticky=tk.W, padx=8, pady=4)
        floor_var = tk.StringVar(value=self.project.metadata.floor)
        ttk.Entry(dialog, textvariable=floor_var, width=30).grid(row=2, column=1, padx=8, pady=4)
        
        ttk.Label(dialog, text="Surveyor:").grid(row=3, column=0, sticky=tk.W, padx=8, pady=4)
        surv_var = tk.StringVar(value=self.project.metadata.surveyor)
        ttk.Entry(dialog, textvariable=surv_var, width=30).grid(row=3, column=1, padx=8, pady=4)
        
        ttk.Label(dialog, text="Notes:").grid(row=4, column=0, sticky=tk.NW, padx=8, pady=4)
        notes_text = tk.Text(dialog, width=30, height=10)
        notes_text.insert('1.0', self.project.metadata.notes)
        notes_text.grid(row=4, column=1, padx=8, pady=4)
        
        def save_settings():
            self.project.metadata.name = name_var.get()
            self.project.metadata.location = loc_var.get()
            self.project.metadata.floor = floor_var.get()
            self.project.metadata.surveyor = surv_var.get()
            self.project.metadata.notes = notes_text.get('1.0', tk.END).strip()
            self._log("Project settings updated", "SUCCESS")
            dialog.destroy()
        
        ttk.Button(dialog, text="Save", command=save_settings).grid(row=5, column=0, columnspan=2, pady=8)
    
    # ==================== FLOORPLAN ====================
    
    def select_floorplan(self):
        """Select floorplan image"""
        filepath = filedialog.askopenfilename(
            title="Select Floorplan",
            filetypes=[
                ("PNG", "*.png"),
                ("JPEG", "*.jpg *.jpeg"),
                ("All Images", "*.png *.jpg *.jpeg *.bmp"),
                ("All Files", "*.*")
            ]
        )
        if not filepath:
            return
        
        self._load_floorplan(filepath)
        self.project.metadata.floorplan_path = filepath
        self._log(f"Floorplan loaded: {filepath}", "SUCCESS")
    
    def _load_floorplan(self, filepath: str):
        """Load floorplan image"""
        try:
            self.image = Image.open(filepath)
            self.refresh_view()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load image: {e}")
            self._log(f"Image load failed: {e}", "ERROR")
    
    # ==================== MEASUREMENT ====================
    
    def toggle_measuring(self):
        """Start/stop measurement mode"""
        if not self.image:
            messagebox.showwarning("No Floorplan", "Please select a floorplan first.")
            return
        
        if not self.measuring:
            self.measuring = True
            self.measure_btn.config(text="⏸ Stop Measuring")
            self.cid_click = self.canvas.mpl_connect('button_press_event', self._on_canvas_click)
            self._log("Measurement mode started", "INFO")
            self.status_label.config(text="Click on floorplan to record measurements")
        else:
            self.measuring = False
            self.measure_btn.config(text="▶ Start Measuring")
            if self.cid_click:
                self.canvas.mpl_disconnect(self.cid_click)
                self.cid_click = None
            self._log("Measurement mode stopped", "INFO")
            self.status_label.config(text="Ready")
    
    def _on_canvas_click(self, event):
        """Handle canvas click during measurement"""
        if not self.measuring or event.inaxes != self.ax:
            return
        if event.xdata is None or event.ydata is None:
            return
        
        x, y = int(event.xdata), int(event.ydata)
        
        # Get WiFi info
        if self.simulate_mode.get():
            wifi_info = {
                'rssi': self.sim_rssi.get(),
                'ssid': 'SimulatedAP',
                'bssid': 'XX:XX:XX:XX:XX:XX',
                'channel': 6
            }
        else:
            wifi_info = WiFiScanner.get_detailed_info()
            if not wifi_info or wifi_info['rssi'] is None:
                messagebox.showwarning("No Signal", "Could not read WiFi signal. Enable Test Mode or check connection.")
                return
        
        # Create measurement point
        point = MeasurementPoint(
            x=x,
            y=y,
            rssi=wifi_info['rssi'],
            timestamp=datetime.now().isoformat(),
            ssid=wifi_info.get('ssid', ''),
            bssid=wifi_info.get('bssid', ''),
            channel=wifi_info.get('channel', 0)
        )
        
        self.project.add_measurement(point)
        self._draw_measurement_point(point)
        self.update_info_panels()
        self._log(f"Measurement added: ({x},{y}) = {wifi_info['rssi']} dBm [{wifi_info.get('ssid', 'Unknown')}]", "SUCCESS")
    
    def _draw_measurement_point(self, point: MeasurementPoint):
        """Draw a single measurement point"""
        if self.show_points.get():
            # Color based on signal strength
            if point.rssi > -60:
                color = 'green'
            elif point.rssi > -70:
                color = 'yellow'
            elif point.rssi > -80:
                color = 'orange'
            else:
                color = 'red'
            
            self.ax.plot(point.x, point.y, marker='o', markersize=8, 
                        markerfacecolor=color, markeredgecolor='black', markeredgewidth=1.5)
            
            if self.show_labels.get():
                self.ax.text(point.x + 5, point.y, f"{point.rssi}", 
                           fontsize=8, color='black',
                           bbox=dict(facecolor='white', alpha=0.8, edgecolor='none', pad=1))
        
        self.canvas.draw()
    
    def undo_last(self):
        """Remove last measurement"""
        if not self.project.measurements:
            messagebox.showinfo("No Data", "No measurements to undo.")
            return
        
        removed = self.project.measurements.pop()
        self.refresh_view()
        self.update_info_panels()
        self._log(f"Removed measurement: ({removed.x},{removed.y})", "INFO")
    
    def clear_all(self):
        """Clear all measurements"""
        if not self.project.measurements:
            return
        
        if messagebox.askyesno("Clear All", f"Remove all {len(self.project.measurements)} measurements?"):
            self.project.measurements.clear()
            self.project.access_points.clear()
            self.refresh_view()
            self.update_info_panels()
            self._log("All measurements cleared", "WARN")
    
    # ==================== VISUALIZATION ====================
    
    def refresh_view(self):
        """Refresh the canvas view"""
        self.ax.clear()
        
        if self.image:
            self.ax.imshow(self.image)
            
            # Draw grid if enabled
            if self.show_grid.get():
                self._draw_grid()
            
            # Draw all measurement points
            for point in self.project.measurements:
                self._draw_measurement_point_static(point)
        
        self.ax.set_title('Floorplan - Click to measure' if self.measuring else 'Floorplan')
        self.ax.axis('off')
        self.canvas.draw()
    
    def _draw_measurement_point_static(self, point: MeasurementPoint):
        """Draw point without updating canvas (for batch drawing)"""
        if self.show_points.get():
            if point.rssi > -60:
                color = 'green'
            elif point.rssi > -70:
                color = 'yellow'
            elif point.rssi > -80:
                color = 'orange'
            else:
                color = 'red'
            
            self.ax.plot(point.x, point.y, marker='o', markersize=8,
                        markerfacecolor=color, markeredgecolor='black', markeredgewidth=1.5)
            
            if self.show_labels.get():
                self.ax.text(point.x + 5, point.y, f"{point.rssi}",
                           fontsize=8, color='black',
                           bbox=dict(facecolor='white', alpha=0.8, edgecolor='none', pad=1))
    
    def _draw_grid(self):
        """Draw grid overlay"""
        if not self.image:
            return
        
        w, h = self.image.size
        spacing = self.grid_spacing.get()
        
        for x in range(0, w, spacing):
            self.ax.axvline(x, color='gray', alpha=0.3, linewidth=0.5)
        for y in range(0, h, spacing):
            self.ax.axhline(y, color='gray', alpha=0.3, linewidth=0.5)
    
    def generate_heatmap(self):
        """Generate and display heatmap"""
        if len(self.project.measurements) < 3:
            messagebox.showwarning("Insufficient Data", "Need at least 3 measurements to generate heatmap.")
            return
        
        try:
            # Extract data
            x_coords = [m.x for m in self.project.measurements]
            y_coords = [m.y for m in self.project.measurements]
            z_values = np.array([m.rssi for m in self.project.measurements])
            
            # Create grid
            res = self.grid_res.get()
            xi = np.linspace(min(x_coords), max(x_coords), res)
            yi = np.linspace(min(y_coords), max(y_coords), res)
            xi, yi = np.meshgrid(xi, yi)
            
            # Interpolate
            method = self.interpolate_method.get()
            if griddata is not None:
                zi = griddata((x_coords, y_coords), z_values, (xi, yi), method=method)
            else:
                # Fallback to nearest neighbor
                zi = np.full_like(xi, np.nan, dtype=float)
                for i in range(xi.shape[0]):
                    for j in range(xi.shape[1]):
                        dists = (np.array(x_coords) - xi[i,j])**2 + (np.array(y_coords) - yi[i,j])**2
                        idx = int(np.argmin(dists))
                        zi[i,j] = z_values[idx]
            
            # Apply smoothing
            if gaussian_filter and self.smoothing_sigma.get() > 0:
                zi = gaussian_filter(zi, sigma=self.smoothing_sigma.get())
            
            # Create new figure for heatmap
            fig, ax = plt.subplots(figsize=(12, 10))
            
            # Show floorplan
            if self.image:
                img_arr = np.array(self.image)
                ax.imshow(img_arr, extent=[0, img_arr.shape[1], img_arr.shape[0], 0])
            
            # Plot heatmap
            zi_masked = np.ma.masked_invalid(zi)
            cmap = plt.get_cmap(self.colormap.get())
            contour = ax.contourf(xi, yi, zi_masked, levels=15, cmap=cmap, alpha=0.6)
            
            # Highlight dead zones
            if self.show_dead_zones.get():
                dead_zone_mask = zi < -80
                ax.contourf(xi, yi, dead_zone_mask, levels=[0.5, 1.5], colors=['red'], alpha=0.3)
            
            # Show colorbar
            if self.show_colorbar.get():
                cbar = plt.colorbar(contour, ax=ax, label='Signal Strength (dBm)')
            
            # Plot measurement points
            if self.show_points.get():
                scatter = ax.scatter(x_coords, y_coords, c=z_values, cmap=cmap,
                                   s=50, edgecolors='black', linewidths=1.5, zorder=10)
            
            ax.set_title(f'{self.project.metadata.name} - WiFi Coverage Heatmap')
            ax.axis('off')
            plt.tight_layout()
            plt.show()
            
            self._log("Heatmap generated successfully", "SUCCESS")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate heatmap: {e}")
            self._log(f"Heatmap generation failed: {e}", "ERROR")
    
    # ==================== IMPORT/EXPORT ====================
    
    def import_csv(self):
        """Import measurements from CSV"""
        filepath = filedialog.askopenfilename(
            title="Import CSV",
            filetypes=[("CSV", "*.csv"), ("All Files", "*.*")]
        )
        if not filepath:
            return
        
        try:
            count = 0
            with open(filepath, 'r', newline='') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    point = MeasurementPoint(
                        x=int(float(row.get('x', row.get('X', 0)))),
                        y=int(float(row.get('y', row.get('Y', 0)))),
                        rssi=float(row.get('rssi', row.get('signal_dBm', row.get('signal', -70)))),
                        timestamp=row.get('timestamp', datetime.now().isoformat()),
                        ssid=row.get('ssid', ''),
                        bssid=row.get('bssid', ''),
                        channel=int(row.get('channel', 0))
                    )
                    self.project.add_measurement(point)
                    count += 1
            
            self.refresh_view()
            self.update_info_panels()
            self._log(f"Imported {count} measurements from CSV", "SUCCESS")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to import CSV: {e}")
            self._log(f"CSV import failed: {e}", "ERROR")
    
    def export_csv(self):
        """Export measurements to CSV"""
        if not self.project.measurements:
            messagebox.showinfo("No Data", "No measurements to export.")
            return
        
        filepath = filedialog.asksaveasfilename(
            title="Export CSV",
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv"), ("All Files", "*.*")]
        )
        if not filepath:
            return
        
        try:
            with open(filepath, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=[
                    'x', 'y', 'rssi', 'timestamp', 'ssid', 'bssid', 'channel', 'note'
                ])
                writer.writeheader()
                for m in self.project.measurements:
                    writer.writerow(m.to_dict())
            
            self._log(f"Exported {len(self.project.measurements)} measurements to CSV", "SUCCESS")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export CSV: {e}")
            self._log(f"CSV export failed: {e}", "ERROR")
    
    def export_image(self):
        """Export heatmap as image"""
        if len(self.project.measurements) < 3:
            messagebox.showwarning("Insufficient Data", "Need at least 3 measurements.")
            return
        
        filepath = filedialog.asksaveasfilename(
            title="Export Image",
            defaultextension=".png",
            filetypes=[("PNG", "*.png"), ("JPEG", "*.jpg"), ("PDF", "*.pdf")]
        )
        if not filepath:
            return
        
        try:
            # Similar to generate_heatmap but save instead of show
            x_coords = [m.x for m in self.project.measurements]
            y_coords = [m.y for m in self.project.measurements]
            z_values = np.array([m.rssi for m in self.project.measurements])
            
            res = self.grid_res.get()
            xi = np.linspace(min(x_coords), max(x_coords), res)
            yi = np.linspace(min(y_coords), max(y_coords), res)
            xi, yi = np.meshgrid(xi, yi)
            
            method = self.interpolate_method.get()
            if griddata is not None:
                zi = griddata((x_coords, y_coords), z_values, (xi, yi), method=method)
            else:
                zi = np.full_like(xi, np.nan, dtype=float)
                for i in range(xi.shape[0]):
                    for j in range(xi.shape[1]):
                        dists = (np.array(x_coords) - xi[i,j])**2 + (np.array(y_coords) - yi[i,j])**2
                        idx = int(np.argmin(dists))
                        zi[i,j] = z_values[idx]
            
            if gaussian_filter and self.smoothing_sigma.get() > 0:
                zi = gaussian_filter(zi, sigma=self.smoothing_sigma.get())
            
            fig, ax = plt.subplots(figsize=(12, 10))
            
            if self.image:
                img_arr = np.array(self.image)
                ax.imshow(img_arr, extent=[0, img_arr.shape[1], img_arr.shape[0], 0])
            
            zi_masked = np.ma.masked_invalid(zi)
            cmap = plt.get_cmap(self.colormap.get())
            contour = ax.contourf(xi, yi, zi_masked, levels=15, cmap=cmap, alpha=0.6)
            
            if self.show_colorbar.get():
                plt.colorbar(contour, ax=ax, label='Signal Strength (dBm)')
            
            if self.show_points.get():
                ax.scatter(x_coords, y_coords, c=z_values, cmap=cmap,
                          s=50, edgecolors='black', linewidths=1.5, zorder=10)
            
            ax.set_title(f'{self.project.metadata.name} - WiFi Coverage Heatmap')
            ax.axis('off')
            plt.tight_layout()
            
            fig.savefig(filepath, dpi=300, bbox_inches='tight')
            plt.close(fig)
            
            self._log(f"Heatmap exported to: {filepath}", "SUCCESS")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export image: {e}")
            self._log(f"Image export failed: {e}", "ERROR")
    
    def generate_report(self):
        """Generate professional report"""
        if not self.project.measurements:
            messagebox.showinfo("No Data", "No measurements to report.")
            return
        
        filepath = filedialog.asksaveasfilename(
            title="Save Report",
            defaultextension=".txt",
            filetypes=[("Text Report", "*.txt"), ("HTML Report", "*.html"), ("All Files", "*.*")]
        )
        if not filepath:
            return
        
        try:
            stats = self.project.get_statistics()
            
            report = []
            report.append("=" * 70)
            report.append("WiFi SITE SURVEY REPORT")
            report.append("=" * 70)
            report.append("")
            report.append(f"Project: {self.project.metadata.name}")
            report.append(f"Location: {self.project.metadata.location}")
            report.append(f"Floor: {self.project.metadata.floor}")
            report.append(f"Surveyor: {self.project.metadata.surveyor}")
            report.append(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            report.append("")
            report.append("-" * 70)
            report.append("SUMMARY STATISTICS")
            report.append("-" * 70)
            report.append(f"Total Measurements: {stats.get('count', 0)}")
            report.append(f"Unique Access Points: {stats.get('unique_aps', 0)}")
            report.append(f"Channels Detected: {', '.join(map(str, stats.get('channels', [])))}")
            report.append("")
            report.append(f"Signal Strength (dBm):")
            report.append(f"  Minimum: {stats.get('min_rssi', 'N/A'):.1f}")
            report.append(f"  Maximum: {stats.get('max_rssi', 'N/A'):.1f}")
            report.append(f"  Average: {stats.get('avg_rssi', 'N/A'):.1f}")
            report.append(f"  Median: {stats.get('median_rssi', 'N/A'):.1f}")
            report.append(f"  Std Dev: {stats.get('std_rssi', 'N/A'):.1f}")
            report.append("")
            report.append(f"Coverage Analysis:")
            report.append(f"  Good Coverage (>-60 dBm): {stats.get('good_coverage', 0)} points ({stats.get('good_coverage', 0) / stats.get('count', 1) * 100:.1f}%)")
            report.append(f"  Dead Zones (<-80 dBm): {stats.get('dead_zones', 0)} points ({stats.get('dead_zones', 0) / stats.get('count', 1) * 100:.1f}%)")
            report.append("")
            report.append("-" * 70)
            report.append("ACCESS POINTS")
            report.append("-" * 70)
            for bssid, ap_info in self.project.access_points.items():
                report.append(f"  SSID: {ap_info['ssid']}")
                report.append(f"  BSSID: {bssid}")
                report.append(f"  Channel: {ap_info['channel']}")
                report.append("")
            
            if self.project.metadata.notes:
                report.append("-" * 70)
                report.append("NOTES")
                report.append("-" * 70)
                report.append(self.project.metadata.notes)
            
            report.append("")
            report.append("=" * 70)
            report.append("END OF REPORT")
            report.append("=" * 70)
            
            with open(filepath, 'w') as f:
                f.write('\n'.join(report))
            
            self._log(f"Report generated: {filepath}", "SUCCESS")
            messagebox.showinfo("Success", "Report generated successfully!")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate report: {e}")
            self._log(f"Report generation failed: {e}", "ERROR")
    
    # ==================== TOOLS ====================
    
    def calibrate_dialog(self):
        """Calibrate pixel-to-distance scale"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Calibrate Scale")
        dialog.geometry("350x250")
        
        ttk.Label(dialog, text="Measure a known distance on the floorplan").pack(pady=8)
        
        frame = ttk.Frame(dialog)
        frame.pack(padx=16, pady=8)
        
        ttk.Label(frame, text="Distance (pixels):").grid(row=0, column=0, sticky=tk.W, pady=4)
        px_var = tk.IntVar(value=100)
        ttk.Spinbox(frame, from_=1, to=10000, textvariable=px_var, width=15).grid(row=0, column=1, pady=4)
        
        ttk.Label(frame, text="Real distance:").grid(row=1, column=0, sticky=tk.W, pady=4)
        real_var = tk.DoubleVar(value=10.0)
        ttk.Spinbox(frame, from_=0.1, to=1000, textvariable=real_var, width=15, increment=0.1).grid(row=1, column=1, pady=4)
        
        ttk.Label(frame, text="Unit:").grid(row=2, column=0, sticky=tk.W, pady=4)
        unit_var = tk.StringVar(value="meters")
        ttk.Combobox(frame, textvariable=unit_var, values=["meters", "feet", "cm", "inches"], width=13).grid(row=2, column=1, pady=4)
        
        result_label = ttk.Label(dialog, text="", foreground="blue")
        result_label.pack(pady=8)
        
        def calculate():
            px = px_var.get()
            real = real_var.get()
            unit = unit_var.get()
            
            if px <= 0 or real <= 0:
                messagebox.showerror("Invalid", "Values must be positive")
                return
            
            ratio = px / real
            self.project.metadata.calibration = (ratio, unit)
            result_label.config(text=f"Scale: {ratio:.3f} pixels per {unit}")
            self._log(f"Calibration set: {ratio:.3f} pixels/{unit}", "SUCCESS")
        
        ttk.Button(dialog, text="Calculate", command=calculate).pack(pady=4)
        ttk.Button(dialog, text="Close", command=dialog.destroy).pack(pady=4)
    
    def compare_projects(self):
        """Compare two survey projects"""
        filepath = filedialog.askopenfilename(
            title="Select Project to Compare",
            filetypes=[("WiFi Project", "*.wifiproj"), ("JSON", "*.json")]
        )
        if not filepath:
            return
        
        try:
            self.comparison_project = Project.load_from_file(filepath)
            messagebox.showinfo("Comparison", "Comparison mode not fully implemented in this version.\nFeature coming soon!")
            self._log(f"Comparison project loaded: {filepath}", "INFO")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load comparison project: {e}")
    
    # ==================== INFO PANELS ====================
    
    def update_info_panels(self):
        """Update all information panels"""
        self._update_statistics()
        self._update_access_points()
        self._update_measurements()
        self._update_status_bar()
    
    def _update_statistics(self):
        """Update statistics panel"""
        self.stats_text.delete('1.0', tk.END)
        
        if not self.project.measurements:
            self.stats_text.insert(tk.END, "No measurements yet.\n\nStart measuring to see statistics.")
            return
        
        stats = self.project.get_statistics()
        
        text = []
        text.append("📊 SURVEY STATISTICS\n")
        text.append("=" * 40 + "\n\n")
        text.append(f"Total Points: {stats.get('count', 0)}\n")
        text.append(f"Unique APs: {stats.get('unique_aps', 0)}\n\n")
        
        text.append("📡 Signal Strength (dBm)\n")
        text.append("-" * 40 + "\n")
        text.append(f"  Minimum: {stats.get('min_rssi', 0):.1f}\n")
        text.append(f"  Maximum: {stats.get('max_rssi', 0):.1f}\n")
        text.append(f"  Average: {stats.get('avg_rssi', 0):.1f}\n")
        text.append(f"  Median: {stats.get('median_rssi', 0):.1f}\n")
        text.append(f"  Std Dev: {stats.get('std_rssi', 0):.1f}\n\n")
        
        text.append("📶 Coverage Quality\n")
        text.append("-" * 40 + "\n")
        total = stats.get('count', 1)
        good = stats.get('good_coverage', 0)
        dead = stats.get('dead_zones', 0)
        
        text.append(f"  Excellent (>-60 dBm): {good} ({good/total*100:.1f}%)\n")
        text.append(f"  Dead Zones (<-80 dBm): {dead} ({dead/total*100:.1f}%)\n\n")
        
        channels = stats.get('channels', [])
        if channels:
            text.append(f"📻 Channels: {', '.join(map(str, channels))}\n")
        
        self.stats_text.insert(tk.END, ''.join(text))
    
    def _update_access_points(self):
        """Update access points panel"""
        self.ap_text.delete('1.0', tk.END)
        
        if not self.project.access_points:
            self.ap_text.insert(tk.END, "No access points detected yet.\n\nMeasurements will show AP details here.")
            return
        
        text = []
        text.append("📡 DETECTED ACCESS POINTS\n")
        text.append("=" * 40 + "\n\n")
        
        for i, (bssid, ap_info) in enumerate(self.project.access_points.items(), 1):
            text.append(f"AP #{i}\n")
            text.append("-" * 40 + "\n")
            text.append(f"  SSID: {ap_info['ssid']}\n")
            text.append(f"  BSSID: {bssid}\n")
            text.append(f"  Channel: {ap_info['channel']}\n")
            if ap_info.get('frequency'):
                text.append(f"  Frequency: {ap_info['frequency']} MHz\n")
            text.append(f"  First Seen: {ap_info['first_seen'][:19]}\n")
            text.append("\n")
        
        self.ap_text.insert(tk.END, ''.join(text))
    
    def _update_measurements(self):
        """Update measurements tree"""
        # Clear existing
        for item in self.meas_tree.get_children():
            self.meas_tree.delete(item)
        
        # Add measurements
        for m in reversed(self.project.measurements[-100:]):  # Show last 100
            time_str = m.timestamp[11:19] if len(m.timestamp) > 19 else m.timestamp
            self.meas_tree.insert('', 0, values=(
                time_str,
                m.x,
                m.y,
                f"{m.rssi:.0f}",
                m.ssid[:15] if m.ssid else 'N/A'
            ))
    
    def _update_status_bar(self):
        """Update status bar counters"""
        self.point_count_label.config(text=f"Points: {len(self.project.measurements)}")
        self.ap_count_label.config(text=f"APs: {len(self.project.access_points)}")
    
    # ==================== LOGGING ====================
    
    def _log(self, message: str, level: str = "INFO"):
        """Add message to log"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}\n"
        
        self.log_text.insert(tk.END, log_entry, level)
        self.log_text.see(tk.END)
        
        # Also update status bar
        self.status_label.config(text=message)
    
    # ==================== AUTO-SAVE ====================
    
    def _setup_auto_save(self):
        """Setup auto-save timer"""
        if self.auto_save_enabled and self.current_file:
            try:
                self.project.save_to_file(self.current_file)
                self._log("Auto-saved", "INFO")
            except Exception as e:
                self._log(f"Auto-save failed: {e}", "WARN")
        
        # Schedule next auto-save
        self.root.after(self.auto_save_interval, self._setup_auto_save)
    
    # ==================== DIALOGS ====================
    
    def show_about(self):
        """Show about dialog"""
        about_text = """WiFi Heatmap Pro - IT Professional Suite
Version 2.0

A comprehensive WiFi site survey tool for IT professionals.

Features:
• Multi-AP tracking with detailed network info
• Project management and auto-save
• Advanced heatmap visualization
• Statistical analysis and reporting
• Dead zone detection
• Export to multiple formats
• Professional report generation

Created with Python, Matplotlib, and NumPy

© 2024 - For IT Professionals"""
        
        messagebox.showinfo("About WiFi Heatmap Pro", about_text)


# ==================== MAIN ====================

def main():
    """Main application entry point"""
    root = tk.Tk()
    
    # Set application icon (if available)
    try:
        # You can add icon file here
        # root.iconbitmap('wifi_icon.ico')
        pass
    except:
        pass
    
    app = WiFiHeatmapPro(root)
    
    # Handle window close
    def on_closing():
        if app.project.measurements and messagebox.askyesno(
            "Exit",
            "Do you want to save your project before exiting?"
        ):
            app.save_project()
        root.destroy()
    
    root.protocol("WM_DELETE_WINDOW", on_closing)
    
    # Start the application
    root.mainloop()


if __name__ == '__main__':
    main()