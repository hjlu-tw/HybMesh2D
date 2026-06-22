from __future__ import annotations
import os

from PyQt6.QtWidgets import QFileDialog

from app.utils import repo_root


class PostprocessControllerMixin:
    """Result loading / visualization control.

    The ResultCanvasView owns its own variable / colormap / overlay controls, so
    this mixin is thin: it routes result files into the canvas, auto-loads the
    solver output on completion, and exposes programmatic delegates.
    """

    RESULTS_MODE_INDEX = 4

    # ------------------------------------------------------------------ #
    def open_result_dialog(self):
        """Prompt for a Tecplot solution file and load it into the Results view."""
        root = repo_root()
        start = os.path.join(root, "results", "solver")
        if not os.path.isdir(start):
            start = root
        path, _ = QFileDialog.getOpenFileName(
            self.main_window, "Open Solver Result", start,
            "Tecplot (*.dat *.dat.* xtecp*);;All Files (*)")
        if path:
            self.load_result(path)

    def load_result(self, path: str):
        """Load a Tecplot result file into the Results canvas and show it."""
        if not path or not os.path.exists(path):
            self.main_window.log_panel.log(f"[ERROR] Result file not found: {path}")
            return
        try:
            self.main_window.result_canvas_view.load_result_path(path)
        except Exception as e:
            self.main_window.log_panel.log(f"[ERROR] Failed to load result: {e}")
            return

        # from_file() only raises when the data region is shorter than the
        # NODAL count; a truncated/malformed file can still parse into a result
        # with no nodes or no connectivity, which renders blank. Don't claim
        # success or switch to the Results view in that case.
        result = self.main_window.result_canvas_view._result
        n_nodes = 0 if result is None else len(result.nodes)
        n_elems = 0 if result is None else len(result.elements)
        if n_nodes == 0 or n_elems == 0:
            self.main_window.result_canvas_view.clear()
            self.global_result_data = None
            self.main_window.log_panel.log(
                f"[ERROR] {os.path.basename(path)} has no usable mesh data "
                f"({n_nodes} node(s), {n_elems} element(s)) — file may be "
                "truncated or malformed.")
            return

        self.global_result_data = result
        self.global_result_path = path
        self.main_window.mode_combo.setCurrentIndex(self.RESULTS_MODE_INDEX)
        zones = result.zones if result else []
        self.main_window.log_panel.log(
            f"Loaded result {os.path.basename(path)} "
            f"({len(zones)} zone(s)).")

    def auto_load_solver_result(self):
        """Called after a successful solver run to surface the Tecplot output."""
        path = getattr(self, "global_result_path", "")
        if path and os.path.exists(path):
            self.load_result(path)
            return True
        return False

    # ------------------------------------------------------------------ #
    # Programmatic delegates (the canvas control bar does the same interactively)
    # ------------------------------------------------------------------ #
    def change_variable(self, var_name: str):
        self.main_window.result_canvas_view.var_combo.setCurrentText(var_name)

    def update_colormap(self, cmap: str):
        self.main_window.result_canvas_view.set_cmap(cmap)

    def toggle_mesh_overlay(self, show: bool):
        self.main_window.result_canvas_view.mesh_cb.setChecked(show)

    def toggle_streamlines(self, show: bool):
        self.main_window.result_canvas_view.stream_cb.setChecked(show)

    def export_result_screenshot(self):
        self.main_window.result_canvas_view._save_png()
