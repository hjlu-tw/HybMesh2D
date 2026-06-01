from __future__ import annotations
from app.views.collapsible import CollapsibleSection
from app.utils import make_button

class ActionsPanel(CollapsibleSection):
    def __init__(self, parent=None):
        super().__init__("Output", start_collapsed=True, parent=parent)

        self.save_btn = make_button("Export Mesh (.dat)", '#062510')
        self.generate_btn = make_button("Save Configuration (.json)", '#1b1f2a')

        self.add_widget(self.save_btn)
        self.add_widget(self.generate_btn)

    @property
    def preview_btn(self):
        win = self.window()
        return win.cad_preview_btn if (win and hasattr(win, "cad_preview_btn")) else None
