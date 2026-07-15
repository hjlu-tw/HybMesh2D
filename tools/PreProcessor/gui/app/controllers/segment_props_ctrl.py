"""Per-segment property editing for AppController, split out of segment_ctrl as a
sibling mixin (behaviour unchanged): match-previous, per-segment BC, CAD patch/group
naming, closed-loop toggle and global-spline toggle. Composed into AppController
alongside SegmentControllerMixin; resolves through the shared flat self
(active_session, get_selected_segment_indices, _apply_geometry_update)."""
from __future__ import annotations
from app.commands.segment_cmds import (
    ToggleIsClosedCmd, ToggleGlobalSplineCmd, UpdateMultipleSegmentsStateCmd,
)


class SegmentPropsControllerMixin:
    """Per-segment properties: match-previous, BC, patch, closed, spline (moved)."""

    def update_match_previous(self, checked: bool):
        session = self.active_session()
        if not session:
            return
        indices = self.get_selected_segment_indices()
        if not indices:
            return

        old_states = {}
        for idx in indices:
            seg = session.project_model.get_segment(idx)
            if seg:
                old_states[idx] = seg.to_dict()

        for idx in indices:
            seg = session.project_model.get_segment(idx)
            if seg:
                seg.match_previous = checked

        any_changed = False
        states_dict = {}
        for idx in indices:
            seg = session.project_model.get_segment(idx)
            if seg:
                new_state = seg.to_dict()
                states_dict[idx] = (old_states[idx], new_state)
                if new_state != old_states[idx]:
                    any_changed = True

        if any_changed:
            def refresh():
                if session is self.active_session():
                    sb = self.main_window.sidebar_view
                    sb.match_previous_cb.blockSignals(True)
                    sb.match_previous_cb.setChecked(checked)
                    sb.match_previous_cb.blockSignals(False)
                    self._apply_geometry_update(session)
            cmd = UpdateMultipleSegmentsStateCmd(session, states_dict, refresh_cb=refresh)
            session.command_history.execute(cmd)

    def update_segment_bc(self, text: str):
        """Set the per-segment boundary condition on the selected edge(s). The
        tag is metadata only (no geometry change) and flows to the mesher via
        the .meta sidecar; blank inherits the global BC_GEOM."""
        session = self.active_session()
        if not session:
            return
        indices = self.get_selected_segment_indices()
        if not indices:
            return
        bc = (text or "").strip()

        old_states = {}
        for idx in indices:
            seg = session.project_model.get_segment(idx)
            if seg:
                old_states[idx] = seg.to_dict()

        for idx in indices:
            seg = session.project_model.get_segment(idx)
            if seg:
                seg.bc = bc

        any_changed = False
        states_dict = {}
        for idx in indices:
            seg = session.project_model.get_segment(idx)
            if seg:
                new_state = seg.to_dict()
                states_dict[idx] = (old_states[idx], new_state)
                if new_state != old_states[idx]:
                    any_changed = True

        if any_changed:
            cmd = UpdateMultipleSegmentsStateCmd(session, states_dict, refresh_cb=None)
            session.command_history.execute(cmd)

    def open_cad_patch_dialog(self):
        """#1/#6: pop-up to assign a patch/group label to ALL currently-selected
        edges. The label is a free-form GROUPING tag (number or alias); the BC is
        chosen per group later in the Mesh Generator. Offers existing group names
        in an editable combo so edges are easily added to the same group."""
        from PyQt6.QtWidgets import QInputDialog
        session = self.active_session()
        if not session:
            return
        indices = self.get_selected_segment_indices()
        if not indices:
            self.main_window.log_panel.log(
                "Select one or more edges first, then assign a patch/group.")
            return
        # Shared current label (blank if the selection is mixed / unset).
        labels = set()
        for idx in indices:
            seg = session.project_model.get_segment(idx)
            if seg:
                labels.add((getattr(seg, "bc", "") or "").strip())
        current = labels.pop() if len(labels) == 1 else ""
        # Existing distinct labels across this geometry (for the dropdown), in
        # first-appearance order, so edges are easily grouped under an existing name.
        existing = []
        for seg in session.project_model.segments:
            b = (getattr(seg, "bc", "") or "").strip()
            if b and b not in existing:
                existing.append(b)
        items = list(existing)
        if current and current not in items:
            items.insert(0, current)
        if not items:
            items = [""]
        cur_idx = items.index(current) if current in items else 0
        text, ok = QInputDialog.getItem(
            self.main_window, "Assign patch / group",
            f"Patch / group name for {len(indices)} selected edge(s).\n"
            "Free-form grouping label (e.g. airfoil, wall_top, 1); the physical BC\n"
            "is chosen per group in the Mesh Generator. Blank = geometry default.",
            items, cur_idx, True)
        if not ok:
            return
        self.update_segment_bc(text)
        shown = text.strip() or "(cleared)"
        self.main_window.log_panel.log(
            f"Assigned patch/group '{shown}' to {len(indices)} edge(s).")

    def handle_is_closed_changed(self, text: str):
        session = self.active_session()
        if session:
            is_closed = (text == "True")
            if session.project_model.is_closed != is_closed:
                def refresh():
                    sb = self.main_window.sidebar_view
                    sb.is_closed_combo.blockSignals(True)
                    sb.is_closed_combo.setCurrentText(str(session.project_model.is_closed))
                    sb.is_closed_combo.blockSignals(False)
                    self._apply_geometry_update(session)
                cmd = ToggleIsClosedCmd(session, is_closed, refresh)
                session.command_history.execute(cmd)

    def handle_global_spline_changed(self, checked: bool):
        session = self.active_session()
        if session:
            if session.project_model.global_spline != checked:
                def refresh():
                    sb = self.main_window.sidebar_view
                    sb.global_spline_cb.blockSignals(True)
                    sb.global_spline_cb.setChecked(session.project_model.global_spline)
                    sb.global_spline_cb.blockSignals(False)
                    self._apply_geometry_update(session)
                cmd = ToggleGlobalSplineCmd(session, checked, refresh)
                session.command_history.execute(cmd)
