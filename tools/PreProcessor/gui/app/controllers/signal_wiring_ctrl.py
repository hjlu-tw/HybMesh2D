"""Signal wiring for AppController, extracted from __init__ to keep
controller.py small. All methods run on the composed AppController instance."""
from __future__ import annotations

from PyQt6.QtWidgets import QMenu
from app.utils import block_signals


class SignalWiringMixin:
    def _wire_sidebar_signals(self):
        # ── Wire static signals (sidebar → controller) ──────────────────
        sb = self.main_window.sidebar_view
        sb.load_btn.clicked.connect(self.load_geometry)
        sb.load_stl_btn.clicked.connect(self.load_stl_geometry)
        sb.load_json_btn.clicked.connect(self.load_json_config)
        sb.split_btn.clicked.connect(self.add_split_point)
        sb.remove_split_btn.clicked.connect(self.remove_split_point)
        sb.insert_btn.clicked.connect(self.handle_insert_point)
        sb.move_btn.clicked.connect(lambda: self.move_selected_vertex_to())
        # Geometry layers and their edges live in one model tree; an edge-row
        # selection drives the edge properties.
        sb.geometry_tree.itemSelectionChanged.connect(self.handle_segment_list_selected)
        sb.strategy_combo.currentTextChanged.connect(
            self.handle_strategy_changed)
        sb.is_closed_combo.currentTextChanged.connect(
            self.handle_closed_mode_changed)
        if sb.preview_btn:
            sb.preview_btn.clicked.connect(self.preview_backend)
        if sb.file_preview_btn:
            sb.file_preview_btn.clicked.connect(self.preview_backend)
        sb.save_btn.clicked.connect(self.save_output)
        if getattr(self.main_window, "cad_cancel_btn", None) is not None:
            self.main_window.cad_cancel_btn.clicked.connect(self.cancel_backend)
        sb.generate_btn.clicked.connect(self.generate_json)
        sb.extrude_stl_btn.clicked.connect(self.extrude_active_to_stl)
        # "Add Analytic Edge" is a shape-tool menu: pick a shape, draw it on the
        # canvas (Custom Formula adds a blank edge).
        self._shape_tool_menu = QMenu(self.main_window)
        for label, tool in [
            ("Line", "line"),
            ("Circle", "circle"),
            ("Arc", "arc"),
            ("Rectangle", "rectangle"),
            ("Triangle", "triangle"),
            ("Polygon (closed)", "polygon"),
            ("Polyline (open)", "polyline"),
        ]:
            act = self._shape_tool_menu.addAction(label)
            if tool == "polyline":
                act.setToolTip("Draw an OPEN multi-segment line (not auto-closed)")
            act.triggered.connect(lambda _checked=False, t=tool: self.enter_shape_tool(t))
        self._shape_tool_menu.addSeparator()
        custom_act = self._shape_tool_menu.addAction("Custom Formula…")
        custom_act.setToolTip("Define an edge by a math equation "
                              "(parametric x(t),y(t) or explicit y=f(x))")
        custom_act.triggered.connect(lambda _checked=False: self.enter_shape_tool("custom"))
        self._shape_tool_menu.addSeparator()
        weld_act = self._shape_tool_menu.addAction("Weld / Connect Points…")
        weld_act.setToolTip("Weld two points: click a point (a red open endpoint "
                            "or any vertex), then click a target — snap to another "
                            "point to weld them, or a free point to connect a line")
        weld_act.triggered.connect(lambda _checked=False: self.enter_endpoint_tool())
        sb.add_curve_seg_btn.setMenu(self._shape_tool_menu)
        sb.curve_preview_btn.clicked.connect(self.preview_curve_formula)
        
        # Wire live preview for curve editing
        for w in [sb.curve_t_min, sb.curve_t_max, sb.curve_n,
                  sb.curve_start_node, sb.curve_end_node,
                  sb.h_line_y, sb.h_line_x_start, sb.h_line_x_end,
                  sb.v_line_x, sb.v_line_y_start, sb.v_line_y_end,
                  sb.line_x0, sb.line_y0, sb.line_x1, sb.line_y1,
                  sb.circle_cx, sb.circle_cy, sb.circle_r,
                  sb.arc_cx, sb.arc_cy, sb.arc_r, sb.arc_theta0, sb.arc_theta1,
                  sb.tri_x0, sb.tri_y0, sb.tri_x1, sb.tri_y1, sb.tri_x2, sb.tri_y2,
                  sb.quad_x0, sb.quad_y0, sb.quad_x1, sb.quad_y1,
                  sb.quad_x2, sb.quad_y2, sb.quad_x3, sb.quad_y3]:
            w.valueChanged.connect(self.preview_curve_formula)
        for w in [sb.curve_x_formula, sb.curve_y_formula, sb.curve_formula]:
            w.textChanged.connect(self.preview_curve_formula)
        sb.poly_vertices.textChanged.connect(self.preview_curve_formula)
        sb.curve_mode_param.toggled.connect(self.handle_curve_type_changed)
        sb.curve_type_combo.currentIndexChanged.connect(self.handle_curve_type_changed)

        # Undo / Redo / Remove / Quality Check
        self.main_window.undo_btn.clicked.connect(self.undo)
        self.main_window.redo_btn.clicked.connect(self.redo)
        sb.remove_seg_btn.clicked.connect(self.remove_selected_segment)
        sb.curve_bake_btn.clicked.connect(self.bake_selected_curve)
        sb.join_edges_btn.clicked.connect(self.join_selected_edges_to_polygon)
        self.main_window.quality_check_cb.toggled.connect(self.handle_quality_check_toggled)
        self.main_window.quality_mode_combo.currentTextChanged.connect(self.handle_quality_mode_changed)
        self.main_window.show_vertices_cb.toggled.connect(self.handle_show_vertices_toggled)
        self.main_window.show_nodes_cb.toggled.connect(self.handle_show_nodes_toggled)
        sb.dup_btn.clicked.connect(self.duplicate_with_transform)

        # Parameter-change signals (all route to update_segment_params)
        for widget in [sb.uniform_n, sb.tanh_n, sb.tanh_intensity,
                       sb.cosine_n, sb.curv_n, sb.curv_sens,
                       sb.geo_n, sb.geo_ratio, sb.geo_ratio_end, sb.uniform_spacing]:
            widget.valueChanged.connect(self.update_segment_params)
        sb.uniform_type_combo.currentTextChanged.connect(
            self.update_segment_params)
        sb.match_previous_cb.toggled.connect(self.update_match_previous)
        # #1: patch/group name is assigned via a pop-up (applies to all selected).
        sb.group_btn.clicked.connect(self.open_cad_patch_dialog)
        sb.auto_split_btn.clicked.connect(self.auto_detect_segments_from_button)

        # Distribution tool window: open it + drive a live resample preview.
        sb.distribution_btn.clicked.connect(self._open_distribution)
        sb.distribution_apply_btn.clicked.connect(self._apply_distribution)
        sb._distribution_dialog.finished.connect(
            lambda _r: self._restore_resampled_after_distribution())

        # Duplicate & Transform tool window: opening it auto-shows the gizmo +
        # live preview; closing it clears them.
        sb.transform_btn.clicked.connect(self._open_transform)
        sb._transform_dialog.finished.connect(lambda _r: self._close_transform())

        # Wire duplicate live preview connections
        sb.dup_type_combo.currentIndexChanged.connect(self.handle_dup_type_changed)
        sb.dup_base_mode_combo.currentIndexChanged.connect(self.handle_dup_base_mode_changed)
        sb.dup_delete_orig_cb.toggled.connect(self.on_duplicate_param_changed)
        for w in [sb.dup_rot_angle, sb.dup_rot_px, sb.dup_rot_py,
                  sb.dup_mh_py, sb.dup_mv_px,
                  sb.dup_ma_px, sb.dup_ma_py, sb.dup_ma_dx, sb.dup_ma_dy,
                  sb.dup_ps_px, sb.dup_ps_py,
                  sb.dup_trans_dx, sb.dup_trans_dy,
                  sb.dup_scale_sx, sb.dup_scale_sy, sb.dup_scale_px, sb.dup_scale_py]:
            w.valueChanged.connect(self.on_duplicate_param_changed)

        # Advanced settings
        sb.global_spline_cb.toggled.connect(self.handle_global_spline_changed)

        # New tab button
        sb.new_tab_btn.clicked.connect(self.new_blank_tab)
        sb.auto_detect_btn.clicked.connect(self.auto_detect_segments)

        # Model tree: visibility (per-row checkbox), navigation, focus, context menu
        sb.geometry_tree.itemChanged.connect(self.handle_geom_visibility_changed)
        sb.geometry_tree.currentItemChanged.connect(self.handle_tree_current_changed)
        sb.geometry_tree.itemDoubleClicked.connect(self.handle_geom_list_double_clicked)
        self.main_window.focus_geom_btn.clicked.connect(self.focus_to_selected_geometry)
        self.main_window.cad_clear_btn.clicked.connect(self.clear_cad_canvas)
        self.main_window.cad_clear_all_btn.clicked.connect(self.clear_all_geometry)
        self.main_window.cad_redraw_btn.clicked.connect(self.redraw_canvas)
        sb.geometry_tree.context_menu_requested.connect(self.show_geometry_context_menu)

    def _wire_tab_signals(self):
        # ── Wire tab signals ────────────────────────────────────────────
        tw = self.main_window.tab_widget
        tw.tabCloseRequested.connect(self.close_tab)
        tw.currentChanged.connect(self.switch_tab)

        # Mesh Generator / Statistics have their own (shared-state) tab strip.
        self.main_window.mesh_tab_bar.tabCloseRequested.connect(self.close_mesh_tab)

    def _wire_canvas_signals(self):
        sb = self.main_window.sidebar_view
        # ── Wire shared canvas signals ──────────────────────────────────
        self.main_window.canvas_view.point_clicked.connect(self.handle_point_clicked)
        self.main_window.canvas_view.point_deselected.connect(self.handle_point_deselected)
        self.main_window.canvas_view.segment_clicked.connect(self.handle_canvas_segment_clicked)
        self.main_window.canvas_view.segment_double_clicked.connect(self.handle_canvas_segment_double_clicked)
        self.main_window.canvas_view.segment_context_requested.connect(self.handle_canvas_context_menu)
        self.main_window.canvas_view.box_selected.connect(self.handle_canvas_box_selected)
        # Interactive shape drawing finished → create the analytic edge.
        self.main_window.canvas_view.shape_drawn.connect(self.on_shape_drawn)
        self.main_window.canvas_view.endpoint_weld_requested.connect(self.handle_endpoint_weld)
        # Live drag of the transform base point / mirror axis on the canvas.
        self.main_window.canvas_view.transform_handle_cb = self._on_transform_handle_dragged
        # Live drag of the selected analytic edge's control points.
        self.main_window.canvas_view.edge_handle_cb = self._on_edge_handle_dragged
        # Live drag of the selected vertex / split point (#6).
        self.main_window.canvas_view.vertex_move_cb = self._on_vertex_move_dragged
        # Snap placement clicks (while drawing) to nearby edge endpoints.
        self.main_window.canvas_view.snap_cb = self._snap_draw_xy

        # ── Canvas tools: measure, grid snap, view history ────────────────
        mw_ = self.main_window
        cv = mw_.canvas_view
        # The snap step/flag are read by _snap_draw_xy through the window, so the
        # checkbox and spin box need no handler of their own: toggling them changes
        # the NEXT placement rather than mutating anything now.
        mw_.grid_snap_on = False
        mw_.grid_snap_cb.toggled.connect(self._on_grid_snap_toggled)
        mw_.grid_snap_step.valueChanged.connect(self._on_grid_snap_step_changed)

        mw_.measure_btn.toggled.connect(self._on_measure_toggled)
        cv.measure_done_cb = self._on_measure_done
        cv.measure_ended_cb = self._on_measure_ended
        cv.view_history_changed_cb = self._on_view_history_changed
        mw_.view_back_btn.clicked.connect(cv.view_back)
        mw_.view_fwd_btn.clicked.connect(cv.view_forward)

        # Wire Selection Mode dropdown (now in the sidebar, beside the tree)
        def _on_selection_mode_changed(index):
            mode = 'vertex' if index == 0 else 'edge'
            # Drop any edge/vertex selection carried over from the previous mode
            # so switching modes always starts from a clean slate (important when
            # several geometry layers are loaded).
            self._clear_cad_selection()
            self.main_window.canvas_view.set_selection_mode(mode)
            # Swap the Details pane to match the active edit mode.
            sb.show_details_for_mode(mode)

        sb.select_mode_combo.currentIndexChanged.connect(_on_selection_mode_changed)
        # Default the CAD canvas to Edge mode. The combo is preset to "Edge"
        # before this signal was wired, so push the mode into the canvas once
        # to apply its overlay / box-select side effects.
        _initial_mode = 'vertex' if sb.select_mode_combo.currentIndex() == 0 else 'edge'
        self.main_window.canvas_view.set_selection_mode(_initial_mode)
        sb.show_details_for_mode(_initial_mode)

    def _wire_mesh_signals(self):
        # ── Wire Mesh Generation signals ───────────────────────────────
        mw = self.main_window
        mw.mode_changed.connect(self.handle_mode_changed)
        mw.mode_changed.connect(mw.update_status_stage)
        
        mw.mesh_config_panel.load_config_btn.clicked.connect(self.load_mesh_config)
        mw.mesh_config_panel.save_config_btn.clicked.connect(self.save_mesh_config)
        mw.mesh_config_panel.add_active_geom_btn.clicked.connect(self.add_active_preprocessor_geometry)
        mw.mesh_config_panel.preview_btn.clicked.connect(self.preview_mesh_generator)
        mw.mesh_config_panel.run_mesh_btn.clicked.connect(self.run_mesh_generator)
        mw.mesh_config_panel.cancel_mesh_btn.clicked.connect(self.cancel_mesh_generator)
        mw.mesh_config_panel.geom_files_changed.connect(self.handle_mesh_geom_files_changed)
        mw.mesh_config_panel.mesh_config_changed.connect(self.handle_mesh_config_changed)
        mw.mesh_config_panel.add_all_sessions_btn.clicked.connect(self.add_all_sessions_to_mesh)
        mw.mesh_config_panel.export_mesh_requested.connect(self.export_mesh_files)  # #5
        # Domain Source = Custom geometry hides the rectangle box + its BC colours;
        # selecting a geometry in the list highlights it on the mesh canvas.
        mw.mesh_config_panel.domain_source_changed.connect(
            mw.mesh_canvas_view.set_domain_is_custom)
        mw.mesh_config_panel.geom_selection_changed.connect(
            mw.mesh_canvas_view.highlight_geometry_file)
        mw.mesh_config_panel.segment_highlight_requested.connect(
            mw.mesh_canvas_view.highlight_segment)

        # Toolbar Mesh Buttons
        mw.mesh_preview_btn.clicked.connect(self.preview_mesh_generator)
        mw.mesh_generate_btn.clicked.connect(self.run_mesh_generator)
        mw.mesh_cancel_btn.clicked.connect(self.cancel_mesh_generator)
        # (#8) The per-format "Export …" buttons were removed from the mesh config
        # panel; export-to-a-path stays wired from the Results panel (below).
        mw.mesh_focus_btn.clicked.connect(mw.mesh_canvas_view.auto_range)
        mw.mesh_clear_btn.clicked.connect(self.clear_mesh_canvas)
        mw.mesh_send_solver_btn.clicked.connect(self.send_mesh_to_solver)

    def _wire_solver_stl3d_signals(self):
        mw = self.main_window
        # Solver panel (Phase 3)
        sp = mw.solver_config_panel
        sp.run_solver_btn.clicked.connect(self.run_solver_pipeline)
        sp.cancel_solver_btn.clicked.connect(self.cancel_solver)
        # Owned by the toolbar, not the panel (see _build_canvas_toolbar).
        mw.solver_export_case_btn.clicked.connect(self.export_portable_case)
        sp.load_cfg_btn.clicked.connect(self.load_solver_config)
        sp.save_cfg_btn.clicked.connect(self.save_solver_config)
        sp.bc_detect_btn.clicked.connect(self.detect_bc_from_mesh)
        sp.build_init_cond_btn.clicked.connect(lambda: self.open_dll_builder("init_cond"))
        sp.build_motion_btn.clicked.connect(lambda: self.open_dll_builder("motion"))
        sp.build_phi_shape_btn.clicked.connect(self.generate_phi_from_cad_shape)
        sp.bc_dll_btn.clicked.connect(self.open_bc_dll_builder)
        sp.probe_coords_btn.clicked.connect(self.open_probe_coords_dialog)
        # Linf mode: ticking "from model unit" must re-derive Linf immediately, or the
        # panel shows a stale reference Reynolds number until the next run.
        sp.linf_from_unit.toggled.connect(self.on_linf_mode_changed)
        self.init_solver()

        # Immersed-solid (STL3d) panel
        s3 = mw.stl3d_config_panel
        s3.browse_btn.clicked.connect(self.browse_stl3d)
        s3.fit_domain_btn.clicked.connect(self.fit_stl3d_domain)
        s3.run_btn.clicked.connect(self.run_stl3d)
        s3.cancel_btn.clicked.connect(self.cancel_stl3d)
        s3.config_changed.connect(self.on_stl3d_config_changed)
        s3.send_solver_btn.clicked.connect(self.send_stl3d_to_solver)
        mw.stl3d_canvas.clear_btn.clicked.connect(self.clear_stl3d)
        mw.stl3d_canvas.clear_phi_btn.clicked.connect(self.clear_stl3d_phi)
        self.init_stl3d()

        # Results / post-processing
        mw.result_canvas_view.load_btn.clicked.connect(self.open_result_dialog)
        mw.result_control_panel.bind(mw.result_canvas_view, self)

        # Full pipeline (Run All) — toolbar button + menu actions
        if getattr(mw, "run_all_btn", None) is not None:
            mw.run_all_btn.clicked.connect(self.run_full_pipeline)

    def _wire_toolbar_sync(self):
        mw = self.main_window
        # Wire Toolbar Toggles & Synchronization with Sidebar Panel
        def _make_sync_checkbox_fn(canvas_method, cb_sidebar, cb_toolbar):
            def sync_fn(checked):
                canvas_method(checked)
                for cb in (cb_sidebar, cb_toolbar):
                    with block_signals(cb):
                        cb.setChecked(checked)
            return sync_fn

        sync_wireframe = _make_sync_checkbox_fn(
            mw.mesh_canvas_view.set_wireframe_visible,
            mw.mesh_stats_panel.show_wireframe_cb,
            mw.mesh_show_wireframe_cb
        )
        sync_bc = _make_sync_checkbox_fn(
            mw.mesh_canvas_view.set_bc_coloring_visible,
            mw.mesh_stats_panel.show_bc_coloring_cb,
            mw.mesh_show_bc_cb
        )
        sync_domain = _make_sync_checkbox_fn(
            mw.mesh_canvas_view.set_domain_box_visible,
            mw.mesh_stats_panel.show_domain_box_cb,
            mw.mesh_show_domain_cb
        )

        def sync_color_mode(text):
            mode_map = {
                "Element Type": "element_type",
                "Quality (Aspect Ratio)": "quality_aspect",
                "Quality (Skewness)": "quality_skewness",
                "Uniform": "uniform"
            }
            mode_val = mode_map.get(text, "uniform")
            mw.mesh_canvas_view.set_color_mode(mode_val)
            
            # Sync toolbar
            with block_signals(mw.mesh_color_mode_combo):
                mw.mesh_color_mode_combo.setCurrentText(text)
            
            # Sync sidebar panel
            with block_signals(mw.mesh_stats_panel.color_mode_combo):
                mw.mesh_stats_panel.color_mode_combo.setCurrentText(text)

        mw.mesh_show_wireframe_cb.toggled.connect(sync_wireframe)
        mw.mesh_stats_panel.show_wireframe_cb.toggled.connect(sync_wireframe)
        
        mw.mesh_show_bc_cb.toggled.connect(sync_bc)
        mw.mesh_stats_panel.show_bc_coloring_cb.toggled.connect(sync_bc)
        
        mw.mesh_show_domain_cb.toggled.connect(sync_domain)
        mw.mesh_stats_panel.show_domain_box_cb.toggled.connect(sync_domain)

        mw.mesh_color_mode_combo.currentTextChanged.connect(sync_color_mode)
        mw.mesh_stats_panel.color_mode_combo.currentTextChanged.connect(sync_color_mode)

        # Wire stats panel buttons
        mw.mesh_stats_panel.fit_view_requested.connect(mw.mesh_canvas_view.auto_range)
        mw.mesh_stats_panel.export_vtk_requested.connect(self.export_generated_vtk)
        mw.mesh_stats_panel.export_star_cd_requested.connect(self.export_star_cd)
