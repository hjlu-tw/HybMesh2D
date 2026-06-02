from __future__ import annotations
from PyQt6.QtWidgets import QWidget, QFormLayout, QComboBox, QLabel
from PyQt6.QtCore import Qt
from app.views.collapsible import CollapsibleSection
from app.utils import make_button, COMBO_STYLE, align_form_labels, help_label, help_widget

class FilePanel(CollapsibleSection):
    def __init__(self, parent=None):
        super().__init__("Project", start_collapsed=True, parent=parent)

        self.load_btn = make_button("Import Geometry (.dat)")
        self.load_btn.setToolTip("Open a .dat geometry file from disk")
        self.load_json_btn = make_button("Load Configuration (.json)", '#301540')
        self.load_json_btn.setToolTip("Open a .json configuration file with geometry and resampling settings")
        self.new_tab_btn = make_button("New Session", '#1a2525')
        self.new_tab_btn.setToolTip("Create a new empty geometry workspace tab")

        self.file_name_label = QLabel("No geometry imported")
        self.file_name_label.setStyleSheet(
            "color: #6a7aaa; font-style: italic; margin-bottom: 4px;")
        self.file_name_label.setWordWrap(True)

        form = QFormLayout()
        self.is_closed_combo = QComboBox()
        self.is_closed_combo.addItems(["True", "False"])
        self.is_closed_combo.setStyleSheet(COMBO_STYLE)
        self.is_closed_combo.setToolTip("Whether the geometry forms a closed loop (True) or is open-ended (False)")
        form.addRow(help_label("Closed Curve:", "Whether the geometry forms a closed loop (True) or is open-ended (False)"), self.is_closed_combo)
        align_form_labels(form)

        self.add_widget(help_widget(self.load_btn, "Open a .dat geometry file from disk"))
        self.add_widget(help_widget(self.load_json_btn, "Open a .json configuration file with geometry and resampling settings"))
        self.add_widget(help_widget(self.new_tab_btn, "Create a new empty geometry workspace tab"))
        self.add_widget(self.file_name_label)
        self.add_layout(form)
