from __future__ import annotations
import os
import copy
import tempfile
import numpy as np
from PyQt6.QtWidgets import QFileDialog
from app.models.session import GeometrySession
from app.workers.backend_run import BackendWorker
from app.workers.exit_codes import describe
from app.views.output_dialog import OutputDialog
from app.services.geometry_service import load_points_dat, GeometryService

from app.utils import find_binary_executable, repo_root

class BackendControllerMixin:
    """Mixin containing C++ backend execution, config generation, and file exporting logic."""

    def handle_quality_check_toggled(self, checked: bool):
        # Show the Length/Ratio selector only while the heatmap is enabled.
        self.main_window.quality_mode_combo.setVisible(checked)
        session = self.active_session()
        if session and session.resampled_points is not None:
            mode = self.main_window.quality_mode_combo.currentText().lower()
            self.main_window.canvas_view.load_resampled_data(
                session.resampled_points, checked, mode,
                gap_indices=getattr(session, "resampled_gaps", None))

    def handle_quality_mode_changed(self, mode: str):
        session = self.active_session()
        if session and session.resampled_points is not None:
            show_q = self.main_window.quality_check_cb.isChecked()
            self.main_window.canvas_view.load_resampled_data(
                session.resampled_points, show_q, mode.lower(),
                gap_indices=getattr(session, "resampled_gaps", None))

    def handle_show_vertices_toggled(self, checked: bool):
        self.main_window.canvas_view.set_geometry_symbols_visible(checked)

    def handle_show_nodes_toggled(self, checked: bool):
        self.main_window.canvas_view.set_resampled_nodes_visible(checked)

    def _find_executable(self) -> str | None:
        return find_binary_executable("surface_resampler")

    @staticmethod
    def _split_preview_pieces(pts: np.ndarray) -> tuple[np.ndarray, set]:
        """Strip 'nan' separator rows from a preview output array and return the
        cleaned points plus the set of connect-break indices (each is the index,
        in the cleaned array, of the last point before a separator)."""
        pts = np.atleast_2d(np.asarray(pts, dtype=float))
        if pts.size == 0:
            return np.empty((0, 2)), set()
        finite = np.isfinite(pts).all(axis=1)
        clean = pts[finite]
        if finite.all():
            return clean, set()
        real_cumsum = np.cumsum(finite)
        sep_rows = np.where(~finite)[0]
        gaps = {int(real_cumsum[r] - 1) for r in sep_rows if real_cumsum[r] >= 1}
        return clean, gaps



    def _write_temp_config(self, session: GeometrySession,
                           output_path: str,
                           preview_markers: bool = False) -> tuple[str, list[str]]:
        """Write config to a temp file and return its path and a list of extra temp files.

        When ``preview_markers`` is set, the backend emits 'nan nan' separator
        rows between disconnected pieces so the canvas can break the preview
        polyline exactly there (used for Preview, never for real saves)."""
        self._sync_active_curve_segment_from_ui()
        pm = session.project_model

        orig_input = pm.input_file
        orig_output = pm.output_file
        orig_segments = pm.segments

        created_files = []

        # All mutations below are TRANSIENT (weld copy, temp input path, output
        # path). Wrap them so the project model is always restored — otherwise an
        # exception between the swap and the restore (e.g. np.savetxt or
        # export_config raising) would leave the welded deepcopy permanent,
        # silently altering the user's hand-placed edge coordinates and detaching
        # the segment objects from the undo history.
        try:
            # Weld near-coincident endpoints of separately-drawn boundary edges so
            # the mesher (which only joins pieces coincident to 1e-7) chains them
            # into ONE connected boundary instead of disconnected pieces. Operate
            # on a copy so the user's in-memory edges keep their exact coordinates.
            # Each edge stays a distinct segment, so its own per-segment BC is preserved.
            if len([s for s in pm.segments if getattr(s, "type", "") == "curve"]) >= 2:
                try:
                    welded = copy.deepcopy(pm.segments)
                    nw = GeometryService.weld_boundary_endpoints(
                        welded, self._endpoint_tolerance(session))
                    if nw:
                        pm.segments = welded
                        self.log(
                            f"Welded {nw} boundary junction(s) so the edges form one "
                            "connected boundary (each edge keeps its own BC).")
                except Exception as e:
                    pm.segments = orig_segments
                    self.log(f"Endpoint weld skipped: {e}")

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
            pm.export_config(tmp_cfg.name,
                             extra={"preview_markers": True} if preview_markers else None)
            created_files.append(tmp_cfg.name)
            tmp_cfg.close()
        finally:
            # Restore original paths / edges so we don't pollute the project model
            pm.input_file = orig_input
            pm.output_file = orig_output
            pm.segments = orig_segments

        return tmp_cfg.name, created_files

    def _confirm_open_endpoints_before_preview(self, session) -> bool:
        """Warn (once per endpoint configuration) when analytic/open curve edges
        leave genuinely-open endpoints with no internal polyline gap to flag
        them. Returns True to proceed, False to abort."""
        open_eps = self.open_endpoints_unclustered(session)
        if not open_eps:
            session._open_decision_sig = None
            return True
        sig = self.open_endpoints_signature(open_eps)
        if sig == getattr(session, "_open_decision_sig", None):
            return True  # this configuration was already acknowledged

        from app.utils import confirm
        if not confirm(
                self.main_window, "Open boundary",
                f"{len(open_eps)} open endpoint(s) detected — the boundary is not "
                "closed. The mesher will bridge the gap with a straight line.\n\n"
                "Preview anyway?"):
            return False
        session._open_decision_sig = sig
        self.log(
            f"Preview: proceeding with {len(open_eps)} open endpoint(s).")
        return True

    def _resolve_unclosed_before_preview(self, session) -> bool:
        """Detect unclosed gaps and, if any, prompt the user. Returns True to
        proceed with the preview, False to abort. Sets
        ``session._preview_break_internal`` so the finished-callback knows whether
        to break the polyline at internal gaps (Keep Open) or bridge them (Line).
        """
        gaps = self.find_geometry_gaps(session)
        if not gaps:
            session._preview_break_internal = False
            session._gap_decision_sig = None
            # No internal polyline gaps, but analytic / open-polygon curve edges
            # may still leave dangling endpoints the mesher would silently bridge
            # (find_geometry_gaps only inspects the file polyline).
            return self._confirm_open_endpoints_before_preview(session)

        sig = self.gaps_signature(gaps)
        if (sig == getattr(session, "_gap_decision_sig", None)
                and getattr(session, "_gap_decision", None) in ("keep_open", "line")):
            session._preview_break_internal = (session._gap_decision == "keep_open")
            return True

        from app.views.unclosed_dialog import UnclosedPointsDialog
        dlg = UnclosedPointsDialog(gaps, self.main_window)
        from app.utils import offset_popup
        offset_popup(dlg, self.main_window)
        dlg.exec()
        choice = dlg.choice

        if choice == "cancel":
            return False
        if choice == "keep_open":
            session._gap_decision_sig = sig
            session._gap_decision = "keep_open"
            session._preview_break_internal = True
            self.log(
                f"Preview: keeping {len(gaps)} gap(s) open (not bridged).")
            return True

        # choice == "stitch"
        method = dlg.method
        if method == "line":
            session._gap_decision_sig = sig
            session._gap_decision = "line"
            session._preview_break_internal = False
            self.log(
                f"Preview: closing {len(gaps)} gap(s) with a straight line.")
            return True

        # midpoint / snap mutate the points (undoable); the gaps then disappear
        self.stitch_gaps(session, gaps, method)
        session._gap_decision_sig = None
        session._gap_decision = None
        session._preview_break_internal = False
        self.log(f"Stitched {len(gaps)} gap(s) ({method}).")
        return True

    def preview_backend(self):
        """Run backend with a temp output path; display result on canvas."""
        session = self.active_session()
        if not session:
            return
        if (not session.project_model.input_file
                and not session.project_model.segments
                and session.original_points is None):
            self.log("No geometry loaded.")
            return
        exe = self._find_executable()
        if not exe:
            self.log(
                "Executable not found. Please build the C++ project.")
            return

        # Unclosed-point check: a moved-away edge can leave a gap that preview
        # would otherwise silently bridge. Prompt the user before running.
        if not self._resolve_unclosed_before_preview(session):
            return

        tmp_out = tempfile.NamedTemporaryFile(
            dir=self.temp_dir, suffix="_preview.dat", delete=False)
        tmp_out_name = tmp_out.name
        tmp_out.close()

        cfg_path, created_files = self._write_temp_config(
            session, tmp_out_name, preview_markers=True)
        to_cleanup = created_files + [tmp_out_name]

        self.log("--- Preview: Starting Backend ---")
        self._run_backend(exe, cfg_path, session,
                          on_finish=lambda rc: self._on_preview_finished(
                              rc, tmp_out_name, to_cleanup, session))

    def save_output(self):
        """Ask user for output path, then run backend and save."""
        session = self.active_session()
        if not session:
            return
        if not session.project_model.input_file and not session.project_model.segments:
            self.log("No geometry loaded.")
            return
        exe = self._find_executable()
        if not exe:
            self.log(
                "Executable not found. Please build the C++ project.")
            return

        default_out = session.project_model.output_file
        tmp_dir = tempfile.gettempdir()
        if default_out and (tmp_dir in default_out or "/tmp" in default_out or "Temporary" in default_out):
            default_out = ""

        if not default_out:
            root_dir = repo_root()
            if session.file_path:
                stem = os.path.splitext(os.path.basename(session.file_path))[0]
            else:
                # Untitled session: name after its (unique) display name so
                # different sessions don't all export "output_resampled.dat".
                stem = session.display_name.lstrip("*").replace(" ", "_") or "output"
            default_out = os.path.join(root_dir, "results", "resampled",
                                       f"{stem}_resampled.dat")

        dlg = OutputDialog(default_out, self.main_window)
        from app.utils import offset_popup
        offset_popup(dlg, self.main_window)
        if dlg.exec() != OutputDialog.DialogCode.Accepted:
            return

        out_path = dlg.output_path
        # No snapshot of the MESH-stage per-segment edits here. The BC label and
        # the No-BL flag are SegmentModel fields, so _write_temp_config carries
        # them into the resampler's config and the sidecar comes back correct —
        # including the case this wrapper had to guard against by hand, a NEW
        # geometry saved over an existing output name. It inherits nothing now
        # because the model, not the file being overwritten, is the source.
        session.project_model.output_file = out_path
        cfg_path, created_files = self._write_temp_config(session, out_path)

        self.log("--- Save: Starting Backend ---")
        self._run_backend(exe, cfg_path, session,
                          on_finish=lambda rc: self._on_save_finished(
                              rc, out_path, created_files, session))

    def generate_json(self):
        session = self.active_session()
        if not session:
            return
        self._sync_active_curve_segment_from_ui()
        if not session.project_model.input_file and not session.project_model.segments:
            self.log("No geometry loaded.")
            return

        root_dir = repo_root()
        default_filename = "gui_config.json"
        if session.file_path:
            stem = os.path.splitext(os.path.basename(session.file_path))[0]
            default_filename = f"{stem}_config.json"
        default_path = os.path.join(root_dir, "config", "preprocessor", default_filename)

        path, _ = QFileDialog.getSaveFileName(
            self.main_window, "Export JSON Config",
            default_path, "JSON Files (*.json)")
        if not path:
            return

        pm = session.project_model
        orig_input = pm.input_file
        pm.input_file = session.file_path

        pm.transform = self.main_window.sidebar_view.get_transform_dict()
        pm.export_config(path)

        pm.input_file = orig_input
        self.log(f"Config exported: {path}")

    def _backend_running(self) -> bool:
        w = getattr(self, "_worker", None)
        return w is not None and w.isRunning()

    def _set_backend_running_ui(self, running: bool):
        """Toggle the resample buttons + progress bar as one unit so a run can
        never leave a button stuck disabled (the old per-caller disable could
        strand the Save button if a Preview was already in flight)."""
        # Two live on the toolbar, one in the sidebar footer; each is addressed
        # at its own owner (see _cad_resample_buttons).
        for btn in self._cad_resample_buttons():
            btn.setEnabled(not running)
        self.main_window.sidebar_view.set_save_enabled(not running)
        cancel = getattr(self.main_window, "cad_cancel_btn", None)
        if cancel is not None:
            cancel.setEnabled(running)
        # The progress bar is shared with the mesh/solver/STL3d stages, whose runs
        # can overlap this one; claim/release so finishing here cannot hide or
        # reset a bar another stage is driving. Indeterminate: the resampler
        # emits no % markers.
        if running:
            self.main_window.claim_progress("cad")
        else:
            self.main_window.release_progress("cad")

    def cancel_backend(self):
        """Cancel the in-flight resample (Preview/Save)."""
        w = getattr(self, "_worker", None)
        if w is not None and w.isRunning():
            self.log("Cancelling resample…")
            w.cancel()

    def _run_backend(self, exe: str, cfg_path: str,
                     session: GeometrySession, on_finish):
        if self._backend_running():
            self.log("Backend is already running. Please wait.")
            return
        # Keep the shared log across runs/pages (don't clear); just mark a new
        # run. Users can clear manually via the log panel's Clear button.
        self.log("--- Running PreProcessor (resample) ---")
        self._set_backend_running_ui(True)
        self._worker = BackendWorker(exe, cfg_path)
        # Remember which session this run belongs to so close_tab can cancel it
        # and the finished-callback can tell whether the session still exists.
        self._worker_session = session
        self._worker.log_signal.connect(self.log)
        # Clear the running-state UI for EVERY caller, connected BEFORE on_finish
        # so the buttons come back even if the callback raises. Callers such as
        # the pipeline's _pipe_after_resample never restored it themselves, which
        # left Preview/Apply/Save disabled for the rest of the session.
        self._worker.finished_signal.connect(self._on_backend_finished_ui)
        self._worker.finished_signal.connect(on_finish)
        self._worker.start()

    def _on_backend_finished_ui(self):
        """Zero-arg slot: restore the idle UI whatever the run's outcome was."""
        self._set_backend_running_ui(False)

    def _on_preview_finished(self, rc: int, tmp_out: str, to_cleanup: list[str],
                             session: GeometrySession):
        # UI state is restored by _on_backend_finished_ui (connected first).
        try:
            if rc == 0 and os.path.exists(tmp_out):
                try:
                    # allow_nonfinite: the backend writes 'nan nan' piece-separator
                    # rows (preview_markers) that _split_preview_pieces strips below;
                    # the default finiteness guard would reject the whole preview.
                    pts = load_points_dat(tmp_out, allow_nonfinite=True)
                    if session not in self.sessions:
                        # Tab was closed while the backend ran; discard the
                        # result (temp files are still cleaned in `finally`).
                        return
                    # 'nan nan' separator rows mark exact piece boundaries; strip
                    # them and convert to connect-break indices for the canvas.
                    pts, gaps = self._split_preview_pieces(pts)
                    # Keep Open: also break the polyline at internal gaps (a
                    # moved edge's jump lives inside one segment, so the backend
                    # piece markers miss it — fall back to the distance heuristic).
                    if getattr(session, "_preview_break_internal", False):
                        extra = self.main_window.canvas_view._detect_gap_indices(pts)
                        gaps = set(gaps) | set(extra)
                    session.resampled_points = pts
                    session.resampled_gaps = gaps
                    if session is self.active_session():
                        show_q = self.main_window.quality_check_cb.isChecked()
                        mode = self.main_window.quality_mode_combo.currentText().lower()
                        self.main_window.canvas_view.load_resampled_data(
                            pts, show_q, mode, gap_indices=gaps)
                        # Clear orange segment overlay so the resampled result
                        # is not obscured by the selection highlight
                        self.main_window.canvas_view.clear_segment_highlight()
                        self.preview_curve_formula()
                    self.log(
                        f"Preview done ({len(pts)} points).")
                except Exception as e:
                    self.log(f"Preview load error: {e}")
            else:
                reason = describe(rc)
                if reason:
                    self.log(f"--- Preview {reason} ---")
                else:
                    self.log(
                        f"--- Preview Backend Failed (code {rc}) ---")
        finally:
            for path in to_cleanup:
                try:
                    if os.path.exists(path):
                        os.remove(path)
                except Exception as e:
                    self.log(f"Failed to delete temp file {path}: {e}")

    def _on_save_finished(self, rc: int, out_path: str, to_cleanup: list[str],
                          session: GeometrySession):
        # UI state is restored by _on_backend_finished_ui (connected first).
        try:
            if rc == 0:
                self.log(
                    f"--- Saved to: {out_path} ---")
                if os.path.exists(out_path):
                    try:
                        pts = load_points_dat(out_path)
                        # The file is already written to disk; only update the
                        # in-memory session/UI if that session still exists.
                        if session not in self.sessions:
                            return
                        session.resampled_points = pts
                        if session is self.active_session():
                            show_q = self.main_window.quality_check_cb.isChecked()
                            mode = self.main_window.quality_mode_combo.currentText().lower()
                            self.main_window.canvas_view.load_resampled_data(pts, show_q, mode)
                            self.main_window.canvas_view.clear_segment_highlight()
                            self.preview_curve_formula()
                        self.log(
                            f"Loaded result ({len(pts)} points).")

                        # Do NOT auto-add the exported geometry to the mesh
                        # config — the Mesh Generator page starts blank and the
                        # user opts in per geometry via the Geometry Layers
                        # checkboxes. Just refresh that list so the now-exported
                        # session becomes available (unchecked) to import.
                        self.sync_mesh_layers_panel()
                    except Exception as e:
                        self.log(f"Result load error: {e}")
            else:
                reason = describe(rc)
                if reason:
                    self.log(f"--- Save {reason} ---")
                else:
                    self.log(
                        f"--- Backend Failed (code {rc}) ---")
        finally:
            for path in to_cleanup:
                try:
                    if os.path.exists(path):
                        os.remove(path)
                except Exception as e:
                    self.log(f"Failed to delete temp file {path}: {e}")
