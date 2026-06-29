"""Heatmap interpolation and rendering."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional, Sequence, Tuple

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.figure import Figure

try:
    from scipy.interpolate import griddata
    from scipy.ndimage import gaussian_filter
except ImportError:
    griddata = None
    gaussian_filter = None


MIN_HEATMAP_POINTS = 3


def image_bounds(width: int, height: int) -> Tuple[float, float, float, float]:
    """Return (x_min, x_max, y_min, y_max) for a floorplan image."""
    return (0.0, float(width), 0.0, float(height))


def can_render_heatmap(point_count: int) -> bool:
    return point_count >= MIN_HEATMAP_POINTS


@dataclass
class HeatmapConfig:
    method: str = "cubic"
    grid_res: int = 300
    smoothing_sigma: float = 1.0
    colormap: str = "RdYlGn"
    show_dead_zones: bool = True
    show_colorbar: bool = True
    show_points: bool = True
    dead_zone_threshold: float = -80.0
    contour_levels: int = 15
    heatmap_alpha: float = 0.6


def render_inline_heatmap_layer(
    ax,
    xi: np.ndarray,
    yi: np.ndarray,
    zi: np.ndarray,
    config: HeatmapConfig,
    alpha: Optional[float] = None,
) -> None:
    """Draw heatmap contours on an existing axes (no colorbar/title)."""
    zi_masked = np.ma.masked_invalid(zi)
    cmap = plt.get_cmap(config.colormap)
    heat_alpha = config.heatmap_alpha if alpha is None else alpha
    ax.contourf(
        xi,
        yi,
        zi_masked,
        levels=config.contour_levels,
        cmap=cmap,
        alpha=heat_alpha,
        zorder=2,
    )

    if config.show_dead_zones:
        dead_zone_mask = zi < config.dead_zone_threshold
        ax.contourf(
            xi,
            yi,
            dead_zone_mask,
            levels=[0.5, 1.5],
            colors=["red"],
            alpha=0.25,
            zorder=3,
        )


def _nearest_neighbor_grid(
    x_coords: Sequence[float],
    y_coords: Sequence[float],
    z_values: np.ndarray,
    xi: np.ndarray,
    yi: np.ndarray,
) -> np.ndarray:
    zi = np.full_like(xi, np.nan, dtype=float)
    x_arr = np.array(x_coords)
    y_arr = np.array(y_coords)

    for i in range(xi.shape[0]):
        for j in range(xi.shape[1]):
            dists = (x_arr - xi[i, j]) ** 2 + (y_arr - yi[i, j]) ** 2
            idx = int(np.argmin(dists))
            zi[i, j] = z_values[idx]

    return zi


def interpolate_signal_grid(
    x_coords: Sequence[float],
    y_coords: Sequence[float],
    z_values: Iterable[float],
    bounds: Tuple[float, float, float, float],
    config: HeatmapConfig,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Interpolate RSSI values across a grid within the given bounds."""
    x_min, x_max, y_min, y_max = bounds
    values = np.array(list(z_values), dtype=float)

    xi = np.linspace(x_min, x_max, config.grid_res)
    yi = np.linspace(y_min, y_max, config.grid_res)
    xi, yi = np.meshgrid(xi, yi)

    if griddata is not None:
        zi = griddata((x_coords, y_coords), values, (xi, yi), method=config.method)
    else:
        zi = _nearest_neighbor_grid(x_coords, y_coords, values, xi, yi)

    if gaussian_filter is not None and config.smoothing_sigma > 0:
        zi = gaussian_filter(zi, sigma=config.smoothing_sigma)

    return xi, yi, zi


def render_heatmap_on_axes(
    ax,
    image: Optional[np.ndarray],
    xi: np.ndarray,
    yi: np.ndarray,
    zi: np.ndarray,
    x_coords: Sequence[float],
    y_coords: Sequence[float],
    z_values: np.ndarray,
    config: HeatmapConfig,
    title: str,
) -> None:
    if image is not None:
        ax.imshow(image, extent=[0, image.shape[1], image.shape[0], 0])

    zi_masked = np.ma.masked_invalid(zi)
    cmap = plt.get_cmap(config.colormap)
    contour = ax.contourf(
        xi,
        yi,
        zi_masked,
        levels=config.contour_levels,
        cmap=cmap,
        alpha=config.heatmap_alpha,
    )

    if config.show_dead_zones:
        dead_zone_mask = zi < config.dead_zone_threshold
        ax.contourf(xi, yi, dead_zone_mask, levels=[0.5, 1.5], colors=["red"], alpha=0.3)

    if config.show_colorbar:
        plt.colorbar(contour, ax=ax, label="Signal Strength (dBm)")

    if config.show_points:
        ax.scatter(
            x_coords,
            y_coords,
            c=z_values,
            cmap=cmap,
            s=50,
            edgecolors="black",
            linewidths=1.5,
            zorder=10,
        )

    ax.set_title(title)
    ax.axis("off")


def create_heatmap_figure(
    image: Optional[np.ndarray],
    x_coords: Sequence[float],
    y_coords: Sequence[float],
    z_values: Iterable[float],
    config: HeatmapConfig,
    title: str,
    bounds: Optional[Tuple[float, float, float, float]] = None,
) -> Figure:
    values = np.array(list(z_values), dtype=float)

    if bounds is None:
        bounds = (min(x_coords), max(x_coords), min(y_coords), max(y_coords))

    xi, yi, zi = interpolate_signal_grid(x_coords, y_coords, values, bounds, config)

    fig, ax = plt.subplots(figsize=(12, 10))
    render_heatmap_on_axes(
        ax,
        image,
        xi,
        yi,
        zi,
        x_coords,
        y_coords,
        values,
        config,
        title,
    )
    fig.tight_layout()
    return fig
