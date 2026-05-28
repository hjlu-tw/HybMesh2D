from __future__ import annotations
from app.views.collapsible import CollapsibleSection
from app.utils import make_button

class ActionsPanel(CollapsibleSection):
    def __init__(self, parent=None):
        super().__init__("Output", start_collapsed=True, parent=parent)

        self.preview_btn = make_button("Run & Preview", '#082544')
        self.save_btn = make_button("Export Mesh (.dat)", '#062510')
        self.generate_btn = make_button("Save Configuration (.json)", '#1b1f2a')

        self.add_widget(self.preview_btn)
        self.add_widget(self.save_btn)
        self.add_widget(self.generate_btn)
