from __future__ import annotations
import os

from PyQt6.QtWidgets import QFileDialog

from app.utils import (
    repo_root, report_info,
)
from app.services.logging_setup import get_logger

_log = get_logger(__name__)


class SolverToolsControllerMixin:
    def open_dll_builder(self, dll_type: str):
        from app.views.dll_builder_dialog import DllBuilderDialog
        sp = self.main_window.solver_config_panel
        target = sp.init_cond_dll if dll_type == "init_cond" else sp.motion_dll
        dlg = DllBuilderDialog(self.main_window, dll_type, target.text().strip())
        from app.utils import offset_popup
        offset_popup(dlg, self.main_window)
        if dlg.exec() and dlg.result_path:
            target.setText(dlg.result_path)
            self.main_window.log_panel.log(
                f"[IBM] {dll_type} DLL source set: {dlg.result_path}")

    def generate_phi_from_cad_shape(self):
        """Auto-generate an ANALYTIC immersed-solid phi init DLL from a CAD shape
        (circle -> solid disk; polygon/triangle/quad/closed custom -> point-in-
        polygon over the sampled boundary), wire it into the solver's IBM config,
        and skip the STL3d phi.dat path (ibm_phi_file left empty)."""
        from PyQt6.QtWidgets import QInputDialog
        from app.services.geometry_service import GeometryService
        from app.services.dll_templates import render_analytic_phi_from_shape
        log = self.main_window.log_panel.log

        session = self.active_session()

        def _is_solid(seg):
            if getattr(seg, "type", "") != "curve":
                return False
            ct = getattr(seg, "curve_type", "")
            if ct in ("circle", "triangle", "quadrilateral"):
                return True
            if ct in ("polygon", "custom"):
                return bool(getattr(seg, "closed", False))
            return False

        shapes = ([s for s in session.project_model.segments if _is_solid(s)]
                  if session is not None else [])
        if not shapes:
            report_info(
                self.main_window, "Analytic phi",
                "No closed CAD shape found. Draw a circle / polygon / triangle / "
                "quad (closed) in the CAD tab, then try again.")
            return

        seg = shapes[0]
        if len(shapes) > 1:
            labels = [f"Edge {s.id}: {getattr(s, 'curve_type', '?')}" for s in shapes]
            choice, ok = QInputDialog.getItem(
                self.main_window, "Analytic phi from CAD shape",
                "Choose the solid shape:", labels, 0, False)
            if not ok:
                return
            seg = shapes[labels.index(choice)]

        ct = getattr(seg, "curve_type", "")
        if ct == "circle":
            cx = float(seg.parameters.get("cx", 0.0))
            cy = float(seg.parameters.get("cy", 0.0))
            r = float(seg.parameters.get("r", 1.0))
            src = render_analytic_phi_from_shape("circle", cx=cx, cy=cy, radius=r)
            desc = f"disk @({cx:g},{cy:g}) r={r:g}"
        else:
            pr = GeometryService.get_segment_points(session, seg)
            if pr is None or len(pr[0]) < 3:
                log("[IBM] Could not read the shape's boundary points.")
                return
            verts = list(zip((float(x) for x in pr[0]), (float(y) for y in pr[1])))
            src = render_analytic_phi_from_shape("polygon", verts=verts)
            desc = f"{ct} point-in-polygon ({len(verts)} verts)"

        dll_dir = os.path.join(repo_root(), "results", "solver", "dll_src")
        try:
            os.makedirs(dll_dir, exist_ok=True)
            cc = os.path.join(dll_dir, f"ibm_phi_shape_edge{seg.id}.cc")
            with open(cc, "w") as f:
                f.write(src)
        except OSError as e:
            log(f"[IBM] Failed to write analytic phi DLL: {e}")
            return

        sc = self.global_solver_config
        sc.immersed_solid = True
        sc.stationary_solid = True
        sc.rigid_moving_body = False
        sc.motion_dll = ""
        sc.init_cond_dll = cc
        sc.ibm_phi_file = ""            # analytic — no phi.dat needed
        panel = self.main_window.solver_config_panel
        panel.set_config(sc)
        if hasattr(panel, "_update_ibm_visibility"):
            panel._update_ibm_visibility()
        self.main_window.mode_combo.setCurrentIndex(3)   # Solver

        log("--- Generated ANALYTIC phi from CAD shape ---")
        log(f"  shape    : Edge {seg.id} ({desc})")
        log(f"  init DLL : {cc}")
        log("  Solver: immersed_solid ON; phi is evaluated analytically (no "
            "phi.dat). Set the mesh (.vrt/.cel/.bnd) and Run Solver.")

    def open_probe_coords_dialog(self):
        """Enter probe-point coordinates in the GUI, write them to a file and
        link it into the solver config's probe field (#10)."""
        from app.views.probe_points_dialog import ProbePointsDialog
        sp = self.main_window.solver_config_panel
        cur = sp.probe_points_def_fn.text().strip()
        initial = ""
        if cur and os.path.exists(cur):
            try:
                with open(cur) as f:
                    initial = f.read()
            except OSError:
                pass
        dlg = ProbePointsDialog(self.main_window, initial)
        from app.utils import offset_popup
        offset_popup(dlg, self.main_window)
        if not dlg.exec() or not dlg.points():
            return
        # Reuse the existing path when set, otherwise ask where to save.
        path = cur
        if not path:
            default_dir = os.path.join(repo_root(), "results", "solver")
            os.makedirs(default_dir, exist_ok=True)
            path, _ = QFileDialog.getSaveFileName(
                self.main_window, "Save probe-point file",
                os.path.join(default_dir, "probe_points.dat"),
                "Probe points (*.dat *.txt);;All Files (*)")
            if not path:
                return
        try:
            with open(path, "w") as f:
                f.write(dlg.as_file_text())
        except OSError as e:
            self.main_window.log_panel.log(f"[probe] write failed: {e}")
            return
        sp.probe_points_def_fn.setText(path)
        self.main_window.log_panel.log(
            f"[probe] wrote {len(dlg.points())} point(s) → {path}")
        # Visualise the probe locations on the Results canvas (#5): they persist
        # across variable changes / result reloads, so they overlay the contour
        # once a result is loaded (run the solver, then Load Result).
        try:
            self.main_window.result_canvas_view.set_solver_probe_points(dlg.points())
            self.main_window.log_panel.log(
                "[probe] locations overlaid on the Results canvas "
                "(visible once a result is loaded).")
        except Exception:
            _log.warning(
                "could not overlay the probe locations on the Results "
                "canvas", exc_info=True)

    def refresh_solver_probe_overlay(self):
        """#4: parse the configured probe-point file and overlay its markers on
        the Results canvas, so the probe locations stay visible after a config /
        session reload (the file link survives, so the markers should too). A
        no-op when no probe file is set. Called on entering Solver mode."""
        import os
        from app.views.probe_points_dialog import parse_probe_points
        sp = self.main_window.solver_config_panel
        path = sp.probe_points_def_fn.text().strip()
        if not path or not os.path.exists(path):
            return
        try:
            with open(path) as f:
                pts = parse_probe_points(f.read())
        except OSError:
            return
        try:
            self.main_window.result_canvas_view.set_solver_probe_points(pts)
        except Exception:
            _log.warning(
                "could not overlay the probe points read from "
                "file", exc_info=True)
