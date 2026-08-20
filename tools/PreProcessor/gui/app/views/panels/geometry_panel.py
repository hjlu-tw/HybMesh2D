from __future__ import annotations
from app.views.collapsible import CollapsibleSection
from app.utils import help_widget
from app.views.panels.geometry_tree import GeometryTreeView


class GeometryPanel(CollapsibleSection):
    """Model tree: geometry layers (with a visibility 'eye') and their edges.

    Replaces the former geometry-layer list + flat edge list with a single tree.
    Layer visibility is the per-row checkbox; add/remove/convert and other
    commands are reached through the tree's right-click context menu (built by
    the controller). The ``context_menu_requested`` signal lives on the tree."""

    def __init__(self, parent=None):
        super().__init__("Model Tree", start_collapsed=True, parent=parent)

        self.geometry_tree = GeometryTreeView()
        self.add_widget(help_widget(
            self.geometry_tree,
            "Geometry layers and their edges. Toggle the checkbox to show/hide a "
            "layer; double-click to fit it in view; right-click for actions."))

    @property
    def context_menu_requested(self):
        # Back-compat: expose the tree's signal under the panel name the
        # controller historically connected to.
        return self.geometry_tree.context_menu_requested
