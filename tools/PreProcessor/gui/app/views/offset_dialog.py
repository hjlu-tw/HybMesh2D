"""Ask for the distance and the side of a derived offset geometry (#152).

The dialog collects two things and decides nothing: the magnitude and the side
are combined into ONE signed distance here, and every rule about what that sign
MEANS belongs to `app/services/geometry_offset.py`. The side labels change with
the source's closure because "outward" is only a statement about a closed
outline — an open polyline has no inside, so what the user is choosing there is a
hand, not a direction out of something.

The distance is a physical length, so it is a `SciDoubleSpinBox`: a boundary-layer
seam on a chord-normalised geometry is routinely 1e-3..1e-5, which a plain
`QDoubleSpinBox` with `decimals(3)` would silently clamp.
"""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QComboBox, QDialog, QFormLayout, QHBoxLayout, QLabel, QVBoxLayout,
)

from app.utils import make_button
from app.views.clean_double_spin_box import SciDoubleSpinBox


class OffsetGeometryDialog(QDialog):
    """Collect (magnitude, side) for one offset and hand back a signed distance."""

    def __init__(self, source_name: str, closed: bool, unit: str = "",
                 suggested: float = 0.0, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Offset Geometry")
        self.setStyleSheet("QDialog{background:#141826;}")
        self.setMinimumWidth(360)
        self._closed = bool(closed)

        v = QVBoxLayout(self)
        v.setContentsMargins(12, 12, 12, 12)
        v.setSpacing(8)
        hint = QLabel(
            "A new geometry whose points are '%s' moved along the local normal. "
            "It arrives segmented exactly as its source and remembers where it "
            "came from, so it can be regenerated when the source changes."
            % source_name)
        hint.setStyleSheet("color:#a0a8c0; font-size:11px;")
        hint.setWordWrap(True)
        v.addWidget(hint)

        form = QFormLayout()
        form.setSpacing(6)
        self.distance = SciDoubleSpinBox()
        self.distance.setRange(0.0, 1e12)
        self.distance.setValue(float(suggested) if suggested > 0 else 0.0)
        form.addRow("Distance%s:" % (" (%s)" % unit if unit else ""), self.distance)

        self.side = QComboBox()
        if self._closed:
            self.side.addItem("Outward (away from the body)", 1.0)
            self.side.addItem("Inward (into the body)", -1.0)
        else:
            # An open polyline has no inside. The hand is stated in the words the
            # service states it in, so the two cannot drift apart.
            self.side.addItem("Right of travel (+)", 1.0)
            self.side.addItem("Left of travel (-)", -1.0)
        form.addRow("Side:", self.side)
        v.addLayout(form)

        row = QHBoxLayout()
        row.addStretch(1)
        cancel = make_button("Cancel", "#301a1a")
        ok = make_button("Create Offset", "#1e2a38")
        cancel.clicked.connect(self.reject)
        ok.clicked.connect(self.accept)
        row.addWidget(cancel)
        row.addWidget(ok)
        v.addLayout(row)

    def signed_distance(self) -> float:
        """The magnitude and the side as the one number the service takes."""
        return float(self.distance.value()) * float(self.side.currentData())
