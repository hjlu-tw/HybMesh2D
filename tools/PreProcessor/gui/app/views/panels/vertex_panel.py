from PyQt6.QtWidgets import QWidget, QFormLayout, QLabel, QCheckBox
from PyQt6.QtCore import Qt
from app.views.collapsible import CollapsibleSection
from app.utils import make_button, align_form_labels, help_label, help_widget, SPIN_STYLE
from app.views.clean_double_spin_box import CleanDoubleSpinBox

class VertexPanel(CollapsibleSection):
    def __init__(self, parent=None):
        super().__init__("Vertex", start_collapsed=True, parent=parent)

        # 1. Selection Section
        self.selection_sec = CollapsibleSection("Vertex Selection", start_collapsed=False)
        self.add_widget(self.selection_sec)

        self.selected_info = QLabel("Selected Vertex: None")
        self.selected_info.setStyleSheet("color: #00E5FF; font-weight: bold;")

        self.split_btn = make_button("Add Breakpoint", '#102438')
        self.split_btn.setEnabled(False)
        self.split_btn.setToolTip("Split the geometry at the selected vertex, creating two separate edges")
        self.remove_split_btn = make_button("Remove Breakpoint", '#251010')
        self.remove_split_btn.setEnabled(False)
        self.remove_split_btn.setToolTip("Remove the split at the selected vertex, merging two edges")
        self.auto_detect_btn = make_button("Auto Detect Breakpoints", '#1b2a4a')
        self.auto_detect_btn.setToolTip("Automatically detect and split edges at all sharp corners")

        self.keep_vertex_cb = QCheckBox("Preserve vertex on removal")
        self.keep_vertex_cb.setStyleSheet("color: #FF8A65; font-size: 11px;")
        self.keep_vertex_cb.setToolTip("Preserve the original vertex position during resampling")

        self.selection_sec.add_widget(self.selected_info)
        self.selection_sec.add_widget(help_widget(self.split_btn, "Split the geometry at the selected vertex, creating two separate edges"))
        self.selection_sec.add_widget(help_widget(self.remove_split_btn, "Remove the split at the selected vertex, merging two edges"))
        self.selection_sec.add_widget(help_widget(self.keep_vertex_cb, "Preserve the original vertex position during resampling"))
        self.selection_sec.add_widget(help_widget(self.auto_detect_btn, "Automatically detect and split edges at all sharp corners"))

        # 2. Insert Section
        self.insert_sec = CollapsibleSection("Insert Vertex", start_collapsed=False)
        self.add_widget(self.insert_sec)

        form = QFormLayout()
        self.insert_x = CleanDoubleSpinBox()
        self.insert_x.setRange(-1e6, 1e6)
        self.insert_x.setDecimals(6)
        self.insert_x.setStyleSheet(SPIN_STYLE)
        self.insert_x.setToolTip("X-coordinate for a new vertex to insert into the geometry")

        self.insert_y = CleanDoubleSpinBox()
        self.insert_y.setRange(-1e6, 1e6)
        self.insert_y.setDecimals(6)
        self.insert_y.setStyleSheet(SPIN_STYLE)
        self.insert_y.setToolTip("Y-coordinate for a new vertex to insert into the geometry")

        form.addRow(help_label("X:", "X-coordinate for a new vertex to insert into the geometry"), self.insert_x)
        form.addRow(help_label("Y:", "Y-coordinate for a new vertex to insert into the geometry"), self.insert_y)
        align_form_labels(form)

        self.insert_btn = make_button("Insert & Split")
        self.insert_btn.setToolTip("Insert a new vertex at the specified (X, Y) coordinates")

        self.insert_sec.add_layout(form)
        self.insert_sec.add_widget(help_widget(self.insert_btn, "Insert a new vertex at the specified (X, Y) coordinates"))
