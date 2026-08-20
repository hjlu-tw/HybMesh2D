from __future__ import annotations
from app.commands.segment_cmds import (
    AddCurveSegmentCmd, UpdateSegmentStateCmd)


class PendingEditControllerMixin:
    def _on_pending_dialog_changed(self, params, n_points):
        """The numeric dialog changed → update the pending edge, reposition the
        canvas control points, and refresh the preview (live, req 1).

        The open/closed toggle lives outside ``params`` and is the one thing the
        owner has to be TOLD rather than read from the dialog itself — it holds
        the dialog opaquely, so asking it is this layer's job."""
        dlg = self.edge_edit.dialog
        closed = dlg.is_closed() if (dlg is not None
                                     and hasattr(dlg, "is_closed")) else None
        if not self.edge_edit.update(params, n_points, closed=closed):
            return
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
                self.log(
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
        session = self.active_session()
        done = self.edge_edit.commit()
        self._clear_pending_canvas()
        if done is None or not session:
            return
        seg, is_new, orig_state = done.seg, done.is_new, done.orig_state
        if is_new:
            cmd = AddCurveSegmentCmd(
                session,
                refresh_cb=self._refresh_segment_list,
                select_cb=self._select_segment_by_index,
                preconfigured_seg=seg,
            )
            session.command_history.execute(cmd)
            self.log(f"Added {seg.curve_type} Edge {seg.id}.")
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
            self.log(f"Updated {seg.curve_type} Edge {seg.id}.")
        session.is_geometry_modified = True
        self.main_window.update_title(session.display_name, True)

    def _cancel_pending_edit(self):
        # The owner restores the shape (params + the polygon open/closed flag);
        # what is left here is the canvas and what the user is told.
        done = self.edge_edit.cancel()
        self._clear_pending_canvas()
        if done is not None and done.reverted:
            self._refresh_segment_list()
            self.log("Edit cancelled (reverted).")
        else:
            self.log("Add edge cancelled.")

    def _clear_pending_canvas(self):
        """Drop the edit session's canvas decoration. The state itself is the
        owner's and is already gone by the time this runs."""
        session = self.active_session()
        canvas = self.main_window.canvas_view
        canvas.clear_edge_handles()
        if session is not None:
            canvas.clear_curve_preview(session.session_id)
        # Restore the always-on endpoint markers for the remaining edges.
        self._refresh_endpoint_markers()
