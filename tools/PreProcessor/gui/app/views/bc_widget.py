from __future__ import annotations
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QComboBox, QLineEdit, QLabel
from PyQt6.QtCore import pyqtSignal
from app.utils import COMBO_STYLE, LINEEDIT_STYLE, BC_COLORS, DEFAULT_BC_COLOR

class BCWidget(QWidget):
    """
    A unified boundary condition selector widget.
    Dropdown list for Wall, Inlet, Outlet, Farfield, Symmetry.
    Includes a 'Custom' option which reveals a text field to input custom BC names.
    Includes a colored indicator square corresponding to the selected boundary condition.
    """
    textChanged = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(4)

        self.combo = QComboBox()
        self.combo.addItems(["Wall", "Inlet", "Outlet", "Farfield", "Symmetry", "Custom"])
        self.combo.setStyleSheet(COMBO_STYLE)

        self.custom = QLineEdit()
        self.custom.setStyleSheet(LINEEDIT_STYLE)
        self.custom.setPlaceholderText("Enter custom BC...")
        self.custom.setVisible(False)

        self.indicator = QLabel()
        self.indicator.setFixedSize(16, 16)
        self.indicator.setStyleSheet("background-color: #9ca3af; border-radius: 4px; border: 1px solid #333852;")

        self.layout.addWidget(self.combo)
        self.layout.addWidget(self.custom)
        self.layout.addWidget(self.indicator)

        self.combo.currentTextChanged.connect(self._on_combo_changed)
        self.custom.textChanged.connect(self._on_custom_changed)

        self._update_indicator()

    def _on_combo_changed(self, text: str):
        is_custom = (text == "Custom")
        self.custom.setVisible(is_custom)
        if is_custom:
            self.custom.setFocus()
        self._update_indicator()
        self.textChanged.emit(self.text())

    def _on_custom_changed(self, text: str):
        self._update_indicator()
        self.textChanged.emit(self.text())

    def text(self) -> str:
        t = self.combo.currentText()
        if t == "Custom":
            return self.custom.text().strip()
        return t.lower()

    def setText(self, val: str):
        val_clean = val.strip()
        val_lower = val_clean.lower()
        standards = ["wall", "inlet", "outlet", "farfield", "symmetry"]
        self.combo.blockSignals(True)
        self.custom.blockSignals(True)
        try:
            if val_lower in standards:
                idx = standards.index(val_lower)
                self.combo.setCurrentIndex(idx)
                self.custom.setVisible(False)
                self.custom.clear()
            else:
                self.combo.setCurrentText("Custom")
                self.custom.setText(val_clean)
                self.custom.setVisible(True)
            self._update_indicator()
        finally:
            self.combo.blockSignals(False)
            self.custom.blockSignals(False)
        self.textChanged.emit(self.text())

    def _update_indicator(self):
        val = self.text().lower()
        color = BC_COLORS.get(val, DEFAULT_BC_COLOR)
        self.indicator.setStyleSheet(
            f"background-color: {color}; border-radius: 4px; border: 1px solid #333852;"
        )
