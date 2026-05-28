from __future__ import annotations
import os
import tempfile
import numpy as np
from PyQt6.QtWidgets import QFileDialog
from app.models.session import GeometrySession
from app.workers.backend_run import BackendWorker
from app.views.output_dialog import OutputDialog
from app.services.geometry_service import GeometryService

class BackendControllerMixin:
    """Mixin containing C++ backend execution, config generation, and file exporting logic."""

    def handle_quality_check_toggled(self, checked: bool):
        session = self.active_session()
        if session and session.resampled_points is not None:
            self.main_window.canvas_view.load_resampled_data(
                session.resampled_points, checked)

    def handle_show_vertices_toggled(self, checked: bool):
        self.main_window.canvas_view.set_geometry_symbols_visible(checked)

    def handle_show_nodes_toggled(self, checked: bool):
        self.main_window.canvas_view.set_resampled_nodes_visible(checked)

    def _find_executable(self) -> str | None:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        candidates = [
            os.path.abspath(os.path.join(base_dir, "../../../../../build/surface_resampler")),
            os.path.abspath("../../../build/surface_resampler"),
            os.path.abspath("./build/surface_resampler"),
        ]
        for c in candidates:
            if os.path.exists(c):
                return c
        return None



    def _write_temp_config(self, session: GeometrySession,
                           output_path: str) -> tuple[str, list[str]]:
        """Write config to a temp file and return its path and a list of extra temp files."""
        self._sync_active_curve_segment_from_ui()
        pm = session.project_model

        orig_input = pm.input_file
        orig_output = pm.output_file

        created_files = []

        # If geometry was modified (or it's a blank tab with curve points), save points to a temp .dat
        if (session.is_geometry_modified or not session.file_path) and session.original_points is not None:
            tmp_dat = tempfile.NamedTemporaryFile(
                dir=self.temp_dir, suffix=".dat", delete=False, mode="w")
            np.savetxt(tmp_dat.name, session.original_points, fmt="%.10f")
            pm.input_file = tmp_dat.name
            created_files.append(tmp_dat.name)
            tmp_dat.close()
        else:
            pm.input_file = session.file_path

        pm.output_file = output_path

        # Sync transform from sidebar
        pm.transform = self.main_window.sidebar_view.get_transform_dict()

        tmp_cfg = tempfile.NamedTemporaryFile(
            dir=self.temp_dir, suffix=".json", delete=False, mode="w")
        pm.export_config(tmp_cfg.name)
        created_files.append(tmp_cfg.name)
        tmp_cfg.close()

        # Restore original paths so we don't pollute the project model
        pm.input_file = orig_input
        pm.output_file = orig_output

        return tmp_cfg.name, created_files

    def preview_backend(self):
        """Run backend with a temp output path; display result on canvas."""
        session = self.active_session()
        if not session:
            return
        if not session.project_model.input_file and not session.project_model.segments:
            self.main_window.log_panel.log("No geometry loaded.")
            return
        exe = self._find_executable()
        if not exe:
            self.main_window.log_panel.log(
                "Executable not found. Please build the C++ project.")
            return

        tmp_out = tempfile.NamedTemporaryFile(
            dir=self.temp_dir, suffix="_preview.dat", delete=False)
        tmp_out_name = tmp_out.name
        tmp_out.close()

        cfg_path, created_files = self._write_temp_config(session, tmp_out_name)
        to_cleanup = created_files + [tmp_out_name]

        self.main_window.sidebar_view.preview_btn.setEnabled(False)
        self.main_window.log_panel.log("--- Preview: Starting Backend ---")
        self._run_backend(exe, cfg_path, session,
                          on_finish=lambda rc: self._on_preview_finished(
                              rc, tmp_out_name, to_cleanup, session))

    def save_output(self):
        """Ask user for output path, then run backend and save."""
        session = self.active_session()
        if not session:
            return
        if not session.project_model.input_file and not session.project_model.segments:
            self.main_window.log_panel.log("No geometry loaded.")
            return
        exe = self._find_executable()
        if not exe:
            self.main_window.log_panel.log(
                "Executable not found. Please build the C++ project.")
            return

        default_out = session.project_model.output_file
        tmp_dir = tempfile.gettempdir()
        if default_out and (tmp_dir in default_out or "/tmp" in default_out or "Temporary" in default_out):
            default_out = ""

        if not default_out:
            default_out = session.default_output_path

        dlg = OutputDialog(default_out, self.main_window)
        if dlg.exec() != OutputDialog.DialogCode.Accepted:
            return

        out_path = dlg.output_path
        session.project_model.output_file = out_path
        cfg_path, created_files = self._write_temp_config(session, out_path)

        self.main_window.sidebar_view.save_btn.setEnabled(False)
        self.main_window.log_panel.log("--- Save: Starting Backend ---")
        self._run_backend(exe, cfg_path, session,
                          on_finish=lambda rc: self._on_save_finished(
                              rc, out_path, created_files, session))

    def generate_json(self):
        session = self.active_session()
        if not session:
            return
        self._sync_active_curve_segment_from_ui()
        if not session.project_model.input_file and not session.project_model.segments:
            self.main_window.log_panel.log("No geometry loaded.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self.main_window, "Export JSON Config",
            "gui_config.json", "JSON Files (*.json)")
        if not path:
            return

        pm = session.project_model
        orig_input = pm.input_file
        pm.input_file = session.file_path

        pm.transform = self.main_window.sidebar_view.get_transform_dict()
        pm.export_config(path)

        pm.input_file = orig_input
        self.main_window.log_panel.log(f"Config exported: {path}")

    def _run_backend(self, exe: str, cfg_path: str,
                     session: GeometrySession, on_finish):
        if hasattr(self, "_worker") and self._worker is not None and self._worker.isRunning():
            self.main_window.log_panel.log("Backend is already running. Please wait.")
            return
        self._worker = BackendWorker(exe, cfg_path)
        self._worker.log_signal.connect(self.main_window.log_panel.log)
        self._worker.finished_signal.connect(on_finish)
        self._worker.start()

    def _on_preview_finished(self, rc: int, tmp_out: str, to_cleanup: list[str],
                             session: GeometrySession):
        self.main_window.sidebar_view.preview_btn.setEnabled(True)
        try:
            if rc == 0 and os.path.exists(tmp_out):
                try:
                    pts = np.loadtxt(tmp_out)
                    session.resampled_points = pts
                    if session is self.active_session():
                        show_q = self.main_window.quality_check_cb.isChecked()
                        self.main_window.canvas_view.load_resampled_data(pts, show_q)
                        self.preview_curve_formula()
                    self.main_window.log_panel.log(
                        f"Preview done ({len(pts)} points).")
                except Exception as e:
                    self.main_window.log_panel.log(f"Preview load error: {e}")
            else:
                self.main_window.log_panel.log(
                    f"--- Preview Backend Failed (code {rc}) ---")
        finally:
            for path in to_cleanup:
                try:
                    if os.path.exists(path):
                        os.remove(path)
                except Exception as e:
                    self.main_window.log_panel.log(f"Failed to delete temp file {path}: {e}")

    def _on_save_finished(self, rc: int, out_path: str, to_cleanup: list[str],
                          session: GeometrySession):
        self.main_window.sidebar_view.save_btn.setEnabled(True)
        try:
            if rc == 0:
                self.main_window.log_panel.log(
                    f"--- Saved to: {out_path} ---")
                if os.path.exists(out_path):
                    try:
                        pts = np.loadtxt(out_path)
                        session.resampled_points = pts
                        if session is self.active_session():
                            show_q = self.main_window.quality_check_cb.isChecked()
                            self.main_window.canvas_view.load_resampled_data(pts, show_q)
                            self.preview_curve_formula()
                        self.main_window.log_panel.log(
                            f"Loaded result ({len(pts)} points).")
                    except Exception as e:
                        self.main_window.log_panel.log(f"Result load error: {e}")
            else:
                self.main_window.log_panel.log(
                    f"--- Backend Failed (code {rc}) ---")
        finally:
            for path in to_cleanup:
                try:
                    if os.path.exists(path):
                        os.remove(path)
                except Exception as e:
                    self.main_window.log_panel.log(f"Failed to delete temp file {path}: {e}")
