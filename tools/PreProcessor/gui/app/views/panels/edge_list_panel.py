from __future__ import annotations
from PyQt6.QtWidgets import QHBoxLayout
from app.views.collapsible import CollapsibleSection
from app.utils import make_button, help_widget


class EdgeListPanel(CollapsibleSection):
    """Edge actions. The edges themselves now live in the Model Tree; this
    section holds the commands that act on the tree's current selection (also
    available via the tree's right-click menu)."""

    def __init__(self, parent=None):
        super().__init__("Edge Actions", start_collapsed=True, parent=parent)

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

        self.add_layout(btn_layout)
        self.add_widget(help_widget(self.curve_bake_btn, "Convert the selected analytic curve into a discrete edge"))
