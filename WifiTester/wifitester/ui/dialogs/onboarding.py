"""First-run onboarding wizard."""

from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, ttk
from typing import Callable


class OnboardingWizard(tk.Toplevel):
    def __init__(
        self,
        parent: tk.Tk,
        on_complete: Callable[[dict], None],
        on_skip: Callable[[], None],
    ) -> None:
        super().__init__(parent)
        self.title("Welcome to WiFi Heatmap Pro")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.on_complete = on_complete
        self.on_skip = on_skip
        self.step = 0
        self.result: dict = {
            "project_name": "New Survey",
            "location": "",
            "surveyor": "",
            "floorplan_path": "",
            "simulate_mode": False,
        }

        self.body = ttk.Frame(self, padding=16)
        self.body.pack(fill=tk.BOTH, expand=True)

        self.nav = ttk.Frame(self, padding=(16, 0, 16, 16))
        self.nav.pack(fill=tk.X)

        self.back_btn = ttk.Button(self.nav, text="Back", command=self._back)
        self.back_btn.pack(side=tk.LEFT)
        self.skip_btn = ttk.Button(self.nav, text="Skip", command=self._skip)
        self.skip_btn.pack(side=tk.LEFT, padx=8)
        self.next_btn = ttk.Button(self.nav, text="Next", command=self._next)
        self.next_btn.pack(side=tk.RIGHT)

        self._render_step()

    def _clear_body(self) -> None:
        for child in self.body.winfo_children():
            child.destroy()

    def _render_step(self) -> None:
        self._clear_body()
        self.back_btn.state(["!disabled"] if self.step > 0 else ["disabled"])

        if self.step == 0:
            self._step_welcome()
        elif self.step == 1:
            self._step_project()
        elif self.step == 2:
            self._step_floorplan()
        elif self.step == 3:
            self._step_wifi_mode()
        else:
            self._step_finish()

    def _step_welcome(self) -> None:
        ttk.Label(self.body, text="WiFi Heatmap Pro", font=("Arial", 16, "bold")).pack(anchor=tk.W)
        ttk.Label(
            self.body,
            text=(
                "Map WiFi coverage on a floorplan in four steps:\n\n"
                "1. Create a survey project\n"
                "2. Load a floorplan image\n"
                "3. Click points to record signal strength\n"
                "4. View the heatmap overlay on the map"
            ),
            justify=tk.LEFT,
            wraplength=420,
        ).pack(anchor=tk.W, pady=(12, 0))

    def _step_project(self) -> None:
        ttk.Label(self.body, text="Project details", font=("Arial", 12, "bold")).pack(anchor=tk.W)
        form = ttk.Frame(self.body)
        form.pack(fill=tk.X, pady=(12, 0))

        self.name_var = tk.StringVar(value=self.result["project_name"])
        self.location_var = tk.StringVar(value=self.result["location"])
        self.surveyor_var = tk.StringVar(value=self.result["surveyor"])

        ttk.Label(form, text="Project name").grid(row=0, column=0, sticky=tk.W, pady=4)
        ttk.Entry(form, textvariable=self.name_var, width=36).grid(row=0, column=1, pady=4)
        ttk.Label(form, text="Location").grid(row=1, column=0, sticky=tk.W, pady=4)
        ttk.Entry(form, textvariable=self.location_var, width=36).grid(row=1, column=1, pady=4)
        ttk.Label(form, text="Surveyor").grid(row=2, column=0, sticky=tk.W, pady=4)
        ttk.Entry(form, textvariable=self.surveyor_var, width=36).grid(row=2, column=1, pady=4)

    def _step_floorplan(self) -> None:
        ttk.Label(self.body, text="Floorplan", font=("Arial", 12, "bold")).pack(anchor=tk.W)
        ttk.Label(
            self.body,
            text="Choose a PNG or JPG image of your floor layout.",
            wraplength=420,
        ).pack(anchor=tk.W, pady=(8, 0))

        self.floorplan_var = tk.StringVar(value=self.result["floorplan_path"])
        path_row = ttk.Frame(self.body)
        path_row.pack(fill=tk.X, pady=(12, 0))

        ttk.Entry(path_row, textvariable=self.floorplan_var, width=42).pack(
            side=tk.LEFT, fill=tk.X, expand=True
        )
        ttk.Button(path_row, text="Browse...", command=self._browse_floorplan).pack(
            side=tk.LEFT, padx=(8, 0)
        )

    def _step_wifi_mode(self) -> None:
        ttk.Label(self.body, text="WiFi source", font=("Arial", 12, "bold")).pack(anchor=tk.W)
        self.simulate_var = tk.BooleanVar(value=self.result["simulate_mode"])
        ttk.Radiobutton(
            self.body,
            text="Use live WiFi readings from this computer",
            variable=self.simulate_var,
            value=False,
        ).pack(anchor=tk.W, pady=(12, 4))
        ttk.Radiobutton(
            self.body,
            text="Test mode — simulate signal strength (no WiFi required)",
            variable=self.simulate_var,
            value=True,
        ).pack(anchor=tk.W)

    def _step_finish(self) -> None:
        ttk.Label(self.body, text="Ready to survey", font=("Arial", 12, "bold")).pack(anchor=tk.W)
        ttk.Label(
            self.body,
            text=(
                "Click on the map to record points while surveying.\n"
                "The app samples signal several times per click for accuracy.\n\n"
                "You can reopen this guide from Help → Getting Started."
            ),
            wraplength=420,
            justify=tk.LEFT,
        ).pack(anchor=tk.W, pady=(12, 0))
        self.next_btn.config(text="Start Surveying")

    def _browse_floorplan(self) -> None:
        path = filedialog.askopenfilename(
            title="Select Floorplan",
            filetypes=[
                ("Images", "*.png *.jpg *.jpeg *.bmp"),
                ("All Files", "*.*"),
            ],
        )
        if path:
            self.floorplan_var.set(path)

    def _store_step_values(self) -> None:
        if self.step == 1:
            self.result["project_name"] = self.name_var.get().strip() or "New Survey"
            self.result["location"] = self.location_var.get().strip()
            self.result["surveyor"] = self.surveyor_var.get().strip()
        elif self.step == 2:
            self.result["floorplan_path"] = self.floorplan_var.get().strip()
        elif self.step == 3:
            self.result["simulate_mode"] = self.simulate_var.get()

    def _next(self) -> None:
        self._store_step_values()

        if self.step < 4:
            self.step += 1
            self._render_step()
            return

        self.on_complete(self.result)
        self.destroy()

    def _back(self) -> None:
        if self.step == 0:
            return
        self._store_step_values()
        self.step -= 1
        self.next_btn.config(text="Next")
        self._render_step()

    def _skip(self) -> None:
        self.on_skip()
        self.destroy()


def show_onboarding_if_needed(
    parent: tk.Tk,
    settings: dict,
    on_complete: Callable[[dict], None],
    on_skip: Callable[[], None],
) -> None:
    if settings.get("onboarding_completed"):
        return
    OnboardingWizard(parent, on_complete=on_complete, on_skip=on_skip)
