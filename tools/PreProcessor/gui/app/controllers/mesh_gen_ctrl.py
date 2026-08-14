from __future__ import annotations
import os
import tempfile
from typing import TYPE_CHECKING
from PyQt6.QtWidgets import QFileDialog
from app.models.vtk_mesh import VTKMesh
from app.models.mesh_config import MeshConfig
from app.workers.mesh_gen_run import MeshGenWorker
from app.workers.exit_codes import RC_CANCELLED, RC_TIMEOUT
from app.utils import find_binary_executable, repo_root, confirm

if TYPE_CHECKING:
    from app.models.mesh_config import MeshConfig

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
            from app.utils import report_warning
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
            cfg = self.config_from_panel("mesh_config_panel")
            cfg.save_to_file(path)
            self.log(f"Saved mesh configuration to {path}")
        except Exception as e:
            self.log(f"[ERROR] Failed to save mesh config: {e}")
            from app.utils import report_error
            report_error(self.main_window, "Save Mesh Config Failed",
                         "The mesh configuration could not be saved to disk.",
                         detail=str(e))

    def preview_mesh_generator(self):
        """Update and fit the canvas view to the current geometry input files and domain box coordinates."""
        cfg = self.config_from_panel("mesh_config_panel")
        # ONE definition of "is this domain box usable", shared with validate() — the
        # preview used to restate the custom-outline exemption inline, so a change to
        # what makes a domain valid would have had to be made in two places. Only the
        # domain is checked here (not the whole pre-flight): a preview is what the user
        # looks at WHILE editing, so it must not refuse to draw the geometry because
        # some unrelated size has not been filled in yet.
        errors = cfg.domain_box_errors()
        if errors:
            for e in errors:
                self.log(f"[ERROR] {e}")
            return

        self.main_window.mesh_canvas_view.update_mesh_config(cfg, fit_view=False)
        if self.global_vtk_mesh:
            self.main_window.mesh_canvas_view.render_mesh(self.global_vtk_mesh, fit_view=False)
        self.log("Mesh generator preview updated.")

    def clear_mesh_canvas(self):
        """Clear the previously generated mesh AND the previous boundary/surface-
        point previews, then re-show the current (possibly edited) boundaries.
        Keeps the geometry layers list. Use this after editing CAD geometry to
        drop the stale mesh + old surface points and see the updated boundaries."""
        self.global_vtk_mesh = None
        self.global_vtk_path = ""
        mc = self.main_window.mesh_canvas_view
        # clear_mesh wipes the mesh, domain box, BC items AND the BC/surface
        # previews; also drop the old geometry (surface-point) previews.
        mc.clear_mesh()
        mc.update_geometry_previews([])
        mc.update_seed_previews([])
        self.main_window.mesh_stats_panel.update_stats(None)
        # Re-show the current boundaries + seeds from the current config (reflects edits).
        cfg = self.config_from_panel("mesh_config_panel")
        mc.update_mesh_config(cfg, fit_view=False)
        self._refresh_mesh_previews(cfg)
        self.log(
            "Cleared previous mesh and surface points; showing current boundaries.")

    def run_mesh_generator(self):
        """Extract GUI parameters, save to temporary config file, and execute HybMesh2D in background."""
        if hasattr(self, '_mesh_worker') and self._mesh_worker is not None and self._mesh_worker.isRunning():
            self.log("Mesh generation is already running. Please wait.")
            return

        exe = self._find_mesh_gen_executable()
        if not exe:
            self.log("HybMesh2D binary not found. Please build the C++ project.")
            return

        # Extract current config values from UI (via the model, so the fields the panel
        # cannot author — bc_geom above all — are not reset on the way to the mesher).
        cfg = self.config_from_panel("mesh_config_panel")

        # Diagnostic: report the geometry files actually handed to HybMesh2D.
        # (A geometry that previews on the canvas but is missing/empty here is the
        # usual cause of "mesh generates but shows no boundary/BL".)
        geom_bbox = None    # (xmin, ymin, xmax, ymax) of the boundary geometry
        domain_bbox = None  # ditto for the custom outer-domain outline, if any
        if not cfg.geom_files:
            self.log(
                "[WARNING] No geometry files in the mesh config — the mesh will "
                "have no boundary/BL. If you drew with 'Add analytic edge', run "
                "'Save & Export' in CAD mode (or 'Add Active'/check it in Geometry "
                "Layers) so it is written to a .dat first.")
        else:
            geom_bbox, domain_bbox = self._scan_geometry_files(cfg)

        # Pre-flight parameter validation: block on errors (invalid domain,
        # non-positive sizes, shrinking BL) BEFORE launching the backend, and
        # log advisory warnings. This turns a cryptic C++ crash into an
        # actionable message pointing at the offending parameter.
        errors, warnings = cfg.validate(geom_bbox=geom_bbox, domain_bbox=domain_bbox)
        for w in warnings:
            self.log(f"[WARNING] {w}")
        if errors:
            for e in errors:
                self.log(f"[ERROR] {e}")
            from app.utils import report_error
            report_error(
                self.main_window, "Invalid Mesh Parameters",
                "The mesh cannot be generated — please fix the following:\n\n"
                + "\n".join(f"• {e}" for e in errors))
            return

        # Overrule solver output path to temporary folder to prevent generating permanent files on disk
        temp_vtk_path = os.path.abspath(os.path.join(self.temp_dir, "global_mesh.vtk"))
        expected_vtk = temp_vtk_path

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

        # Keep the shared log across runs/pages (don't clear); the header below
        # separates runs. Users can clear manually via the log panel.
        self.log("--- Starting HybMesh2D Mesh Generation ---")
        
        self._mesh_worker = MeshGenWorker(exe, tmp_cfg.name)
        self._mesh_worker.log_signal.connect(self.log)
        self._mesh_worker.progress_signal.connect(self._on_mesh_gen_progress)
        self._mesh_worker.finished_signal.connect(
            lambda rc: self._on_mesh_gen_finished(rc, tmp_cfg.name, expected_vtk)
        )
        # Determinate progress driven by parsed stdout markers (R5). Claimed so a
        # CAD resample finishing mid-run cannot hide the bar we are driving.
        self.main_window.claim_progress("mesh", determinate=True)
        self._mesh_worker.start()

    def _scan_geometry_files(self, cfg) -> tuple:
        """Log each geometry file's point count (a body that previews but is
        missing/empty here is the usual cause of "no boundary/BL") and return
        ``(geom_bbox, domain_bbox)``, each an (xmin, ymin, xmax, ymax) or None
        when nothing usable was read.

        The two are kept apart because containment is about bodies inside the
        domain: `geom_bbox` covers the boundary bodies only (seeds and the
        outer-domain outline excluded), `domain_bbox` covers the custom outline
        that *is* the domain."""
        import numpy as np
        boundary = set(cfg.boundary_files)
        domain_path = cfg.domain_file
        mins = [float("inf"), float("inf")]
        maxs = [float("-inf"), float("-inf")]
        dmins = [float("inf"), float("inf")]
        dmaxs = [float("-inf"), float("-inf")]
        have = have_dom = False
        for gf in cfg.geom_files:
            if not os.path.exists(gf):
                self.log(f"[WARNING] Geometry file missing: {gf}")
                continue
            try:
                pts = np.loadtxt(gf, ndmin=2)
            except Exception:
                # Fall back to a bare point count so at least the diagnostic prints.
                try:
                    with open(gf) as _f:
                        npts = sum(1 for ln in _f if ln.strip())
                    self.log(
                        f"[geom] {os.path.basename(gf)} ({npts} points)")
                except OSError:
                    pass
                continue
            self.log(
                f"[geom] {os.path.basename(gf)} ({len(pts)} points)")
            is_boundary, is_domain = gf in boundary, gf == domain_path
            if (is_boundary or is_domain) and pts.size and pts.shape[1] >= 2:
                xy = pts[:, :2]
                xy = xy[np.isfinite(xy).all(axis=1)]
                if xy.size:
                    lo = [float(xy[:, 0].min()), float(xy[:, 1].min())]
                    hi = [float(xy[:, 0].max()), float(xy[:, 1].max())]
                    if is_boundary:
                        mins = [min(mins[i], lo[i]) for i in (0, 1)]
                        maxs = [max(maxs[i], hi[i]) for i in (0, 1)]
                        have = True
                    if is_domain:
                        dmins, dmaxs, have_dom = lo, hi, True
        return ((mins[0], mins[1], maxs[0], maxs[1]) if have else None,
                (dmins[0], dmins[1], dmaxs[0], dmaxs[1]) if have_dom else None)

    def _on_mesh_gen_progress(self, pct: int):
        self.main_window.set_progress("mesh", pct)

    def cancel_mesh_generator(self):
        """Cancel background mesh generation thread."""
        if hasattr(self, '_mesh_worker') and self._mesh_worker is not None and self._mesh_worker.isRunning():
            self.log("Cancelling mesh generation...")
            self._mesh_worker.cancel()

    def _find_mesh_gen_executable(self) -> str | None:
        """Locate compiled HybMesh2D executable in build candidate paths or PATH."""
        return find_binary_executable("HybMesh2D")



    def _get_expected_vtk_path(self, cfg: MeshConfig) -> str:
        """Calculate the expected output VTK filename matching src/cli.cpp logic."""
        root_dir = repo_root()

        # Name from BOUNDARY geometries only — seeds share geom_files but must
        # not count (matches HybMesh2D, which names from geomFiles alone).
        boundaries = cfg.boundary_files
        if cfg.output_filename:
            # A .vtk path, as the name promises: the Output field may hold the
            # ".*" all-formats placeholder, and callers here go on to test this
            # path for existence or hand it to the mesh stats panel as a file.
            path = MeshConfig.output_path_for(cfg.output_filename, ".vtk")
        elif not cfg.geom_files or len(boundaries) == 0:
            path = MeshConfig.auto_output_name([])
        else:
            path = MeshConfig.auto_output_name(boundaries)

        if os.path.isabs(path):
            return path
        return os.path.abspath(os.path.join(root_dir, path))

    def _on_mesh_gen_finished(self, rc: int, tmp_cfg_name: str, expected_vtk_path: str):
        """Handle execution thread termination, load VTK result, and refresh canvas."""
        self.main_window.release_progress("mesh")
        self.main_window.mesh_config_panel.run_mesh_btn.setEnabled(True)
        self.main_window.mesh_config_panel.cancel_mesh_btn.setEnabled(False)
        self.main_window.mesh_generate_btn.setEnabled(True)
        self.main_window.mesh_cancel_btn.setEnabled(False)

        # Cleanup temporary config file
        try:
            if os.path.exists(tmp_cfg_name):
                os.remove(tmp_cfg_name)
        except Exception as e:
            self.log(f"Failed to delete temp config file {tmp_cfg_name}: {e}")

        # Check return code
        if rc == 0:
            self.log("--- Mesh Generation Success ---")
            self.main_window.mesh_canvas_view.clear_error_highlights()
            if os.path.exists(expected_vtk_path):
                try:
                    mesh = VTKMesh.from_file(expected_vtk_path)
                    self.global_vtk_mesh = mesh
                    self.global_vtk_path = expected_vtk_path
                    self.main_window.mesh_canvas_view.update_mesh_config(self.global_mesh_config, fit_view=False)
                    self.main_window.mesh_canvas_view.render_mesh(mesh, fit_view=False)
                    self.main_window.mesh_stats_panel.update_stats(mesh, expected_vtk_path)
                    self.log(f"Successfully loaded and rendered mesh from {expected_vtk_path}")
                except Exception as e:
                    self.log(f"Failed to load generated mesh VTK: {e}")
            else:
                self.log(f"Error: Expected VTK file not found at {expected_vtk_path}")
        else:
            if rc == RC_CANCELLED:
                self.log("--- Mesh Generation Cancelled by User ---")
            elif rc == RC_TIMEOUT:
                self.log("--- Mesh Generation Timed Out (10 min) ---")
            else:
                self.log(f"--- Mesh Generation Failed (code {rc}) ---")

            # Clear the previous mesh results from session and UI
            self.global_vtk_mesh = None
            self.global_vtk_path = ""
            self.main_window.mesh_canvas_view.clear_mesh_results()
            self.main_window.mesh_stats_panel.update_stats(None)

            # Clear previous error highlights first, then try to detect and highlight new ones
            self.main_window.mesh_canvas_view.clear_error_highlights()
            if rc not in (RC_CANCELLED, RC_TIMEOUT):
                self._try_highlight_self_intersection_error()

        # Auto-export chain (Export-before-Generate foolproofing): run the pending
        # export only if a mesh is now actually available; drop it otherwise.
        pending = getattr(self, "_pending_after_mesh", None)
        self._pending_after_mesh = None
        if pending is not None:
            if self.global_vtk_path and os.path.exists(self.global_vtk_path):
                pending()
            else:
                self.log(
                    "[Export] Mesh generation did not produce a usable mesh; export skipped.")

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

            self.log(
                f"[GUI] Intersection detected between Geometry {geom_id1} and Geometry {geom_id2} — highlighted on canvas."
            )
            self.main_window.mesh_canvas_view.highlight_error_geometry([geom_id1, geom_id2])
            if x is not None and y is not None:
                self.main_window.mesh_canvas_view.highlight_self_intersection_point(x, y)
                self.log(f"[GUI] Intersection coordinate: ({x}, {y})")
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

            self.log(
                f"[GUI] Self-intersection detected in Geometry {geom_id} — highlighted on canvas."
            )
            self.main_window.mesh_canvas_view.highlight_error_geometry(geom_id)
            if x is not None and y is not None:
                self.main_window.mesh_canvas_view.highlight_self_intersection_point(x, y)
                self.log(f"[GUI] Self-intersection coordinate: ({x}, {y})")
            return

        self.main_window.mesh_canvas_view.clear_error_highlights()

    def _offer_generate_then(self, retry_fn, what: str):
        """Foolproof guard for Export-before-Generate: prompt the user and, if they
        agree, run the mesh generator now and re-run `retry_fn` once it finishes."""
        w = getattr(self, "_mesh_worker", None)
        if w is not None and w.isRunning():
            self.log(
                "Mesh generation is running; please wait for it to finish, then export.")
            return
        # headless_default False: a batch export must fail loudly rather than
        # silently kick off a mesh run nobody asked for.
        if not confirm(
                self.main_window, "No Mesh Generated",
                f"No mesh has been generated yet, so {what} cannot be exported."
                "\n\nGenerate the mesh now and export automatically when it "
                "finishes?", headless_default=False):
            return
        self._pending_after_mesh = retry_fn
        self.log(
            f"[Export] No mesh yet — generating first, then exporting {what}.")
        self.run_mesh_generator()
        # If generation did not actually start (e.g. binary missing, invalid
        # domain), drop the pending action so it can't fire on a later run.
        w = getattr(self, "_mesh_worker", None)
        if w is None or not w.isRunning():
            self._pending_after_mesh = None
