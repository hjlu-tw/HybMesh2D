from __future__ import annotations
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QListWidget
from app.views.collapsible import CollapsibleSection
from app.utils import make_button, help_widget, LIST_STYLE

class EdgeListPanel(CollapsibleSection):
    def __init__(self, parent=None):
        super().__init__("Edge List", start_collapsed=True, parent=parent)

        # Single unified Edge list (discrete + analytic edges, numbered 1..N).
        lbl_edges = QLabel("Edges:")
        lbl_edges.setStyleSheet("color: #a0c0d0; font-weight: bold; font-size: 11px; margin-top: 4px;")

        self.segment_list = QListWidget()
        self.segment_list.setMaximumHeight(240)
        self.segment_list.setStyleSheet(LIST_STYLE)
        self.segment_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.segment_list.setToolTip("All edges — discrete (from file) and analytic (curves) — numbered in order")

        # Back-compat aliases: discrete and analytic edges now live in one list,
        # so both former names point at the same widget.
        self.file_segment_list = self.segment_list
        self.curve_segment_list = self.segment_list

        self.add_curve_seg_btn = make_button("Add Analytic Edge", '#3a180a')
        self.add_curve_seg_btn.setToolTip("Add a new analytic curve edge to the geometry")
        self.remove_seg_btn = make_button("Remove Edge", '#4a1212')
        self.remove_seg_btn.setEnabled(False)
        self.remove_seg_btn.setToolTip("Remove the currently selected edge from the geometry")
        self.curve_bake_btn = make_button("Convert to Discrete", '#1b5e20')
        self.curve_bake_btn.setEnabled(False)
        self.curve_bake_btn.setToolTip("Convert the selected analytic curve into a discrete edge")

        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.addWidget(help_widget(self.add_curve_seg_btn, "Add a new analytic curve edge to the geometry"))
        btn_layout.addWidget(help_widget(self.remove_seg_btn, "Remove the currently selected edge from the geometry"))

        self.add_widget(lbl_edges)
        self.add_widget(help_widget(self.segment_list, "All edges — discrete (from file) and analytic (curves) — numbered in order"))
        self.add_layout(btn_layout)
        self.add_widget(help_widget(self.curve_bake_btn, "Convert the selected analytic curve into a discrete edge"))
