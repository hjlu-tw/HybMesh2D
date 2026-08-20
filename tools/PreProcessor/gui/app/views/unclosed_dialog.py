from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                             QPushButton, QComboBox, QPlainTextEdit)
from PyQt6.QtCore import Qt


# Stitch methods, in the order shown in the combo box.
STITCH_METHODS = [
    ("midpoint", "Merge both endpoints to their midpoint"),
    ("line",     "Close with a straight line (keep both points)"),
    ("snap",     "Snap back onto the originally-connected point"),
]


class UnclosedPointsDialog(QDialog):
    """Shown on Preview when the geometry has unclosed gaps.

    Lists each gap's two endpoint coordinates and offers a stitch method (chosen
    from a list) or keeping the geometry open — instead of silently bridging the
    gap. ``choice`` ∈ {'stitch','keep_open','cancel'} and ``method`` ∈ the
    STITCH_METHODS keys are read after exec().
    """

    def __init__(self, gaps: list[dict], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Unclosed Points Detected")
        self.setMinimumWidth(540)
        self.setModal(True)
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        self.setStyleSheet("background: #121422; color: #a0a8c0;")

        self.choice = "cancel"

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        desc = QLabel(
            f"Found {len(gaps)} unclosed gap(s) in the geometry. The preview will "
            "NOT bridge them automatically. You can stitch them closed, or keep "
            "the boundary open.")
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #8892b0;")
        layout.addWidget(desc)

        pos_lbl = QLabel("Unclosed points:")
        pos_lbl.setStyleSheet("font-weight: bold;")
        layout.addWidget(pos_lbl)

        listing = QPlainTextEdit()
        listing.setReadOnly(True)
        listing.setStyleSheet(
            "background: #181b2a; color: #a0a8c0; border: 1px solid #333852; padding: 4px;")
        lines = []
        for n, g in enumerate(gaps, 1):
            p0, p1 = g["p0"], g["p1"]
            lines.append(
                f"Gap {n}:  ({p0[0]:.6g}, {p0[1]:.6g})  ↔  "
                f"({p1[0]:.6g}, {p1[1]:.6g})   gap = {g['dist']:.6g}")
        listing.setPlainText("\n".join(lines))
        listing.setFixedHeight(min(140, 28 + 18 * len(gaps)))
        layout.addWidget(listing)

        method_row = QHBoxLayout()
        method_lbl = QLabel("Stitch method:")
        method_lbl.setStyleSheet("font-weight: bold;")
        self.method_combo = QComboBox()
        self.method_combo.setStyleSheet(
            "background: #181b2a; color: #dde6ff; border: 1px solid #4a5070; padding: 4px;")
        for _key, label in STITCH_METHODS:
            self.method_combo.addItem(label)
        method_row.addWidget(method_lbl)
        method_row.addWidget(self.method_combo, 1)
        layout.addLayout(method_row)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedWidth(90)
        cancel_btn.setStyleSheet(
            "background-color: #26293c; color: #dde6ff; border: 1px solid #4a5070; border-radius: 4px; padding: 6px;")
        cancel_btn.clicked.connect(self._on_cancel)

        keep_btn = QPushButton("Keep Open")
        keep_btn.setStyleSheet(
            "background-color: #26293c; color: #dde6ff; border: 1px solid #4a5070; border-radius: 4px; padding: 6px 14px;")
        keep_btn.clicked.connect(self._on_keep_open)

        self.stitch_btn = QPushButton("Stitch")
        self.stitch_btn.setDefault(True)
        self.stitch_btn.setStyleSheet(
            "background-color: #388e3c; color: white; font-weight: bold;"
            " padding: 6px 18px; border-radius: 4px;")
        self.stitch_btn.clicked.connect(self._on_stitch)

        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(keep_btn)
        btn_row.addWidget(self.stitch_btn)
        layout.addLayout(btn_row)

    # ── Handlers ──────────────────────────────────────────────────────────
    def _on_cancel(self):
        self.choice = "cancel"
        self.reject()

    def _on_keep_open(self):
        self.choice = "keep_open"
        self.accept()

    def _on_stitch(self):
        self.choice = "stitch"
        self.accept()

    @property
    def method(self) -> str:
        return STITCH_METHODS[self.method_combo.currentIndex()][0]
