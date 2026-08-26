from __future__ import annotations
import os

import numpy as np
from PyQt6.QtWidgets import QFileDialog

from app.utils import repo_root


def _split_gap_pieces(pts: np.ndarray, gaps) -> list:
    """Split a polyline at connect-break indices (each gap is the index of the
    last point before a break, matching session.resampled_gaps)."""
    if pts is None or len(pts) < 2:
        return []
    if not gaps:
        return [pts]
    pieces, start = [], 0
    for b in sorted(int(g) for g in gaps):
        if b + 1 > start:
            pieces.append(pts[start:b + 1])
        start = b + 1
    if start < len(pts):
        pieces.append(pts[start:])
    return [p for p in pieces if len(p) >= 2]


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
            self.log(f"[ERROR] Result file not found: {path}")
            return
        try:
            # No permission flag travels any more (#43): the load asks nothing,
            # so an unattended run and an interactive one take one path and a CI
            # screenshot shows what the user would see. The `_pipeline_running`
            # guard below is a different question — it is about the ERROR modal,
            # which is still a modal.
            self.main_window.result_canvas_view.load_result_path(path)
        except Exception as e:
            self.log(f"[ERROR] Failed to load result: {e}")
            # Only interrupt a person. This is also reached from the solver's
            # finished handler, which Run All chains in batch mode ("no per-stage
            # dialogs"): a modal there opens a nested event loop that blocks the
            # rest of the pipeline until someone physically clicks OK, so an
            # unattended run would hang instead of failing with the log line above.
            if not getattr(self, "_pipeline_running", False):
                from app.utils import report_warning
                report_warning(self.main_window, "Load Result Failed",
                               f"'{os.path.basename(path)}' could not be loaded as a "
                               "result field.", detail=str(e))
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
            self.log(
                f"[ERROR] {os.path.basename(path)} has no usable mesh data "
                f"({n_nodes} node(s), {n_elems} element(s)) — file may be "
                "truncated or malformed.")
            return

        self.global_result_data = result
        self.global_result_path = path
        self.main_window.mode_combo.setCurrentIndex(self.RESULTS_MODE_INDEX)
        zones = result.zones if result else []
        self.log(
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
        # var_name is the variable CODE; the combo shows readable labels with the
        # code stored as item data (#6), so select by data, not display text.
        self.main_window.result_canvas_view.select_variable(var_name)

    def update_colormap(self, cmap: str):
        self.main_window.result_canvas_view.set_cmap(cmap)

    def toggle_mesh_overlay(self, show: bool):
        self.main_window.result_canvas_view.mesh_cb.setChecked(show)

    def toggle_streamlines(self, show: bool):
        self.main_window.result_canvas_view.stream_cb.setChecked(show)

    def export_result_screenshot(self):
        self.main_window.result_canvas_view._save_png()

    def open_surface_definition(self):
        """Results ▸ Define Surface… — the same picker as the canvas's Surface…
        button (which curve counts as the surface, and where s = 0 is)."""
        self.main_window.result_canvas_view.open_surface_dialog()

    # ------------------------------------------------------------------ #
    # Geometry overlay data provider (used by ResultControlPanel)
    # ------------------------------------------------------------------ #
    def cad_overlay_sessions(self) -> list:
        """[(session_id, display_name, color, has_geom)] for the overlay picker —
        one entry per open session, so the panel can tick individual geometries."""
        out: list = []
        for s in getattr(self, "sessions", []):
            pts = s.resampled_points if s.resampled_points is not None else s.original_points
            has_geom = pts is not None and len(pts) >= 2
            out.append((s.session_id, s.display_name, getattr(s, "color", ""), has_geom))
        return out

    def cad_overlay_polylines(self, session_ids=None) -> list:
        """CAD outline polylines (list of (N,2) arrays) from open sessions —
        resampled points if present (what got meshed), else the raw loaded points,
        split at piece breaks and closed per the project flag. With `session_ids`
        (a set) only those sessions are included; otherwise all of them."""
        polys: list = []
        for s in getattr(self, "sessions", []):
            if session_ids is not None and s.session_id not in session_ids:
                continue
            use_resampled = s.resampled_points is not None
            pts = s.resampled_points if use_resampled else s.original_points
            if pts is None or len(pts) < 2:
                continue
            pts = np.atleast_2d(np.asarray(pts, dtype=float))[:, :2]
            gaps = s.resampled_gaps if use_resampled else None
            closed = getattr(s.project_model, "is_closed", False)
            for piece in _split_gap_pieces(pts, gaps):
                if closed and not np.allclose(piece[0], piece[-1]):
                    piece = np.vstack([piece, piece[0]])
                polys.append(piece)
        if not polys:
            self.log(
                "[Results] CAD overlay: no geometry selected / found in the open "
                "project(s).")
        return polys
