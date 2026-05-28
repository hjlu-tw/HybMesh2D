from __future__ import annotations
import os
import tempfile
from PyQt6.QtWidgets import QFileDialog
from app.models.session import GeometrySession
from app.models.vtk_mesh import VTKMesh
from app.workers.mesh_gen_run import MeshGenWorker

class MeshGenControllerMixin:
    """Mixin containing HybMesh2D mesh generator execution, config editor mapping, and results visualization logic."""

    def load_mesh_config(self):
        """Prompt file dialog to load a Background_para.dat configuration file."""
        session = self.active_session()
        if not session:
            return
        
        path, _ = QFileDialog.getOpenFileName(
            self.main_window, 
            "Load Mesh Configuration", 
            "", 
            "Config Files (Background_para.dat Background_para*.dat *.dat);;All Files (*)"
        )
        if not path:
            return

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
            return
        
        path, _ = QFileDialog.getSaveFileName(
            self.main_window, 
            "Save Mesh Configuration", 
            "Background_para.dat", 
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

    def add_active_preprocessor_geometry(self):
        """Auto-add the resampled output file of the active PreProcessor session into the mesh generator input list."""
        session = self.active_session()
        if not session:
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
        session.mesh_config = cfg

        # Save to temporary config file for generation
        tmp_cfg = tempfile.NamedTemporaryFile(
            dir=self.temp_dir, suffix="_mesh_para.dat", delete=False, mode="w"
        )
        cfg.save_to_file(tmp_cfg.name)
        tmp_cfg.close()

        expected_vtk = self._get_expected_vtk_path(cfg)

        # Disable/Enable panel trigger buttons
        self.main_window.mesh_config_panel.run_mesh_btn.setEnabled(False)
        self.main_window.mesh_config_panel.cancel_mesh_btn.setEnabled(True)

        self.main_window.log_panel.log("--- Starting HybMesh2D Mesh Generation ---")
        
        self._mesh_worker = MeshGenWorker(exe, tmp_cfg.name)
        self._mesh_worker.log_signal.connect(self.main_window.log_panel.log)
        self._mesh_worker.finished_signal.connect(
            lambda rc: self._on_mesh_gen_finished(rc, tmp_cfg.name, expected_vtk, session)
        )
        self._mesh_worker.start()

    def cancel_mesh_generator(self):
        """Cancel background mesh generation thread."""
        if hasattr(self, '_mesh_worker') and self._mesh_worker is not None and self._mesh_worker.isRunning():
            self.main_window.log_panel.log("Cancelling mesh generation...")
            self._mesh_worker.cancel()

    def _find_mesh_gen_executable(self) -> str | None:
        """Locate compiled HybMesh2D executable in build candidate paths."""
        base_dir = os.path.dirname(os.path.abspath(__file__))
        candidates = [
            os.path.abspath(os.path.join(base_dir, "../../../../../build/HybMesh2D")),
            os.path.abspath("../../../build/HybMesh2D"),
            os.path.abspath("./build/HybMesh2D"),
            os.path.abspath("./HybMesh2D")
        ]
        for c in candidates:
            if os.path.exists(c):
                return c
        return None



    def _get_expected_vtk_path(self, cfg: MeshConfig) -> str:
        """Calculate the expected output VTK filename matching main.cpp logic."""
        root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../.."))

        
        path = ""
        if cfg.output_filename:
            path = cfg.output_filename
        elif not cfg.geom_files:
            path = "Results/mesh_cartesian.vtk"
        elif len(cfg.geom_files) == 1:
            stem = os.path.splitext(os.path.basename(cfg.geom_files[0]))[0]
            path = f"Results/mesh_{stem}.vtk"
        else:
            path = "Results/mesh_multiple.vtk"

        if os.path.isabs(path):
            return path
        return os.path.abspath(os.path.join(root_dir, path))


    def _on_mesh_gen_finished(self, rc: int, tmp_cfg_name: str, expected_vtk_path: str, session: GeometrySession):
        """Handle execution thread termination, load VTK result, and refresh canvas."""
        self.main_window.mesh_config_panel.run_mesh_btn.setEnabled(True)
        self.main_window.mesh_config_panel.cancel_mesh_btn.setEnabled(False)

        # Cleanup temporary config file
        try:
            if os.path.exists(tmp_cfg_name):
                os.remove(tmp_cfg_name)
        except Exception as e:
            self.main_window.log_panel.log(f"Failed to delete temp config file {tmp_cfg_name}: {e}")

        # Check return code
        if rc == 0:
            self.main_window.log_panel.log("--- Mesh Generation Success ---")
            if os.path.exists(expected_vtk_path):
                try:
                    mesh = VTKMesh.from_file(expected_vtk_path)
                    session.vtk_mesh = mesh
                    if session is self.active_session():
                        self.main_window.mesh_canvas_view.render_mesh(mesh)
                        self.main_window.mesh_stats_panel.update_stats(mesh)
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
