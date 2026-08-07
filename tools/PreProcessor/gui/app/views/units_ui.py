"""Qt side of the length-unit system: the selector widget and the suffix plumbing.

The numbers and rules live in ``app/services/units.py`` (Qt-free); this module only
puts them on screen.

**Units are shown as the spin box's own suffix, not baked into labels.** Qt strips the
suffix before parsing and appends it after formatting, so ``1.2e-07 mm`` round-trips
through :class:`SciDoubleSpinBox` untouched (verified for typed input both with and
without the unit). The alternative — rewriting every ``help_label("Domain X Min:")``
text — would mean holding a reference to a few dozen labels across five mixins purely
so they could be re-titled, and every field added later would silently miss out. The
suffix rides on the widget that owns the number, which is the thing that cannot be
forgotten.

Only fields holding a *physical length* get a suffix. Growth rates, angles, layer
counts and iteration counts are dimensionless, and stamping a unit on them would be a
lie that looks authoritative.
"""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QLineEdit, QWidget,
)
from PyQt6.QtCore import pyqtSignal

from app.services import units
from app.utils import COMBO_STYLE, SPIN_STYLE, block_signals
from app.views.clean_double_spin_box import SciDoubleSpinBox


def apply_unit_suffix(widgets, unit: str, custom_name: str = "") -> None:
    """Show ``unit`` inside each spin box in ``widgets``.

    Missing/None entries are skipped so a caller can pass a list built from
    ``getattr(panel, name, None)`` without pre-filtering — panels are assembled from
    mixins and not every field exists in every configuration.
    """
    sym = units.symbol(unit, custom_name)
    for w in widgets:
        if w is None or not hasattr(w, "setSuffix"):
            continue
        w.setSuffix(f" {sym}")


def clear_unit_suffix(widgets) -> None:
    for w in widgets:
        if w is not None and hasattr(w, "setSuffix"):
            w.setSuffix("")


class UnitSelector(QWidget):
    """Unit combo, plus the factor/name fields a custom unit needs.

    ``unit_changed`` carries ``(code, metres_per_unit, name)`` — the factor is emitted
    rather than looked up by the receiver, so no call site has to know that ``custom``
    is special.
    """

    unit_changed = pyqtSignal(str, float, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)

        self.combo = QComboBox()
        self.combo.setStyleSheet(COMBO_STYLE)
        for code in units.unit_codes():
            if code == units.CUSTOM:
                self.combo.addItem("Custom…", code)
            else:
                self.combo.addItem(
                    f"{units.symbol(code)} — {units.name(code)}", code)
        self.combo.setToolTip(
            "The unit every length in this project is expressed in: domain bounds, "
            "mesh sizes, BL thickness, resampling spacings.\n\n"
            "Changing it does NOT rescale anything — it relabels. To convert an "
            "existing geometry, re-import it and state the file's unit, or use "
            "Transform ▸ Scale.\n\n"
            "It reaches the solver as Linf (metres per grid unit): Re = fs_UnitRe × "
            "Linf, so this is what keeps a millimetre mesh from running at 1000× the "
            "intended Reynolds number.")
        row.addWidget(self.combo, 1)

        # Custom unit: how many metres one unit is, and what to call it. Shown only
        # for "Custom…" — a factor box that is meaningless for mm is worse than absent.
        self._custom_lbl = QLabel("=")
        self._custom_lbl.setStyleSheet("color:#8a93ad;")
        self.metres = SciDoubleSpinBox()
        self.metres.setRange(0.0, 1e9)
        self.metres.setValue(1.0)
        self.metres.setSuffix(" m")
        self.metres.setStyleSheet(SPIN_STYLE)
        self.metres.setToolTip(
            "Metres in one model unit — this is Linf.\n"
            "A unit-chord aerofoil grid running 0…1 with a 25.4 mm chord is 0.0254.")
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("name")
        self.name_edit.setMaximumWidth(70)
        self.name_edit.setStyleSheet(
            "background:#0c0d16; color:#a0a8c0; border:1px solid #2c2e43; padding:2px;")
        self.name_edit.setToolTip("What to call this unit in labels, e.g. 'chord'")
        for w in (self._custom_lbl, self.metres, self.name_edit):
            row.addWidget(w)

        self.combo.currentIndexChanged.connect(self._emit)
        self.metres.valueChanged.connect(self._emit)
        self.name_edit.editingFinished.connect(self._emit)
        self._update_custom_visibility()

    # ── state ────────────────────────────────────────────────────────────
    def unit(self) -> str:
        return self.combo.currentData() or units.DEFAULT_UNIT

    def custom_metres(self) -> float:
        return float(self.metres.value())

    def custom_name(self) -> str:
        return self.name_edit.text().strip()

    def metres_per_unit(self) -> float:
        return units.metres_per_unit(self.unit(), self.custom_metres())

    def set_unit(self, unit: str, custom_metres: float = 1.0,
                 custom_name: str = "") -> None:
        """Populate without emitting — this is a programmatic push, not a user edit.

        Same reason ``controller.push_panel_config`` exists: an unguarded set here
        would be recorded as an undoable user change and would mark the project dirty
        on load.
        """
        code = units.parse(unit, units.DEFAULT_UNIT)
        idx = self.combo.findData(code)
        with block_signals(self.combo, self.metres, self.name_edit):
            if idx >= 0:
                self.combo.setCurrentIndex(idx)
            if custom_metres and custom_metres > 0:
                self.metres.setValue(float(custom_metres))
            self.name_edit.setText(custom_name or "")
        self._update_custom_visibility()

    # ── internals ────────────────────────────────────────────────────────
    def _update_custom_visibility(self) -> None:
        show = self.unit() == units.CUSTOM
        for w in (self._custom_lbl, self.metres, self.name_edit):
            w.setVisible(show)

    def _emit(self, *_a) -> None:
        self._update_custom_visibility()
        self.unit_changed.emit(self.unit(), self.metres_per_unit(),
                               self.custom_name())
