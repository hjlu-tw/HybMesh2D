from __future__ import annotations
from app.commands.segment_cmds import (
    AddCurveSegmentCmd, UpdateSegmentStateCmd)


class PendingEditControllerMixin:
    def _on_pending_dialog_changed(self, params, n_points):
        """The numeric dialog changed → update the pending edge, reposition the
        canvas control points, and refresh the preview (live, req 1)."""
        seg = self._pending_seg
        if seg is None:
            return
        seg.parameters.update(params)
        seg.parameters["n_points"] = n_points
        # #1: a polygon switched back to By Node Count no longer sends 'spacing';
        # clear any stale key so the backend uses the node count (mirrors the
        # sidebar's _sync_active_curve_segment_from_ui).
        if getattr(seg, "curve_type", "") == "polygon" and "spacing" not in params:
            seg.parameters.pop("spacing", None)
        # The polygon dialog's open/closed toggle lives outside `params`; mirror
        # it onto the segment so the live preview honours it immediately.
        dlg = self._pending_dialog
        if dlg is not None and hasattr(dlg, "is_closed") \
                and getattr(seg, "curve_type", "") == "polygon":
            seg.closed = dlg.is_closed()
        self._show_pending_handles()
        self._preview_pending()

    def _record_segment_state_edit(self, session, seg, old_state, refresh_cb=None):
        """Record an in-place edit of an existing segment so it is undoable.

        ``old_state`` is ``seg.to_dict()`` captured BEFORE the edit; the edit has
        already been applied in place, so the command is *recorded* (not executed)
        — which also clears the redo stack. Returns True if a command was pushed.
        """
        if seg is None or session is None or old_state is None:
            return False
        segs = session.project_model.segments
        try:
            idx = segs.index(seg)
        except ValueError:
            # The pending segment object was orphaned (e.g. an intervening
            # undo deep-copied the list). Fall back to a stable id match so the
            # edit is still recorded rather than silently dropped.
            idx = next((i for i, s in enumerate(segs) if s.id == seg.id), -1)
            if idx < 0:
                self.main_window.log_panel.log(
                    "Edit not recorded: the edge is no longer present.")
                return False
            seg = segs[idx]
        new_state = seg.to_dict()
        if new_state == old_state:
            return False
        if refresh_cb is None:
            refresh_cb = self._refresh_segment_list
        cmd = UpdateSegmentStateCmd(session, idx, old_state, new_state,
                                    refresh_cb=refresh_cb)
        session.command_history.record(cmd)
        return True

    def _commit_pending_edge(self):
        seg = self._pending_seg
        is_new = self._pending_is_new
        orig_state = self._pending_orig_state
        session = self.active_session()
        self._clear_pending_state()
        if seg is None or not session:
            return
        if is_new:
            cmd = AddCurveSegmentCmd(
                session,
                refresh_cb=self._refresh_segment_list,
                select_cb=self._select_segment_by_index,
                preconfigured_seg=seg,
            )
            session.command_history.execute(cmd)
            self.main_window.log_panel.log(f"Added {seg.curve_type} Edge {seg.id}.")
        else:
            # Editing an existing edge: params were mutated in place — record the
            # change (undoable) then redraw and reselect it.
            self._record_segment_state_edit(session, seg, orig_state)
            self._refresh_segment_list()
            try:
                self._select_segment_by_index(
                    session.project_model.segments.index(seg))
            except ValueError:
                pass
            self.main_window.log_panel.log(f"Updated {seg.curve_type} Edge {seg.id}.")
        session.is_geometry_modified = True
        self.main_window.update_title(session.display_name, True)

    def _cancel_pending_edit(self):
        seg = self._pending_seg
        is_new = self._pending_is_new
        orig = self._pending_orig
        orig_state = self._pending_orig_state
        self._clear_pending_state()
        if (not is_new) and seg is not None and orig is not None:
            # Restore the edited edge's original shape (incl. the open/closed
            # flag the polygon dialog may have toggled).
            seg.parameters = orig
            if orig_state is not None and hasattr(seg, "closed"):
                seg.closed = bool(orig_state.get("closed", True))
            self._refresh_segment_list()
            self.main_window.log_panel.log("Edit cancelled (reverted).")
        else:
            self.main_window.log_panel.log("Add edge cancelled.")

    def _clear_pending_state(self):
        session = self.active_session()
        canvas = self.main_window.canvas_view
        self._pending_seg = None
        self._pending_dialog = None
        self._pending_is_new = True
        self._pending_orig = None
        self._pending_orig_state = None
        canvas.clear_edge_handles()
        if session is not None:
            canvas.clear_curve_preview(session.session_id)
        # Restore the always-on endpoint markers for the remaining edges.
        self._refresh_endpoint_markers()
