from __future__ import annotations
import os
import numpy as np
from PyQt6.QtWidgets import QFileDialog
from PyQt6.QtCore import QSettings
from app.models.session import SESSION_COLORS
from app.utils import repo_root, report_warning


class SessionLoadControllerMixin:
    """Mixin containing geometry / STL / JSON file loading and recent-files logic."""

    def load_geometry(self):
        file_paths, _ = QFileDialog.getOpenFileNames(
            self.main_window, "Open Geometry File(s)",
            "examples/geometries", "Data Files (*.dat)")
        for fp in file_paths:
            if os.path.exists(fp):
                self._load_geometry_file(fp)
            else:
                self.main_window.log_panel.log(f"File not found: {fp}")

    def load_geometry_from_path(self, file_path: str):
        if os.path.exists(file_path):
            self._load_geometry_file(file_path)
        else:
            self.main_window.log_panel.log(f"File not found: {file_path}")

    def load_stl_geometry(self):
        file_paths, _ = QFileDialog.getOpenFileNames(
            self.main_window, "Import STL Surface(s) — z=0 only",
            "examples/geometries", "STL Files (*.stl)")
        for fp in file_paths:
            if os.path.exists(fp):
                self._load_stl_file(fp)
            else:
                self.main_window.log_panel.log(f"File not found: {fp}")

    def _load_stl_file(self, file_path: str):
        """Load a planar (z=0) STL, auto-detect its boundary outline as surface
        points, and bring each detected loop in as a geometry session.

        The boundary points are written to temporary ``.dat`` files so the rest
        of the pipeline (resampler, mesh generator, export) is unchanged.
        """
        from app.services.stl_loader import load_planar_boundary_loops, STLPlanarError
        try:
            loops = load_planar_boundary_loops(file_path)
        except STLPlanarError as e:
            self.main_window.log_panel.log(f"[STL] {e}")
            report_warning(self.main_window, "STL Import Failed",
                               "The STL file could not be imported.", detail=str(e))
            return
        except Exception as e:
            self.main_window.log_panel.log(
                f"[STL] Failed to read '{os.path.basename(file_path)}': {e}")
            return

        base = os.path.splitext(os.path.basename(file_path))[0]
        multi = len(loops) > 1
        for i, pts in enumerate(loops):
            suffix = f"_loop{i + 1}" if multi else ""
            dat_path = os.path.join(self.temp_dir, f"{base}{suffix}.dat")
            try:
                np.savetxt(dat_path, pts, fmt="%.10f")
            except Exception as e:
                self.main_window.log_panel.log(f"[STL] Could not stage loop {i + 1}: {e}")
                continue
            self._load_geometry_file(dat_path, record_recent=False)

        # Record the original STL (not the temp .dat) in the recent-files list.
        self.update_recent_files(os.path.abspath(file_path))
        n_total = sum(len(p) for p in loops)
        self.main_window.log_panel.log(
            f"Imported STL '{os.path.basename(file_path)}' — detected "
            f"{len(loops)} boundary loop(s), {n_total} surface points (z=0 plane).")

    def _load_geometry_file(self, file_path: str, record_recent: bool = True):
        if file_path.lower().endswith(".json"):
            self._load_json_config_direct(file_path)
            return
        if file_path.lower().endswith(".stl"):
            self._load_stl_file(file_path)
            return
        try:
            # Check if active session is empty/untitled and has no loaded points
            active = self.active_session()
            if active and not active.file_path and active.original_points is None:
                session = active
                # Update tab text
                label = os.path.basename(file_path)
                self.main_window.tab_widget.setTabText(self.active_idx, label)
                session.file_path = file_path
                session._untitled_no = None  # no longer a blank/untitled session
                session.color = SESSION_COLORS[
                    (session.session_id - 1) % len(SESSION_COLORS)]
            else:
                session = self._new_session(file_path)

            session.project_model.input_file = file_path
            session.project_model.output_file = session.default_output_path
            from app.services.geometry_service import load_points_dat
            session.original_points = load_points_dat(file_path)

            abs_path = os.path.abspath(file_path)
            if abs_path not in session.mesh_config.geom_files:
                session.mesh_config.geom_files.append(abs_path)
            if record_recent:
                self.update_recent_files(abs_path)

            self._apply_geometry_update(session, re_detect=True)
            if session is self.active_session():
                self._sync_sidebar_to_session()
            n_pts = len(session.original_points)
            n_seg = max(0, len(session.split_indices) - 1)
            self.main_window.log_panel.log(
                f"Loaded '{os.path.basename(file_path)}' — "
                f"{n_pts} points, {n_seg} auto-detected edges.")
        except Exception as e:
            self.main_window.log_panel.log(f"Error loading file: {e}")

    def _load_json_config_direct(self, file_path: str):
        try:
            import json
            with open(file_path) as f:
                config = json.load(f)
            self._apply_json_config(config, file_path)
            self.main_window.log_panel.log(f"Loaded JSON configuration from '{os.path.basename(file_path)}'")
        except Exception as e:
            self.main_window.log_panel.log(f"Error loading JSON: {e}")

    def load_json_config(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self.main_window, "Load JSON Config", "",
            "JSON Files (*.json);;All Files (*)")
        if not file_path:
            return
        try:
            import json
            with open(file_path) as f:
                config = json.load(f)
            self._apply_json_config(config, file_path)
        except Exception as e:
            self.main_window.log_panel.log(f"Error loading JSON: {e}")

    def _apply_json_config(self, config: dict, config_path: str):
        from app.models.project import CONFIG_FORMAT_VERSION
        # Missing version = legacy v0 (explicit, not "assume current"). A file
        # older than this build is migrated field-by-field by ProjectModel;
        # a NEWER file is loaded read-only best-effort with a clear warning.
        cfg_version = int(config.get("format_version", 0))
        if cfg_version > CONFIG_FORMAT_VERSION:
            self.main_window.log_panel.log(
                f"[WARNING] Config format version {cfg_version} is newer than this "
                f"build supports ({CONFIG_FORMAT_VERSION}). Loading read-only, "
                "best-effort — some settings may be ignored. Save with this build "
                "to write a compatible file."
            )
        elif cfg_version < CONFIG_FORMAT_VERSION:
            self.main_window.log_panel.log(
                f"[INFO] Migrating config from format v{cfg_version} to "
                f"v{CONFIG_FORMAT_VERSION}."
            )

        input_file = config.get("input_file", "")
        if not input_file:
            self.main_window.log_panel.log("[WARNING] JSON config lacks 'input_file'. Configuration load aborted.")
            return

        # Try to resolve relative path if not absolute
        if input_file and not os.path.isabs(input_file):
            candidate1 = os.path.abspath(os.path.join(os.path.dirname(config_path), input_file))
            candidate2 = os.path.abspath(os.path.join(os.path.dirname(config_path), "..", "..", input_file))
            root_dir = repo_root()
            candidate3 = os.path.abspath(os.path.join(root_dir, input_file))

            if os.path.exists(candidate1):
                input_file = candidate1
            elif os.path.exists(candidate2):
                input_file = candidate2
            elif os.path.exists(candidate3):
                input_file = candidate3

        # If input file doesn't exist, ask user
        if input_file and not os.path.exists(input_file):
            self.main_window.log_panel.log(
                f"input_file '{input_file}' not found. Please select .dat manually.")
            input_file, _ = QFileDialog.getOpenFileName(
                self.main_window, "Select Geometry File",
                "", "Data Files (*.dat)")
            if not input_file:
                return
            config["input_file"] = input_file

        # Check if active session is empty/untitled and has no loaded points
        active = self.active_session()
        if active and not active.file_path and active.original_points is None:
            session = active
            label = os.path.basename(input_file) if input_file else "Untitled"
            self.main_window.tab_widget.setTabText(self.active_idx, label)
            session.file_path = input_file
            if input_file:
                session._untitled_no = None  # adopted a file; no longer untitled
            self._refresh_session_colors()
        else:
            session = self._new_session(input_file)

        session.project_model.load_from_config(config)

        if input_file and os.path.exists(input_file):
            try:
                from app.services.geometry_service import load_points_dat
                session.original_points = load_points_dat(input_file)
                abs_path = os.path.abspath(input_file)
                if abs_path not in session.mesh_config.geom_files:
                    session.mesh_config.geom_files.append(abs_path)
            except Exception as e:
                self.main_window.log_panel.log(f"Error reading geometry: {e}")
                return

        # Restore split_indices from file segments in config
        session.split_indices = (
            session.project_model.get_split_indices_from_file_segments())

        # Apply geometry without auto-detecting features
        self._apply_geometry_update(session, re_detect=False)

        if session is self.active_session():
            self._sync_sidebar_to_session()

        self.update_recent_files(config_path)
        self.main_window.log_panel.log(
            f"Loaded config '{os.path.basename(config_path)}' — "
            f"{len(session.project_model.segments)} segments.")

    def update_recent_files(self, file_path: str):
        if not file_path:
            return
        abs_path = os.path.abspath(file_path)
        settings = QSettings("HybMesh", "PreProcessor")
        files = settings.value("recentFiles", [])
        if not isinstance(files, list):
            files = []
        if abs_path in files:
            files.remove(abs_path)
        files.insert(0, abs_path)
        files = files[:10]  # keep up to 10 files
        settings.setValue("recentFiles", files)
        self.main_window.refresh_recent_files_menu(files, self)

    def init_recent_files(self):
        settings = QSettings("HybMesh", "PreProcessor")
        files = settings.value("recentFiles", [])
        if not isinstance(files, list):
            files = []
        self.main_window.refresh_recent_files_menu(files, self)

    def load_recent_file(self, file_path: str):
        if not os.path.exists(file_path):
            self.main_window.log_panel.log(f"Recent file not found: {file_path}")
            # Remove from settings
            settings = QSettings("HybMesh", "PreProcessor")
            files = settings.value("recentFiles", [])
            if isinstance(files, list) and file_path in files:
                files.remove(file_path)
                settings.setValue("recentFiles", files)
                self.main_window.refresh_recent_files_menu(files, self)
            return

        if file_path.lower().endswith(".json"):
            try:
                import json
                with open(file_path) as f:
                    config = json.load(f)
                self._apply_json_config(config, file_path)
            except Exception as e:
                self.main_window.log_panel.log(f"Error loading JSON: {e}")
        else:
            self._load_geometry_file(file_path)
