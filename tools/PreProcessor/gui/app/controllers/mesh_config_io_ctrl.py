"""Read / write the mesher's ``Background_para.dat`` through a file dialog.

Split out of ``mesh_gen_ctrl.py``, which had grown past this project's GUI file
budget once #47's merge added a geometry pre-flight refusal to it. The cut is the
one that file's own docstring already described and then declined to make —
**running** the mesh generator is one concern, **reading and writing the config
file that describes a run** is another — and it is the same cut
``pipeline_io_ctrl.py`` was taken out of ``pipeline_ctrl.py`` on, for the same
budget.

The two share nothing but the config class and the panel it is pushed into: the
dialogs never touch the worker, the canvas or the progress bar.
"""
from __future__ import annotations
import os

from PyQt6.QtWidgets import QFileDialog

from app.utils import repo_root, report_error, report_warning


class MeshConfigIoControllerMixin:
    """Load a mesh config off disk into the panel, and save the panel's back."""

    def load_mesh_config(self):
        """Prompt file dialog to load a Background_para.dat configuration file."""
        root_dir = repo_root()
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
            self.push_panel_config(self.main_window.mesh_config_panel, self.global_mesh_config)
            self.log(f"Loaded mesh configuration from {path}")
            missing = getattr(self.global_mesh_config, "missing_geom_files", [])
            if missing:
                self.log(
                    f"[WARNING] Geometry file(s) not found (paths may be broken): {', '.join(missing)}"
                )
            for w in getattr(self.global_mesh_config, "parse_warnings", []):
                self.log(f"[WARNING] {w}")
            self.sync_mesh_layers_panel()
        except Exception as e:
            self.log(f"[ERROR] Failed to load mesh config: {e}")
            report_warning(self.main_window, "Load Mesh Config Failed",
                           "The mesh configuration could not be loaded.",
                           detail=str(e))

    def save_mesh_config(self):
        """Extract config settings from UI panel and save them to a file."""
        root_dir = repo_root()

        default_name = "Background_para.dat"
        session = self.active_session()
        if session and session.file_path:
            stem = os.path.splitext(os.path.basename(session.file_path))[0]
            default_name = f"Background_para_{stem}.dat"
        # config/local/, for the reason given in .gitignore's "Local working
        # configs" block: config/mesh/ already carries two of these files as
        # tracked accidents, so a default proposing that folder can overwrite one.
        out_dir = os.path.join(root_dir, "config", "local")
        os.makedirs(out_dir, exist_ok=True)
        default_path = os.path.join(out_dir, default_name)

        path, _ = QFileDialog.getSaveFileName(
            self.main_window,
            "Save Mesh Configuration",
            default_path,
            "Config Files (*.dat);;All Files (*)"
        )
        if not path:
            return

        try:
            cfg = self.config_from_panel("mesh_config_panel")
            cfg.save_to_file(path)
            self.log(f"Saved mesh configuration to {path}")
        except Exception as e:
            self.log(f"[ERROR] Failed to save mesh config: {e}")
            report_error(self.main_window, "Save Mesh Config Failed",
                         "The mesh configuration could not be saved to disk.",
                         detail=str(e))
