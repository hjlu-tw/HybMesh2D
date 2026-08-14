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
        # Defined here so SidebarView's delegation resolves ``extrude_stl_btn``;
        # it is placed in the persistent footer (next to Export/Save) rather than
        # this collapsed section, for discoverability.
        self.extrude_stl_btn = make_button("Export 2D STL", '#15303a')
        self.extrude_stl_btn.setToolTip(
            "Export the selected 2D profile(s) as a flat sheet STL (z=0) for the "
            "Immersed Boundary (φ) page")

        self.add_widget(help_widget(self.save_btn, "Export the resampled geometry to a .dat mesh file"))
        self.add_widget(help_widget(self.generate_btn, "Save the current configuration to a .json file for CLI processing"))

