from __future__ import annotations
import os
import shutil
from PyQt6.QtWidgets import QFileDialog
from app.utils import repo_root

class MeshExportControllerMixin:
    """Mixin containing mesh file-export logic (VTK, Star-CD) and export-path resolution."""

    @staticmethod
    def _next_available_path(path: str) -> str:
        """Return `path` if free, else the first `<stem>_N.<ext>` that does not
        exist yet, so a repeated export proposes a fresh name instead of
        silently overwriting the previous file."""
        if not path or not os.path.exists(path):
            return path
        root, ext = os.path.splitext(path)
        i = 1
        while os.path.exists(f"{root}_{i}{ext}"):
            i += 1
        return f"{root}_{i}{ext}"

    def _resolve_export_path(self, default_fallback_path: str, ext: str) -> str:
        """Resolve the default export path based on global configuration settings.

        The returned path is de-duplicated (see `_next_available_path`) so each
        export defaults to a name that does not clobber a previous export."""
        root_dir = repo_root()
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
        return self._next_available_path(default_path)

    def export_mesh_files(self):
        """#5: Export the generated mesh in the enabled write formats to a chosen
        location (the Output panel's Export button). Falls back to VTK if no
        format is toggled, and pops one save dialog per enabled format."""
        cfg = None
        panel = getattr(self.main_window, "mesh_config_panel", None)
        if panel is not None:
            try:
                cfg = panel.get_config()
            except Exception:
                cfg = None
        want_vtk = bool(cfg.export_vtk) if cfg else True
        want_star = bool(cfg.export_starcd) if cfg else False
        if not (want_vtk or want_star):
            # Nothing toggled: default to VTK so the button always does something.
            want_vtk = True
        if want_vtk:
            self.export_generated_vtk()
        if want_star:
            self.export_star_cd()

    def export_generated_vtk(self):
        """Export the generated VTK mesh file to a user-selected path."""
        vtk_path = self.global_vtk_path
        if not vtk_path or not os.path.exists(vtk_path):
            vtk_path = self._get_expected_vtk_path(self.global_mesh_config) if self.global_mesh_config else ""

        if not vtk_path or not os.path.exists(vtk_path):
            self._offer_generate_then(self.export_generated_vtk, "the VTK mesh")
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
            self._offer_generate_then(self.export_star_cd, "the Star-CD files")
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
