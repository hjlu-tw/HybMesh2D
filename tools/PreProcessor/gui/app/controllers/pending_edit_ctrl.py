from __future__ import annotations
from app.commands.segment_cmds import (
    AddCurveSegmentCmd, UpdateSegmentStateCmd)
from app.services.logging_setup import get_logger

logger = get_logger(__name__)

# ``confirm`` is imported inside the two prompt helpers, not here. This module's
# commit/cancel path is deliberately drivable with no Qt at all — that is what
# tests/test_edge_edit_owner.py exercises, and it is how the lifecycle stopped
# needing a canvas and a dialog to be reasoned about. A module-level
# ``from app.utils import confirm`` pulls in PyQt6 and ends that; session_tabs_ctrl
# imports it inside close_tab for its own reasons and sets the precedent.


class PendingEditControllerMixin:
    # ── The "at most one edit is live" invariant, at the Qt boundary ──────
    def _make_way_for_edit(self) -> bool:
        """Clear the way for a new edit. False means: do not begin one.

        The six ``_edit_in_progress()`` guards fire first and are unchanged;
        this is reached only by the routes they do not block. The owner REFUSES
        to begin while another edit is live — overwriting its snapshots is how a
        later Cancel restores the wrong shape — so the live one has to be ended
        deliberately, and that is a question for the user rather than a decision
        for a Qt-free module.
        """
        if not self.edge_edit.is_active():
            return True
        from app.utils import confirm
        # headless_default True: a batch run must not stall on this, and
        # cancelling is the same answer it gives everywhere else.
        if not confirm(self.main_window, "An edit is already open",
                       "Cancel the edit in progress and start this one?",
                       headless_default=True):
            self.log("An edit is already open — the new one was not started.")
            return False
        self._cancel_live_edit()
        return True

    def _cancel_live_edit(self):
        """Cancel whichever edit kind is live, through its own Cancel path."""
        if self.edge_edit.is_shape_active():
            self._cancel_file_edit()
        elif self.edge_edit.is_active():
            self._cancel_pending_edit()

    def _release_edits_for_session(self, session, what: str) -> bool:
        """A CAD session is being left (switched away from, or closed).

        Returns False to ABORT the switch/close. An edit belongs to the session
        it began in, so leaving that session must end it — otherwise the commit
        that arrives afterwards targets a tab the user is no longer looking at.
        A live DRAG is dropped silently: it holds only the snapshot that would
        have made the gesture undoable, and a gesture the user walked away from
        should record nothing.
        """
        if self.edge_edit.release_drag_for(session):
            logger.debug("dropped a live handle drag on the session being left")
        if not self.edge_edit.belongs_to(session):
            return True
        from app.utils import confirm
        if not confirm(self.main_window, "Edit in progress",
                       f"An edge edit is in progress. Cancel it and {what}?",
                       headless_default=True):
            self.log(f"Kept the edit in progress — did not {what}.")
            return False
        self._cancel_live_edit()
        return True

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
        done = self.edge_edit.commit()
        if done is None:
            # A dialog signal arriving after the state was cleared. Not
            # something the user did, so no pop-up and no user-log line.
            logger.debug("commit with no edit live — ignored")
            return
        self._clear_pending_canvas()
        # The session the edit BEGAN in, never active_session(): resolving the
        # target through whichever tab is in front now is how an edit came to
        # land on another tab's edge (segment ids are per-session, so the id
        # fallback matched).
        session = done.session or self.active_session()
        if not session:
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
            self.log(f"Updated {seg.curve_type} Edge {seg.id}.")
        session.is_geometry_modified = True
        # The list, the selection and the window title all describe the tab in
        # FRONT. When the edit's own session is not that tab, updating them
        # would relabel someone else's geometry with this one's name.
        if session is self.active_session():
            self._refresh_segment_list()
            if not is_new:
                try:
                    self._select_segment_by_index(
                        session.project_model.segments.index(seg))
                except ValueError:
                    pass
            self.main_window.update_title(session.display_name, True)

    def _cancel_pending_edit(self):
        # The owner restores the shape (params + the polygon open/closed flag);
        # what is left here is the canvas and what the user is told.
        done = self.edge_edit.cancel()
        if done is None:
            logger.debug("cancel with no edit live — ignored")
            return
        self._clear_pending_canvas()
        if done.reverted:
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
