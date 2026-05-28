from __future__ import annotations
from PyQt6.QtWidgets import QWidget, QFormLayout, QComboBox, QLabel
from PyQt6.QtCore import Qt
from app.views.collapsible import CollapsibleSection
from app.utils import make_button, COMBO_STYLE, align_form_labels

class FilePanel(CollapsibleSection):
    def __init__(self, parent=None):
        super().__init__("Project", start_collapsed=True, parent=parent)

        self.load_btn = make_button("Import Geometry (.dat)")
        self.load_json_btn = make_button("Load Configuration (.json)", '#301540')
        self.new_tab_btn = make_button("New Session", '#1a2525')

        self.file_name_label = QLabel("No geometry imported")
        self.file_name_label.setStyleSheet(
            "color: #6a7aaa; font-style: italic; margin-bottom: 4px;")
        self.file_name_label.setWordWrap(True)

        form = QFormLayout()
        self.is_closed_combo = QComboBox()
        self.is_closed_combo.addItems(["True", "False"])
        self.is_closed_combo.setStyleSheet(COMBO_STYLE)
        form.addRow("Closed Curve:", self.is_closed_combo)
        align_form_labels(form)

        self.add_widget(self.load_btn)
        self.add_widget(self.load_json_btn)
        self.add_widget(self.new_tab_btn)
        self.add_widget(self.file_name_label)
        self.add_layout(form)
