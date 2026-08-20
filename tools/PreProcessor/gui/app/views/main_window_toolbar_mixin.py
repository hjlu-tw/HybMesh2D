from __future__ import annotations
from PyQt6.QtCore import QTimer, QEvent


class MainWindowToolbarMixin:
    """
    Responsive canvas-toolbar layout and its driving events for
    :class:`MainWindow`.

    Mixed into ``MainWindow`` (after ``QMainWindow``); every method references
    ``self.*`` widgets/flags that ``MainWindow.__init__`` creates, resolved at
    call time via the MRO.

    **One row or two is measured, not guessed.** This used to compare the WINDOW width
    against a hardcoded threshold, which was wrong twice over: the toolbar is narrower
    than the window (the sidebar takes the rest), and a fixed number goes stale the
    moment a control is added, renamed, or translated — a Chinese label is not the width
    of an English one. Adding the canvas tools pushed the single row to ~1509px of
    content inside a 1240px toolbar, so labels were cut off at any window size above the
    threshold. :meth:`_row_fits` asks the widgets how wide they actually need to be.
    """

    def _row_width(self, widgets) -> int:
        """Width one row of ``widgets`` needs: size hints + spacing + margins."""
        shown = [w for w in widgets if w.isVisible()]
        if not shown:
            return 0
        margins = self.tb_layout.contentsMargins()
        return (sum(w.sizeHint().width() for w in shown)
                + self.tb_layout.horizontalSpacing() * (len(shown) - 1)
                + margins.left() + margins.right())

    def _row_fits(self, widgets) -> bool:
        """Whether ``widgets`` fit on one row of the toolbar as it is now.

        Measured against the TOOLBAR's width, not the window's. Falls back to the window
        width only before the first layout pass, when the toolbar has no width yet and
        refusing to answer would make the arrangement flap on startup.
        """
        avail = self.canvas_toolbar.width() or self.width()
        return self._row_width(widgets) <= avail

    def eventFilter(self, watched, event) -> bool:
        if event.type() in (QEvent.Type.Show, QEvent.Type.Hide):
            if not getattr(self, '_layout_queued', False):
                self._layout_queued = True
                QTimer.singleShot(0, self._run_queued_layout)
        return super().eventFilter(watched, event)

    def _run_queued_layout(self):
        self._layout_queued = False
        self.adjust_toolbar_layout()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.adjust_toolbar_layout()

    def adjust_toolbar_layout(self):
        # Prevent recursion
        if getattr(self, '_adjusting_layout', False):
            return
        self._adjusting_layout = True

        try:
            # Clear layout first
            while self.tb_layout.count() > 0:
                self.tb_layout.takeAt(0)

            # Reset all column stretches
            for col in range(30):
                self.tb_layout.setColumnStretch(col, 0)

            idx = self.sidebar_stack.currentIndex()

            if idx == 0:
                # The single-row arrangement is spelled out FIRST so it can be
                # measured before it is chosen.
                cad_single_row = [
                    self.undo_btn,
                    self.redo_btn,
                    self.cad_sep1,
                    self.focus_geom_btn,
                    self.cad_clear_btn,
                    self.cad_clear_all_btn,
                    self.cad_redraw_btn,
                    self.cad_preview_btn,
                    self.cad_curve_preview_btn,
                    self.cad_file_preview_btn,
                    self.cad_cancel_btn,
                    self.cad_sep2,
                    self.measure_btn,
                    self.grid_snap_cb,
                    self.grid_snap_step,
                    self.view_back_btn,
                    self.view_fwd_btn,
                    self.show_vertices_cb,
                    self.show_nodes_cb,
                    self.quality_check_cb,
                    self.quality_mode_combo,
                    self.progress_bar,
                ]
                # cad_sep2 only exists in the single-row arrangement, so it must be
                # visible while measuring or the row is under-measured by its width
                # on every pass that follows a two-row one.
                self.cad_sep2.setVisible(True)
                is_narrow = not self._row_fits(cad_single_row)

                if is_narrow:
                    self.canvas_toolbar.setFixedHeight(68)
                    # cad_sep2 is redundant in two-row mode; hide so it is not
                    # left visible-but-unpositioned after the grid is rebuilt.
                    self.cad_sep2.setVisible(False)

                    row0_widgets = [
                        self.undo_btn,
                        self.redo_btn,
                        self.cad_sep1,
                        self.focus_geom_btn,
                        self.cad_clear_btn,
                        self.cad_clear_all_btn,
                        self.cad_redraw_btn,
                        self.cad_preview_btn,
                        self.cad_curve_preview_btn,
                        self.cad_file_preview_btn,
                        self.cad_cancel_btn,
                    ]
                    row1_widgets = [
                        self.measure_btn,
                        self.grid_snap_cb,
                        self.grid_snap_step,
                        self.view_back_btn,
                        self.view_fwd_btn,
                        self.show_vertices_cb,
                        self.show_nodes_cb,
                        self.quality_check_cb,
                        self.quality_mode_combo,
                        self.progress_bar,
                    ]

                    # Add to row 0
                    col_idx = 0
                    for w in row0_widgets:
                        if w.isVisible():
                            self.tb_layout.addWidget(w, 0, col_idx)
                            col_idx += 1

                    # Add to row 1
                    col_idx = 0
                    for w in row1_widgets:
                        if w.isVisible():
                            self.tb_layout.addWidget(w, 1, col_idx)
                            col_idx += 1

                    max_col = max(self.tb_layout.columnCount() - 1, 0)
                    self.tb_layout.setColumnStretch(max_col + 1, 1)
                else:
                    self.canvas_toolbar.setFixedHeight(36)
                    all_widgets = cad_single_row
                    col_idx = 0
                    for w in all_widgets:
                        if w.isVisible():
                            self.tb_layout.addWidget(w, 0, col_idx)
                            col_idx += 1
                    self.tb_layout.setColumnStretch(col_idx, 1)

            elif idx in (1, 2):  # Mesh modes
                mesh_single_row = [
                    self.undo_btn,
                    self.redo_btn,
                    self.cad_sep1,
                    self.mesh_preview_btn,
                    self.mesh_generate_btn,
                    self.mesh_cancel_btn,
                    self.mesh_send_solver_btn,
                    self.mesh_sep2,
                    self.mesh_focus_btn,
                    self.mesh_clear_btn,
                    self.mesh_sep3,
                    self.mesh_show_wireframe_cb,
                    self.mesh_show_bc_cb,
                    self.mesh_show_domain_cb,
                    self.mesh_sep4,
                    self.mesh_color_label,
                    self.mesh_color_mode_combo,
                    self.progress_bar,
                ]
                self.mesh_sep3.setVisible(True)     # see the CAD branch
                is_narrow = not self._row_fits(mesh_single_row)

                if is_narrow:
                    self.canvas_toolbar.setFixedHeight(68)
                    # mesh_sep3 is redundant in two-row mode; hide so it is not
                    # left visible-but-unpositioned after the grid is rebuilt.
                    self.mesh_sep3.setVisible(False)
                    row0_widgets = [
                        self.undo_btn,
                        self.redo_btn,
                        self.cad_sep1,
                        self.mesh_preview_btn,
                        self.mesh_generate_btn,
                        self.mesh_cancel_btn,
                        self.mesh_send_solver_btn,
                        self.mesh_sep2,
                        self.mesh_focus_btn,
                        self.mesh_clear_btn,
                    ]
                    row1_widgets = [
                        self.mesh_show_wireframe_cb,
                        self.mesh_show_bc_cb,
                        self.mesh_show_domain_cb,
                        self.mesh_sep4,
                        self.mesh_color_label,
                        self.mesh_color_mode_combo,
                        self.progress_bar,
                    ]

                    # Add to row 0
                    col_idx = 0
                    for w in row0_widgets:
                        if w.isVisible():
                            self.tb_layout.addWidget(w, 0, col_idx)
                            col_idx += 1

                    # Add to row 1
                    col_idx = 0
                    for w in row1_widgets:
                        if w.isVisible():
                            self.tb_layout.addWidget(w, 1, col_idx)
                            col_idx += 1

                    max_col = max(self.tb_layout.columnCount() - 1, 0)
                    self.tb_layout.setColumnStretch(max_col + 1, 1)
                else:
                    self.canvas_toolbar.setFixedHeight(36)
                    all_widgets = mesh_single_row
                    col_idx = 0
                    for w in all_widgets:
                        if w.isVisible():
                            self.tb_layout.addWidget(w, 0, col_idx)
                            col_idx += 1
                    self.tb_layout.setColumnStretch(col_idx, 1)

            else:  # Solver / Results / STL3d modes — minimal toolbar
                self.canvas_toolbar.setFixedHeight(36)
                self.mesh_sep3.setVisible(False)
                col_idx = 0
                # Solver (idx 3) shows Run Solver / Cancel; Immersed Boundary
                # (idx 5) shows Generate phi / Cancel — reparented from their
                # side panels onto the toolbar (see MainWindow.__init__).
                widgets = [self.undo_btn, self.redo_btn, self.cad_sep1]
                if idx == 3:
                    widgets += self.solver_tb_widgets
                elif idx == 5:
                    widgets += self.ib_tb_widgets
                # Include the progress bar so a background run shows it placed in
                # the grid instead of floating over the undo/redo buttons.
                widgets.append(self.progress_bar)
                for w in widgets:
                    if w.isVisible():
                        self.tb_layout.addWidget(w, 0, col_idx)
                        col_idx += 1
                self.tb_layout.setColumnStretch(col_idx, 1)
        finally:
            self._adjusting_layout = False
