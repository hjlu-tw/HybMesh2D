from __future__ import annotations
import os
import tempfile
import shutil
from PyQt6.QtWidgets import QFileDialog
from app.models.session import GeometrySession
from app.models.vtk_mesh import VTKMesh
from app.workers.mesh_gen_run import MeshGenWorker
from app.utils import find_binary_executable

class MeshGenControllerMixin:
    """Mixin containing HybMesh2D mesh generator execution, config editor mapping, and results visualization logic."""

    def load_mesh_config(self):
        """Prompt file dialog to load a Background_para.dat configuration file."""
        root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
        default_dir = os.path.join(root_dir, "config", "mesh")
        
        path, _ = QFileDialog.getOpenFileName(
            self.main_window, 
            "Load Mesh Configuration", 
            default_dir, 
            "Config Files (Background_para.dat Background_para*.dat *.dat);;All Files (*)"
        )
        if not path:
            return

        session = self.active_session()
        if not session:
            session = self._new_session("")

        try:
            session.mesh_config.load_from_file(path)
            self.main_window.mesh_config_panel.set_config(session.mesh_config)
            self.main_window.log_panel.log(f"Loaded mesh configuration from {path}")
        except Exception as e:
            self.main_window.log_panel.log(f"Failed to load mesh config: {e}")

    def save_mesh_config(self):
        """Extract config settings from UI panel and save them to a file."""
        session = self.active_session()
        if not session:
            self.main_window.log_panel.log("No active session. Please create or import geometry first.")
            return
        
        root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
        
        default_name = "Background_para.dat"
        if session.file_path:
            stem = os.path.splitext(os.path.basename(session.file_path))[0]
            default_name = f"Background_para_{stem}.dat"
        default_path = os.path.join(root_dir, "config", "mesh", default_name)

        path, _ = QFileDialog.getSaveFileName(
            self.main_window, 
            "Save Mesh Configuration", 
            default_path, 
            "Config Files (*.dat);;All Files (*)"
        )
        if not path:
            return

        try:
            cfg = self.main_window.mesh_config_panel.get_config()
            cfg.save_to_file(path)
            session.mesh_config = cfg
            self.main_window.log_panel.log(f"Saved mesh configuration to {path}")
        except Exception as e:
            self.main_window.log_panel.log(f"Failed to save mesh config: {e}")

    def preview_mesh_generator(self):
        """Update and fit the canvas view to the current geometry input files and domain box coordinates."""
        session = self.active_session()
        if not session:
            self.main_window.log_panel.log("No active session. Please create or import geometry first.")
            return

        cfg = self.main_window.mesh_config_panel.get_config()
        if cfg.domain_x_min >= cfg.domain_x_max:
            self.main_window.log_panel.log("[ERROR] Domain X Min must be strictly less than X Max.")
            return
        if cfg.domain_y_min >= cfg.domain_y_max:
            self.main_window.log_panel.log("[ERROR] Domain Y Min must be strictly less than Y Max.")
            return
        session.mesh_config = cfg

        self.main_window.mesh_canvas_view.update_mesh_config(cfg, fit_view=False)
        if session.vtk_mesh:
            self.main_window.mesh_canvas_view.render_mesh(session.vtk_mesh, fit_view=False)
        self.main_window.log_panel.log("Mesh generator preview updated.")

    def add_active_preprocessor_geometry(self):
        """Auto-add the resampled output file of the active PreProcessor session into the mesh generator input list."""
        session = self.active_session()
        if not session:
            self.main_window.log_panel.log("No active session. Please create or import geometry first.")
            return
        
        if not session.project_model.output_file:
            self.main_window.log_panel.log(
                "No resampled output file specified. Run 'Save & Export' in PreProcessor mode first."
            )
            return

        path = session.project_model.output_file
        abs_path = os.path.abspath(path)
        if not os.path.exists(abs_path):
            self.main_window.log_panel.log(
                f"Resampled file does not exist at '{abs_path}'. Run 'Save & Export' first."
            )
            return

        cfg = self.main_window.mesh_config_panel.get_config()
        if abs_path not in cfg.geom_files:
            cfg.geom_files.append(abs_path)
            self.main_window.mesh_config_panel.set_config(cfg)
            session.mesh_config = cfg
            self.main_window.log_panel.log(f"Added resampled geometry to configuration: {abs_path}")
        else:
            self.main_window.log_panel.log("Geometry file is already in the list.")

    def run_mesh_generator(self):
        """Extract GUI parameters, save to temporary config file, and execute HybMesh2D in background."""
        session = self.active_session()
        if not session:
            self.main_window.log_panel.log("No active session. Please create or import geometry first.")
            return

        if hasattr(self, '_mesh_worker') and self._mesh_worker is not None and self._mesh_worker.isRunning():
            self.main_window.log_panel.log("Mesh generation is already running. Please wait.")
            return

        exe = self._find_mesh_gen_executable()
        if not exe:
            self.main_window.log_panel.log("HybMesh2D binary not found. Please build the C++ project.")
            return

        # Extract current config values from UI
        cfg = self.main_window.mesh_config_panel.get_config()
        if cfg.domain_x_min >= cfg.domain_x_max:
            self.main_window.log_panel.log("[ERROR] Domain X Min must be strictly less than X Max.")
            return
        if cfg.domain_y_min >= cfg.domain_y_max:
            self.main_window.log_panel.log("[ERROR] Domain Y Min must be strictly less than Y Max.")
            return
        
        # Overrule solver output path to temporary folder to prevent generating permanent files on disk
        temp_vtk_path = os.path.abspath(os.path.join(self.temp_dir, f"mesh_session_{session.session_id}.vtk"))
        expected_vtk = temp_vtk_path

        session.mesh_config = cfg
        self.main_window.mesh_canvas_view.update_mesh_config(cfg)

        import copy
        tmp_cfg_data = copy.deepcopy(cfg)
        tmp_cfg_data.output_filename = temp_vtk_path
        tmp_cfg_data.export_vtk = True
        tmp_cfg_data.export_starcd = True

        # Save to temporary config file for generation
        tmp_cfg = tempfile.NamedTemporaryFile(
            dir=self.temp_dir, suffix="_mesh_para.dat", delete=False, mode="w"
        )
        tmp_cfg_data.save_to_file(tmp_cfg.name)
        tmp_cfg.close()

        # Disable/Enable panel and toolbar trigger buttons
        self.main_window.mesh_config_panel.run_mesh_btn.setEnabled(False)
        self.main_window.mesh_config_panel.cancel_mesh_btn.setEnabled(True)
        self.main_window.mesh_generate_btn.setEnabled(False)
        self.main_window.mesh_cancel_btn.setEnabled(True)

        self.main_window.log_panel.clear_log()
        self.main_window.log_panel.log("--- Starting HybMesh2D Mesh Generation ---")
        
        self._mesh_worker = MeshGenWorker(exe, tmp_cfg.name)
        self._mesh_worker.log_signal.connect(self.main_window.log_panel.log)
        self._mesh_worker.finished_signal.connect(
            lambda rc: self._on_mesh_gen_finished(rc, tmp_cfg.name, expected_vtk, session)
        )
        self.main_window.progress_bar.setVisible(True)
        self._mesh_worker.start()

    def cancel_mesh_generator(self):
        """Cancel background mesh generation thread."""
        if hasattr(self, '_mesh_worker') and self._mesh_worker is not None and self._mesh_worker.isRunning():
            self.main_window.log_panel.log("Cancelling mesh generation...")
            self._mesh_worker.cancel()

    def _find_mesh_gen_executable(self) -> str | None:
        """Locate compiled HybMesh2D executable in build candidate paths or PATH."""
        return find_binary_executable("HybMesh2D")



    def _get_expected_vtk_path(self, cfg: MeshConfig) -> str:
        """Calculate the expected output VTK filename matching main.cpp logic."""
        root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../.."))

        path = ""
        if cfg.output_filename:
            path = cfg.output_filename
        elif not cfg.geom_files:
            path = "results/meshes/mesh_cartesian.vtk"
        elif len(cfg.geom_files) == 1:
            stem = os.path.splitext(os.path.basename(cfg.geom_files[0]))[0]
            path = f"results/meshes/mesh_{stem}.vtk"
        else:
            path = "results/meshes/mesh_multiple.vtk"

        if os.path.isabs(path):
            return path
        return os.path.abspath(os.path.join(root_dir, path))

    def _resolve_export_path(self, session: GeometrySession, default_fallback_path: str, ext: str) -> str:
        """Resolve the default export path based on session configuration settings."""
        root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../.."))
        default_dir = os.path.join(root_dir, "results", "meshes")
        
        user_filename = session.mesh_config.output_filename if (session and session.mesh_config) else ""
        if user_filename:
            if user_filename.endswith(".*"):
                user_filename = user_filename[:-2] + ext
            else:
                user_filename = os.path.splitext(user_filename)[0] + ext
            if not os.path.isabs(user_filename):
                default_path = os.path.abspath(os.path.join(root_dir, user_filename))
            else:
                default_path = user_filename
        else:
            default_path = os.path.join(default_dir, os.path.basename(default_fallback_path))
        return default_path


    def _on_mesh_gen_finished(self, rc: int, tmp_cfg_name: str, expected_vtk_path: str, session: GeometrySession):
        """Handle execution thread termination, load VTK result, and refresh canvas."""
        self.main_window.progress_bar.setVisible(False)
        self.main_window.mesh_config_panel.run_mesh_btn.setEnabled(True)
        self.main_window.mesh_config_panel.cancel_mesh_btn.setEnabled(False)
        self.main_window.mesh_generate_btn.setEnabled(True)
        self.main_window.mesh_cancel_btn.setEnabled(False)

        # Cleanup temporary config file
        try:
            if os.path.exists(tmp_cfg_name):
                os.remove(tmp_cfg_name)
        except Exception as e:
            self.main_window.log_panel.log(f"Failed to delete temp config file {tmp_cfg_name}: {e}")

        # Check return code
        if rc == 0:
            self.main_window.log_panel.log("--- Mesh Generation Success ---")
            self.main_window.mesh_canvas_view.clear_error_highlights()
            if os.path.exists(expected_vtk_path):
                try:
                    mesh = VTKMesh.from_file(expected_vtk_path)
                    session.vtk_mesh = mesh
                    session.vtk_path = expected_vtk_path
                    if session is self.active_session():
                        self.main_window.mesh_canvas_view.update_mesh_config(session.mesh_config, fit_view=False)
                        self.main_window.mesh_canvas_view.render_mesh(mesh, fit_view=False)
                        self.main_window.mesh_stats_panel.update_stats(mesh, expected_vtk_path)
                    self.main_window.log_panel.log(f"Successfully loaded and rendered mesh from {expected_vtk_path}")
                except Exception as e:
                    self.main_window.log_panel.log(f"Failed to load generated mesh VTK: {e}")
            else:
                self.main_window.log_panel.log(f"Error: Expected VTK file not found at {expected_vtk_path}")
        elif rc == -2:
            self.main_window.log_panel.log("--- Mesh Generation Cancelled by User ---")
        elif rc == -3:
            self.main_window.log_panel.log("--- Mesh Generation Timed Out (10 min) ---")
        else:
            self.main_window.log_panel.log(f"--- Mesh Generation Failed (code {rc}) ---")
            # Try to detect self-intersection errors and highlight the failed geometry
            self._try_highlight_self_intersection_error()

    def _try_highlight_self_intersection_error(self):
        """Parse log output for self-intersection error and highlight the offending geometry."""
        import re
        log_text = self.main_window.log_panel.get_log_text()
        # C++ prints: "Error: Self-intersection detected in the final front of Geometry N."
        match = re.search(
            r"Self-intersection detected.*?Geometry\s+(\d+)",
            log_text, re.IGNORECASE
        )
        if match:
            geom_id = int(match.group(1))
            self.main_window.log_panel.log(
                f"[GUI] Self-intersection found in Geometry {geom_id} — highlighted on canvas."
            )
            self.main_window.mesh_canvas_view.highlight_error_geometry(geom_id)
        else:
            self.main_window.mesh_canvas_view.clear_error_highlights()

    def export_generated_vtk(self):
        """Export the generated VTK mesh file to a user-selected path."""
        session = self.active_session()
        if not session:
            self.main_window.log_panel.log("No active session. Please create or import geometry first.")
            return

        vtk_path = session.vtk_path
        if not vtk_path or not os.path.exists(vtk_path):
            vtk_path = self._get_expected_vtk_path(session.mesh_config) if session.mesh_config else ""

        if not vtk_path or not os.path.exists(vtk_path):
            self.main_window.log_panel.log("No generated VTK mesh available to export. Generate a mesh first.")
            return

        default_path = self._resolve_export_path(session, vtk_path, ".vtk")

        dest_path, _ = QFileDialog.getSaveFileName(
            self.main_window,
            "Export VTK Mesh",
            default_path,
            "VTK Files (*.vtk);;All Files (*)"
        )
        if not dest_path:
            return

        try:
            shutil.copy2(vtk_path, dest_path)
            self.main_window.log_panel.log(f"Successfully exported VTK mesh to {dest_path}")
        except Exception as e:
            self.main_window.log_panel.log(f"Failed to export VTK mesh: {e}")

    def export_star_cd(self):
        """Export the generated Star-CD mesh files (.vrt, .cel, .bnd) to a user-selected prefix."""
        session = self.active_session()
        if not session:
            self.main_window.log_panel.log("No active session. Please create or import geometry first.")
            return

        vtk_path = session.vtk_path
        if not vtk_path or not os.path.exists(vtk_path):
            vtk_path = self._get_expected_vtk_path(session.mesh_config) if session.mesh_config else ""

        if not vtk_path or not os.path.exists(vtk_path):
            self.main_window.log_panel.log("No generated mesh available. Export cannot proceed.")
            return

        base_name, _ = os.path.splitext(vtk_path)
        vrt_path = base_name + ".vrt"
        cel_path = base_name + ".cel"
        bnd_path = base_name + ".bnd"

        missing = []
        if not os.path.exists(vrt_path): missing.append(".vrt")
        if not os.path.exists(cel_path): missing.append(".cel")
        if not os.path.exists(bnd_path): missing.append(".bnd")

        if missing:
            self.main_window.log_panel.log(
                f"[INFO] Missing Star-CD files: {', '.join(missing)}. "
                "Ensure 'Export Star-CD' is enabled in the configuration panel, and regenerate the mesh."
            )
            return

        default_path = self._resolve_export_path(session, vrt_path, ".vrt")

        dest_vrt, _ = QFileDialog.getSaveFileName(
            self.main_window,
            "Export Star-CD Files",
            default_path,
            "Star-CD VRT (*.vrt);;All Files (*)"
        )
        if not dest_vrt:
            return

        dest_base, _ = os.path.splitext(dest_vrt)
        dest_cel = dest_base + ".cel"
        dest_bnd = dest_base + ".bnd"

        try:
            shutil.copy2(vrt_path, dest_vrt)
            shutil.copy2(cel_path, dest_cel)
            shutil.copy2(bnd_path, dest_bnd)
            self.main_window.log_panel.log(f"Successfully exported Star-CD files to {dest_base}.{{vrt,cel,bnd}}")
        except Exception as e:
            self.main_window.log_panel.log(f"Failed to export Star-CD files: {e}")
