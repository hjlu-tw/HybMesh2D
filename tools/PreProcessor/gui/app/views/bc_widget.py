from __future__ import annotations
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QComboBox, QLineEdit, QLabel,
    QStyledItemDelegate, QStyleOptionViewItem
)
from PyQt6.QtCore import pyqtSignal, Qt, QSize
from PyQt6.QtGui import QColor, QFont
from app.utils import COMBO_STYLE, LINEEDIT_STYLE, BC_COLORS, DEFAULT_BC_COLOR

# BC type definitions: (display_name, technical_name, config_value)
# config_value is what gets written to the config file / returned by text()
BC_TYPE_DEFS = [
    ("inlet",       "FIXED_BC",             "inlet"),
    ("outlet",      "NON_REFLECT_BC",        "outlet"),
    ("WALL",        "NO_SLIP_BC_ADIAW",      "wall"),
    ("SYMP",        "REFLECT_BC",            "symmetry"),
    ("isothermal",  "NO_SLIP_BC_ACONTW",     "isothermal"),
    ("FREE",        "FIXED_BC",              "free"),
    ("Custom",      "",                      "custom"),
]


class _BCTypeDelegate(QStyledItemDelegate):
    """Custom delegate that renders BC items with a bold display name and
    a smaller, muted technical name on the same line."""

    def sizeHint(self, option: QStyleOptionViewItem, index) -> QSize:
        return QSize(0, 30)

    def paint(self, painter, option, index):
        from PyQt6.QtWidgets import QStyle, QApplication
        # Draw the background (selection / hover)
        style = QApplication.style()
        style.drawPrimitive(QStyle.PrimitiveElement.PE_PanelItemViewItem, option, painter)

        display_name = index.data(Qt.ItemDataRole.DisplayRole) or ""
        tech_name = index.data(Qt.ItemDataRole.UserRole) or ""

        rect = option.rect
        is_selected = bool(option.state & QStyle.StateFlag.State_Selected)
        text_color = QColor("#ffffff") if is_selected else QColor("#c8d0e8")
        tech_color = QColor("#cccccc") if is_selected else QColor("#606880")

        x = rect.left() + 8
        y_mid = rect.top() + rect.height() // 2 + 4  # +4 to vertically center text

        # Display name (bold, normal size)
        painter.save()
        font = painter.font()
        font.setBold(True)
        font.setPointSize(9)
        painter.setFont(font)
        painter.setPen(text_color)
        painter.drawText(x, y_mid, display_name)

        # Technical name (small, muted, after display name)
        if tech_name:
            fm = painter.fontMetrics()
            name_w = fm.horizontalAdvance(display_name)
            font2 = QFont(font)
            font2.setBold(False)
            font2.setPointSize(7)
            painter.setFont(font2)
            painter.setPen(tech_color)
            painter.drawText(x + name_w + 6, y_mid, f"({tech_name})")
        painter.restore()


class BCWidget(QWidget):
    """
    A unified boundary condition selector widget.
    Dropdown list for supported BC types with technical names shown as smaller secondary text.
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
        self.combo.setStyleSheet(COMBO_STYLE)
        self.combo.setItemDelegate(_BCTypeDelegate(self.combo))
        self.combo.setMinimumWidth(90)
        self.combo.setMaximumWidth(160)

        for display_name, tech_name, _ in BC_TYPE_DEFS:
            self.combo.addItem(display_name)
            idx = self.combo.count() - 1
            self.combo.setItemData(idx, tech_name, Qt.ItemDataRole.UserRole)
            if tech_name:
                self.combo.setItemData(
                    idx,
                    f"{display_name}  —  {tech_name}",
                    Qt.ItemDataRole.ToolTipRole
                )

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
        """Return the config-file value for the selected BC type."""
        display = self.combo.currentText()
        if display == "Custom":
            return self.custom.text().strip()
        # Look up config value from definitions
        for disp, tech, config_val in BC_TYPE_DEFS:
            if disp == display:
                return config_val
        return display.lower()

    def setText(self, val: str):
        """Set the widget from a config-file value or display name."""
        val_clean = val.strip()
        val_lower = val_clean.lower()

        self.combo.blockSignals(True)
        self.custom.blockSignals(True)
        try:
            matched = False
            # Try to match by config value
            for i, (disp, tech, config_val) in enumerate(BC_TYPE_DEFS):
                if val_lower == config_val and disp != "Custom":
                    self.combo.setCurrentIndex(i)
                    self.custom.setVisible(False)
                    self.custom.clear()
                    matched = True
                    break
            if not matched:
                # Try to match by display name (case-insensitive)
                for i, (disp, tech, config_val) in enumerate(BC_TYPE_DEFS):
                    if val_lower == disp.lower() and disp != "Custom":
                        self.combo.setCurrentIndex(i)
                        self.custom.setVisible(False)
                        self.custom.clear()
                        matched = True
                        break
            if not matched:
                # Fall back to custom
                custom_idx = next(
                    (i for i, (d, _, _) in enumerate(BC_TYPE_DEFS) if d == "Custom"), -1
                )
                if custom_idx >= 0:
                    self.combo.setCurrentIndex(custom_idx)
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
