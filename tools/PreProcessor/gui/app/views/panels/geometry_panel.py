from __future__ import annotations
from PyQt6.QtWidgets import QListWidget
from app.views.collapsible import CollapsibleSection
from app.utils import make_button, help_widget

class GeometryPanel(CollapsibleSection):
    def __init__(self, parent=None):
        super().__init__("Geometry Entities", start_collapsed=True, parent=parent)

        self.geom_list = QListWidget()
        self.geom_list.setMaximumHeight(120)
        self.geom_list.setStyleSheet("""
            QListWidget {
                background: #181b2a;
                color: #8892b0;
                border: 1px solid #333852;
                border-radius: 4px;
            }
            QListWidget::item {
                padding: 4px;
            }
            QListWidget::item:selected {
                background: #2e3e70;
                color: #ffffff;
                font-weight: bold;
            }
            QListWidget::item:hover {
                background: #20243c;
                color: #dde6ff;
            }
            QListWidget::indicator {
                width: 14px;
                height: 14px;
                border: 1px solid #4f5b8c;
                border-radius: 3px;
                background-color: #181b2a;
            }
            QListWidget::indicator:checked {
                background-color: #5a9ad4;
                border-color: #5a9ad4;
                image: url("data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxMiIgaGVpZ2h0PSIxMiIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9IiNmZmZmZmYiIHN0cm9rZS13aWR0aD0iNCIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIiBzdHJva2UtbGluZWpvaW49InJvdW5kIj48cG9seWxpbmUgcG9pbnRzPSIyMCA2IDkgMTcgNCAxMiI+PC9wb2x5bGluZT48L3N2Zz4=");
            }
            QListWidget::indicator:unchecked:hover {
                border-color: #5a9ad4;
            }
        """)

        self.toggle_visibility_btn = make_button("Toggle Visibility", '#1a2035')
        self.toggle_visibility_btn.setToolTip(
            "Show or hide the selected geometry layer on the canvas")

        self.add_widget(help_widget(self.geom_list, "List of loaded geometry layers/entities"))
        self.add_widget(help_widget(self.toggle_visibility_btn, "Show or hide the selected geometry layer on the canvas"))
