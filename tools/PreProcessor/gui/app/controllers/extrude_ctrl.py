from __future__ import annotations
import os

import numpy as np
from PyQt6.QtWidgets import QDialog, QFileDialog

from app.utils import repo_root, report_info, report_error, confirm
from app.services.stl_extrude import _signed_area


def _poly_area(poly: np.ndarray) -> float:
    """Absolute shoelace area of a 2D loop (|signed area|; the one formula lives
    in stl_extrude._signed_area)."""
    return abs(_signed_area(poly))


def _point_in_poly(pt: np.ndarray, poly: np.ndarray) -> bool:
    """Even-odd ray-cast point-in-polygon test (heuristic, for nesting warnings)."""
    x, y = float(pt[0]), float(pt[1])
    n = len(poly)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if ((yi > y) != (yj > y)) and \
                (x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-300) + xi):
            inside = not inside
        j = i
    return inside


def _fraction_inside(inner: np.ndarray, outer: np.ndarray, samples: int = 16) -> float:
    """Fraction of a small evenly-spaced sample of ``inner`` that lies in ``outer``.

    Sampling (instead of testing every vertex) keeps this O(samples · |outer|) so
    dense profiles do not stall, while using several points — not just the
    centroid, which falls outside a concave loop — makes the nesting test robust
    to non-convex outer/inner shapes.
    """
    if len(inner) == 0:
        return 0.0
    take = min(samples, len(inner))
    sel = np.linspace(0, len(inner) - 1, take).round().astype(int)
    hits = sum(1 for i in sel if _point_in_poly(inner[i], outer))
    return hits / float(take)


class ExtrudeControllerMixin:
    """Export the 2D CAD profile(s) as a flat-sheet STL for the immersed solid.

    The project is 2D, so each visible geometry layer's polyline is triangulated
    into a planar z=0 sheet (filled cross-section, no z-extrusion); all are
    written to one binary STL that the Immersed Solid (STL→φ) page can consume
    directly. Bridges the 2D editor to the STL3d preprocessor without any
    external CAD tool. (A true 3D prism is still available via
    ``stl_extrude.extrude_loop`` should the solver gain 3D support.)
    """

    def _extrude_profile_stem(self, session_ids=None) -> str:
        """Filename stem for the exported STL, named after a layer that is
        actually in the export: one of the selected `session_ids` if given, else
        the active layer when visible, else the first visible layer with a file —
        so the suggested name never points at a layer left out of the STL."""
        if session_ids is not None:
            candidates = [s for s in self.sessions if s.session_id in session_ids]
        else:
            active = self.active_session()
            candidates = []
            if active is not None and getattr(active, "is_visible", True):
                candidates.append(active)
            candidates.extend(s for s in self.sessions
                              if s is not active and getattr(s, "is_visible", True))
        for s in candidates:
            fp = getattr(s, "file_path", "")
            if fp:
                return os.path.splitext(os.path.basename(fp))[0]
        return "profile"

    @staticmethod
    def _session_has_geom(s) -> bool:
        """True if a session carries a usable polyline (>= 3 points), from its
        authored points or its last resampled output."""
        pts = s.original_points
        if pts is None or len(pts) < 3:
            pts = getattr(s, "resampled_points", None)
        return pts is not None and len(pts) >= 3

    def _collect_extrude_loops(self, session_ids=None):
        """Return (loops, used_names, skipped_names, open_names).

        With `session_ids` (a set), collect exactly those sessions; otherwise
        collect every currently-visible session. Prefers each session's authored
        polyline (original_points); falls back to its last resampled output if the
        raw points are unavailable. ``open_names`` lists the used layers whose
        per-profile ``closed`` flag is False (they are sealed into a closed loop on
        export — surfaced as a warning, not guessed from the points, which cannot
        tell an unrepeated-first-vertex closed loop from an open one).
        """
        loops: list[np.ndarray] = []
        used: list[str] = []
        skipped: list[str] = []
        open_names: list[str] = []
        for s in self.sessions:
            if session_ids is None:
                if not getattr(s, "is_visible", True):
                    continue
            elif s.session_id not in session_ids:
                continue
            pts = s.original_points
            if pts is None or len(pts) < 3:
                pts = getattr(s, "resampled_points", None)
            if pts is None or len(pts) < 3:
                skipped.append(s.display_name)
                continue
            arr = np.asarray(pts, dtype=np.float64)[:, :2]
            if not np.all(np.isfinite(arr)):
                skipped.append(s.display_name)
                continue
            loops.append(arr)
            used.append(s.display_name)
            if not getattr(getattr(s, "project_model", None), "is_closed", True):
                open_names.append(s.display_name)
        return loops, used, skipped, open_names

    def _loop_issue_warnings(self, loops: list[np.ndarray], names: list[str],
                             open_names: list[str]) -> list[str]:
        """Surface the flat-sheet export's key limitations (never silently): open
        profiles are sealed into a closed loop, and nested loops are filled as
        solid (not cut as holes — STL3d marks them solid via z-ray parity)."""
        warnings: list[str] = []
        if open_names:
            warnings.append(
                "Open profile(s) will be SEALED into a closed loop "
                f"({', '.join(open_names)}); a closing edge joins the last point "
                "back to the first. Mark the profile closed (or close it) if that "
                "is not what you want.")
        areas = [_poly_area(a) for a in loops]
        nested = []
        for i, (ai, ni) in enumerate(zip(loops, names)):
            if any(j != i and areas[j] > areas[i] and _fraction_inside(ai, loops[j]) > 0.5
                   for j in range(len(loops))):
                nested.append(ni)
        if nested:
            warnings.append(
                "Nested profile(s) are FILLED as solid, not cut as holes "
                f"({', '.join(nested)}); STL3d will mark these interiors solid. "
                "Remove inner loops if you need voids.")
        return warnings

    def extrude_active_to_stl(self):
        """Export the visible 2D profile(s) as a flat z=0 sheet STL (2D project).

        Method name kept for the existing button/menu wiring; it no longer
        extrudes in z — each profile is triangulated into a planar lamina.
        """
        log = self.log
        if getattr(self, "_extrude_worker", None) is not None and self._extrude_worker.isRunning():
            log("[Export] An STL export is already running. Please wait.")
            return
        # Source selection: with two or more CAD layers that have geometry, let
        # the user pick which become the immersed-boundary STL (so a layer meant
        # only for the mesh isn't swept in). Zero/one candidate -> no prompt.
        candidates = [s for s in self.sessions if self._session_has_geom(s)]
        session_ids = None
        if len(candidates) >= 2:
            from app.views.extrude_source_dialog import ExtrudeSourceDialog
            dlg = ExtrudeSourceDialog(self.sessions, self._session_has_geom,
                                      self.main_window)
            from app.utils import offset_popup
            offset_popup(dlg, self.main_window)
            if dlg.exec() != QDialog.DialogCode.Accepted:
                log("[Export] Cancelled (source selection).")
                return
            session_ids = dlg.selected_ids()
            if not session_ids:
                log("[Export] No source layer selected.")
                report_info(self.main_window, "Export 2D STL",
                            "No source layer selected.")
                return

        loops, used, skipped, open_names = self._collect_extrude_loops(session_ids)
        if not loops:
            log("[Export] No 2D geometry to export. Draw or import a closed "
                "profile first (bake analytic curves so they have points).")
            report_info(
                self.main_window, "Export 2D STL",
                "No 2D geometry found.\n\nDraw or import a closed profile first. "
                "Analytic curves must be converted to discrete points first.")
            return
        if skipped:
            log(f"[Export] Skipped layers without usable points: {', '.join(skipped)}")

        # Surface the flat-sheet limitations loudly (open profiles are sealed;
        # nested loops fill instead of becoming holes) and let the user abort
        # rather than silently producing a wrong immersed solid.
        issues = self._loop_issue_warnings(loops, used, open_names)
        if issues:
            for w in issues:
                log(f"[Export] ⚠ {w}")
            if not confirm(
                    self.main_window, "Export 2D STL",
                    "Heads up before exporting:\n\n• " + "\n\n• ".join(issues)
                    + "\n\nExport anyway?"):
                log("[Export] Cancelled (profile warnings).")
                return

        # 2D project: export a flat sheet at z=0 (no z-extrusion / thickness).
        z0 = z1 = 0.0

        # Into results/, never examples/. `examples/geometries/` is INPUT and is
        # tracked (60 files); the default name is derived from the session stem,
        # so a session opened from `examples/geometries/I_coarse.dat` proposed
        # `I_coarse_2d.stl` — right on top of a committed sibling, and accepting
        # the default overwrote it in place (measured once: a binary STL replaced
        # by a 4.6x larger ascii re-export of the same body). results/stl3d/ is
        # where this file is headed anyway — the export hands off to the Immersed
        # Solid page — and results/ is gitignored, so nothing it writes can dirty
        # the tree.
        #
        # The directory is created BEFORE the dialog, and that is deliberate: given
        # a path whose folder does not exist, the save dialog falls back to the
        # last-used one, which loses the very default this fix is about. So
        # cancelling the export still leaves an empty `results/stl3d/` behind —
        # harmless, because it is gitignored, and the same trade the mesh, solver
        # and pipeline save dialogs make with `config/local/`.
        out_dir = os.path.join(repo_root(), "results", "stl3d")
        os.makedirs(out_dir, exist_ok=True)
        default_path = os.path.join(
            out_dir, f"{self._extrude_profile_stem(session_ids)}_2d.stl")
        path, _ = QFileDialog.getSaveFileName(
            self.main_window, "Save 2D Profile STL", default_path,
            "STL Files (*.stl);;All Files (*)")
        if not path:
            return
        if not path.lower().endswith(".stl"):
            path += ".stl"

        # Triangulation (ear clipping, O(N^2)) + STL write can take seconds on a
        # dense imported profile, so run it off the GUI thread; the hand-off to
        # the Immersed Solid page happens in _on_extrude_done.
        from app.workers.extrude_run import ExtrudeWorker
        self._extrude_pending = {"z0": z0, "z1": z1,
                                 "n_loops": len(loops), "used": list(used)}
        log(f"[Export] Triangulating {len(loops)} profile(s) into a flat 2D STL "
            "in the background…")
        self._extrude_worker = ExtrudeWorker(loops, used, z0, z1, path, flat=True)
        self._extrude_worker.result_signal.connect(self._on_extrude_done)
        self._extrude_worker.start()

    def _on_extrude_done(self, m: dict):
        """Report the extrusion result and offer the Immersed Solid hand-off."""
        log = self.log
        # Keep the finished worker alive until its finished() signal fires before
        # releasing it — dropping the last reference to a QThread whose run() is
        # still unwinding can abort with "QThread destroyed while running".
        worker = self._extrude_worker
        self._extrude_worker = None
        if worker is not None:
            self._retiring_workers.add(worker)
            worker.finished.connect(lambda w=worker: self._retiring_workers.discard(w))
        info = getattr(self, "_extrude_pending", None) or {}
        if m.get("failed"):
            log("[Export] Could not triangulate (degenerate / self-intersecting "
                f"loop, skipped): {', '.join(m['failed'])}")
        if m.get("error") == "no_facets":
            log("[Export] Triangulation produced no facets — check that the "
                "profile is a simple (non-self-intersecting) closed loop.")
            # A failed export is a failed WRITE: nothing landed on disk, so it is
            # an error, not a warning (report_warning is for failed reads).
            report_error(self.main_window, "Export 2D STL Failed",
                         "Could not triangulate any profile, so no STL was "
                         "written.",
                         detail="The profile is degenerate or self-intersecting.")
            return
        if m.get("error"):
            log(f"[Export] Failed: {m['error']}")
            report_error(self.main_window, "Export 2D STL Failed",
                         "The STL could not be written.", detail=str(m["error"]))
            return

        path, n = m["path"], m["n_facets"]
        used = info.get("used", [])
        log(f"--- Exported {info.get('n_loops', 0)} profile(s) [{', '.join(used)}] → "
            f"flat 2D STL, {n:,} facets (z=0) ---")
        log(f"STL written to {path}")

        if confirm(self.main_window, "Export 2D STL",
                   "STL saved.\n\nLoad it into the Immersed Boundary (φ) page now?",
                   headless_default=False):
            self._load_stl3d(path, auto_fit=True)
            self.main_window.mode_combo.setCurrentIndex(5)   # Immersed Solid
