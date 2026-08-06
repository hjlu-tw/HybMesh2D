from __future__ import annotations
import os
import numpy as np
from PyQt6.QtWidgets import QFileDialog, QMenu, QInputDialog
from PyQt6.QtCore import Qt
from app.utils import block_signals

# Bump when the .hws workspace schema changes in a backward-incompatible way.
# A missing field on load is treated as version 0 (legacy); a file whose
# version exceeds this is loaded best-effort with a warning rather than refused.
#
#   v1 -> v2: added the top-level "project" section (mesh / solver / immersed-
#             solid configuration). Before v2 a workspace only held the CAD
#             sessions, so saving and reloading silently reset every Mesh,
#             Solver and IB panel to defaults — the case could not be
#             reproduced from its own workspace file.
WORKSPACE_FORMAT_VERSION = 2


class SessionIOControllerMixin:
    """Mixin containing workspace persistence (.hws read/write + version
    migration) and the model-tree context menus for layers and edges."""

    # ── Workspace Persistence & Layer Menu (E5 & E7) ─────────────────────────

    def save_workspace(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self.main_window, "Save Workspace", "",
            "HybMesh Workspace Files (*.hws);;All Files (*)")
        if not file_path:
            return
        if not file_path.endswith(".hws"):
            file_path += ".hws"
        try:
            self._write_workspace_file(file_path)
            # The mesh/solver/IB state is now on disk, so it is no longer unsaved.
            self._reset_project_baseline()
            self.main_window.log_panel.log(f"Workspace manually saved to '{os.path.basename(file_path)}'")
        except Exception as e:
            self.main_window.log_panel.log(f"[ERROR] Failed to save workspace: {e}")
            from app.utils import report_error
            report_error(self.main_window, "Save Workspace Failed",
                         "The workspace could not be saved — your changes are "
                         "NOT on disk.", detail=str(e))

    def load_workspace(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self.main_window, "Load Workspace", "",
            "HybMesh Workspace Files (*.hws);;All Files (*)")
        if not file_path:
            return
        try:
            self._read_workspace_file(file_path)
        except Exception as e:
            self.main_window.log_panel.log(f"[ERROR] Failed to load workspace: {e}")
            from app.utils import report_warning
            report_warning(self.main_window, "Load Workspace Failed",
                           f"'{os.path.basename(file_path)}' could not be loaded. "
                           "It may be corrupt or from an incompatible version.",
                           detail=str(e))

    def _write_workspace_file(self, file_path: str):
        import json
        import copy

        # Reject non-finite coordinates up front with a clear, named error.
        # Standard JSON has no NaN/Infinity literal, so writing them produces a
        # file that strict parsers (e.g. the C++ nlohmann reader) refuse to load.
        bad_fields = []
        for session in self.sessions:
            for label, arr in (("original_points", session.original_points),
                               ("resampled_points", session.resampled_points)):
                if arr is not None and not np.all(np.isfinite(arr)):
                    bad_fields.append(f"{session.display_name} ({label})")
        if bad_fields:
            raise ValueError(
                "Cannot save workspace: non-finite (NaN/Inf) coordinates in "
                + ", ".join(bad_fields)
                + ". Check geometry data or curve formulas before saving."
            )

        sessions_data = []
        for session in self.sessions:
            segments_data = [seg.to_dict() for seg in session.project_model.segments]

            project_config = {
                "input_file": session.project_model.input_file,
                "output_file": session.project_model.output_file,
                "closed_mode": session.project_model.closed_mode,
                "is_closed": session.project_model.is_closed,
                "segments": segments_data,
                "global_spline": session.project_model.global_spline,
                "transform": copy.deepcopy(session.project_model.transform) if session.project_model.transform else None
            }

            session_dict = {
                "file_path": session.file_path,
                "display_name": session.display_name.lstrip('*'),
                "is_visible": session.is_visible,
                "is_geometry_modified": session.is_geometry_modified,
                "split_indices": session.split_indices,
                "current_segment_idx": session.current_segment_idx,
                "selected_point_idx": session.selected_point_idx,
                "original_points": session.original_points.tolist() if session.original_points is not None else None,
                "resampled_points": session.resampled_points.tolist() if session.resampled_points is not None else None,
                "project_config": project_config,
                "mesh_config": session.mesh_config.to_dict(),
                "vtk_path": session.vtk_path
            }
            sessions_data.append(session_dict)

        workspace_data = {
            "format_version": WORKSPACE_FORMAT_VERSION,
            "active_idx": self.active_idx,
            "sessions": sessions_data,
            "project": self._collect_project_state(),
        }

        # Serialise fully (allow_nan=False) before opening the file so a failure
        # leaves any previous workspace file intact rather than half-written.
        text = json.dumps(workspace_data, indent=2, allow_nan=False)
        abs_path = os.path.abspath(file_path)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        # Atomic write: serialise to a sibling temp file, flush+fsync it, then
        # os.replace() over the target. A crash / disk-full mid-write can then
        # only leave the (discarded) temp behind — never a truncated workspace or,
        # worse, a corrupt autosave recovery file. os.replace is atomic on the
        # same filesystem, which the sibling temp guarantees.
        import tempfile as _tempfile
        d = os.path.dirname(abs_path) or "."
        fd, tmp_path = _tempfile.mkstemp(
            dir=d, prefix=".hws-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(text)
                f.flush()
                os.fsync(f.fileno())
            # mkstemp forces 0600, and os.replace stamps that onto the target —
            # silently making an existing group/world-readable workspace private.
            # Restore the mode the file already had, or the umask default for a
            # new one, so saving never changes who can open the workspace.
            try:
                mode = os.stat(abs_path).st_mode & 0o777
            except OSError:
                umask = os.umask(0)         # read-only peek; restore immediately
                os.umask(umask)
                mode = 0o666 & ~umask
            os.chmod(tmp_path, mode)
            os.replace(tmp_path, abs_path)
        except Exception:
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except OSError:
                pass
            raise

    @staticmethod
    def _migrate_workspace(data: dict, from_version: int) -> dict:
        """Upgrade an older .hws workspace dict to WORKSPACE_FORMAT_VERSION.

        Extension point for backward-compatible workspace migration, routed
        through by ``_read_workspace_file``. Add an ``if v < N`` block here when
        the workspace schema changes incompatibly."""
        import copy as _copy
        v = int(from_version)
        out = _copy.deepcopy(data)
        # v0 -> v1: stamp the version; no structural change.
        if v < 1:
            v = 1
        # v1 -> v2: the "project" section did not exist. Nothing to recover — the
        # mesh/solver/IB state was simply never written — so seed it empty and let
        # the loader keep the freshly-reset defaults. Kept explicit so a v1 file
        # takes the same code path as a v2 one instead of hitting a missing key.
        if v < 2:
            out.setdefault("project", {})
            v = 2
        out["format_version"] = WORKSPACE_FORMAT_VERSION
        return out

    def _read_workspace_file(self, file_path: str):
        import json
        import numpy as np
        from app.models.session import GeometrySession
        from app.models.segment import SegmentModel
        from app.models.vtk_mesh import VTKMesh
        from app.models.project import _legacy_closed_mode

        if not os.path.exists(file_path):
            return

        with open(file_path, encoding="utf-8") as f:
            workspace_data = json.load(f)

        # Explicit version handling: missing = legacy v0 (not "current"). Older
        # files are migrated field-by-field through _migrate_workspace; a NEWER
        # file is loaded read-only best-effort with a clear warning.
        file_version = int(workspace_data.get("format_version", 0))
        if file_version > WORKSPACE_FORMAT_VERSION:
            self.main_window.log_panel.log(
                f"[WARNING] Workspace format version {file_version} is newer than "
                f"this build supports ({WORKSPACE_FORMAT_VERSION}). Loading read-only, "
                "best-effort — some data may be ignored. Save with this build to "
                "write a compatible file."
            )
        elif file_version < WORKSPACE_FORMAT_VERSION:
            self.main_window.log_panel.log(
                f"[INFO] Migrating workspace from format v{file_version} to "
                f"v{WORKSPACE_FORMAT_VERSION}."
            )
            workspace_data = self._migrate_workspace(workspace_data, file_version)

        # headless_default True: a batch run has to be able to load a workspace.
        from app.utils import confirm
        if self.sessions and not confirm(
                self.main_window, "Load Workspace",
                "Loading a workspace will close all current tabs. "
                "Do you want to proceed?"):
            return

        with block_signals(self.main_window.tab_widget):
            while self.sessions:
                session = self.sessions.pop(0)
                self.main_window.canvas_view.remove_geometry(session.session_id)
            while self.main_window.tab_widget.count() > 0:
                self.main_window.tab_widget.removeTab(0)
            self.active_idx = -1
            self.main_window.canvas_view.clear_active_overlays()
            self.main_window.canvas_view.set_active_points(None)
            self.main_window.mesh_canvas_view.clear_mesh()

        sessions_data = workspace_data.get("sessions", [])
        for session_dict in sessions_data:
            session = GeometrySession()
            session.command_history.on_change = self._update_undo_redo_buttons
            session.file_path = session_dict.get("file_path", "")
            display_name = session_dict.get("display_name", "Untitled")
            session.display_name = display_name
            session.is_geometry_modified = session_dict.get("is_geometry_modified", False)
            session.is_visible = session_dict.get("is_visible", True)
            session.split_indices = session_dict.get("split_indices", [])
            session.current_segment_idx = session_dict.get("current_segment_idx", -1)
            session.selected_point_idx = session_dict.get("selected_point_idx", None)
            session.vtk_path = session_dict.get("vtk_path", "")

            orig_pts = session_dict.get("original_points", None)
            if orig_pts is not None:
                session.original_points = np.array(orig_pts, dtype=np.float64)
            res_pts = session_dict.get("resampled_points", None)
            if res_pts is not None:
                session.resampled_points = np.array(res_pts, dtype=np.float64)

            for label, arr in (("original_points", session.original_points),
                               ("resampled_points", session.resampled_points)):
                if arr is not None and not np.all(np.isfinite(arr)):
                    self.main_window.log_panel.log(
                        f"[WARNING] '{display_name}' has non-finite (NaN/Inf) "
                        f"values in {label}; geometry may render incorrectly."
                    )

            pconf = session_dict.get("project_config", {})
            session.project_model.input_file = pconf.get("input_file", "")
            session.project_model.output_file = pconf.get("output_file", "")
            # Saved workspace expresses explicit intent → manual mode; legacy
            # files without closed_mode map from the is_closed bool.
            session.project_model.closed_mode = pconf.get(
                "closed_mode", _legacy_closed_mode(pconf))
            session.project_model.is_closed = pconf.get("is_closed", True)
            session.project_model.global_spline = pconf.get("global_spline", False)
            session.project_model.transform = pconf.get("transform", None)

            session.project_model.segments = []
            for sj in pconf.get("segments", []):
                seg = SegmentModel.from_dict(sj.get("id"), sj)
                session.project_model.segments.append(seg)

            mconf = session_dict.get("mesh_config", {})
            session.mesh_config.load_from_dict(mconf)

            if session.vtk_path and os.path.exists(session.vtk_path):
                try:
                    session.vtk_mesh = VTKMesh.from_file(session.vtk_path)
                except Exception:
                    session.vtk_mesh = None

            self.sessions.append(session)
            self.main_window.tab_widget.addTab(session.display_name)

            self.main_window.canvas_view.add_geometry(
                session.session_id, None, session.color)
            self.main_window.canvas_view.set_geometry_visible(
                session.session_id, session.is_visible)

            if session.original_points is not None:
                self._apply_geometry_update(session, re_detect=False)

        self._refresh_session_colors()
        self._sync_geometry_list()

        # Mesh / Solver / Immersed-Solid configuration (v2+). Applied after the
        # sessions exist so the mesh panel's geometry list resolves against them.
        self._apply_project_state(workspace_data.get("project", {}))

        target_idx = workspace_data.get("active_idx", -1)
        if 0 <= target_idx < len(self.sessions):
            self.active_idx = target_idx
            self.main_window.tab_widget.setCurrentIndex(self.active_idx)
            self.switch_tab(self.active_idx)

        # Everything just loaded IS the saved state — snapshot it as the baseline
        # so a freshly-opened workspace does not immediately look modified.
        self._reset_project_baseline()

        self.main_window.log_panel.log(f"Workspace loaded from '{os.path.basename(file_path)}'")

    _CONTEXT_MENU_QSS = """
        QMenu {
            background-color: #121422;
            color: #a0a8c0;
            border: 1px solid #1c1e36;
        }
        QMenu::item {
            padding: 6px 20px;
        }
        QMenu::item:selected {
            background-color: #3b82f6;
            color: #ffffff;
        }
    """

    def show_geometry_context_menu(self, global_pos, item):
        """Right-click menu on the model tree. The actions offered depend on the
        clicked row: a geometry layer (session), an edge, or empty space."""
        tree = self.main_window.sidebar_view.geometry_tree
        kind = tree.kind(item)

        if kind == "edge":
            self._show_edge_context_menu(global_pos, tree.edge_index(item))
            return
        if kind != "session":
            # Empty space: offer to add a new analytic edge to the active layer.
            if self.active_session() is not None:
                menu = QMenu(self.main_window)
                menu.setStyleSheet(self._CONTEXT_MENU_QSS)
                add_action = menu.addAction("Add Analytic Edge")
                if menu.exec(global_pos) == add_action:
                    self.add_curve_segment()
            return

        session_id = tree.session_id_of(item)
        session = None
        session_idx = -1
        for i, s in enumerate(self.sessions):
            if s.session_id == session_id:
                session = s
                session_idx = i
                break
        if not session:
            return

        menu = QMenu(self.main_window)
        menu.setStyleSheet(self._CONTEXT_MENU_QSS)

        focus_action = menu.addAction("Focus View")

        show_hide_label = "Hide Layer" if session.is_visible else "Show Layer"
        show_hide_action = menu.addAction(show_hide_label)

        rename_action = menu.addAction("Rename...")

        menu.addSeparator()
        add_edge_action = menu.addAction("Add Analytic Edge")

        menu.addSeparator()
        close_action = menu.addAction("Close / Delete Tab")

        action = menu.exec(global_pos)
        if action == focus_action:
            self.main_window.canvas_view.fit_to_geometry(session_id)
        elif action == add_edge_action:
            if session_idx != self.active_idx:
                self.main_window.tab_widget.setCurrentIndex(session_idx)
            self.add_curve_segment()
        elif action == show_hide_action:
            new_visible = not session.is_visible
            session.is_visible = new_visible
            item.setCheckState(0, Qt.CheckState.Checked if new_visible else Qt.CheckState.Unchecked)
            self.main_window.canvas_view.set_geometry_visible(session_id, new_visible)
            if session is self.active_session():
                self.main_window.canvas_view.set_active_overlays_visible(new_visible)
        elif action == rename_action:
            new_name, ok = QInputDialog.getText(
                self.main_window, "Rename Geometry Layer",
                "Enter new name for the geometry layer:",
                text=session.display_name.lstrip('*')
            )
            if ok and new_name.strip():
                session.display_name = new_name.strip()
                item.setText(0, session.display_name)
                self.main_window.tab_widget.setTabText(session_idx, session.display_name)
                if session is self.active_session():
                    self.main_window.update_title(session.display_name, session.is_geometry_modified)
        elif action == close_action:
            self.close_tab(session_idx)

    def _show_edge_context_menu(self, global_pos, seg_idx: int):
        """Right-click menu on an edge row. Selects the edge first so the
        existing edge commands (which act on current_segment_idx) apply."""
        session = self.active_session()
        if session is None or seg_idx is None:
            return
        if not (0 <= seg_idx < len(session.project_model.segments)):
            return
        self._select_segment_by_index(seg_idx)
        seg = session.project_model.get_segment(seg_idx)

        menu = QMenu(self.main_window)
        menu.setStyleSheet(self._CONTEXT_MENU_QSS)
        autodetect_action = menu.addAction("Auto Detect Sub-edges")
        bake_action = menu.addAction("Convert to Discrete") if (seg and seg.type == "curve") else None
        menu.addSeparator()
        remove_action = menu.addAction("Remove Edge")

        action = menu.exec(global_pos)
        if action is None:
            return
        if action == remove_action:
            self.remove_selected_segment()
        elif bake_action is not None and action == bake_action:
            self.bake_selected_curve()
        elif action == autodetect_action:
            self.auto_detect_segments_from_button()
