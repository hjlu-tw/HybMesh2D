from __future__ import annotations
import os

import numpy as np
from PyQt6.QtWidgets import QFileDialog, QInputDialog, QMessageBox

from app.utils import repo_root
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
    """Extrude the 2D CAD profile(s) into a watertight 3D STL (Q2 method A).

    Each visible geometry layer's polyline becomes a prism (triangulated caps +
    side walls); all are written to one binary STL that the Immersed Solid
    (STL→φ) page can consume directly. Bridges the 2D editor to the STL3d
    preprocessor without any external CAD tool.
    """

    def _extrude_profile_stem(self) -> str:
        s = self.active_session()
        if s is not None and getattr(s, "file_path", ""):
            return os.path.splitext(os.path.basename(s.file_path))[0]
        return "profile"

    def _collect_extrude_loops(self):
        """Return (loops, used_names, skipped_names, open_names) from visible sessions.

        Prefers each session's authored polyline (original_points); falls back to
        its last resampled output if the raw points are unavailable. ``open_names``
        lists the used layers whose per-profile ``closed`` flag is False (they are
        sealed into a solid on extrude — surfaced as a warning, not guessed from
        the points, which cannot tell an unrepeated-first-vertex closed loop from
        an open one).
        """
        loops: list[np.ndarray] = []
        used: list[str] = []
        skipped: list[str] = []
        open_names: list[str] = []
        for s in self.sessions:
            if not getattr(s, "is_visible", True):
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
        """Surface the prism extruder's key limitations (never silently): open
        profiles are sealed into a solid, and nested loops are extruded as solid
        (not subtracted as holes — STL3d marks them solid via z-ray parity)."""
        warnings: list[str] = []
        if open_names:
            warnings.append(
                "Open profile(s) will be SEALED into a closed solid "
                f"({', '.join(open_names)}); a side wall joins the last point back "
                "to the first. Mark the profile closed (or close it) if that is not "
                "what you want.")
        areas = [_poly_area(a) for a in loops]
        nested = []
        for i, (ai, ni) in enumerate(zip(loops, names)):
            if any(j != i and areas[j] > areas[i] and _fraction_inside(ai, loops[j]) > 0.5
                   for j in range(len(loops))):
                nested.append(ni)
        if nested:
            warnings.append(
                "Nested profile(s) are extruded as SOLID, not subtracted as holes "
                f"({', '.join(nested)}); STL3d will mark these interiors solid. "
                "Remove inner loops if you need voids.")
        return warnings

    def extrude_active_to_stl(self):
        log = self.main_window.log_panel.log
        if getattr(self, "_extrude_worker", None) is not None and self._extrude_worker.isRunning():
            log("[Extrude] An extrusion is already running. Please wait.")
            return
        loops, used, skipped, open_names = self._collect_extrude_loops()
        if not loops:
            log("[Extrude] No 2D geometry to extrude. Draw or import a closed "
                "profile first (bake analytic curves so they have points).")
            QMessageBox.information(
                self.main_window, "Extrude → STL",
                "No 2D geometry found.\n\nDraw or import a closed profile first. "
                "Analytic curves must be baked into points before extruding.")
            return
        if skipped:
            log(f"[Extrude] Skipped layers without usable points: {', '.join(skipped)}")

        # Surface the prism extruder's limitations loudly (open profiles are
        # sealed; nested loops fill instead of becoming holes) and let the user
        # abort rather than silently producing a wrong immersed solid.
        issues = self._loop_issue_warnings(loops, used, open_names)
        if issues:
            for w in issues:
                log(f"[Extrude] ⚠ {w}")
            proceed = QMessageBox.warning(
                self.main_window, "Extrude → STL",
                "Heads up before extruding:\n\n• " + "\n\n• ".join(issues)
                + "\n\nExtrude anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No)
            if proceed != QMessageBox.StandardButton.Yes:
                log("[Extrude] Cancelled (profile warnings).")
                return

        # Default thickness = 10% of the in-plane extent (sane for a thin slab).
        allpts = np.vstack(loops)
        ext = float(max(np.ptp(allpts[:, 0]), np.ptp(allpts[:, 1])))
        default_t = ext * 0.1 if ext > 0 else 1.0
        # Round for a clean default, but never below the dialog minimum: a tiny
        # extent would otherwise round to 0.0 and silently clamp to 1e-9.
        rounded = round(default_t, 6)
        default_t = rounded if rounded >= 1e-6 else default_t
        thickness, ok = QInputDialog.getDouble(
            self.main_window, "Extrude → STL",
            "Extrusion thickness in z (centered on z=0):",
            default_t, 1e-9, 1e12, 6)
        if not ok:
            return
        z0, z1 = -thickness / 2.0, thickness / 2.0

        default_path = os.path.join(
            repo_root(), "examples", "geometries",
            f"{self._extrude_profile_stem()}_extruded.stl")
        path, _ = QFileDialog.getSaveFileName(
            self.main_window, "Save Extruded STL", default_path,
            "STL Files (*.stl);;All Files (*)")
        if not path:
            return
        if not path.lower().endswith(".stl"):
            path += ".stl"

        # Triangulation (ear clipping, O(N^2)) + STL write can take seconds on a
        # dense imported profile, so run it off the GUI thread; the hand-off to
        # the Immersed Solid page happens in _on_extrude_done.
        from app.workers.extrude_run import ExtrudeWorker
        self._extrude_pending = {"thickness": thickness, "z0": z0, "z1": z1,
                                 "n_loops": len(loops), "used": list(used)}
        log(f"[Extrude] Triangulating {len(loops)} loop(s) and writing STL "
            "in the background…")
        self._extrude_worker = ExtrudeWorker(loops, used, z0, z1, path)
        self._extrude_worker.result_signal.connect(self._on_extrude_done)
        self._extrude_worker.start()

    def _on_extrude_done(self, m: dict):
        """Report the extrusion result and offer the Immersed Solid hand-off."""
        log = self.main_window.log_panel.log
        self._extrude_worker = None          # delivered; release the thread object
        info = getattr(self, "_extrude_pending", None) or {}
        if m.get("failed"):
            log("[Extrude] Could not triangulate (degenerate / self-intersecting "
                f"loop, skipped): {', '.join(m['failed'])}")
        if m.get("error") == "no_facets":
            log("[Extrude] Triangulation produced no facets — check that the "
                "profile is a simple (non-self-intersecting) closed loop.")
            QMessageBox.warning(self.main_window, "Extrude → STL",
                                "Could not triangulate any profile (degenerate "
                                "or self-intersecting loop).")
            return
        if m.get("error"):
            log(f"[Extrude] Failed: {m['error']}")
            QMessageBox.warning(self.main_window, "Extrude → STL", str(m["error"]))
            return

        path, n = m["path"], m["n_facets"]
        thickness, z0, z1 = info.get("thickness", 0.0), info.get("z0", 0.0), info.get("z1", 0.0)
        used = info.get("used", [])
        log(f"--- Extruded {info.get('n_loops', 0)} loop(s) [{', '.join(used)}] → "
            f"{n:,} facets, thickness {thickness:g} (z {z0:g}..{z1:g}) ---")
        log(f"STL written to {path}")

        reply = QMessageBox.question(
            self.main_window, "Extrude → STL",
            "STL saved.\n\nLoad it into the Immersed Solid (STL→φ) page now?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes)
        if reply == QMessageBox.StandardButton.Yes:
            self._load_stl3d(path, auto_fit=True)
            self.main_window.mode_combo.setCurrentIndex(5)   # Immersed Solid
