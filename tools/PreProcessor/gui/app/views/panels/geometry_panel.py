from __future__ import annotations
from PyQt6.QtWidgets import QListWidget
from app.views.collapsible import CollapsibleSection
from app.utils import make_button, help_widget, LIST_INDICATOR_STYLE

class GeometryPanel(CollapsibleSection):
    def __init__(self, parent=None):
        super().__init__("Geometry Entities", start_collapsed=True, parent=parent)

        self.geom_list = QListWidget()
        self.geom_list.setMaximumHeight(120)
        self.geom_list.setStyleSheet(LIST_INDICATOR_STYLE)

        self.toggle_visibility_btn = make_button("Toggle Visibility", '#1a2035')
        self.toggle_visibility_btn.setToolTip(
            "Show or hide the selected geometry layer on the canvas")

        self.add_widget(help_widget(self.geom_list, "List of loaded geometry layers/entities"))
        self.add_widget(help_widget(self.toggle_visibility_btn, "Show or hide the selected geometry layer on the canvas"))
