"""Enter probe-point coordinates in the GUI and auto-generate the probe file
that the solver reads (one 'x y' per line for 2D). #10.

Kept deliberately small: a monospace text box (so paste/edit is trivial) with
live validation + a point count. The controller writes the validated points to
a file and points the solver config's probe field at it."""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QPlainTextEdit, QDialogButtonBox,
)
from PyQt6.QtGui import QFont


def parse_probe_points(text: str) -> list[tuple[float, float]]:
    """Parse 'x y' lines into (x, y) tuples. Blank lines and '#' comments are
    ignored; a line that does not hold two finite floats is skipped."""
    import math
    pts: list[tuple[float, float]] = []
    for line in (text or "").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        parts = s.replace(",", " ").split()
        if len(parts) < 2:
            continue
        try:
            x, y = float(parts[0]), float(parts[1])
        except ValueError:
            continue
        if math.isfinite(x) and math.isfinite(y):
            pts.append((x, y))
    return pts


class ProbePointsDialog(QDialog):
    """Multi-line coordinate entry; ``points()`` returns the validated list."""

    def __init__(self, parent=None, initial_text: str = ""):
        super().__init__(parent)
        self.setWindowTitle("Probe points — enter coordinates")
        self.setStyleSheet("background:#121422; color:#cdd6f4;")
        self.resize(360, 420)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.setSpacing(6)
        hint = QLabel(
            "Enter one probe point per line as 'x y' (2D). Commas are allowed "
            "(x, y); blank lines and '#' comments are ignored. On OK the file is "
            "generated and linked into the solver config automatically.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#8a93ad; font-size:10px;")
        outer.addWidget(hint)

        self.edit = QPlainTextEdit(initial_text)
        self.edit.setFont(QFont("Menlo", 11))
        self.edit.setStyleSheet(
            "QPlainTextEdit{background:#181b2a; color:#d6dcf0; border:1px solid "
            "#333852; border-radius:3px;}")
        self.edit.setPlaceholderText("0.0 0.0\n1.5 0.25\n-0.5 1.0")
        outer.addWidget(self.edit, stretch=1)

        self.count_lbl = QLabel("")
        self.count_lbl.setStyleSheet("color:#8a93ad; font-size:10px;")
        outer.addWidget(self.count_lbl)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        outer.addWidget(self.buttons)

        self.edit.textChanged.connect(self._update_count)
        self._update_count()

    def _update_count(self):
        n = len(self.points())
        self.count_lbl.setText(f"{n} valid probe point(s)")
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(n > 0)

    def points(self) -> list[tuple[float, float]]:
        return parse_probe_points(self.edit.toPlainText())

    def as_file_text(self) -> str:
        """Canonical probe-file contents: one 'x y' per line."""
        return "".join(f"{x:.10g} {y:.10g}\n" for x, y in self.points())
