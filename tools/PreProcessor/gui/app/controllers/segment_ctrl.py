from __future__ import annotations
import os
import math
import copy
import numpy as np
from PyQt6.QtWidgets import QTreeWidgetItem
from PyQt6.QtCore import Qt
from app.models.segment import SegmentModel
from app.models.session import GeometrySession
from app.commands.split_cmds import AddSplitCmd, RemoveSplitCmd, AutoDetectSplitCmd
from app.commands.vertex_cmds import InsertVertexCmd
from app.commands.segment_cmds import (
    UpdateStrategyCmd, ToggleIsClosedCmd, ToggleGlobalSplineCmd, ToggleMatchPreviousCmd, UpdateSegmentStateCmd, UpdateMultipleSegmentsStateCmd,
    CreateSegmentsFromIndicesCmd, RemoveSegmentCmd
)
from app.services.geometry_service import GeometryService
from app.utils import CURVE_TYPE_LABELS

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
            tree.blockSignals(True)
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
                node.setExpanded(True)
            # Make the primary edge the current item so a later layer-row resync
            # (_sync_geometry_list) sees an edge is selected and leaves it alone.
            if primary_child is not None:
                tree.setCurrentItem(primary_child)
            tree.blockSignals(False)

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

        # is_closed
        sb.is_closed_combo.blockSignals(True)
        sb.is_closed_combo.setCurrentText(str(pm.is_closed))
        sb.is_closed_combo.blockSignals(False)

        # Advanced
        sb.global_spline_cb.blockSignals(True)
        sb.global_spline_cb.setChecked(pm.global_spline)
        sb.global_spline_cb.blockSignals(False)
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
        tree.blockSignals(True)
        tree.clear_edge_selection()
        tree.blockSignals(False)
        sb.curve_bake_btn.setEnabled(False)

        # Clear edge highlight + active segment state
        self.handle_segment_selected(-1)
        self.main_window.canvas_view.update_active_segments([])
        self.main_window.canvas_view.set_active_geometry_dimmed(session.session_id, False)

        # Clear vertex selection
        self.handle_point_deselected()

    def handle_point_clicked(self, idx: int):
        session = self.active_session()
        if not session:
            return
        session.selected_point_idx = idx
        self.main_window.canvas_view.update_selected_point(idx)

        sb = self.main_window.sidebar_view
        sb.selected_info.setText(f"Selected Vertex: Index {idx}")

        n_pts = (len(session.original_points)
                 if session.original_points is not None else 0)
        is_closed = session.project_model.is_closed
        is_endpoint = (idx == 0 or idx == n_pts - 1) if not is_closed else False
        is_split = idx in session.split_indices

        sb.split_btn.setEnabled(not is_split)
        sb.remove_split_btn.setEnabled(is_split and not is_endpoint)

    def handle_point_deselected(self):
        """Clear vertex selection when user clicks far from all vertices."""
        session = self.active_session()
        if not session:
            return
        session.selected_point_idx = None
        self.main_window.canvas_view.update_selected_point(None)

        sb = self.main_window.sidebar_view
        sb.selected_info.setText("Selected Vertex: None")
        sb.split_btn.setEnabled(False)
        sb.remove_split_btn.setEnabled(False)

    def add_split_point(self):
        session = self.active_session()
        if session is None or session.selected_point_idx is None:
            return
        idx = session.selected_point_idx
        cmd = AddSplitCmd(
            session, idx,
            sync_cb=lambda: self._on_split_changed(session),
            refresh_cb=lambda: self._apply_geometry_update(session))
        session.command_history.execute(cmd)
        self.main_window.log_panel.log(
            f"Added split point at index {idx}.")
        self.handle_point_clicked(idx)

    def remove_split_point(self):
        session = self.active_session()
        if session is None or session.selected_point_idx is None:
            return
        idx = session.selected_point_idx
        if idx not in session.split_indices:
            return
        keep = self.main_window.sidebar_view.keep_vertex_cb.isChecked()
        cmd = RemoveSplitCmd(
            session, idx, keep,
            sync_cb=lambda: self._on_split_changed(session),
            refresh_cb=lambda: self._apply_geometry_update(session))
        session.command_history.execute(cmd)
        action = "kept" if keep else "deleted"
        self.main_window.log_panel.log(
            f"Removed split point at {idx} (vertex {action}).")
        if keep:
            self.handle_point_clicked(idx)

    def _on_split_changed(self, session: GeometrySession):
        """Called after a lightweight split-only change (no geometry modification)."""
        if session is self.active_session():
            self.main_window.canvas_view.update_split_points(session.split_indices)
        self._sync_file_segments(session)

    def handle_insert_point(self):
        session = self.active_session()
        if session is None or session.original_points is None:
            self.main_window.log_panel.log("No geometry loaded.")
            return
        sb = self.main_window.sidebar_view
        x = sb.insert_x.value()
        y = sb.insert_y.value()
        p = np.array([x, y])

        # Find nearest edge
        pts = session.original_points
        n = len(pts)
        best_idx, min_dist = 0, float("inf")
        for i in range(n - 1):
            v, w = pts[i], pts[i + 1]
            l2 = np.sum((w - v) ** 2)
            t = (np.dot(p - v, w - v) / l2) if l2 > 0 else 0
            t = float(np.clip(t, 0, 1))
            dist = np.linalg.norm(p - (v + t * (w - v)))
            if dist < min_dist:
                min_dist = dist
                best_idx = i

        insert_idx = best_idx + 1
        cmd = InsertVertexCmd(
            session, insert_idx, p, list(session.split_indices),
            refresh_cb=lambda: self._apply_geometry_update(session))
        session.command_history.execute(cmd)
        self.main_window.log_panel.log(
            f"Inserted ({x:.4f}, {y:.4f}) at index {insert_idx}.")
        self.handle_point_clicked(insert_idx)

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
            tree.blockSignals(True)
            tree.clear_edge_selection()
            tree.blockSignals(False)
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
        tree.blockSignals(True)
        tree.clear_edge_selection()
        if item is not None:
            item.setSelected(True)
            tree.setCurrentItem(item)
        tree.blockSignals(False)
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
        self._is_populating = True
        try:
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
                sb.strategy_combo.blockSignals(True)
                sb.strategy_combo.setCurrentText(seg.strategy)
                sb.strategy_combo.blockSignals(False)
                sb.switch_param_form(seg.strategy)
                self._populate_form_from_segment(seg)

            # Show transform duplicate group for all segments
            sb._transform_dup_group.setVisible(True)

            sb.match_previous_cb.blockSignals(True)
            sb.match_previous_cb.setChecked(seg.match_previous)
            sb.match_previous_cb.blockSignals(False)

            # Update base point values
            self.update_duplicate_base_point()
            self._show_duplicate_preview = False

            # Snapshot params for undo
            session.param_snapshot = copy.deepcopy(seg.parameters)
            session.segment_state_snapshot = copy.deepcopy(seg.to_dict())
        finally:
            self._is_populating = False
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
            self.main_window.log_panel.log(
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

    def highlight_selected_segments(self):
        """Highlight every selected edge on the canvas — discrete (file) AND
        analytic (curve) — and dim the base geometry while a selection exists."""
        session = self.active_session()
        if not session:
            return
        sb = self.main_window.sidebar_view

        selected_indices = sb.geometry_tree.selected_edge_indices()

        if not selected_indices:
            self.main_window.canvas_view.update_active_segments_pts([])
            self.main_window.canvas_view.set_active_geometry_dimmed(session.session_id, False)
            return

        # Build a highlight polyline for each selected edge (any type).
        pieces = []
        primary_pos = 0
        current_idx = getattr(session, 'current_segment_idx', -1)
        for seg_idx in selected_indices:
            seg = session.project_model.get_segment(seg_idx)
            if not seg:
                continue
            poly = self._segment_polyline(session, seg)
            if poly is None:
                continue
            pieces.append(poly)
            if seg_idx == current_idx:
                primary_pos = len(pieces) - 1

        self.main_window.canvas_view.update_active_segments_pts(pieces, primary_idx=primary_pos)
        self.main_window.canvas_view.set_active_geometry_dimmed(session.session_id, bool(pieces))

    def _segment_polyline(self, session, seg) -> np.ndarray | None:
        """Return a segment's display points as an (N, 2) array, or None.

        Delegates to GeometryService.get_segment_points so discrete (file),
        analytic (curve) and closed-loop closing edges are all hit-tested with
        exactly the points used for transform / preview."""
        res = GeometryService.get_segment_points(session, seg)
        if res is None or len(res[0]) < 2:
            return None
        return np.column_stack([res[0], res[1]])

    @staticmethod
    def _point_to_polyline_dist(x: float, y: float, sp: np.ndarray) -> float:
        """Minimum distance from (x, y) to the polyline through points ``sp``."""
        best = float('inf')
        for i in range(len(sp) - 1):
            ax, ay = float(sp[i][0]), float(sp[i][1])
            bx, by = float(sp[i + 1][0]), float(sp[i + 1][1])
            dx, dy = bx - ax, by - ay
            len_sq = dx * dx + dy * dy
            if len_sq < 1e-20:
                d = ((x - ax) ** 2 + (y - ay) ** 2) ** 0.5
            else:
                t = max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / len_sq))
                d = ((x - (ax + t * dx)) ** 2 + (y - (ay + t * dy)) ** 2) ** 0.5
            if d < best:
                best = d
        return best

    def handle_canvas_segment_clicked(self, x: float, y: float, extend_selection: bool = False):
        """Handle a canvas click in edge selection mode: select/toggle the
        nearest segment. Both discrete (file) and analytic (curve/polygon)
        segments are considered, so a transformed/duplicated result can be
        clicked directly on the canvas instead of only via the edge list."""
        # Ignore selection clicks while creating/editing an edge (modeless dialog
        # open), so the in-progress control points are not cleared by a stray click.
        if self._edit_in_progress():
            return
        session = self.active_session()
        if not session:
            return

        segments = session.project_model.segments
        best_seg_idx = -1
        best_dist = float('inf')
        for seg_idx, seg in enumerate(segments):
            sp = self._segment_polyline(session, seg)
            if sp is None or len(sp) < 2:
                continue
            d = self._point_to_polyline_dist(x, y, sp)
            if d < best_dist:
                best_dist = d
                best_seg_idx = seg_idx

        if best_seg_idx < 0:
            return

        # Reject clicks too far from any segment (3% of the visible range).
        vb = self.main_window.canvas_view.plot_widget.plotItem.vb
        view_range = vb.viewRange()
        x_range = abs(view_range[0][1] - view_range[0][0])
        y_range = abs(view_range[1][1] - view_range[1][0])
        data_threshold = max(x_range, y_range) * 0.03
        if best_dist > data_threshold:
            return

        sb = self.main_window.sidebar_view
        tree = sb.geometry_tree

        # Find and select/toggle the matching edge row in the model tree.
        found_item = tree.edge_item_by_index(session.session_id, best_seg_idx)

        tree.blockSignals(True)
        if found_item:
            if extend_selection:
                found_item.setSelected(not found_item.isSelected())
                if found_item.isSelected():
                    tree.setCurrentItem(found_item)
                    session.current_segment_idx = best_seg_idx
                else:
                    sel = tree.selected_edge_indices()
                    session.current_segment_idx = sel[0] if sel else -1
            else:
                tree.clear_edge_selection()
                found_item.setSelected(True)
                tree.setCurrentItem(found_item)
                session.current_segment_idx = best_seg_idx
        tree.blockSignals(False)

        seg = session.project_model.get_segment(session.current_segment_idx)
        sb.curve_bake_btn.setEnabled(bool(seg and seg.type == "curve"))
        self.handle_segment_selected(session.current_segment_idx)
        self.highlight_selected_segments()

    def handle_canvas_box_selected(self, x0: float, y0: float,
                                   x1: float, y1: float, extend: bool = False):
        """Handle a rubber-band box selection from the canvas (edge mode).

        Selects every edge segment (discrete or analytic) with at least one
        point inside the box. Shift+drag replaces the current selection;
        Ctrl/Cmd+drag adds to it. No-op in vertex mode."""
        if self._edit_in_progress():
            return
        canvas = self.main_window.canvas_view
        if getattr(canvas, '_selection_mode', 'vertex') != 'edge':
            return
        session = self.active_session()
        if not session:
            return

        xmin, xmax = (x0, x1) if x0 <= x1 else (x1, x0)
        ymin, ymax = (y0, y1) if y0 <= y1 else (y1, y0)

        segments = session.project_model.segments
        hit_set = set()
        for seg_idx, seg in enumerate(segments):
            sp = self._segment_polyline(session, seg)
            if sp is None or len(sp) < 2:
                continue
            inside = ((sp[:, 0] >= xmin) & (sp[:, 0] <= xmax) &
                      (sp[:, 1] >= ymin) & (sp[:, 1] <= ymax))
            if np.any(inside):
                hit_set.add(seg_idx)

        sb = self.main_window.sidebar_view
        tree = sb.geometry_tree
        last_idx = -1
        tree.blockSignals(True)
        if not extend:
            tree.clear_edge_selection()
        for item in tree.edge_items(session.session_id):
            idx = tree.edge_index(item)
            if idx in hit_set:
                item.setSelected(True)
                tree.setCurrentItem(item)
                last_idx = idx
        tree.blockSignals(False)

        if last_idx >= 0:
            session.current_segment_idx = last_idx
            seg = session.project_model.get_segment(last_idx)
            sb.curve_bake_btn.setEnabled(bool(seg and seg.type == "curve"))
            self.handle_segment_selected(last_idx)
        elif not extend:
            sb.curve_bake_btn.setEnabled(False)
            self.handle_segment_selected(-1)
        self.highlight_selected_segments()

        if hit_set:
            self.main_window.log_panel.log(f"Box-selected {len(hit_set)} edge(s).")

    # ── Distribution tool window + live canvas preview ──────────────────────

    def _distribution_indices_or_selection(self):
        """While the Distribution window is open, distribution edits act on the
        CURRENT edge only (per-edge), not the whole selection."""
        session = self.active_session()
        sb = self.main_window.sidebar_view
        if (session and sb._distribution_dialog.isVisible()
                and session.current_segment_idx >= 0):
            return [session.current_segment_idx]
        return self.get_selected_segment_indices()

    def _open_distribution(self):
        self.main_window.sidebar_view.open_distribution_dialog()
        self._preview_distribution()

    def _apply_distribution(self):
        """Apply button: commit the distribution settings of the CURRENT edge
        only (not every selected edge) and show its resampled preview."""
        session = self.active_session()
        if not session:
            return
        idx = session.current_segment_idx
        seg = session.project_model.get_segment(idx)
        if not seg or seg.type != "file":
            self.main_window.log_panel.log("Select a discrete edge to apply its distribution.")
            return
        old_state = seg.to_dict()
        self._read_params_into_segment(seg)
        new_state = seg.to_dict()
        if new_state != old_state:
            def refresh():
                if session is self.active_session():
                    self._apply_geometry_update(session)
            cmd = UpdateSegmentStateCmd(session, idx, old_state, new_state, refresh_cb=refresh)
            session.command_history.execute(cmd)
            session.is_geometry_modified = True
            self.main_window.update_title(session.display_name, True)
        self._preview_distribution()
        self.main_window.log_panel.log(f"Applied distribution to Edge {seg.id}.")

    def _preview_distribution(self):
        """Live-render the chosen point distribution of the CURRENT discrete edge
        onto the canvas while the Distribution window is open."""
        session = self.active_session()
        if not session:
            return
        sb = self.main_window.sidebar_view
        if not sb._distribution_dialog.isVisible():
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

    def _populate_form_from_segment(self, seg: SegmentModel):
        sb = self.main_window.sidebar_view

        def block(b):
            for w in [sb.uniform_n, sb.tanh_n, sb.tanh_intensity,
                      sb.cosine_n, sb.curv_n, sb.curv_sens,
                      sb.geo_n, sb.geo_ratio, sb.geo_ratio_end, sb.uniform_spacing]:
                w.blockSignals(b)
            sb.uniform_type_combo.blockSignals(b)

        block(True)
        p = seg.parameters
        if seg.strategy == "uniform":
            if "spacing" in p:
                sb.uniform_type_combo.setCurrentText("By Spacing")
                sb.uniform_spacing.setValue(p["spacing"])
                sb._toggle_uniform_mode(True)
            else:
                sb.uniform_type_combo.setCurrentText("By Node Count")
                sb.uniform_n.setValue(p.get("n_points", 50))
                sb._toggle_uniform_mode(False)
        elif seg.strategy == "tanh":
            sb.tanh_n.setValue(p.get("n_points", 50))
            sb.tanh_intensity.setValue(p.get("intensity", 2.0))
        elif seg.strategy == "cosine":
            sb.cosine_n.setValue(p.get("n_points", 50))
        elif seg.strategy == "curvature":
            sb.curv_n.setValue(p.get("n_points", 50))
            sb.curv_sens.setValue(p.get("sensitivity", 1.5))
        elif seg.strategy == "geometric":
            sb.geo_n.setValue(p.get("n_points", 50))
            sb.geo_ratio.setValue(p.get("ratio", 1.2))
            sb.geo_ratio_end.setValue(p.get("ratio_end", 1.0))
        block(False)

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
        sb = self.main_window.sidebar_view
        seg.parameters.clear()
        if seg.strategy == "uniform":
            if sb.uniform_type_combo.currentText() == "By Spacing":
                seg.parameters["spacing"] = sb.uniform_spacing.value()
            else:
                seg.parameters["n_points"] = sb.uniform_n.value()
        elif seg.strategy == "tanh":
            seg.parameters["n_points"] = sb.tanh_n.value()
            seg.parameters["intensity"] = sb.tanh_intensity.value()
        elif seg.strategy == "cosine":
            seg.parameters["n_points"] = sb.cosine_n.value()
        elif seg.strategy == "curvature":
            seg.parameters["n_points"] = sb.curv_n.value()
            seg.parameters["sensitivity"] = sb.curv_sens.value()
        elif seg.strategy == "geometric":
            seg.parameters["n_points"] = sb.geo_n.value()
            seg.parameters["ratio"] = sb.geo_ratio.value()
            end_ratio = sb.geo_ratio_end.value()
            if end_ratio != 1.0:
                seg.parameters["ratio_end"] = end_ratio
            else:
                seg.parameters.pop("ratio_end", None)

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
        self._apply_geometry_update(session)
        self._refresh_segment_list()
        self._sync_geometry_list()
        self.main_window.canvas_view.clear_curve_preview(session.session_id)
        self._update_canvas_curve_segments()
        session.is_geometry_modified = True
        self.main_window.update_title(session.display_name, session.is_geometry_modified)

    def auto_detect_segments(self, angle_threshold_deg: float = 30.0):
        """Auto-detect segment boundaries based on sharp angles."""
        session = self.active_session()
        if not session or session.original_points is None:
            self.main_window.log_panel.log("No geometry loaded.")
            return

        points = session.original_points.copy()
        pm = session.project_model
        if pm.is_closed and len(points) > 0:
            if not np.allclose(points[0], points[-1]):
                points = np.vstack((points, points[0]))

        new_indices = self._auto_detect_features(points, angle_threshold_deg)
        cmd = AutoDetectSplitCmd(
            session, new_indices,
            refresh_cb=lambda: self._apply_geometry_update(session))
        session.command_history.execute(cmd)
        self.main_window.log_panel.log(
            f"Auto-detected {len(new_indices) - 1} edges based on sharp angles (threshold: {angle_threshold_deg}°).")

    def auto_detect_segments_from_button(self):
        """Slot for the Auto Detect Segments button."""
        session = self.active_session()
        if not session:
            return

        seg_idx = session.current_segment_idx
        seg = None
        if 0 <= seg_idx < len(session.project_model.segments):
            seg = session.project_model.get_segment(seg_idx)

        sb = self.main_window.sidebar_view
        angle_threshold = sb.auto_split_angle_sb.value()

        if seg:
            if seg.type == "file" and session.original_points is None:
                self.main_window.log_panel.log("No geometry loaded for file segment.")
                return

            new_indices = self._auto_detect_features_for_segment(seg_idx, angle_threshold)
            if len(new_indices) >= 2:
                cmd = CreateSegmentsFromIndicesCmd(
                    session, seg_idx, new_indices,
                    refresh_cb=lambda: self._apply_geometry_update(session))
                session.command_history.execute(cmd)
                self.main_window.log_panel.log(
                    f"Auto-detected {len(new_indices) - 1} sub-edges for edge {seg.id} (threshold: {angle_threshold}°).")
            else:
                self.main_window.log_panel.log("No sharp corners detected for selected edge.")
            return

        if session.original_points is None:
            self.main_window.log_panel.log("No geometry loaded.")
            return
        self.auto_detect_segments(angle_threshold_deg=angle_threshold)

    def _auto_detect_features(self, points: np.ndarray,
                              angle_threshold_deg: float = 30.0) -> list[int]:
        return GeometryService.auto_detect_features(points, angle_threshold_deg)

    def _auto_detect_features_for_segment(self, segment_idx: int, angle_threshold_deg: float = 30.0) -> list[int]:
        session = self.active_session()
        if not session:
            return []

        seg = session.project_model.get_segment(segment_idx)
        if not seg:
            return []

        if seg.type == "file":
            if session.original_points is None:
                return []
            pts = session.original_points[seg.start_index:seg.end_index + 1]
            local_splits = self._auto_detect_features(pts, angle_threshold_deg)
            return [seg.start_index + i for i in local_splits]
        else:
            n = seg.parameters.get("n_points", 100)
            xs, ys = GeometryService.compute_curve_preview_pts(seg, n, session.original_points)
            if xs is None or len(xs) < 2:
                return []
            pts = np.column_stack([xs, ys])
            return self._auto_detect_features(pts, angle_threshold_deg)

    def _sync_file_segments(self, session: GeometrySession):
        session.project_model.update_file_segments_from_indices(
            session.split_indices)
        if session is self.active_session():
            self._refresh_segment_list(clear_resampled=False)
        self._update_tab_title()
