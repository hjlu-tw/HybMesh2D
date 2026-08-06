from __future__ import annotations
import os
import copy
from PyQt6.QtWidgets import QTreeWidgetItem
from PyQt6.QtCore import Qt
from app.commands.segment_cmds import RemoveSegmentCmd
from app.utils import CURVE_TYPE_LABELS, block_signals

class SegmentControllerMixin:
    """Mixin containing edge segment, break point (split), and properties management logic."""

    def get_selected_segment_indices(self) -> list[int]:
        session = self.active_session()
        if not session:
            return []
        sb = self.main_window.sidebar_view
        indices = list(sb.geometry_tree.selected_edge_indices())
        if not indices and getattr(session, 'current_segment_idx', -1) >= 0:
            indices.append(session.current_segment_idx)
        return sorted(set(indices))

    def _update_join_button(self, selected_indices):
        """Enable "Join → Polygon" once ≥2 JOINABLE edges are selected
        (selection-driven, like "Remove Edge").

        "Joinable" must match what ``join_selected_edges_to_polygon`` actually
        accepts — both analytic ``curve`` edges (incl. arcs) AND discrete
        ``file`` edges (e.g. a rectangle after "split at corners" becomes file
        edges). Counting only ``curve`` here left the button greyed out for the
        common arc + split-rectangle case even though the join would succeed."""
        sb = self.main_window.sidebar_view
        session = self.active_session()
        if not session:
            sb.join_edges_btn.setEnabled(False)
            return
        pm = session.project_model
        n_joinable = sum(1 for i in selected_indices
                         if pm.get_segment(i)
                         and pm.get_segment(i).type in ("curve", "file"))
        sb.join_edges_btn.setEnabled(n_joinable >= 2)

    def _refresh_segment_list(self, clear_resampled: bool = True):
        session = self.active_session()
        if not session:
            return
        # Keep edge ids contiguous 1..N (no gaps / no 10001 jump) after any
        # structural change. This is the single rebuild chokepoint.
        session.project_model.renumber_segments()
        sb = self.main_window.sidebar_view
        tree = sb.geometry_tree

        # Save currently selected segment indices
        selected_indices = list(tree.selected_edge_indices())

        # Fallback to session.current_segment_idx if list has no selection
        if not selected_indices and getattr(session, 'current_segment_idx', -1) >= 0:
            selected_indices = [session.current_segment_idx]

        self._is_refreshing_list = True
        try:
            with block_signals(tree):
                # Edges only ever live under the active session node; clearing every
                # node first guarantees no stale children survive a tab switch.
                tree.clear_all_edges()
                node = tree.session_item(session.session_id)
                primary_child = None
                if node is not None:
                    for idx, seg in enumerate(session.project_model.segments):
                        if seg.type == "curve":
                            c_type = getattr(seg, "curve_type", "custom")
                            lbl_val = CURVE_TYPE_LABELS.get(c_type, c_type.capitalize())
                            c_label = lbl_val(seg) if callable(lbl_val) else lbl_val
                            lbl = f"Edge {seg.id}: {c_label}"
                        else:
                            lbl = (f"Edge {seg.id}: "
                                   f"Idx {seg.start_index} → {seg.end_index}")
                        child = QTreeWidgetItem([lbl])
                        child.setData(0, Qt.ItemDataRole.UserRole,
                                      ("edge", session.session_id, idx))
                        node.addChild(child)
                        if idx in selected_indices:
                            child.setSelected(True)
                            if idx == session.current_segment_idx:
                                primary_child = child
                    # Only auto-expand when an edge is actually selected (e.g. picked
                    # on the canvas), so it stays visible. Plain layer/geometry
                    # selection leaves the node's expand state alone — the user
                    # expands it with the disclosure arrow when they want to.
                    if selected_indices:
                        node.setExpanded(True)
                # Make the primary edge the current item so a later layer-row resync
                # (_sync_geometry_list) sees an edge is selected and leaves it alone.
                if primary_child is not None:
                    tree.setCurrentItem(primary_child)

            if selected_indices:
                if session.current_segment_idx not in selected_indices:
                    session.current_segment_idx = selected_indices[0]
                sb.remove_seg_btn.setEnabled(True)
                sb.show_segment_props(True)
                active_seg = session.project_model.get_segment(session.current_segment_idx)
                if active_seg:
                    if active_seg.type == "file":
                        self.main_window.canvas_view.update_active_segment(
                            active_seg.start_index, active_seg.end_index)
                        self.main_window.canvas_view.set_active_geometry_dimmed(session.session_id, True)
                        self.main_window.canvas_view.clear_curve_preview(session.session_id)
                    else:
                        self.main_window.canvas_view.update_active_segment(None, None)
                        self.main_window.canvas_view.set_active_geometry_dimmed(session.session_id, False)
                        self.main_window.canvas_view.clear_curve_preview(session.session_id)
            else:
                session.current_segment_idx = -1
                sb.remove_seg_btn.setEnabled(False)
                sb.show_segment_props(False)
                self.main_window.canvas_view.update_active_segment(None, None)
                self.main_window.canvas_view.clear_curve_preview(session.session_id)

            self._update_join_button(selected_indices)
            self._update_canvas_curve_segments()
            if clear_resampled:
                session.resampled_points = None
                self.main_window.canvas_view.clear_resampled()
        finally:
            self._is_refreshing_list = False


    def _sync_sidebar_to_session(self):
        session = self.active_session()
        sb = self.main_window.sidebar_view
        if not session:
            self._clear_sidebar()
            return

        pm = session.project_model

        # File label
        if session.file_path:
            sb.file_name_label.setText(
                f"File: {os.path.basename(session.file_path)}")
            sb.file_name_label.setStyleSheet(
                "color: #dde6ff; font-weight: bold; margin-bottom: 5px;")
        else:
            sb.file_name_label.setText("No geometry imported")
            sb.file_name_label.setStyleSheet(
                "color: #6a7aaa; font-style: italic; margin-bottom: 5px;")

        # Closure mode (Auto/Closed/Open) + resolved-state hint.
        self._sync_closed_mode_ui(session)

        # Advanced
        with block_signals(sb.global_spline_cb):
            sb.global_spline_cb.setChecked(pm.global_spline)
        sb.set_transform_from_dict(pm.transform)

        # Selection state
        sb.selected_info.setText("Selected Vertex: None")
        sb.split_btn.setEnabled(False)
        sb.remove_split_btn.setEnabled(False)

        self._refresh_segment_list(clear_resampled=False)
        self._sync_geometry_list()

        # NOTE: The Mesh Generator page is intentionally decoupled from the
        # active CAD tab. It is driven solely by the shared `global_mesh_config`
        # (populated via the Geometry Layers list), so that several CAD
        # geometries can be combined into a single mesh. Switching CAD tabs must
        # therefore NOT overwrite the mesh config / stats / canvas. We only keep
        # the Geometry Layers list in sync so newly added or renamed sessions
        # appear there.
        if hasattr(self.main_window, "mesh_config_panel"):
            self.sync_mesh_layers_panel()

    def _clear_sidebar(self):
        sb = self.main_window.sidebar_view
        sb.file_name_label.setText("No geometry imported")
        sb.geometry_tree.clear_all_edges()
        sb.selected_info.setText("Selected Vertex: None")
        sb.split_btn.setEnabled(False)
        sb.remove_split_btn.setEnabled(False)
        sb.remove_seg_btn.setEnabled(False)
        sb.join_edges_btn.setEnabled(False)
        sb.show_segment_props(False)
        self._sync_geometry_list()

        # The Mesh Generator page is driven by `global_mesh_config`, not by CAD
        # tabs, so closing all CAD tabs must not wipe the mesh configuration or
        # results. Only refresh the Geometry Layers list (now empty).
        if hasattr(self.main_window, "mesh_config_panel"):
            self.sync_mesh_layers_panel()

    def _clear_cad_selection(self):
        """Clear both edge and vertex selection (lists, session state, canvas
        overlays). Used when switching the canvas edit mode so a stale highlight
        from the previous mode is not left displayed."""
        session = self.active_session()
        if not session:
            return
        sb = self.main_window.sidebar_view

        # Clear edge selection without re-triggering selection handlers
        tree = sb.geometry_tree
        with block_signals(tree):
            tree.clear_edge_selection()
        sb.curve_bake_btn.setEnabled(False)
        sb.join_edges_btn.setEnabled(False)

        # Clear edge highlight + active segment state
        self.handle_segment_selected(-1)
        self.main_window.canvas_view.update_active_segments([])
        self.main_window.canvas_view.set_active_geometry_dimmed(session.session_id, False)

        # Clear vertex selection
        self.handle_point_deselected()

    def handle_segment_list_selected(self, *args):
        """Selection handler for the model tree (wired to itemSelectionChanged).

        Acts only on selected edge rows: determines the active edge, enables the
        Convert-to-Discrete button for analytic edges, and refreshes highlights.
        Selecting a layer row (no edges) clears the edge selection/properties."""
        if getattr(self, "_is_refreshing_list", False):
            return
        sb = self.main_window.sidebar_view
        tree = sb.geometry_tree
        sel_edges = tree.selected_edge_items()
        if not sel_edges:
            sb.curve_bake_btn.setEnabled(False)
            self.handle_segment_selected(-1)
            self.main_window.canvas_view.update_active_segments([])
            return

        cur = tree.currentItem()
        if tree.kind(cur) != "edge":
            cur = sel_edges[0]
        idx = tree.edge_index(cur)
        session = self.active_session()
        seg = session.project_model.get_segment(idx) if session else None
        sb.curve_bake_btn.setEnabled(bool(seg and seg.type == "curve"))
        self.handle_segment_selected(idx)
        self.highlight_selected_segments()

    def _select_segment_by_index(self, index: int):
        sb = self.main_window.sidebar_view
        tree = sb.geometry_tree
        if index < 0:
            with block_signals(tree):
                tree.clear_edge_selection()
            sb.curve_bake_btn.setEnabled(False)
            self.handle_segment_selected(-1)
            return

        session = self.active_session()
        if not session or index >= len(session.project_model.segments):
            return

        seg = session.project_model.segments[index]
        item = tree.edge_item_by_index(session.session_id, index)
        # Single-select: drop any prior (e.g. box) selection so only `index`
        # remains highlighted.
        with block_signals(tree):
            tree.clear_edge_selection()
            if item is not None:
                item.setSelected(True)
                tree.setCurrentItem(item)
        sb.curve_bake_btn.setEnabled(seg.type == "curve")

        self.handle_segment_selected(index)
        # Highlight the selected edge (file or curve) and dim the rest.
        self.highlight_selected_segments()

    def handle_segment_selected(self, row: int):
        session = self.active_session()
        if not session:
            return
        sb = self.main_window.sidebar_view
        if row < 0:
            self.main_window.canvas_view.update_active_segment(None, None)
            self.main_window.canvas_view.update_active_segments_pts([])
            self.main_window.canvas_view.set_active_geometry_dimmed(session.session_id, False)
            self.main_window.canvas_view.clear_curve_preview(session.session_id)
            self.main_window.canvas_view.clear_duplicate_preview()
            self.main_window.canvas_view.clear_transform_handles()
            self.main_window.canvas_view.clear_edge_handles()
            self._show_duplicate_preview = False
            session.current_segment_idx = -1
            sb.remove_seg_btn.setEnabled(False)
            sb.show_segment_props(False)
            return

        session.current_segment_idx = row
        seg = session.project_model.get_segment(row)
        if not seg:
            self.main_window.canvas_view.update_active_segment(None, None)
            self.main_window.canvas_view.clear_curve_preview(session.session_id)
            self.main_window.canvas_view.clear_transform_handles()
            self._show_duplicate_preview = False
            sb.remove_seg_btn.setEnabled(False)
            sb.show_segment_props(False)
            return

        # Highlight on canvas
        if seg.type == "file":
            self.main_window.canvas_view.update_active_segment(
                seg.start_index, seg.end_index)
            self.main_window.canvas_view.set_active_geometry_dimmed(session.session_id, True)
            self.main_window.canvas_view.clear_curve_preview(session.session_id)
        else:
            self.main_window.canvas_view.update_active_segment(None, None)
            self.main_window.canvas_view.set_active_geometry_dimmed(session.session_id, False)

        # Enable remove segment button for both file and curve segments
        sb.remove_seg_btn.setEnabled(True)

        # Populate sidebar
        # The canvas cleanup below stays in a finally: it must run even if
        # populating raises, or a stale duplicate-preview line is left on screen.
        try:
            with self.populating():
                sb.show_segment_props(True)
                is_curve = (seg.type == "curve")
                if is_curve:
                    lbl_val = CURVE_TYPE_LABELS.get(seg.curve_type, seg.curve_type.capitalize())
                    shape = lbl_val(seg) if callable(lbl_val) else lbl_val
                    sb.segment_type_label.setText(f"Edge {seg.id}  ·  Analytic ({shape})")
                    sb.show_curve_segment(seg)
                    sb.strategy_combo.setVisible(False)
                    sb.param_stack.setVisible(False)
                else:
                    sb.segment_type_label.setText(f"Edge {seg.id}  ·  Discrete")
                    sb.show_file_segment(seg.start_index, seg.end_index)
                    sb.strategy_combo.setVisible(True)
                    sb.param_stack.setVisible(True)
                    with block_signals(sb.strategy_combo):
                        sb.strategy_combo.setCurrentText(seg.strategy)
                    sb.switch_param_form(seg.strategy)
                    self._populate_form_from_segment(seg)

                # Show transform duplicate group for all segments
                sb._transform_dup_group.setVisible(True)

                with block_signals(sb.match_previous_cb):
                    sb.match_previous_cb.setChecked(seg.match_previous)

                # (#1) The per-edge patch/group name is now assigned via a pop-up
                # (open_cad_patch_dialog), so there is no inline field to populate here.

                # Update base point values
                self.update_duplicate_base_point()
                self._show_duplicate_preview = False

                # Snapshot params for undo
                session.param_snapshot = copy.deepcopy(seg.parameters)
                session.segment_state_snapshot = copy.deepcopy(seg.to_dict())
        finally:
            self.main_window.canvas_view.clear_duplicate_preview()

        # Show the draggable base-point / axis handle for the selected edge.
        self._refresh_transform_handles()

        self._update_canvas_curve_segments()
        if seg.type == "curve":
            self.preview_curve_formula()
        # Show draggable control-point handles for an analytic shape edge.
        self._refresh_edge_handles()
        # Keep the distribution preview in sync if its window is open.
        self._preview_distribution()


    # ── Distribution tool window + live canvas preview ──────────────────────

    def remove_selected_segment(self):
        session = self.active_session()
        if not session:
            return
        idx = session.current_segment_idx
        if idx < 0 or idx >= len(session.project_model.segments):
            return
        seg = session.project_model.segments[idx]

        cmd = RemoveSegmentCmd(session, idx, self._on_segment_removed)
        session.command_history.execute(cmd)
        self.main_window.log_panel.log(f"Removed Edge {seg.id}.")

    def _on_segment_removed(self):
        session = self.active_session()
        if not session:
            return
        # Drop the (removed) selection and rebuild via the canonical redraw so no
        # stray highlight (_multi_segment_curves) or control-point handle lingers.
        session.current_segment_idx = -1
        self.main_window.sidebar_view.geometry_tree.clear_edge_selection()
        self._refresh_segment_list()
        self._sync_geometry_list()
        self.redraw_canvas(announce=False)
        session.is_geometry_modified = True
        self.main_window.update_title(session.display_name, session.is_geometry_modified)
