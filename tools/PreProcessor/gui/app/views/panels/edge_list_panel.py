from __future__ import annotations
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QListWidget
from app.views.collapsible import CollapsibleSection
from app.utils import make_button, help_widget

class EdgeListPanel(CollapsibleSection):
    def __init__(self, parent=None):
        super().__init__("Edge List", start_collapsed=True, parent=parent)

        list_style = """
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
        """

        # Discrete Edges
        lbl_file = QLabel("Discrete Edges:")
        lbl_file.setStyleSheet("color: #a0c0d0; font-weight: bold; font-size: 11px; margin-top: 4px;")

        self.file_segment_list = QListWidget()
        self.file_segment_list.setMaximumHeight(120)
        self.file_segment_list.setStyleSheet(list_style)
        self.file_segment_list.setToolTip("List of discrete edges loaded from geometry file data")

        # Analytic Edges
        lbl_curve = QLabel("Analytic Edges:")
        lbl_curve.setStyleSheet("color: #a0c0d0; font-weight: bold; font-size: 11px; margin-top: 6px;")

        self.curve_segment_list = QListWidget()
        self.curve_segment_list.setMaximumHeight(120)
        self.curve_segment_list.setStyleSheet(list_style)
        self.curve_segment_list.setToolTip("List of analytically-defined curve edges")

        self.add_curve_seg_btn = make_button("Add Analytic Edge", '#3a180a')
        self.add_curve_seg_btn.setToolTip("Add a new analytic curve edge to the geometry")
        self.remove_seg_btn = make_button("Remove Edge", '#4a1212')
        self.remove_seg_btn.setEnabled(False)
        self.remove_seg_btn.setToolTip("Remove the currently selected edge from the geometry")
        self.curve_bake_btn = make_button("Convert to Discrete", '#1b5e20')
        self.curve_bake_btn.setToolTip("Convert the selected analytic curve into a discrete edge")

        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.addWidget(help_widget(self.add_curve_seg_btn, "Add a new analytic curve edge to the geometry"))
        btn_layout.addWidget(help_widget(self.remove_seg_btn, "Remove the currently selected edge from the geometry"))

        self.add_widget(lbl_file)
        self.add_widget(help_widget(self.file_segment_list, "List of discrete edges loaded from geometry file data"))
        self.add_widget(lbl_curve)
        self.add_widget(help_widget(self.curve_segment_list, "List of analytically-defined curve edges"))
        self.add_layout(btn_layout)
        self.add_widget(help_widget(self.curve_bake_btn, "Convert the selected analytic curve into a discrete edge"))
