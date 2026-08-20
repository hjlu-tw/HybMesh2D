from __future__ import annotations
from PyQt6.QtWidgets import QFormLayout, QComboBox, QLabel
from app.views.collapsible import CollapsibleSection
from app.utils import make_button, COMBO_STYLE, align_form_labels, help_label, help_widget

class FilePanel(CollapsibleSection):
    def __init__(self, parent=None):
        super().__init__("Import / File", start_collapsed=True, parent=parent)

        self.load_btn = make_button("Import Geometry (.dat)")
        self.load_btn.setToolTip("Open a .dat geometry file from disk")
        self.load_stl_btn = make_button("Import STL Surface (z=0)", '#15303a')
        self.load_stl_btn.setToolTip(
            "Load a planar (z=0) STL surface and auto-detect its boundary "
            "outline as surface points. Non-planar STL files are rejected.")
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
        self.is_closed_combo.addItems(["Auto", "Closed", "Open"])
        self.is_closed_combo.setStyleSheet(COMBO_STYLE)
        _closed_tip = ("How the boundary's closure is decided:\n"
                       "• Auto — detect from the geometry (endpoints near each "
                       "other → closed; a clear gap → open).\n"
                       "• Closed — force a closed loop (bridge the last→first gap).\n"
                       "• Open — leave the boundary open-ended.")
        self.is_closed_combo.setToolTip(_closed_tip)
        form.addRow(help_label("Closed Loop:", _closed_tip), self.is_closed_combo)
        # Shows the resolved result when the mode is Auto (e.g. "→ Closed").
        self.closed_mode_status = QLabel("")
        self.closed_mode_status.setStyleSheet("color:#6fae7a; font-size:10px;")
        form.addRow("", self.closed_mode_status)
        align_form_labels(form)

        self.add_widget(help_widget(self.load_btn, "Open a .dat geometry file from disk"))
        self.add_widget(help_widget(self.load_stl_btn, "Load a planar (z=0) STL surface and auto-detect its boundary outline as surface points"))
        self.add_widget(help_widget(self.load_json_btn, "Open a .json configuration file with geometry and resampling settings"))
        self.add_widget(help_widget(self.new_tab_btn, "Create a new empty geometry workspace tab"))
        self.add_widget(self.file_name_label)
        self.add_layout(form)
