from __future__ import annotations
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel
from app.utils import SPIN_STYLE


class EdgePropsShapesMixin:
    def _xy_row(self, sx, sy) -> QWidget:
        """Pack two coordinate spinboxes into one [x: <sx>  y: <sy>] row so point
        coordinates read as points instead of one field per line."""
        compact = SPIN_STYLE.replace("max-width: 110px", "max-width: 72px")
        box = QWidget(); h = QHBoxLayout(box)
        h.setContentsMargins(0, 0, 0, 0); h.setSpacing(3)
        for lab, s in (("x", sx), ("y", sy)):
            s.setStyleSheet(compact)
            t = QLabel(lab); t.setStyleSheet("color:#7a82a0; font-size:10px;")
            h.addWidget(t); h.addWidget(s)
        h.addStretch()
        return box
