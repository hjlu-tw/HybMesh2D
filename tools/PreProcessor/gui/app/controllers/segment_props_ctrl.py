"""Per-segment property editing for AppController, split out of segment_ctrl as a
sibling mixin (behaviour unchanged): match-previous, per-segment BC, CAD patch/group
naming, closed-loop toggle and global-spline toggle. Composed into AppController
alongside SegmentControllerMixin; resolves through the shared flat self
(active_session, get_selected_segment_indices, _apply_geometry_update)."""
from __future__ import annotations
from app.commands.segment_cmds import (
    SetClosedModeCmd, ToggleGlobalSplineCmd, UpdateMultipleSegmentsStateCmd,
)

# Sidebar combo text <-> ProjectModel.closed_mode
_CLOSED_MODE_BY_TEXT = {"Auto": "auto", "Closed": "closed", "Open": "open"}
_CLOSED_TEXT_BY_MODE = {v: k for k, v in _CLOSED_MODE_BY_TEXT.items()}


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
                    sb.set_match_previous(checked)
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
        self._apply_bc_to_indices(session, indices, text)

    def _apply_bc_to_indices(self, session, indices, text: str):
        """Apply a patch/group tag to specific segment indices (undoable). Shared
        by the sidebar path (current selection) and the assign-patch dialog (#8)."""
        bc = (text or "").strip()
        old_states = {}
        for idx in indices:
            seg = session.project_model.get_segment(idx)
            if seg:
                old_states[idx] = seg.to_dict()
                seg.bc = bc

        any_changed = False
        states_dict = {}
        for idx in indices:
            seg = session.project_model.get_segment(idx)
            if seg and idx in old_states:
                new_state = seg.to_dict()
                states_dict[idx] = (old_states[idx], new_state)
                if new_state != old_states[idx]:
                    any_changed = True

        if any_changed:
            cmd = UpdateMultipleSegmentsStateCmd(session, states_dict, refresh_cb=None)
            session.command_history.execute(cmd)

    def open_cad_patch_dialog(self):
        """#8: pop-up that lists ALL edges of the active geometry (like the
        Mesh Generator's segment-BC dialog) so the user can see every edge,
        (multi-)select the ones to tag, and assign a free-form patch/group
        label. The physical BC is chosen per group later in the Mesh Generator.
        Pre-selects the edges already selected on the canvas."""
        from PyQt6.QtWidgets import QDialog
        from app.views.panels.mesh_dialogs import AssignPatchDialog
        session = self.active_session()
        if not session:
            return
        segs = session.project_model.segments
        if not segs:
            self.log("No edges to assign a patch/group to.")
            return

        edges = []
        existing = []
        for i, seg in enumerate(segs):
            label = (getattr(seg, "bc", "") or "").strip()
            kind = getattr(seg, "type", "") or ""
            edges.append((i, label, kind))
            if label and label not in existing:
                existing.append(label)

        preselect = self.get_selected_segment_indices()
        highlight = self._patch_highlighter(session)

        def _apply(indices, name):
            self._apply_bc_to_indices(session, indices, name)
            shown = name or "(cleared)"
            self.log(
                f"Assigned patch/group '{shown}' to {len(indices)} edge(s).")

        dlg = AssignPatchDialog(session.display_name, edges, existing,
                                preselect=preselect, highlight_cb=highlight,
                                apply_cb=_apply, parent=self.main_window)
        from app.utils import offset_popup
        offset_popup(dlg, self.main_window)
        accepted = dlg.exec() == QDialog.DialogCode.Accepted
        # Drop the temporary multi-edge highlight the dialog painted.
        self.main_window.canvas_view.update_active_segments([], -1)
        if not accepted:
            return
        indices = dlg.selected_indices()
        if not indices:
            # OK with nothing selected: any Apply during the session already took
            # effect, so this is a no-op, not an error.
            return
        _apply(indices, dlg.patch_name())

    def _patch_highlighter(self, session):
        """Return a callback(indices) that highlights those edges on the CAD
        canvas while the assign-patch dialog selection changes (#8)."""
        canvas = self.main_window.canvas_view
        segs = session.project_model.segments

        def _hl(indices):
            ranges = []
            for i in indices:
                if 0 <= i < len(segs):
                    s = segs[i]
                    start = getattr(s, "start_index", None)
                    end = getattr(s, "end_index", None)
                    if start is not None and end is not None:
                        ranges.append((start, end))
            canvas.update_active_segments(ranges, 0 if ranges else -1)
        return _hl

    def handle_closed_mode_changed(self, text: str):
        session = self.active_session()
        if not session:
            return
        mode = _CLOSED_MODE_BY_TEXT.get(text)
        if mode is None or session.project_model.closed_mode == mode:
            return

        def refresh():
            self._sync_closed_mode_ui(session)
            self._apply_geometry_update(session)
        cmd = SetClosedModeCmd(session, mode, refresh)
        session.command_history.execute(cmd)

    def _sync_closed_mode_ui(self, session):
        """Reflect the session's closed_mode in the sidebar combo, and show the
        resolved state ("→ Closed"/"→ Open") next to it while in Auto mode."""
        pm = session.project_model
        sb = self.main_window.sidebar_view
        status = "→ Closed" if pm.is_closed else "→ Open"
        sb.set_closure_mode(
            _CLOSED_TEXT_BY_MODE.get(pm.closed_mode, "Auto"),
            status if pm.closed_mode == "auto" else "")

    def handle_global_spline_changed(self, checked: bool):
        session = self.active_session()
        if session:
            if session.project_model.global_spline != checked:
                def refresh():
                    sb = self.main_window.sidebar_view
                    sb.set_global_spline(session.project_model.global_spline)
                    self._apply_geometry_update(session)
                cmd = ToggleGlobalSplineCmd(session, checked, refresh)
                session.command_history.execute(cmd)
