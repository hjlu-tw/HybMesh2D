from __future__ import annotations
import os
import shutil
from PyQt6.QtWidgets import QApplication, QFileDialog, QMessageBox
from app.models.mesh_config import MeshConfig
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

    def _current_output_filename(self) -> str:
        """The output base name the user currently intends, preferring the LIVE
        Output-panel field over the (possibly stale) config captured at the last
        Generate. Fix #4: typing a name after generating used to be ignored
        because export read only `global_mesh_config`."""
        panel = getattr(self.main_window, "mesh_config_panel", None)
        if panel is not None:
            try:
                name = (panel.get_config().output_filename or "").strip()
                if name:
                    return name
            except Exception:
                pass
        return (self.global_mesh_config.output_filename
                if self.global_mesh_config else "") or ""

    def _is_session_temp_path(self, path: str) -> bool:
        """True if `path` lives inside the per-session temp dir, which
        `LifecycleControllerMixin.cleanup_temp_dir` rmtree's on exit. Export and
        solver-staging defaults must never resolve there."""
        tmp = getattr(self, "temp_dir", "")
        if not tmp or not path:
            return False
        try:
            tmp = os.path.abspath(tmp)
            return os.path.commonpath([os.path.abspath(path), tmp]) == tmp
        except ValueError:      # different drives (Windows) -> not under temp
            return False

    def _resolve_export_path(self, default_fallback_path: str, ext: str) -> str:
        """Resolve the default export path based on global configuration settings.

        The returned path is de-duplicated (see `_next_available_path`) so each
        export defaults to a name that does not clobber a previous export."""
        root_dir = repo_root()

        user_filename = self._current_output_filename()
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
            # `default_fallback_path` is usually the per-case path
            # (results/meshes/<case>/mesh_<case>.vtk); keep its subdirectory and
            # only swap the extension so the export stays out of the top level.
            default_path = os.path.splitext(default_fallback_path)[0] + ext
            if not os.path.isabs(default_path):
                # Anchor a relative per-case path under the repo root, preserving
                # its subdirectory (basename() would flatten it back to the top).
                default_path = os.path.abspath(os.path.join(root_dir, default_path))
            if self._is_session_temp_path(default_path):
                # …but callers pass `global_vtk_path`, which after a Generate is
                # the session temp mesh (<temp>/global_mesh.vtk). Keeping that
                # directory would default the export — and the solver staging in
                # send_mesh_to_solver — into a tree wiped on exit. Re-derive the
                # stable per-case name instead.
                cfg = self.global_mesh_config
                auto = MeshConfig.auto_output_name(
                    cfg.boundary_files if cfg else [], ext)
                default_path = os.path.abspath(os.path.join(root_dir, auto))
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
            return

        # #3 STAR-CD is the solver's input format, so offer to hand the just-exported
        # grid straight to the Solver stage. "Yes" links these .vrt/.cel/.bnd into the
        # Solver panel and switches to the Solver tab (stopping there so the user can
        # review BCs before running); "No" leaves the export as-is. Headless/batch
        # exports can't service the modal — skip it (equivalent to "No").
        app = QApplication.instance()
        if app is not None and app.platformName() in ("offscreen", "minimal"):
            return
        reply = QMessageBox.question(
            self.main_window,
            "Send to Solver",
            "Star-CD mesh exported.\n\nSend this mesh to the Solver now?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._send_starcd_to_solver(dest_vrt, dest_cel, dest_bnd)

    def send_mesh_to_solver(self):
        """Toolbar one-click hand-off: stage the just-generated Star-CD grid into
        results/meshes (stable files, not the ephemeral temp mesh) and link it
        into the Solver stage. If no mesh exists yet, offer to generate first.

        The mesh is generated with Export Star-CD forced on (see
        MeshGenControllerMixin.run_mesh_generator), so the .vrt/.cel/.bnd sit next
        to the temp VTK — mirror export_star_cd's path derivation."""
        vtk_path = self.global_vtk_path
        if not vtk_path or not os.path.exists(vtk_path):
            vtk_path = self._get_expected_vtk_path(self.global_mesh_config) \
                if self.global_mesh_config else ""
        if not vtk_path or not os.path.exists(vtk_path):
            self._offer_generate_then(self.send_mesh_to_solver, "the mesh for the Solver")
            return

        base_name, _ = os.path.splitext(vtk_path)
        src = {ext: base_name + ext for ext in (".vrt", ".cel", ".bnd")}
        missing = [ext for ext, p in src.items() if not os.path.exists(p)]
        if missing:
            self.main_window.log_panel.log(
                f"[Solver] Missing Star-CD files ({', '.join(missing)}) — the "
                "grid could not be sent. Regenerate the mesh (Generate enables "
                "Star-CD export automatically).")
            return

        # Copy to a stable results location so the Solver reads persistent files
        # rather than the session temp mesh (which is cleaned between runs).
        dest_vrt = self._resolve_export_path(src[".vrt"], ".vrt")
        dest_base, _ = os.path.splitext(dest_vrt)
        dest = {".vrt": dest_vrt, ".cel": dest_base + ".cel", ".bnd": dest_base + ".bnd"}
        try:
            os.makedirs(os.path.dirname(dest_vrt), exist_ok=True)
            for ext in (".vrt", ".cel", ".bnd"):
                shutil.copy2(src[ext], dest[ext])
        except Exception as e:
            self.main_window.log_panel.log(f"[Solver] Failed to stage mesh files: {e}")
            return
        self.main_window.log_panel.log(
            f"[Solver] Staged grid → {dest_base}.{{vrt,cel,bnd}}")
        self._send_starcd_to_solver(dest[".vrt"], dest[".cel"], dest[".bnd"])

    def _send_starcd_to_solver(self, vrt_path: str, cel_path: str, bnd_path: str):
        """#3 Link an exported Star-CD grid into the Solver panel and switch to the
        Solver tab. Sets the manual .vrt/.cel/.bnd inputs to the exported files (and
        turns OFF auto-link so those exact files are used, not the temp mesh), then
        detects the boundary patches so the BC table reflects the mesh. Stops on the
        Solver tab — the user reviews the BCs and presses Run."""
        panel = getattr(self.main_window, "solver_config_panel", None)
        if panel is None:
            self.main_window.log_panel.log(
                "[Export] Solver panel unavailable; mesh not sent to Solver.")
            return
        panel.input_vrt_file.setText(vrt_path)
        panel.input_cel_file.setText(cel_path)
        panel.input_bnd_file.setText(bnd_path)
        if hasattr(panel, "auto_link_mesh"):
            panel.auto_link_mesh.setChecked(False)
        self.main_window.mode_combo.setCurrentIndex(3)   # Solver
        # Populate the BC table from the exported .bnd (input_bnd_file is preferred by
        # _locate_mesh_bnd, so this reads the file we just linked).
        if hasattr(self, "detect_bc_from_mesh"):
            self.detect_bc_from_mesh()
        self.main_window.log_panel.log(
            "[Export] Sent Star-CD mesh to the Solver — review the BCs, then Run Solver.")
