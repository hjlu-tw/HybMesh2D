from __future__ import annotations
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QScrollArea, QFrame
from PyQt6.QtCore import Qt

from app.views.collapsible import CollapsibleSection
from app.views.panels import (
    FilePanel, GeometryPanel, VertexPanel,
    EdgeListPanel, EdgePropsPanel, AdvancedPanel, ActionsPanel
)

class SidebarView(QWidget):
    """
    Left-hand control panel — scrollable, grouped into collapsible sections.
    No emoji icons on buttons; muted/dark colour palette.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: #0c0d16;")
        scroll.verticalScrollBar().setStyleSheet("""
            QScrollBar:vertical {
                border: none;
                background: #0c0d16;
                width: 10px;
                margin: 0px 0px 0px 0px;
            }
            QScrollBar::handle:vertical {
                background: #2c2e43;
                min-height: 20px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical:hover {
                background: #3e415e;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

        content = QWidget()
        content.setStyleSheet("background: #121422; color: #a0a8c0;")
        self._layout = QVBoxLayout(content)
        self._layout.setContentsMargins(6, 6, 6, 6)
        self._layout.setSpacing(6)

        # 1. Project Panel (File)
        self.file_panel = FilePanel(self)
        self._layout.addWidget(self.file_panel)

        # 2. Geometry Panel
        self.geometry_panel = GeometryPanel(self)
        self._layout.addWidget(self.geometry_panel)

        # 3. Vertex Panel
        self.vertex_panel = VertexPanel(self)
        self._layout.addWidget(self.vertex_panel)

        # 4. Edge Panel (List and Properties)
        self.sec_edge_parent = CollapsibleSection("Edge", start_collapsed=True)
        self._layout.addWidget(self.sec_edge_parent)

        self.edge_list_panel = EdgeListPanel(self)
        self.sec_edge_parent.add_widget(self.edge_list_panel)

        self.edge_props_panel = EdgePropsPanel(self)
        self.sec_edge_parent.add_widget(self.edge_props_panel)

        # 5. Advanced Panel
        self.advanced_panel = AdvancedPanel(self)
        self._layout.addWidget(self.advanced_panel)

        # 6. Actions Panel
        self.actions_panel = ActionsPanel(self)
        self._layout.addWidget(self.actions_panel)

        self._layout.addStretch()
        scroll.setWidget(content)
        outer.addWidget(scroll)

    @property
    def preview_btn(self):
        win = self.window()
        return win.cad_preview_btn if (win and hasattr(win, "cad_preview_btn")) else None

    @property
    def curve_preview_btn(self):
        win = self.window()
        return win.cad_curve_preview_btn if (win and hasattr(win, "cad_curve_preview_btn")) else None

    @property
    def file_preview_btn(self):
        win = self.window()
        return win.cad_file_preview_btn if (win and hasattr(win, "cad_file_preview_btn")) else None

    def switch_param_form(self, strategy_name: str):
        self.edge_props_panel.switch_param_form(strategy_name)

    def show_file_segment(self, start: int, end: int):
        self.edge_props_panel.show_file_segment(start, end)

    def show_curve_segment(self, seg):
        self.edge_props_panel.show_curve_segment(seg)

    def show_segment_props(self, visible: bool):
        self.edge_props_panel.show_segment_props(visible)

    def get_transform_dict(self) -> dict | None:
        if not self.apply_transform_cb.isChecked():
            return None
        return {
            "scale": self.transform_scale.value(),
            "rotate": self.transform_rotate.value(),
            "translate": [self.transform_tx.value(), self.transform_ty.value()],
        }

    def set_transform_from_dict(self, d: dict | None):
        if d:
            self.apply_transform_cb.setChecked(True)
            self.transform_scale.setValue(d.get("scale", 1.0))
            self.transform_rotate.setValue(d.get("rotate", 0.0))
            tr = d.get("translate", [0.0, 0.0])
            self.transform_tx.setValue(tr[0])
            self.transform_ty.setValue(tr[1])
        else:
            self.apply_transform_cb.setChecked(False)

    def __getattr__(self, name):
        # Dynamically delegate property lookups to sub-panels
        for panel in [
            self.file_panel,
            self.geometry_panel,
            self.vertex_panel,
            self.edge_list_panel,
            self.edge_props_panel,
            self.advanced_panel,
            self.actions_panel,
        ]:
            if hasattr(panel, name):
                return getattr(panel, name)
            # Special check for transform sub-widgets within EdgePropsPanel
            if panel is self.edge_props_panel and hasattr(panel, "_transform_dup_group"):
                dup = panel._transform_dup_group
                if hasattr(dup, name):
                    return getattr(dup, name)
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")
