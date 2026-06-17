from __future__ import annotations
from app.views.collapsible import CollapsibleSection
from app.utils import make_button, help_widget

class ActionsPanel(CollapsibleSection):
    def __init__(self, parent=None):
        super().__init__("Output", start_collapsed=True, parent=parent)

        self.save_btn = make_button("Export Mesh", '#062510')
        self.save_btn.setToolTip("Export the resampled geometry to a .dat mesh file")
        self.generate_btn = make_button("Save Config", '#1b1f2a')
        self.generate_btn.setToolTip("Save the current configuration to a .json file (.json) for CLI processing")

        self.add_widget(help_widget(self.save_btn, "Export the resampled geometry to a .dat mesh file"))
        self.add_widget(help_widget(self.generate_btn, "Save the current configuration to a .json file for CLI processing"))

    @property
    def preview_btn(self):
        win = self.window()
        return win.cad_preview_btn if (win and hasattr(win, "cad_preview_btn")) else None
