from __future__ import annotations
from contextlib import contextmanager
from PyQt6.QtCore import QObject

@contextmanager
def block_signals(*widgets: QObject):
    """Context manager to block signals of multiple Qt widgets temporarily."""
    for w in widgets:
        if w is not None:
            w.blockSignals(True)
    try:
        yield
    finally:
        for w in widgets:
            if w is not None:
                w.blockSignals(False)
from PyQt6.QtWidgets import QPushButton, QFormLayout
from PyQt6.QtCore import Qt

# Curve type labels mapping
CURVE_TYPE_LABELS = {
    "custom": lambda seg: f"Curve ({'Param' if seg.curve_mode == 'parametric' else 'Explicit'})",
    "horizontal_line": "H Line",
    "vertical_line": "V Line",
    "line": "Line",
    "circle": "Circle",
    "triangle": "Triangle",
    "quadrilateral": "Quad",
    "polygon": "Polygon",
}

from app.styles import COMBO_STYLE, SPIN_STYLE, BUTTON_QSS_TEMPLATE

def make_button(text: str, color: str = '#26293c') -> QPushButton:
    b = QPushButton(text)
    b.setStyleSheet(BUTTON_QSS_TEMPLATE.format(color=color))
    return b

def align_form_labels(layout: QFormLayout, width: int = 120):
    layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
    for i in range(layout.rowCount()):
        label_item = layout.itemAt(i, QFormLayout.ItemRole.LabelRole)
        if label_item:
            lbl = label_item.widget()
            if lbl:
                lbl.setFixedWidth(width)

import os
import shutil

def find_binary_executable(bin_name: str) -> str | None:
    """Locate binary executable in PATH environment or local build candidates."""
    path_run = shutil.which(bin_name)
    if path_run:
        return path_run

    base_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.abspath(os.path.join(base_dir, "../../../../../build")),
        os.path.abspath("../../../build"),
        os.path.abspath("./build"),
        os.path.abspath("."),
    ]
    for folder in candidates:
        full_path = os.path.join(folder, bin_name)
        if os.path.exists(full_path) and os.access(full_path, os.X_OK) and not os.path.isdir(full_path):
            return full_path
    return None

