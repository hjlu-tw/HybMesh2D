"""Distribution tool + spacing/strategy form logic for AppController, split out
of segment_ctrl as a sibling mixin (behaviour unchanged): the point-distribution
dialog (open/apply/preview/restore), strategy-combo handling, and the model<->form
parameter bridge. Composed into AppController alongside SegmentControllerMixin;
resolves through the shared flat self (active_session, main_window,
_apply_geometry_update, and the _is_populating guard owned by AppController.__init__)."""
from __future__ import annotations
import numpy as np
from app.models.segment import SegmentModel
from app.models.distribution_spec import DistributionSpec
from app.commands.segment_cmds import UpdateMultipleSegmentsStateCmd
from app.services.geometry_service import GeometryService


class SegmentDistributionControllerMixin:
    """Point-distribution dialog + strategy/param form (moved from SegmentControllerMixin)."""

    def handle_strategy_changed(self, strategy_name: str):
        session = self.active_session()
        if not session:
            return
        if self._is_populating:
            return

        sb = self.main_window.sidebar_view
        sb.switch_param_form(strategy_name)

        indices = self._distribution_indices_or_selection()
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
                seg.strategy = strategy_name
                self._read_params_into_segment(seg)

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
                    self._apply_geometry_update(session)
                    if session.current_segment_idx >= 0:
                        self._repopulate_strategy(strategy_name)
            cmd = UpdateMultipleSegmentsStateCmd(session, states_dict, refresh_cb=refresh)
            session.command_history.execute(cmd)
            self.log(
                f"Updated strategy to '{strategy_name}' for {len(indices)} selected edges."
            )
        # Refresh the live distribution preview (if its window is open).
        self._preview_distribution()

    def _repopulate_strategy(self, strategy_name: str):
        session = self.active_session()
        if not session:
            return
        seg = session.project_model.get_segment(session.current_segment_idx)
        if seg:
            self._populate_form_from_segment(seg)
        self.main_window.sidebar_view.switch_param_form(strategy_name)

    def _distribution_indices_or_selection(self):
        """#3: distribution / node-count edits apply to EVERY selected *discrete*
        (type=='file') edge, so a multi-edge selection is edited together. When
        only one edge is selected this is just that edge.

        Non-file edges (polygon/curve) are excluded: _read_params_into_segment
        REPLACES seg.parameters with the distribution keys, which would wipe a
        co-selected polygon's vertices_str (geometry data loss).
        Mirrors the type=='file' guard in _apply_distribution."""
        session = self.active_session()
        if not session:
            return []
        return [i for i in self.get_selected_segment_indices()
                if session.project_model.get_segment(i)
                and session.project_model.get_segment(i).type == "file"]

    def _open_distribution(self):
        self.main_window.sidebar_view.open_distribution_dialog()
        self._preview_distribution()

    def _apply_distribution(self):
        """Apply button: commit the current distribution settings to ALL selected
        discrete edges (#3) and show the current edge's resampled preview."""
        session = self.active_session()
        if not session:
            return
        indices = [i for i in self.get_selected_segment_indices()
                   if session.project_model.get_segment(i)
                   and session.project_model.get_segment(i).type == "file"]
        if not indices:
            self.log(
                "Select one or more discrete edges to apply their distribution.")
            return
        old_states = {}
        for idx in indices:
            seg = session.project_model.get_segment(idx)
            if seg:
                old_states[idx] = seg.to_dict()
        for idx in indices:
            seg = session.project_model.get_segment(idx)
            if seg:
                self._read_params_into_segment(seg)
        states_dict = {}
        any_changed = False
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
                    self._apply_geometry_update(session)
            cmd = UpdateMultipleSegmentsStateCmd(session, states_dict, refresh_cb=refresh)
            session.command_history.execute(cmd)
            session.is_geometry_modified = True
            self.main_window.update_title(session.display_name, True)
        self._preview_distribution()
        self.log(
            f"Applied distribution to {len(indices)} edge(s).")

    def _preview_distribution(self):
        """Live-render the chosen point distribution of the CURRENT discrete edge
        onto the canvas while the Distribution window is open."""
        session = self.active_session()
        if not session:
            return
        if not self.main_window.sidebar_view.distribution_tool_visible():
            return
        seg = session.project_model.get_segment(session.current_segment_idx)
        if not seg or seg.type != "file":
            self.main_window.canvas_view.clear_resampled()
            return
        pts = GeometryService.get_segment_points(session, seg)
        if pts is None or len(pts[0]) < 2:
            self.main_window.canvas_view.clear_resampled()
            return
        rx, ry = GeometryService.resample_preview(
            pts[0], pts[1], seg.strategy, seg.parameters)
        if rx is None or len(rx) == 0:
            self.main_window.canvas_view.clear_resampled()
            return
        self.main_window.canvas_view.load_resampled_data(np.column_stack([rx, ry]))

    def _restore_resampled_after_distribution(self):
        """When the Distribution tool closes, keep resampled nodes on the canvas
        (previously it blanked them, so the 'Nodes' toggle showed nothing after
        closing). If the session has a persistent full-geometry preview (from the
        last Preview) restore that; otherwise leave the dialog's last live
        preview in place rather than clearing it."""
        session = self.active_session()
        if session is not None and session.resampled_points is not None:
            mode = self.main_window.quality_mode_combo.currentText().lower()
            self.main_window.canvas_view.load_resampled_data(
                session.resampled_points,
                self.main_window.quality_check_cb.isChecked(), mode,
                gap_indices=getattr(session, "resampled_gaps", None))
        # else: leave the last live preview visible (do not clear).

    def _populate_form_from_segment(self, seg: SegmentModel):
        self.main_window.sidebar_view.show_distribution_spec(
            DistributionSpec.from_parameters(seg.strategy, seg.parameters))

    def update_segment_params(self):
        session = self.active_session()
        if not session:
            return
        if self._is_populating:
            return
        indices = self._distribution_indices_or_selection()
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
                self._read_params_into_segment(seg)

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
                    self._apply_geometry_update(session)
            cmd = UpdateMultipleSegmentsStateCmd(session, states_dict, refresh_cb=refresh)
            session.command_history.record(cmd)
            if session.current_segment_idx in old_states:
                session.segment_state_snapshot = states_dict[session.current_segment_idx][1]
        # Live distribution preview (no-op unless the Distribution window is open).
        self._preview_distribution()

    def _read_params_into_segment(self, seg: SegmentModel):
        """Replace the segment's parameters with what the distribution form says.

        Both halves of this used to live here: reading thirteen widgets by name,
        AND the resampler contract that decides which keys the dict may carry.
        The contract is now in DistributionSpec, where it is testable without a
        QApplication; this method is the two-line join between the form and the
        model. Assigning a fresh dict (rather than clearing and re-inserting) is
        what stops a key from the previous strategy surviving a strategy change.
        """
        spec = self.main_window.sidebar_view.distribution_spec(seg.strategy)
        seg.parameters = spec.to_parameters()
