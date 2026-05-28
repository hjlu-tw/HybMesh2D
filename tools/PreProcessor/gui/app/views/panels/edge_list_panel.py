from __future__ import annotations
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QListWidget
from app.views.collapsible import CollapsibleSection
from app.utils import make_button

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

        # Analytic Edges
        lbl_curve = QLabel("Analytic Edges:")
        lbl_curve.setStyleSheet("color: #a0c0d0; font-weight: bold; font-size: 11px; margin-top: 6px;")

        self.curve_segment_list = QListWidget()
        self.curve_segment_list.setMaximumHeight(120)
        self.curve_segment_list.setStyleSheet(list_style)

        self.add_curve_seg_btn = make_button("Add Analytic Edge", '#3a180a')
        self.remove_seg_btn = make_button("Remove Edge", '#4a1212')
        self.remove_seg_btn.setEnabled(False)
        self.curve_bake_btn = make_button("Convert to Discrete", '#1b5e20')

        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.addWidget(self.add_curve_seg_btn)
        btn_layout.addWidget(self.remove_seg_btn)

        self.add_widget(lbl_file)
        self.add_widget(self.file_segment_list)
        self.add_widget(lbl_curve)
        self.add_widget(self.curve_segment_list)
        self.add_layout(btn_layout)
        self.add_widget(self.curve_bake_btn)
