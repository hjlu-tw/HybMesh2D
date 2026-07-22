from __future__ import annotations
from PyQt6.QtWidgets import QHBoxLayout, QCheckBox
from app.views.collapsible import CollapsibleSection
from app.utils import make_button, help_widget


class EdgeListPanel(CollapsibleSection):
    """Edge actions. The edges themselves now live in the Model Tree; this
    section holds the commands that act on the tree's current selection (also
    available via the tree's right-click menu)."""

    def __init__(self, parent=None):
        super().__init__("Edge Actions", start_collapsed=True, parent=parent)

        self.add_curve_seg_btn = make_button("Add Analytic Edge", '#3a180a')
        self.add_curve_seg_btn.setToolTip("Add a new analytic curve edge to the geometry")
        self.remove_seg_btn = make_button("Remove Edge", '#4a1212')
        self.remove_seg_btn.setEnabled(False)
        self.remove_seg_btn.setToolTip("Remove the currently selected edge from the geometry")
        self.curve_bake_btn = make_button("Convert to Discrete", '#1b5e20')
        self.curve_bake_btn.setEnabled(False)
        self.curve_bake_btn.setToolTip("Convert the selected analytic curve into a discrete edge")

        # Merge several end-to-end curve edges (e.g. 4 hand-drawn lines) into one
        # CLOSED polygon, clearing the "boundary not closed" warning.
        self.join_edges_btn = make_button("Join → Polygon", '#1b3a5e')
        self.join_edges_btn.setEnabled(False)
        self.join_edges_btn.setToolTip(
            "Merge the selected curve edges that connect end-to-end into a single\n"
            "CLOSED polygon edge — clears the 'boundary not closed' warning.\n"
            "Enabled once you select ≥2 curve edges (Shift/Ctrl-click or box-select\n"
            "in Edge mode).")

        # #1: "Assign patch / group…" lives here (in Edge Actions) rather than in
        # the per-edge Edge Properties inspector, so it is always reachable and
        # acts on the WHOLE current selection at once (select several edges in the
        # tree/canvas, then click once) — no more one-edge-at-a-time assignment.
        # A free-form GROUPING label (number or alias); the physical BC TYPE is
        # chosen per group later in the Mesh Generator → Edit segment BCs and the
        # Solver. The label travels via the .meta sidecar. Wired by the controller
        # to open_cad_patch_dialog (resolved through SidebarView delegation).
        self.group_btn = make_button("Assign patch / group…", '#243a52')
        self.group_btn.setToolTip(
            "Assign a patch/group label to ALL currently-selected edges (opens a\n"
            "pop-up). Free-form GROUPING label (e.g. airfoil, wall_top, 1) — NOT a\n"
            "physical BC type. Select MULTIPLE edges (Shift/Ctrl-click or box-select\n"
            "in Edge mode) to group them under one name at once. Choose the BC per\n"
            "group later in the Mesh Generator → Edit segment BCs.")

        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.addWidget(help_widget(self.add_curve_seg_btn, "Add a new analytic curve edge to the geometry"))
        btn_layout.addWidget(help_widget(self.remove_seg_btn, "Remove the currently selected edge from the geometry"))

        self.add_layout(btn_layout)
        self.add_widget(help_widget(self.curve_bake_btn, "Convert the selected analytic curve into a discrete edge"))
        # Join button + a persistent "Force close" toggle beside it.
        join_row = QHBoxLayout()
        join_row.setContentsMargins(0, 0, 0, 0)
        join_row.addWidget(help_widget(self.join_edges_btn,
            "Merge selected end-to-end edges into one polygon"), stretch=1)
        self.join_force_close_cb = QCheckBox("Force close")
        self.join_force_close_cb.setToolTip(
            "When joining, force the result to be a CLOSED loop (bridge the\n"
            "last→first gap). Unchecked: the result is closed only if the edges\n"
            "already form a loop — otherwise it is left open.")
        join_row.addWidget(self.join_force_close_cb)
        self.add_layout(join_row)

        self.add_widget(help_widget(self.group_btn,
            "Assign a patch/group label to ALL selected edges (pop-up)"))
