import os
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                             QLineEdit, QPushButton, QFileDialog)
from PyQt6.QtCore import Qt


class OutputDialog(QDialog):
    """Dialog to confirm the output file path before running the backend."""

    def __init__(self, default_path: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Save Resampled Output")
        self.setMinimumWidth(520)
        self.setModal(True)
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        self.setStyleSheet("background: #121422; color: #a0a8c0;")

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        # Description
        desc = QLabel(
            "The resampled geometry will be written to the file below.\n"
            "You can change the path or keep the suggested default.")
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #8892b0;")
        layout.addWidget(desc)

        # Path input row
        path_lbl = QLabel("Output File:")
        path_lbl.setStyleSheet("font-weight: bold;")
        layout.addWidget(path_lbl)

        path_row = QHBoxLayout()
        self.path_edit = QLineEdit(default_path)
        self.path_edit.setPlaceholderText("Select output file path…")
        self.path_edit.setStyleSheet(
            "background: #181b2a; color: #a0a8c0; border: 1px solid #333852; padding: 4px;")
        browse_btn = QPushButton("...")
        browse_btn.setFixedWidth(38)
        browse_btn.setStyleSheet(
            "background-color: #26293c; color: #dde6ff; border: 1px solid #4a5070; border-radius: 4px; padding: 4px;")
        browse_btn.setToolTip("Browse…")
        browse_btn.clicked.connect(self._browse)
        path_row.addWidget(self.path_edit)
        path_row.addWidget(browse_btn)
        layout.addLayout(path_row)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedWidth(90)
        cancel_btn.setStyleSheet(
            "background-color: #26293c; color: #dde6ff; border: 1px solid #4a5070; border-radius: 4px; padding: 6px;")
        cancel_btn.clicked.connect(self.reject)

        self.ok_btn = QPushButton("Save && Run")
        self.ok_btn.setDefault(True)
        self.ok_btn.setStyleSheet(
            "background-color: #388e3c; color: white; font-weight: bold;"
            " padding: 6px 18px; border-radius: 4px;")
        self.ok_btn.clicked.connect(self.accept)

        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(self.ok_btn)
        layout.addLayout(btn_row)

    # ── Helpers ───────────────────────────────────────────────────────────

    def _browse(self):
        current = self.path_edit.text()
        start_dir = os.path.dirname(current) if current else ""
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Output File", start_dir, "Data Files (*.dat)")
        if path:
            self.path_edit.setText(path)

    @property
    def output_path(self) -> str:
        return self.path_edit.text()
