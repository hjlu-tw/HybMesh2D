"""Live metrics for the active CAD geometry.

Sits in the CAD sidebar as a collapsed section (the sidebar is a fixed 360 px, so a
new always-open block would push the edge properties off screen). Numbers come from
the Qt-free :mod:`app.services.geometry_stats`, so the same values can be logged
from a headless run.

The spacing-quality row is the one worth having: a geometry whose neighbouring
intervals jump more than ~1.2x will grow a poor boundary layer, and until now that
was only discoverable by generating a mesh and looking at the failure. It turns amber
when that happens, using the same threshold as the .dat quality heatmap so the two
never disagree.
"""
from __future__ import annotations

from PyQt6.QtWidgets import QFormLayout, QLabel, QWidget

from app.services import geometry_stats
from app.views.collapsible import CollapsibleSection

_VALUE_QSS = "color:#cdd6f4; font-family:monospace; font-size:11px;"
_WARN_QSS = "color:#e5a13a; font-family:monospace; font-size:11px;"

#: (attribute, label, tooltip) for every row, in display order.
_ROWS = (
    ("points", "Points:", "Number of points in the geometry"),
    ("edges", "Edges:", "Number of edge segments the boundary is split into"),
    ("closed", "Topology:", "Whether the boundary closes back on itself"),
    ("size", "Extent:", "Bounding-box width x height"),
    ("bbox", "Bounds:", "Bounding box as [x min, x max] x [y min, y max]"),
    ("length", "Perimeter:", "Total boundary arc length (includes the closing "
                             "edge when the geometry is closed)"),
    ("spacing", "Spacing:", "Point-to-point distance: minimum / mean / maximum"),
    ("quality", "Uniformity:", "Largest expansion ratio between neighbouring "
                               "intervals. Above 1.2x the boundary layer suffers."),
)


class GeomStatsPanel(QWidget):
    """Collapsible read-out of the active geometry's metrics."""

    def __init__(self, parent=None):
        super().__init__(parent)
        from PyQt6.QtWidgets import QVBoxLayout
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.section = CollapsibleSection("Geometry Statistics", start_collapsed=True)
        outer.addWidget(self.section)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(3)
        self._values: dict[str, QLabel] = {}
        for key, label, tip in _ROWS:
            value = QLabel("—")
            value.setStyleSheet(_VALUE_QSS)
            value.setWordWrap(True)
            value.setToolTip(tip)
            name = QLabel(label)
            name.setStyleSheet("color:#8a93ad; font-size:11px;")
            name.setToolTip(tip)
            form.addRow(name, value)
            self._values[key] = value
        self.section.add_layout(form)

    # ------------------------------------------------------------------ #
    def clear(self):
        """Show "—" everywhere (no geometry, or an empty session)."""
        self.update_stats(None)

    def update_stats(self, points, *, closed: bool = False, n_segments: int = 0):
        """Recompute and display. ``points`` may be None/empty."""
        stats = geometry_stats.compute(points, closed=closed, n_segments=n_segments)
        text = geometry_stats.fmt(stats)
        for key, value in self._values.items():
            value.setText(text.get(key, "—"))
        # Only the uniformity row changes colour: it is the only one that carries a
        # judgement rather than a measurement.
        self._values["quality"].setStyleSheet(
            _WARN_QSS if geometry_stats.is_uneven(stats) else _VALUE_QSS)
        return stats
