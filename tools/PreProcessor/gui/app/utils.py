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

# Common styles
COMBO_STYLE = """
    QComboBox {
        background: #181b2a;
        color: #a0a8c0;
        border: 1px solid #333852;
        border-radius: 3px;
        padding: 3px 20px 3px 6px;
        min-width: 80px;
    }
    QComboBox::drop-down {
        subcontrol-origin: padding;
        subcontrol-position: top right;
        width: 20px;
        border-left-width: 1px;
        border-left-color: #333852;
        border-left-style: solid;
    }
    QComboBox::down-arrow {
        image: url("data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxMCIgaGVpZ2h0PSIxMCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9IiNhMGE4YzAiIHN0cm9rZS13aWR0aD0iMyIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIiBzdHJva2UtbGluZWpvaW49InJvdW5kIj48cG9seWxpbmUgcG9pbnRzPSI2IDkgMTIgMTUgMTggOSI+PC9wb2x5bGluZT48L3N2Zz4=");
    }
"""

SPIN_STYLE = "background:#181b2a; color:#a0a8c0; border:1px solid #333852; padding: 2px; max-width: 110px;"

def make_button(text: str, color: str = '#26293c') -> QPushButton:
    b = QPushButton(text)
    b.setStyleSheet(
        f"QPushButton {{"
        f"  background-color: {color}; color: #dde6ff;"
        f"  border: 1px solid #4a5070; border-radius: 4px;"
        f"  padding: 6px 10px; font-weight: bold;"
        f"}}"
        f"QPushButton:hover {{ background-color: #32364e; }}"
        f"QPushButton:disabled {{ background-color: #171926; color: #555; }}")
    return b

def align_form_labels(layout: QFormLayout, width: int = 120):
    layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
    for i in range(layout.rowCount()):
        label_item = layout.itemAt(i, QFormLayout.ItemRole.LabelRole)
        if label_item:
            lbl = label_item.widget()
            if lbl:
                lbl.setFixedWidth(width)

