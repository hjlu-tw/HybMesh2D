"""Ask what unit an imported geometry file's coordinates are in.

This is the one place a unit legitimately *converts* coordinates, and it exists because
a ``.dat`` or ``.stl`` carries no unit — the number 4500 could be millimetres or metres,
and choosing wrong is the classic 1000x CFD blunder that produces a mesh looking
entirely correct.

Three deliberate choices:

* **The default is "same as the model", i.e. no conversion.** Import is a high-traffic
  action; defaulting to a conversion would make an unread dialog destructive. Dismissing
  it must leave the data exactly as it is on disk.
* **Asked once per import action, not per file.** A multi-select import of an assembly's
  parts is one decision, and asking six times trains people to click through it.
* **Headless returns "no conversion" without showing anything**, like every other dialog
  in this GUI (see ``app/utils``): the CLI and pipeline paths import by path and must
  never block on a modal.
"""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QLabel, QVBoxLayout,
)

from app.services import units
from app.utils import COMBO_STYLE, is_headless

#: Sentinel for "the file is already in the model's unit" — distinct from picking the
#: model's unit by name, because it stays correct if the model unit changes later.
SAME_AS_MODEL = ""


class ImportUnitDialog(QDialog):
    """Modal asking for the incoming file's unit. ``chosen()`` is a unit code or ""."""

    def __init__(self, model_unit: str, n_files: int = 1, model_metres: float = 1.0,
                 model_name: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Import Units")
        self.setStyleSheet("background:#121422; color:#cdd6f4;")
        self.setMinimumWidth(380)
        self._model_unit = model_unit
        self._model_metres = model_metres
        self._model_name = model_name

        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(8)

        what = "file's" if n_files == 1 else f"{n_files} files'"
        head = QLabel(f"What unit are the {what} coordinates in?")
        head.setWordWrap(True)
        lay.addWidget(head)

        self.combo = QComboBox()
        self.combo.setStyleSheet(COMBO_STYLE)
        model_sym = units.symbol(model_unit, model_name)
        self.combo.addItem(f"Same as the model ({model_sym}) — no conversion",
                           SAME_AS_MODEL)
        for code in units.unit_codes():
            if code == units.CUSTOM:
                continue
            self.combo.addItem(f"{units.symbol(code)} — {units.name(code)}", code)
        lay.addWidget(self.combo)

        self._note = QLabel("")
        self._note.setWordWrap(True)
        self._note.setStyleSheet("color:#8a93ad; font-size:10px;")
        lay.addWidget(self._note)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)

        self.combo.currentIndexChanged.connect(self._update_note)
        self._update_note()

    # ── behaviour ────────────────────────────────────────────────────────
    def chosen(self) -> str:
        return self.combo.currentData() or SAME_AS_MODEL

    def scale_factor(self) -> float:
        """Multiplier applied to the imported coordinates (1.0 = untouched)."""
        code = self.chosen()
        if not code:
            return 1.0
        return units.scale_factor(code, self._model_unit, 1.0, self._model_metres)

    def _update_note(self):
        """Say what will happen, in numbers.

        "Coordinates will be multiplied by 0.001" is checkable; "units will be
        converted" is not, and this is a destructive-by-design operation.
        """
        f = self.scale_factor()
        if f == 1.0:
            self._note.setText("Coordinates are imported exactly as stored.")
            return
        model_sym = units.symbol(self._model_unit, self._model_name)
        self._note.setText(
            f"Coordinates will be multiplied by {f:.10g} to reach the model unit "
            f"({model_sym}). The file on disk is not modified.")


def ask_import_unit(parent, model_unit: str, n_files: int = 1,
                    model_metres: float = 1.0, model_name: str = "") -> float | None:
    """Return the scale factor for an import, or None if the user cancelled.

    ``1.0`` means "no conversion", which is also what a headless run gets without a
    dialog ever being constructed.
    """
    if is_headless():
        return 1.0
    dlg = ImportUnitDialog(model_unit, n_files, model_metres, model_name, parent)
    if dlg.exec() != QDialog.DialogCode.Accepted:
        return None
    return dlg.scale_factor()
