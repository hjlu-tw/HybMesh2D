from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QToolButton, QSizePolicy,
                             QFrame)
from PyQt6.QtCore import Qt


class CollapsibleSection(QWidget):
    """
    A collapsible panel with a clickable header and animated content area.
    Usage:
        section = CollapsibleSection("My Section")
        section.add_widget(some_widget)
        section.add_layout(some_layout)
    """

    def __init__(self, title: str, parent=None, start_collapsed: bool = False):
        super().__init__(parent)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 2, 0, 2)
        main_layout.setSpacing(0)

        # ── Header toggle button ──────────────────────────────────────────
        self.toggle_btn = QToolButton()
        self.toggle_btn.setCheckable(True)
        self.toggle_btn.setChecked(not start_collapsed)
        self.toggle_btn.setText(f"  {title}")
        self.toggle_btn.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.toggle_btn.setArrowType(
            Qt.ArrowType.DownArrow if not start_collapsed
            else Qt.ArrowType.RightArrow)
        self.toggle_btn.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.toggle_btn.setStyleSheet("""
            QToolButton {
                background-color: #1e2035;
                color: #c0c8e0;
                border: 1px solid #3a4060;
                border-radius: 4px;
                padding: 5px 6px;
                font-weight: bold;
                font-size: 12px;
                text-align: left;
            }
            QToolButton:checked {
                background-color: #161828;
                border-color: #2e3250;
            }
            QToolButton:hover {
                background-color: #282b48;
            }
        """)

        # ── Content frame ─────────────────────────────────────────────────
        self.content_frame = QFrame()
        self.content_frame.setFrameShape(QFrame.Shape.NoFrame)
        self.content_layout = QVBoxLayout(self.content_frame)
        self.content_layout.setContentsMargins(8, 4, 4, 6)
        self.content_layout.setSpacing(4)

        if start_collapsed:
            self.content_frame.setVisible(False)

        main_layout.addWidget(self.toggle_btn)
        main_layout.addWidget(self.content_frame)

        self.toggle_btn.clicked.connect(self._on_toggle)

    # ── Public helpers ────────────────────────────────────────────────────

    def add_widget(self, widget: QWidget):
        self.content_layout.addWidget(widget)

    def add_layout(self, layout):
        self.content_layout.addLayout(layout)

    def get_content_layout(self):
        return self.content_layout

    def expand(self):
        self.toggle_btn.setChecked(True)
        self._on_toggle(True)

    def collapse(self):
        self.toggle_btn.setChecked(False)
        self._on_toggle(False)

    @property
    def is_expanded(self) -> bool:
        return self.toggle_btn.isChecked()

    # ── Internal ──────────────────────────────────────────────────────────

    def _on_toggle(self, checked: bool):
        self.content_frame.setVisible(checked)
        self.toggle_btn.setArrowType(
            Qt.ArrowType.DownArrow if checked else Qt.ArrowType.RightArrow)
