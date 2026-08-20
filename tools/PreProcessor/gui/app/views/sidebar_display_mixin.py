"""What the sidebar is TOLD, and what it can be ASKED.

The other half of the seam: `sidebar_actions_mixin` carries the intents the
sidebar raises, this carries the verbs its callers call. Split from sidebar.py
for the same reason — layout is a different concern, and this list grows as each
group of controllers stops naming widgets.

Two rules the verbs here exist to enforce:

* **A selection state is set as ONE fact.** "No vertex is selected" was three
  statements — a label, and two buttons disabled — repeated verbatim in four
  controllers, so a fifth caller could set the label and leave the buttons live.
* **Which buttons a fact enables is the panel's decision.** The controller knows
  whether a vertex is a split point and whether it is an endpoint; that those two
  booleans mean "Split off, Remove-split on" is view policy and belongs here.
"""
from __future__ import annotations

from app.utils import block_signals


class SidebarDisplayMixin:
    # ── vertex selection ─────────────────────────────────────────────────
    def show_vertex_selection(self, index: int | None = None, position=None,
                              *, is_split: bool = False,
                              is_endpoint: bool = False):
        """Show which vertex is selected, and what can be done to it.

        `index is None` means nothing is selected: the label says so and every
        vertex action goes dead, which is the state four controllers used to
        spell out by hand.
        """
        vp = self.vertex_panel
        if index is None:
            vp.selected_info.setText("Selected Vertex: None")
            vp.split_btn.setEnabled(False)
            vp.remove_split_btn.setEnabled(False)
            vp.move_btn.setEnabled(False)
            return
        vp.selected_info.setText(f"Selected Vertex: Index {index}")
        # An existing split cannot be split again; an endpoint's split is
        # structural and must not be removed.
        vp.split_btn.setEnabled(not is_split)
        vp.remove_split_btn.setEnabled(is_split and not is_endpoint)
        if position is None:
            vp.move_btn.setEnabled(False)
            return
        with block_signals(vp.move_x, vp.move_y):
            vp.move_x.setValue(position[0])
            vp.move_y.setValue(position[1])
        vp.move_btn.setEnabled(True)

    def vertex_move_target(self) -> tuple[float, float]:
        """The coordinates typed into the Move fields."""
        return self.vertex_panel.move_x.value(), self.vertex_panel.move_y.value()

    def vertex_insert_point(self) -> tuple[float, float]:
        """The coordinates typed into the Insert fields."""
        return self.vertex_panel.insert_x.value(), self.vertex_panel.insert_y.value()

    def keep_vertex_on_remove(self) -> bool:
        """Whether removing a split should keep the vertex as a plain point."""
        return self.vertex_panel.keep_vertex_cb.isChecked()

    # ── which edge actions apply ─────────────────────────────────────────
    def set_remove_edge_enabled(self, enabled: bool):
        self.edge_list_panel.remove_seg_btn.setEnabled(enabled)

    def set_join_edges_enabled(self, enabled: bool):
        self.edge_list_panel.join_edges_btn.setEnabled(enabled)

    def set_bake_curve_enabled(self, enabled: bool):
        self.edge_list_panel.curve_bake_btn.setEnabled(enabled)

    def join_force_close(self) -> bool:
        """Whether Join should close the resulting outline."""
        return self.edge_list_panel.join_force_close_cb.isChecked()

    # ── the edge inspector ───────────────────────────────────────────────
    def show_edge_summary(self, label: str, strategy: str | None):
        """Name the selected edge; `strategy` None means it is analytic.

        An analytic edge's points come from its formula, so the distribution
        controls are hidden rather than shown inert — they would otherwise look
        like settings that simply do nothing.
        """
        ep = self.edge_props_panel
        ep.segment_type_label.setText(label)
        analytic = strategy is None
        ep.strategy_combo.setVisible(not analytic)
        ep.param_stack.setVisible(not analytic)
        if analytic:
            return
        with block_signals(ep.strategy_combo):
            ep.strategy_combo.setCurrentText(strategy)

    def set_match_previous(self, checked: bool):
        with block_signals(self.edge_props_panel.match_previous_cb):
            self.edge_props_panel.match_previous_cb.setChecked(checked)

    def auto_split_angle(self) -> float:
        """The corner-detection threshold, in degrees."""
        return self.edge_props_panel.auto_split_angle_sb.value()

    def arc_radius_locked(self) -> bool:
        """Whether an arc drag should hold the radius fixed."""
        lock = getattr(self.edge_props_panel, "arc_lock_radius", None)
        return lock is not None and lock.isChecked()

    # ── geometry-level state ─────────────────────────────────────────────
    _NAME_QSS = "color: #dde6ff; font-weight: bold; margin-bottom: 5px;"
    _NO_NAME_QSS = "color: #6a7aaa; font-style: italic; margin-bottom: 5px;"

    def show_geometry_name(self, name: str | None):
        """The imported geometry's name, or the empty state.

        The caller passes a NAME, not a path and not a stylesheet: which colour
        an absent geometry is shown in is this panel's business, and it was
        previously spelled out at every call site.
        """
        label = self.file_panel.file_name_label
        label.setText(f"File: {name}" if name else "No geometry imported")
        label.setStyleSheet(self._NAME_QSS if name else self._NO_NAME_QSS)

    def set_closure_mode(self, text: str, status: str = ""):
        """The closed-loop mode, plus the resolved-state hint Auto mode shows."""
        with block_signals(self.file_panel.is_closed_combo):
            self.file_panel.is_closed_combo.setCurrentText(text)
        self.file_panel.closed_mode_status.setText(status)

    def set_global_spline(self, checked: bool):
        with block_signals(self.advanced_panel.global_spline_cb):
            self.advanced_panel.global_spline_cb.setChecked(checked)
