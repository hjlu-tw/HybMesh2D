from __future__ import annotations
from PyQt6.QtCore import QTimer, QEvent


class MainWindowToolbarMixin:
    """
    Responsive canvas-toolbar layout and its driving events for
    :class:`MainWindow`.

    Mixed into ``MainWindow`` (after ``QMainWindow``); every method references
    ``self.*`` widgets/flags that ``MainWindow.__init__`` creates, resolved at
    call time via the MRO. Extracted verbatim — no behaviour change.
    """

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
            width = self.width()

            # Determine threshold based on mode
            if idx == 0:
                threshold = 1200
                is_narrow = (width < threshold)

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
                    ]
                    row1_widgets = [
                        self.show_vertices_cb,
                        self.show_nodes_cb,
                        self.quality_check_cb,
                        self.quality_mode_combo,
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
                    self.cad_sep2.setVisible(True)
                    all_widgets = [
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
                        self.cad_sep2,
                        self.show_vertices_cb,
                        self.show_nodes_cb,
                        self.quality_check_cb,
                        self.quality_mode_combo,
                    ]
                    col_idx = 0
                    for w in all_widgets:
                        if w.isVisible():
                            self.tb_layout.addWidget(w, 0, col_idx)
                            col_idx += 1
                    self.tb_layout.setColumnStretch(col_idx, 1)

            elif idx in (1, 2):  # Mesh modes
                threshold = 1100
                is_narrow = (width < threshold)

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
                    self.mesh_sep3.setVisible(True)
                    all_widgets = [
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
