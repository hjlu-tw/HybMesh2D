from __future__ import annotations
import os
import tempfile
import shutil
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QFileDialog, QListWidgetItem, QMessageBox
from app.models.session import GeometrySession
from app.models.vtk_mesh import VTKMesh
from app.workers.mesh_gen_run import MeshGenWorker
from app.utils import find_binary_executable

class MeshGenControllerMixin:
    """Mixin containing HybMesh2D mesh generator execution, config editor mapping, and results visualization logic."""

    def add_mesh_tab(self):
        """Add a new tab to the Mesh Generator / Statistics tab strip.

        Mesh state is global/shared, so these tabs are visual workspaces; a new
        tab does not fork the config or results — it is a separate label the
        user can keep alongside others while working in mesh modes.
        """
        bar = self.main_window.mesh_tab_bar
        seq = getattr(self, "_mesh_tab_seq", bar.count()) + 1
        self._mesh_tab_seq = seq
        idx = bar.addTab(f"Mesh {seq}")
        bar.setCurrentIndex(idx)
        return idx

    def close_mesh_tab(self, idx: int):
        """Close a mesh-mode tab, always keeping at least one open."""
        bar = self.main_window.mesh_tab_bar
        if bar.count() <= 1:
            return
        bar.removeTab(idx)

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

        try:
            self.global_mesh_config.load_from_file(path)
            self.main_window.mesh_config_panel.set_config(self.global_mesh_config)
            self.main_window.log_panel.log(f"Loaded mesh configuration from {path}")
            missing = getattr(self.global_mesh_config, "missing_geom_files", [])
            if missing:
                self.main_window.log_panel.log(
                    f"[WARNING] Geometry file(s) not found (paths may be broken): {', '.join(missing)}"
                )
            self.sync_mesh_layers_panel()
        except Exception as e:
            self.main_window.log_panel.log(f"Failed to load mesh config: {e}")

    def save_mesh_config(self):
        """Extract config settings from UI panel and save them to a file."""
        root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
        
        default_name = "Background_para.dat"
        session = self.active_session()
        if session and session.file_path:
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
            self.global_mesh_config = cfg
            self.main_window.log_panel.log(f"Saved mesh configuration to {path}")
        except Exception as e:
            self.main_window.log_panel.log(f"Failed to save mesh config: {e}")

    def preview_mesh_generator(self):
        """Update and fit the canvas view to the current geometry input files and domain box coordinates."""
        cfg = self.main_window.mesh_config_panel.get_config()
        if cfg.domain_x_min >= cfg.domain_x_max:
            self.main_window.log_panel.log("[ERROR] Domain X Min must be strictly less than X Max.")
            return
        if cfg.domain_y_min >= cfg.domain_y_max:
            self.main_window.log_panel.log("[ERROR] Domain Y Min must be strictly less than Y Max.")
            return
        self.global_mesh_config = cfg

        self.main_window.mesh_canvas_view.update_mesh_config(cfg, fit_view=False)
        if self.global_vtk_mesh:
            self.main_window.mesh_canvas_view.render_mesh(self.global_vtk_mesh, fit_view=False)
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
            self.global_mesh_config = cfg
            self.main_window.mesh_config_panel.set_config(cfg)
            self.main_window.log_panel.log(f"Added resampled geometry to configuration: {abs_path}")
            self.sync_mesh_layers_panel()
        else:
            self.main_window.log_panel.log("Geometry file is already in the list.")

    def run_mesh_generator(self):
        """Extract GUI parameters, save to temporary config file, and execute HybMesh2D in background."""
        if hasattr(self, '_mesh_worker') and self._mesh_worker is not None and self._mesh_worker.isRunning():
            self.main_window.log_panel.log("Mesh generation is already running. Please wait.")
            return

        exe = self._find_mesh_gen_executable()
        if not exe:
            self.main_window.log_panel.log("HybMesh2D binary not found. Please build the C++ project.")
            return

        # Extract current config values from UI
        cfg = self.main_window.mesh_config_panel.get_config()

        # Diagnostic: report the geometry files actually handed to HybMesh2D.
        # (A geometry that previews on the canvas but is missing/empty here is the
        # usual cause of "mesh generates but shows no boundary/BL".)
        if not cfg.geom_files:
            self.main_window.log_panel.log(
                "[WARNING] No geometry files in the mesh config — the mesh will "
                "have no boundary/BL. If you drew with 'Add analytic edge', run "
                "'Save & Export' in CAD mode (or 'Add Active'/check it in Geometry "
                "Layers) so it is written to a .dat first.")
        else:
            for gf in cfg.geom_files:
                if not os.path.exists(gf):
                    self.main_window.log_panel.log(
                        f"[WARNING] Geometry file missing: {gf}")
                else:
                    try:
                        with open(gf) as _f:
                            npts = sum(1 for ln in _f if ln.strip())
                        self.main_window.log_panel.log(
                            f"[geom] {os.path.basename(gf)} ({npts} points)")
                    except OSError:
                        pass

        if cfg.domain_x_min >= cfg.domain_x_max:
            self.main_window.log_panel.log("[ERROR] Domain X Min must be strictly less than X Max.")
            return
        if cfg.domain_y_min >= cfg.domain_y_max:
            self.main_window.log_panel.log("[ERROR] Domain Y Min must be strictly less than Y Max.")
            return
        
        # Overrule solver output path to temporary folder to prevent generating permanent files on disk
        temp_vtk_path = os.path.abspath(os.path.join(self.temp_dir, "global_mesh.vtk"))
        expected_vtk = temp_vtk_path

        self.global_mesh_config = cfg
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
        self._mesh_worker.progress_signal.connect(self._on_mesh_gen_progress)
        self._mesh_worker.finished_signal.connect(
            lambda rc: self._on_mesh_gen_finished(rc, tmp_cfg.name, expected_vtk)
        )
        # Determinate progress driven by parsed stdout markers (R5).
        pb = self.main_window.progress_bar
        pb.setRange(0, 100)
        pb.setValue(0)
        pb.setVisible(True)
        self._mesh_worker.start()

    def _on_mesh_gen_progress(self, pct: int):
        self.main_window.progress_bar.setValue(pct)

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

    def _resolve_export_path(self, default_fallback_path: str, ext: str) -> str:
        """Resolve the default export path based on global configuration settings."""
        root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../.."))
        default_dir = os.path.join(root_dir, "results", "meshes")
        
        user_filename = self.global_mesh_config.output_filename if self.global_mesh_config else ""
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


    def _on_mesh_gen_finished(self, rc: int, tmp_cfg_name: str, expected_vtk_path: str):
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
                    self.global_vtk_mesh = mesh
                    self.global_vtk_path = expected_vtk_path
                    self.main_window.mesh_canvas_view.update_mesh_config(self.global_mesh_config, fit_view=False)
                    self.main_window.mesh_canvas_view.render_mesh(mesh, fit_view=False)
                    self.main_window.mesh_stats_panel.update_stats(mesh, expected_vtk_path)
                    self.main_window.log_panel.log(f"Successfully loaded and rendered mesh from {expected_vtk_path}")
                except Exception as e:
                    self.main_window.log_panel.log(f"Failed to load generated mesh VTK: {e}")
            else:
                self.main_window.log_panel.log(f"Error: Expected VTK file not found at {expected_vtk_path}")
        else:
            if rc == -2:
                self.main_window.log_panel.log("--- Mesh Generation Cancelled by User ---")
            elif rc == -3:
                self.main_window.log_panel.log("--- Mesh Generation Timed Out (10 min) ---")
            else:
                self.main_window.log_panel.log(f"--- Mesh Generation Failed (code {rc}) ---")

            # Clear the previous mesh results from session and UI
            self.global_vtk_mesh = None
            self.global_vtk_path = ""
            self.main_window.mesh_canvas_view.clear_mesh_results()
            self.main_window.mesh_stats_panel.update_stats(None)

            # Clear previous error highlights first, then try to detect and highlight new ones
            self.main_window.mesh_canvas_view.clear_error_highlights()
            if rc not in (-2, -3):
                self._try_highlight_self_intersection_error()

    def _try_highlight_self_intersection_error(self):
        """Parse log output for self-intersection or cross-geometry intersection errors and highlight the offending geometry and coordinates."""
        import re
        log_text = self.main_window.log_panel.get_log_text()

        # Try to find cross-geometry intersection:
        # "Error: Intersection detected between Geometry <N1> and Geometry <N2> at the final front at point (<X>, <Y>)."
        cross_match = re.search(
            r"Intersection detected between Geometry\s+(\d+)\s+and\s+Geometry\s+(\d+).*?at point\s+\(([-\d\.eE\+]+),\s*([-\d\.eE\+]+)\)",
            log_text, re.IGNORECASE
        )
        if cross_match:
            geom_id1 = int(cross_match.group(1))
            geom_id2 = int(cross_match.group(2))
            try:
                x = float(cross_match.group(3))
                y = float(cross_match.group(4))
            except ValueError:
                x, y = None, None

            self.main_window.log_panel.log(
                f"[GUI] Intersection detected between Geometry {geom_id1} and Geometry {geom_id2} — highlighted on canvas."
            )
            self.main_window.mesh_canvas_view.highlight_error_geometry([geom_id1, geom_id2])
            if x is not None and y is not None:
                self.main_window.mesh_canvas_view.highlight_self_intersection_point(x, y)
                self.main_window.log_panel.log(f"[GUI] Intersection coordinate: ({x}, {y})")
            return

        # Try to find self-intersection:
        # "Error: Self-intersection detected in the final front of Geometry <N> at point (<X>, <Y>)."
        self_match = re.search(
            r"Self-intersection detected.*?Geometry\s+(\d+).*?at point\s+\(([-\d\.eE\+]+),\s*([-\d\.eE\+]+)\)",
            log_text, re.IGNORECASE
        )
        if self_match:
            geom_id = int(self_match.group(1))
            try:
                x = float(self_match.group(2))
                y = float(self_match.group(3))
            except ValueError:
                x, y = None, None

            self.main_window.log_panel.log(
                f"[GUI] Self-intersection detected in Geometry {geom_id} — highlighted on canvas."
            )
            self.main_window.mesh_canvas_view.highlight_error_geometry(geom_id)
            if x is not None and y is not None:
                self.main_window.mesh_canvas_view.highlight_self_intersection_point(x, y)
                self.main_window.log_panel.log(f"[GUI] Self-intersection coordinate: ({x}, {y})")
            return

        self.main_window.mesh_canvas_view.clear_error_highlights()

    def export_generated_vtk(self):
        """Export the generated VTK mesh file to a user-selected path."""
        vtk_path = self.global_vtk_path
        if not vtk_path or not os.path.exists(vtk_path):
            vtk_path = self._get_expected_vtk_path(self.global_mesh_config) if self.global_mesh_config else ""

        if not vtk_path or not os.path.exists(vtk_path):
            self.main_window.log_panel.log("No generated VTK mesh available to export. Generate a mesh first.")
            return

        default_path = self._resolve_export_path(vtk_path, ".vtk")

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
        vtk_path = self.global_vtk_path
        if not vtk_path or not os.path.exists(vtk_path):
            vtk_path = self._get_expected_vtk_path(self.global_mesh_config) if self.global_mesh_config else ""

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

        default_path = self._resolve_export_path(vrt_path, ".vrt")

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

    def sync_mesh_layers_panel(self):
        """Update the Geometry Layers QListWidget in the MeshConfigPanel based on current sessions."""
        panel = self.main_window.mesh_config_panel
        if not hasattr(panel, 'layers_list_widget'):
            return

        panel.layers_list_widget.blockSignals(True)
        panel.layers_list_widget.clear()

        for session in self.sessions:
            name = session.display_name
            out_file = session.project_model.output_file
            display_text = name
            
            abs_out_file = ""
            if out_file:
                abs_out_file = os.path.abspath(out_file)
                if not os.path.exists(abs_out_file):
                    display_text += " (not exported)"
            else:
                display_text += " (no output file)"

            item = QListWidgetItem(display_text)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            
            if abs_out_file and abs_out_file in self.global_mesh_config.geom_files:
                item.setCheckState(Qt.CheckState.Checked)
            else:
                item.setCheckState(Qt.CheckState.Unchecked)

            item.setData(Qt.ItemDataRole.UserRole, (session.session_id, abs_out_file))
            if hasattr(session, "color") and session.color:
                item.setForeground(QColor(session.color))
            
            panel.layers_list_widget.addItem(item)

        panel.layers_list_widget.blockSignals(False)

    def handle_mesh_layer_toggled(self, item: QListWidgetItem):
        """Called when a geometry layer checkbox is checked or unchecked in the Mesh Generator panel."""
        data = item.data(Qt.ItemDataRole.UserRole)
        if not data:
            return
        session_id, abs_out_file = data
        
        session = None
        for s in self.sessions:
            if s.session_id == session_id:
                session = s
                break
        
        if not session:
            return

        is_checked = item.checkState() == Qt.CheckState.Checked
        
        if is_checked:
            if not abs_out_file or not os.path.exists(abs_out_file):
                QMessageBox.warning(
                    self.main_window,
                    "Geometry Not Exported",
                    f"The geometry '{session.display_name}' has not been saved/exported yet.\n"
                    "Please switch to CAD mode and run 'Save & Export' first."
                )
                panel = self.main_window.mesh_config_panel
                panel.layers_list_widget.blockSignals(True)
                item.setCheckState(Qt.CheckState.Unchecked)
                panel.layers_list_widget.blockSignals(False)
                return
            
            if abs_out_file not in self.global_mesh_config.geom_files:
                self.global_mesh_config.geom_files.append(abs_out_file)
        else:
            if abs_out_file in self.global_mesh_config.geom_files:
                self.global_mesh_config.geom_files.remove(abs_out_file)
        
        self.main_window.mesh_config_panel.set_config(self.global_mesh_config)

    def add_all_sessions_to_mesh(self):
        """Add all sessions that have valid exported output files to the global mesh config."""
        added_any = False
        missing_exports = []
        for session in self.sessions:
            out_file = session.project_model.output_file
            if out_file:
                abs_out = os.path.abspath(out_file)
                if os.path.exists(abs_out):
                    if abs_out not in self.global_mesh_config.geom_files:
                        self.global_mesh_config.geom_files.append(abs_out)
                        added_any = True
                else:
                    missing_exports.append(session.display_name)
            else:
                missing_exports.append(session.display_name)
        
        if missing_exports:
            names = ", ".join(missing_exports)
            self.main_window.log_panel.log(
                f"[WARNING] The following sessions cannot be added because they have not been exported yet: {names}"
            )
        
        if added_any or not missing_exports:
            self.main_window.mesh_config_panel.set_config(self.global_mesh_config)
            self.sync_mesh_layers_panel()
            self.main_window.log_panel.log("All exported sessions added to mesh configuration.")
