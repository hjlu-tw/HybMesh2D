from __future__ import annotations
from PyQt6.QtWidgets import QListWidget
from PyQt6.QtCore import pyqtSignal, Qt
from app.views.collapsible import CollapsibleSection
from app.utils import make_button, help_widget, LIST_INDICATOR_STYLE

class GeometryPanel(CollapsibleSection):
    context_menu_requested = pyqtSignal(object, object)  # (global_pos, item)

    def __init__(self, parent=None):
        super().__init__("Geometry Entities", start_collapsed=True, parent=parent)

        self.geom_list = QListWidget()
        self.geom_list.setMaximumHeight(120)
        self.geom_list.setStyleSheet(LIST_INDICATOR_STYLE)
        self.geom_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.geom_list.customContextMenuRequested.connect(self._on_context_menu)

        self.toggle_visibility_btn = make_button("Toggle Visibility", '#1a2035')
        self.toggle_visibility_btn.setToolTip(
            "Show or hide the selected geometry layer on the canvas")

        self.add_widget(help_widget(self.geom_list, "List of loaded geometry layers/entities"))
        self.add_widget(help_widget(self.toggle_visibility_btn, "Show or hide the selected geometry layer on the canvas"))

    def _on_context_menu(self, pos):
        item = self.geom_list.itemAt(pos)
        if item:
            global_pos = self.geom_list.mapToGlobal(pos)
            self.context_menu_requested.emit(global_pos, item)
