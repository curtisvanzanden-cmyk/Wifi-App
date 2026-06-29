"""Signal strength colors and map legend."""

from __future__ import annotations

from matplotlib.patches import Rectangle

# (label, min_dbm inclusive, color)
SIGNAL_BANDS = (
    ("Excellent (> -60)", -60, "#22c55e"),
    ("Good (-60 to -70)", -70, "#eab308"),
    ("Fair (-70 to -80)", -80, "#f97316"),
    ("Poor (< -80)", -90, "#ef4444"),
)

MIN_HEATMAP_POINTS = 3


def rssi_to_color(rssi: float) -> str:
    if rssi > -60:
        return "#22c55e"
    if rssi > -70:
        return "#eab308"
    if rssi > -80:
        return "#f97316"
    return "#ef4444"


def draw_signal_legend(ax) -> None:
    lines = ["Signal strength (dBm):"]
    for label, _, _color in SIGNAL_BANDS:
        lines.append(f"  {label}")

    ax.text(
        0.02,
        0.02,
        "\n".join(lines),
        transform=ax.transAxes,
        fontsize=8,
        va="bottom",
        ha="left",
        bbox=dict(facecolor="white", alpha=0.85, edgecolor="#cccccc", pad=4),
        zorder=20,
    )

    y = 0.14
    for _label, _threshold, color in reversed(SIGNAL_BANDS):
        ax.add_patch(
            Rectangle(
                (0.025, y),
                0.02,
                0.02,
                transform=ax.transAxes,
                facecolor=color,
                edgecolor="black",
                linewidth=0.5,
                zorder=21,
            )
        )
        y -= 0.03
