from __future__ import annotations
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QPushButton, QHBoxLayout
from PyQt6.QtCore import Qt


class SettingsDialog(QDialog):
    """Non-modal dialog hosting global geometry settings (spline smoothing and
    the output transform). The actual controls live in the passed-in panel
    widget, which keeps its identity so the controller's existing signal
    connections and the sidebar's attribute delegation continue to work."""

    def __init__(self, settings_panel, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Geometry Settings")
        self.setModal(False)
        self.setMinimumWidth(320)
        self.setStyleSheet("background: #121422; color: #a0a8c0;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # The panel is a CollapsibleSection; keep it expanded inside the dialog.
        if hasattr(settings_panel, "expand"):
            settings_panel.expand()
        layout.addWidget(settings_panel)
        layout.addStretch()

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.close_btn = QPushButton("Close")
        self.close_btn.setStyleSheet(
            "QPushButton { background:#181b30; color:#dde2ff; border:1px solid #2d3356;"
            "  border-radius:4px; padding:5px 16px; font-weight:bold; }"
            "QPushButton:hover { background:#2c3258; border-color:#5a9ad4; color:#fff; }")
        self.close_btn.clicked.connect(self.hide)
        btn_row.addWidget(self.close_btn)
        layout.addLayout(btn_row)
