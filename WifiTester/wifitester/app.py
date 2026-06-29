"""WiFi Heatmap Pro desktop application."""

import csv
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

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
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
except Exception:
    raise RuntimeError("matplotlib and numpy required: pip install matplotlib numpy")

from wifitester import __version__
from wifitester.models.project import MeasurementPoint, Project
from wifitester.services.heatmap import (
    MIN_HEATMAP_POINTS,
    HeatmapConfig,
    can_render_heatmap,
    create_heatmap_figure,
    image_bounds,
    interpolate_signal_grid,
    render_inline_heatmap_layer,
)
from wifitester.services.sampler import median_rssi
from wifitester.services.settings import load_settings, save_settings
from wifitester.services.wifi_scanner import WiFiScanner
from wifitester.ui.dialogs.onboarding import OnboardingWizard, show_onboarding_if_needed
from wifitester.ui.signal_style import draw_signal_legend, rssi_to_color


AUTOSAVE_DIR = Path.home() / ".config" / "wifitester" / "autosave"
AUTOSAVE_FILE = AUTOSAVE_DIR / "autosave.wifiproj"


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
        self.settings = load_settings()
        self._floorplan_photo = None

        # UI state
        self.measuring = False
        self.sampling_active = False
        self.auto_save_enabled = True
        self.auto_save_interval = 300000  # 5 minutes
        self._live_wifi_info = None
        self._pending_sample: Optional[dict] = None
        self._sample_readings: list[float] = []
        self._sample_wifi_meta: list[dict] = []

        # Matplotlib setup
        self.fig: Figure = Figure(figsize=(10, 8))
        self.ax = self.fig.add_subplot(111)
        self.canvas = None
        self.cid_click = None

        # Configuration
        self.view_mode = tk.StringVar(value="points")
        self.overlay_opacity = tk.DoubleVar(value=0.6)
        self.show_advanced = tk.BooleanVar(value=False)
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
        self.live_rssi_text = tk.StringVar(value="Signal: —")

        self.view_mode.trace_add("write", lambda *_: self.refresh_view())
        self.overlay_opacity.trace_add("write", lambda *_: self.refresh_view())
        self.show_points.trace_add("write", lambda *_: self.refresh_view())
        self.show_labels.trace_add("write", lambda *_: self.refresh_view())
        self.show_grid.trace_add("write", lambda *_: self.refresh_view())
        self.show_dead_zones.trace_add("write", lambda *_: self.refresh_view())

        self._build_ui()
        self._setup_auto_save()
        self._start_live_rssi_poll()
        self._log("WiFi Heatmap Pro initialized")
        self.root.after(300, self._maybe_show_onboarding)
    
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
        tools_menu.add_command(label="Show Heatmap on Map", command=self.show_heatmap_view, accelerator="Ctrl+G")
        tools_menu.add_command(label="Export Image...", command=self.export_image)
        tools_menu.add_command(label="Generate Report...", command=self.generate_report)
        
        # View menu
        view_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="View", menu=view_menu)
        view_menu.add_radiobutton(label="Points only", variable=self.view_mode, value="points")
        view_menu.add_radiobutton(label="Heatmap only", variable=self.view_mode, value="heatmap")
        view_menu.add_radiobutton(label="Heatmap overlay", variable=self.view_mode, value="overlay")
        view_menu.add_separator()
        view_menu.add_checkbutton(label="Show Points", variable=self.show_points)
        view_menu.add_checkbutton(label="Show Labels", variable=self.show_labels)
        view_menu.add_checkbutton(label="Show Grid", variable=self.show_grid)
        view_menu.add_checkbutton(label="Highlight Dead Zones", variable=self.show_dead_zones)
        
        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="Getting Started...", command=self.show_getting_started)
        help_menu.add_command(label="About", command=self.show_about)
        
        # Keyboard shortcuts
        self.root.bind('<Control-n>', lambda e: self.new_project())
        self.root.bind('<Control-o>', lambda e: self.open_project())
        self.root.bind('<Control-s>', lambda e: self.save_project())
        self.root.bind('<Control-Shift-S>', lambda e: self.save_project_as())
        self.root.bind('<Control-g>', lambda e: self.show_heatmap_view())
        self.root.bind('<Control-z>', lambda e: self.undo_last())
    
    def _build_left_panel(self, parent):
        """Build simplified left control panel."""
        panel = ttk.Frame(parent, padding=8)
        panel.pack(fill=tk.BOTH, expand=True)

        ttk.Label(panel, text="Project", font=("Arial", 11, "bold")).pack(anchor=tk.W)
        self.project_name_label = ttk.Label(panel, text=self.project.metadata.name, wraplength=260)
        self.project_name_label.pack(anchor=tk.W, pady=(4, 8))

        self.thumbnail_label = ttk.Label(panel, text="No floorplan loaded", relief=tk.SUNKEN)
        self.thumbnail_label.pack(fill=tk.X, pady=(0, 8))

        ttk.Button(panel, text="Load Floorplan", command=self.select_floorplan).pack(fill=tk.X, pady=2)
        ttk.Button(panel, text="Project Settings", command=self.edit_project_settings).pack(fill=tk.X, pady=2)

        ttk.Separator(panel).pack(fill=tk.X, pady=10)

        ttk.Label(panel, text="Survey", font=("Arial", 11, "bold")).pack(anchor=tk.W)
        self.measure_btn = ttk.Button(panel, text="Start Surveying", command=self.toggle_measuring)
        self.measure_btn.pack(fill=tk.X, pady=4)
        ttk.Button(panel, text="Undo Last", command=self.undo_last).pack(fill=tk.X, pady=2)
        ttk.Button(panel, text="Clear All", command=self.clear_all).pack(fill=tk.X, pady=2)

        ttk.Checkbutton(panel, text="Test mode (simulate RSSI)", variable=self.simulate_mode).pack(
            anchor=tk.W, pady=(8, 2)
        )
        sim_frame = ttk.Frame(panel)
        sim_frame.pack(fill=tk.X, pady=2)
        ttk.Label(sim_frame, text="Simulated RSSI:").pack(side=tk.LEFT)
        ttk.Spinbox(sim_frame, from_=-100, to=-20, textvariable=self.sim_rssi, width=6).pack(
            side=tk.LEFT, padx=4
        )

        ttk.Separator(panel).pack(fill=tk.X, pady=10)

        ttk.Label(panel, text="Map view", font=("Arial", 11, "bold")).pack(anchor=tk.W)
        for label, value in (
            ("Points", "points"),
            ("Heatmap", "heatmap"),
            ("Overlay", "overlay"),
        ):
            ttk.Radiobutton(panel, text=label, variable=self.view_mode, value=value).pack(anchor=tk.W)

        self.heatmap_hint_label = ttk.Label(
            panel,
            text=f"Add {MIN_HEATMAP_POINTS}+ points to enable heatmap.",
            foreground="#666666",
            wraplength=260,
        )
        self.heatmap_hint_label.pack(anchor=tk.W, pady=(6, 0))

        ttk.Label(panel, text="Overlay opacity").pack(anchor=tk.W, pady=(8, 0))
        ttk.Scale(panel, from_=0.2, to=1.0, variable=self.overlay_opacity, orient=tk.HORIZONTAL).pack(
            fill=tk.X
        )

        ttk.Separator(panel).pack(fill=tk.X, pady=10)

        ttk.Button(panel, text="Export Image", command=self.export_image).pack(fill=tk.X, pady=2)
        ttk.Button(panel, text="Export CSV", command=self.export_csv).pack(fill=tk.X, pady=2)
        ttk.Button(panel, text="Generate Report", command=self.generate_report).pack(fill=tk.X, pady=2)

        ttk.Separator(panel).pack(fill=tk.X, pady=10)

        ttk.Checkbutton(
            panel,
            text="Show advanced settings",
            variable=self.show_advanced,
            command=self._toggle_advanced_panel,
        ).pack(anchor=tk.W)

        self.advanced_frame = ttk.LabelFrame(panel, text="Advanced", padding=6)
        self._build_advanced_panel(self.advanced_frame)

        ttk.Separator(panel).pack(fill=tk.X, pady=10)
        ttk.Button(panel, text="Refresh View", command=self.refresh_view).pack(fill=tk.X, pady=2)

    def _build_advanced_panel(self, parent):
        ttk.Label(parent, text="Interpolation").pack(anchor=tk.W)
        ttk.Combobox(
            parent,
            textvariable=self.interpolate_method,
            values=["cubic", "linear", "nearest"],
            state="readonly",
            width=18,
        ).pack(fill=tk.X, pady=2)

        ttk.Label(parent, text="Colormap").pack(anchor=tk.W, pady=(6, 0))
        ttk.Combobox(
            parent,
            textvariable=self.colormap,
            values=["RdYlGn", "viridis", "plasma", "coolwarm", "jet"],
            state="readonly",
            width=18,
        ).pack(fill=tk.X, pady=2)

        ttk.Label(parent, text="Resolution").pack(anchor=tk.W, pady=(6, 0))
        ttk.Scale(parent, from_=50, to=500, variable=self.grid_res, orient=tk.HORIZONTAL).pack(fill=tk.X)

        ttk.Label(parent, text="Smoothing").pack(anchor=tk.W, pady=(6, 0))
        ttk.Scale(parent, from_=0, to=5, variable=self.smoothing_sigma, orient=tk.HORIZONTAL).pack(fill=tk.X)

        ttk.Checkbutton(parent, text="Show colorbar on export", variable=self.show_colorbar).pack(anchor=tk.W, pady=2)
        ttk.Checkbutton(parent, text="Show grid", variable=self.show_grid).pack(anchor=tk.W, pady=2)
        ttk.Label(parent, text="Grid spacing (px)").pack(anchor=tk.W)
        ttk.Spinbox(parent, from_=10, to=200, textvariable=self.grid_spacing, width=18).pack(fill=tk.X, pady=2)

    def _toggle_advanced_panel(self):
        if self.show_advanced.get():
            self.advanced_frame.pack(fill=tk.X, pady=(6, 0))
        else:
            self.advanced_frame.pack_forget()
    
    def _build_center_panel(self, parent):
        """Build center canvas area with toolbar and inline map."""
        toolbar_frame = ttk.Frame(parent)
        toolbar_frame.pack(fill=tk.X, padx=4, pady=4)

        self.live_rssi_label = ttk.Label(
            toolbar_frame,
            textvariable=self.live_rssi_text,
            font=("Arial", 10, "bold"),
        )
        self.live_rssi_label.pack(side=tk.LEFT, padx=(4, 16))

        ttk.Button(toolbar_frame, text="Load Floorplan", command=self.select_floorplan).pack(
            side=tk.LEFT, padx=2
        )
        ttk.Button(toolbar_frame, text="Show Heatmap", command=self.show_heatmap_view).pack(
            side=tk.LEFT, padx=2
        )
        ttk.Button(toolbar_frame, text="Export Image", command=self.export_image).pack(
            side=tk.LEFT, padx=2
        )

        self.banner_frame = ttk.Frame(parent)
        self.banner_frame.pack(fill=tk.X, padx=4)
        self.banner_label = ttk.Label(
            self.banner_frame,
            text="",
            foreground="#b45309",
            wraplength=900,
        )
        self.banner_label.pack(fill=tk.X, padx=4, pady=2)
        self.banner_frame.pack_forget()

        self.canvas_host = ttk.Frame(parent)
        self.canvas_host.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.canvas_host)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        self.ax.axis("off")
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
        self._stop_measuring()
        self._update_floorplan_thumbnail()
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
            else:
                self.image = None
                self._update_floorplan_thumbnail()
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
            self._update_floorplan_thumbnail()
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
        self._log(f"Floorplan loaded: {filepath}", "SUCCESS")
    
    def _load_floorplan(self, filepath: str):
        """Load floorplan image"""
        try:
            self.image = Image.open(filepath)
            self.project.metadata.floorplan_path = filepath
            self._update_floorplan_thumbnail()
            self.refresh_view()
            self._start_measuring()
            self._hide_wifi_banner()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load image: {e}")
            self._log(f"Image load failed: {e}", "ERROR")

    def _update_floorplan_thumbnail(self):
        self.project_name_label.config(text=self.project.metadata.name)
        if not self.image:
            self.thumbnail_label.config(image="", text="No floorplan loaded")
            self._floorplan_photo = None
            return

        thumb = self.image.copy()
        thumb.thumbnail((220, 140))
        self._floorplan_photo = ImageTk.PhotoImage(thumb)
        self.thumbnail_label.config(image=self._floorplan_photo, text="")

    def _update_heatmap_hint(self):
        count = len(self.project.measurements)
        remaining = max(0, MIN_HEATMAP_POINTS - count)
        if remaining:
            self.heatmap_hint_label.config(
                text=f"Add {remaining} more point(s) to enable heatmap view."
            )
        else:
            self.heatmap_hint_label.config(text="Heatmap view is available.")

    def _maybe_show_onboarding(self):
        show_onboarding_if_needed(
            self.root,
            self.settings,
            on_complete=self._apply_onboarding,
            on_skip=self._skip_onboarding,
        )

    def show_getting_started(self):
        OnboardingWizard(
            self.root,
            on_complete=self._apply_onboarding,
            on_skip=lambda: None,
        )

    def _skip_onboarding(self):
        self.settings["onboarding_completed"] = True
        save_settings(self.settings)

    def _apply_onboarding(self, data: dict):
        self.project.metadata.name = data.get("project_name", "New Survey")
        self.project.metadata.location = data.get("location", "")
        self.project.metadata.surveyor = data.get("surveyor", "")
        self.simulate_mode.set(bool(data.get("simulate_mode", False)))
        self.settings["onboarding_completed"] = True
        save_settings(self.settings)
        self._update_floorplan_thumbnail()
        self.root.title(f"WiFi Heatmap Pro - {self.project.metadata.name}")

        floorplan = data.get("floorplan_path", "")
        if floorplan and os.path.exists(floorplan):
            self._load_floorplan(floorplan)
        else:
            self.refresh_view()

        self._log("Onboarding complete — ready to survey", "SUCCESS")

    def _start_live_rssi_poll(self):
        if not self.simulate_mode.get():
            self._live_wifi_info = WiFiScanner.get_detailed_info()
        else:
            self._live_wifi_info = {
                "rssi": self.sim_rssi.get(),
                "ssid": "SimulatedAP",
                "bssid": "",
                "channel": 6,
            }

        if self._live_wifi_info and self._live_wifi_info.get("rssi") is not None:
            ssid = self._live_wifi_info.get("ssid") or "Unknown"
            self.live_rssi_text.set(
                f"Signal: {self._live_wifi_info['rssi']} dBm · {ssid}"
            )
            if not self.simulate_mode.get() and self.image and not self.sampling_active:
                self._hide_wifi_banner()
        else:
            self.live_rssi_text.set("Signal: unavailable")
            if self.image and not self.simulate_mode.get():
                self._show_wifi_banner(
                    "Cannot read WiFi signal. Enable Test mode in the sidebar or check your connection."
                )

        interval = int(self.settings.get("live_rssi_interval_ms", 500))
        self.root.after(interval, self._start_live_rssi_poll)

    def _show_wifi_banner(self, message: str):
        self.banner_label.config(text=message)
        if not self.banner_frame.winfo_ismapped():
            self.banner_frame.pack(fill=tk.X, padx=4, pady=(0, 4), before=self.canvas_host)

    def _hide_wifi_banner(self):
        self.banner_frame.pack_forget()

    # ==================== MEASUREMENT ====================

    def _start_measuring(self):
        if not self.image or self.measuring:
            return
        self.measuring = True
        self.measure_btn.config(text="Pause Surveying")
        self.cid_click = self.canvas.mpl_connect("button_press_event", self._on_canvas_click)
        self.canvas.get_tk_widget().config(cursor="crosshair")
        self.status_label.config(text="Surveying — click the map to record a point")
        self._log("Survey mode started", "INFO")

    def _stop_measuring(self):
        if not self.measuring:
            return
        self.measuring = False
        self.measure_btn.config(text="Start Surveying")
        if self.cid_click:
            self.canvas.mpl_disconnect(self.cid_click)
            self.cid_click = None
        self.canvas.get_tk_widget().config(cursor="")
        self.status_label.config(text="Surveying paused")
        self._log("Survey mode paused", "INFO")
    
    def toggle_measuring(self):
        """Start/stop measurement mode"""
        if not self.image:
            messagebox.showwarning("No Floorplan", "Load a floorplan image to begin surveying.")
            return

        if self.measuring:
            self._stop_measuring()
            self.refresh_view()
        else:
            self._start_measuring()

    def _on_canvas_click(self, event):
        """Handle canvas click during measurement"""
        if not self.measuring or self.sampling_active or event.inaxes != self.ax:
            return
        if event.xdata is None or event.ydata is None:
            return

        x, y = int(event.xdata), int(event.ydata)
        self._pending_sample = {"x": x, "y": y}
        self._sample_readings = []
        self._sample_wifi_meta = []
        self.sampling_active = True
        self.status_label.config(text=f"Sampling at ({x}, {y})...")
        self._collect_sample_reading()

    def _collect_sample_reading(self):
        if not self._pending_sample:
            self.sampling_active = False
            return

        if self.simulate_mode.get():
            wifi_info = {
                "rssi": self.sim_rssi.get(),
                "ssid": "SimulatedAP",
                "bssid": "XX:XX:XX:XX:XX:XX",
                "channel": 6,
            }
        else:
            wifi_info = WiFiScanner.get_detailed_info()
            if not wifi_info or wifi_info.get("rssi") is None:
                self.sampling_active = False
                self._pending_sample = None
                self._show_wifi_banner(
                    "Could not read WiFi signal. Enable Test mode or check your connection."
                )
                self.status_label.config(text="Measurement failed — no WiFi signal")
                return

        self._sample_readings.append(float(wifi_info["rssi"]))
        self._sample_wifi_meta.append(wifi_info)

        target = int(self.settings.get("sample_count", 5))
        if len(self._sample_readings) < target:
            self.status_label.config(
                text=f"Sampling {len(self._sample_readings)}/{target} at "
                f"({self._pending_sample['x']}, {self._pending_sample['y']})..."
            )
            interval = int(self.settings.get("sample_interval_ms", 300))
            self.root.after(interval, self._collect_sample_reading)
            return

        self._finish_sampled_measurement()

    def _finish_sampled_measurement(self):
        pending = self._pending_sample or {}
        x, y = pending.get("x", 0), pending.get("y", 0)
        rssi = median_rssi(self._sample_readings)
        latest = self._sample_wifi_meta[-1] if self._sample_wifi_meta else {}

        point = MeasurementPoint(
            x=x,
            y=y,
            rssi=rssi if rssi is not None else latest.get("rssi", -70),
            timestamp=datetime.now().isoformat(),
            ssid=latest.get("ssid", ""),
            bssid=latest.get("bssid", ""),
            channel=latest.get("channel", 0),
        )

        self.project.add_measurement(point)
        self.sampling_active = False
        self._pending_sample = None
        self._sample_readings = []
        self._sample_wifi_meta = []

        self.refresh_view()
        self.update_info_panels()
        self._log(
            f"Point {len(self.project.measurements)}: ({x},{y}) = {point.rssi:.0f} dBm "
            f"[{point.ssid or 'Unknown'}]",
            "SUCCESS",
        )
        self.status_label.config(text=f"Recorded point {len(self.project.measurements)}")
    
    def undo_last(self):
        """Remove last measurement"""
        if not self.project.measurements:
            messagebox.showinfo("No Data", "No measurements to undo.")
            return

        removed = self.project.remove_last_measurement()
        if removed is None:
            return
        self.refresh_view()
        self.update_info_panels()
        self._log(f"Removed measurement: ({removed.x},{removed.y})", "INFO")
    
    def clear_all(self):
        """Clear all measurements"""
        if not self.project.measurements:
            return
        
        if messagebox.askyesno("Clear All", f"Remove all {len(self.project.measurements)} measurements?"):
            self.project.clear_measurements()
            self.refresh_view()
            self.update_info_panels()
            self._log("All measurements cleared", "WARN")
    
    # ==================== VISUALIZATION ====================
    
    def refresh_view(self):
        """Refresh the canvas view with optional inline heatmap."""
        self.ax.clear()
        self._update_heatmap_hint()

        if not self.image:
            self.ax.text(
                0.5,
                0.55,
                "Load a floorplan to begin your survey",
                ha="center",
                va="center",
                fontsize=14,
                transform=self.ax.transAxes,
            )
            self.ax.text(
                0.5,
                0.45,
                "Use Load Floorplan in the sidebar or toolbar",
                ha="center",
                va="center",
                fontsize=10,
                color="#666666",
                transform=self.ax.transAxes,
            )
            self.ax.set_title("WiFi Heatmap Pro")
            self.ax.axis("off")
            self.canvas.draw()
            return

        mode = self.view_mode.get()
        show_floorplan = mode in ("points", "overlay")
        show_heatmap = mode in ("heatmap", "overlay")

        if show_floorplan:
            self.ax.imshow(self.image, zorder=1)

        if self.show_grid.get():
            self._draw_grid()

        if show_heatmap and can_render_heatmap(len(self.project.measurements)):
            try:
                self._draw_inline_heatmap(mode)
            except Exception as exc:
                self._log(f"Inline heatmap failed: {exc}", "ERROR")
        elif show_heatmap:
            self.ax.text(
                0.5,
                0.95,
                f"Need {MIN_HEATMAP_POINTS}+ points for heatmap (have {len(self.project.measurements)})",
                ha="center",
                va="top",
                transform=self.ax.transAxes,
                fontsize=9,
                color="#666666",
                bbox=dict(facecolor="white", alpha=0.8, edgecolor="none"),
            )

        if self.show_points.get() or mode == "points":
            for point in self.project.measurements:
                self._draw_measurement_point_static(point)

        draw_signal_legend(self.ax)

        title = "Surveying — click to measure" if self.measuring else self.project.metadata.name
        self.ax.set_title(title)
        self.ax.axis("off")
        self.canvas.draw()

    def _draw_inline_heatmap(self, mode: str):
        x_coords = [m.x for m in self.project.measurements]
        y_coords = [m.y for m in self.project.measurements]
        z_values = [m.rssi for m in self.project.measurements]
        width, height = self.image.size
        bounds = image_bounds(width, height)

        config = self._heatmap_config()
        config.show_colorbar = False
        config.show_points = False

        xi, yi, zi = interpolate_signal_grid(
            x_coords,
            y_coords,
            z_values,
            bounds,
            config,
        )

        alpha = 1.0 if mode == "heatmap" else self.overlay_opacity.get()
        if mode == "heatmap":
            self.ax.clear()
            self.ax.imshow(self.image, zorder=1)

        render_inline_heatmap_layer(self.ax, xi, yi, zi, config, alpha=alpha)

    def _draw_measurement_point_static(self, point: MeasurementPoint):
        """Draw point on the map."""
        if not self.show_points.get():
            return

        color = rssi_to_color(point.rssi)
        self.ax.plot(
            point.x,
            point.y,
            marker="o",
            markersize=8,
            markerfacecolor=color,
            markeredgecolor="black",
            markeredgewidth=1.5,
            zorder=10,
        )

        if self.show_labels.get():
            self.ax.text(
                point.x + 5,
                point.y,
                f"{point.rssi:.0f}",
                fontsize=8,
                color="black",
                zorder=11,
                bbox=dict(facecolor="white", alpha=0.8, edgecolor="none", pad=1),
            )
    
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
    
    def _heatmap_config(self) -> HeatmapConfig:
        return HeatmapConfig(
            method=self.interpolate_method.get(),
            grid_res=self.grid_res.get(),
            smoothing_sigma=self.smoothing_sigma.get(),
            colormap=self.colormap.get(),
            show_dead_zones=self.show_dead_zones.get(),
            show_colorbar=self.show_colorbar.get(),
            show_points=self.show_points.get(),
        )

    def _heatmap_image_array(self):
        if not self.image:
            return None
        return np.array(self.image)

    def show_heatmap_view(self):
        """Switch to inline heatmap view on the main canvas."""
        if not can_render_heatmap(len(self.project.measurements)):
            messagebox.showinfo(
                "More points needed",
                f"Add at least {MIN_HEATMAP_POINTS} measurements in different areas to build a heatmap.",
            )
            return

        self.view_mode.set("overlay")
        self.refresh_view()
        self._log("Heatmap overlay shown on map", "SUCCESS")

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
                    'x', 'y', 'rssi', 'timestamp', 'ssid', 'bssid', 'channel'
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
            x_coords = [m.x for m in self.project.measurements]
            y_coords = [m.y for m in self.project.measurements]
            z_values = [m.rssi for m in self.project.measurements]
            title = f"{self.project.metadata.name} - WiFi Coverage Heatmap"
            bounds = None
            if self.image:
                width, height = self.image.size
                bounds = image_bounds(width, height)

            fig = create_heatmap_figure(
                self._heatmap_image_array(),
                x_coords,
                y_coords,
                z_values,
                self._heatmap_config(),
                title,
                bounds=bounds,
            )
            fig.savefig(filepath, dpi=300, bbox_inches="tight")
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
    
    def _autosave_path(self) -> Path:
        if self.current_file:
            return Path(self.current_file)
        AUTOSAVE_DIR.mkdir(parents=True, exist_ok=True)
        return AUTOSAVE_FILE

    def _setup_auto_save(self):
        """Setup auto-save timer"""
        if self.auto_save_enabled and self.project.measurements:
            try:
                path = self._autosave_path()
                self.project.save_to_file(str(path))
                if path == AUTOSAVE_FILE:
                    self._log(f"Auto-saved to {path}", "INFO")
                else:
                    self._log("Auto-saved", "INFO")
            except OSError as e:
                self._log(f"Auto-save failed: {e}", "WARN")

        self.root.after(self.auto_save_interval, self._setup_auto_save)
    
    # ==================== DIALOGS ====================
    
    def show_about(self):
        """Show about dialog"""
        about_text = f"""WiFi Heatmap Pro
Version {__version__}

WiFi site survey tool for floorplan-based coverage mapping.

• Live signal monitoring and multi-sample measurements
• Inline heatmap overlay on floorplans
• Project save/load and CSV export
• Survey statistics and text reports

Python · Matplotlib · NumPy · SciPy"""
        
        messagebox.showinfo("About WiFi Heatmap Pro", about_text)


# ==================== MAIN ====================

def main():
    """Main application entry point"""
    root = tk.Tk()
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