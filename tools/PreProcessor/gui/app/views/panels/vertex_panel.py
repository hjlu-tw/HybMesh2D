from __future__ import annotations
from PyQt6.QtWidgets import QWidget, QFormLayout, QDoubleSpinBox, QLabel, QCheckBox
from PyQt6.QtCore import Qt
from app.views.collapsible import CollapsibleSection
from app.utils import make_button, align_form_labels

class VertexPanel(CollapsibleSection):
    def __init__(self, parent=None):
        super().__init__("Vertex", start_collapsed=True, parent=parent)

        # 1. Selection Section
        self.selection_sec = CollapsibleSection("Vertex Selection", start_collapsed=True)
        self.add_widget(self.selection_sec)

        self.selected_info = QLabel("Selected Vertex: None")
        self.selected_info.setStyleSheet("color: #00E5FF; font-weight: bold;")

        self.split_btn = make_button("Add Breakpoint", '#102438')
        self.split_btn.setEnabled(False)
        self.remove_split_btn = make_button("Remove Breakpoint", '#251010')
        self.remove_split_btn.setEnabled(False)
        self.auto_detect_btn = make_button("Auto Detect Breakpoints", '#1b2a4a')

        self.keep_vertex_cb = QCheckBox("Preserve vertex on removal")
        self.keep_vertex_cb.setStyleSheet("color: #FF8A65; font-size: 11px;")

        self.selection_sec.add_widget(self.selected_info)
        self.selection_sec.add_widget(self.split_btn)
        self.selection_sec.add_widget(self.remove_split_btn)
        self.selection_sec.add_widget(self.keep_vertex_cb)
        self.selection_sec.add_widget(self.auto_detect_btn)

        # 2. Insert Section
        self.insert_sec = CollapsibleSection("Insert Vertex", start_collapsed=True)
        self.add_widget(self.insert_sec)

        form = QFormLayout()
        self.insert_x = QDoubleSpinBox()
        self.insert_x.setRange(-1e6, 1e6)
        self.insert_x.setDecimals(6)
        self.insert_x.setStyleSheet("background:#181b2a; color:#a0a8c0; border:1px solid #333852;")

        self.insert_y = QDoubleSpinBox()
        self.insert_y.setRange(-1e6, 1e6)
        self.insert_y.setDecimals(6)
        self.insert_y.setStyleSheet("background:#181b2a; color:#a0a8c0; border:1px solid #333852;")

        form.addRow("X:", self.insert_x)
        form.addRow("Y:", self.insert_y)
        align_form_labels(form)

        self.insert_btn = make_button("Insert & Split")

        self.insert_sec.add_layout(form)
        self.insert_sec.add_widget(self.insert_btn)
