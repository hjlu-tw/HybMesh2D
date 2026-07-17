"""Widget-factory helpers shared by SolverConfigPanel and its mixins (behaviour
unchanged). These are the module-level `_spin` / `_ispin` / `_edit` / `_check`
/ `_combo` constructors and `_parse_float`, extracted verbatim so both the panel
and solver_config_build_mixin can import them without a circular dependency."""
from __future__ import annotations
from PyQt6.QtWidgets import QComboBox, QSpinBox, QLineEdit, QCheckBox
from PyQt6.QtGui import QPalette, QColor

from app.utils import COMBO_STYLE, SPIN_STYLE, LINEEDIT_STYLE
from app.views.clean_double_spin_box import CleanDoubleSpinBox


def _spin(decimals: int, lo: float, hi: float, tip: str) -> CleanDoubleSpinBox:
    s = CleanDoubleSpinBox()
    s.setRange(lo, hi)
    s.setDecimals(decimals)
    s.setStyleSheet(SPIN_STYLE)
    s.setToolTip(tip)
    return s


def _ispin(lo: int, hi: int, tip: str) -> QSpinBox:
    s = QSpinBox()
    s.setRange(lo, hi)
    s.setStyleSheet(SPIN_STYLE)
    s.setToolTip(tip)
    return s


def _edit(tip: str, placeholder: str = "") -> QLineEdit:
    e = QLineEdit()
    e.setStyleSheet(LINEEDIT_STYLE)
    e.setToolTip(tip)
    if placeholder:
        e.setPlaceholderText(placeholder)
        # LINEEDIT_STYLE pins an explicit text colour, so the placeholder would
        # otherwise render like a real value. Force a dim tone via the palette so
        # it reads as a format hint (#6).
        pal = e.palette()
        pal.setColor(QPalette.ColorRole.PlaceholderText, QColor("#5a6480"))
        e.setPalette(pal)
    return e


def _check(text: str, tip: str) -> QCheckBox:
    c = QCheckBox(text)
    c.setStyleSheet("color:#a0a8c0;")
    c.setToolTip(tip)
    return c


def _combo(items: list[str], tip: str) -> QComboBox:
    c = QComboBox()
    c.addItems(items)
    c.setStyleSheet(COMBO_STYLE)
    c.setToolTip(tip)
    return c


def _parse_float(text: str, fallback: float) -> float:
    try:
        return float(text.strip())
    except (ValueError, AttributeError):
        return fallback
