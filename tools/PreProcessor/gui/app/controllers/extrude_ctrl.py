from __future__ import annotations
import os

import numpy as np
from PyQt6.QtWidgets import QFileDialog, QInputDialog, QMessageBox

from app.utils import repo_root


def _poly_area(poly: np.ndarray) -> float:
    """Absolute shoelace area of a 2D loop."""
    x, y = poly[:, 0], poly[:, 1]
    return 0.5 * abs(float(np.sum(x * np.roll(y, -1) - np.roll(x, -1) * y)))


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

    def _collect_extrude_loops(self) -> tuple[list[np.ndarray], list[str], list[str]]:
        """Return (loops, used_names, skipped_names) from visible sessions.

        Prefers each session's authored polyline (original_points); falls back to
        its last resampled output if the raw points are unavailable.
        """
        loops: list[np.ndarray] = []
        used: list[str] = []
        skipped: list[str] = []
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
        return loops, used, skipped

    def _loop_issue_warnings(self, loops: list[np.ndarray], names: list[str]) -> list[str]:
        """Surface the prism extruder's key limitation (never silently): nested
        loops are extruded as solid, not subtracted as holes — STL3d marks them
        solid via z-ray parity. (Open vs closed is not detectable from points
        alone — a closed loop stored without a repeated first vertex looks the
        same — so that is left to the per-segment ``closed`` flag, not guessed
        here.)"""
        warnings: list[str] = []
        areas = [_poly_area(a) for a in loops]
        nested = []
        for i, (ai, ni) in enumerate(zip(loops, names)):
            centroid = ai.mean(axis=0)
            if any(j != i and areas[j] > areas[i] and _point_in_poly(centroid, loops[j])
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
        loops, used, skipped = self._collect_extrude_loops()
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
        issues = self._loop_issue_warnings(loops, used)
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
        default_t = round(ext * 0.1, 6) if ext > 0 else 1.0
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

        try:
            from app.services.stl_extrude import extrude_loop, write_binary_stl
            parts, failed = [], []
            for arr, nm in zip(loops, used):
                t = extrude_loop(arr, z0, z1)
                if len(t):
                    parts.append(t)
                else:
                    failed.append(nm)
            if failed:
                log("[Extrude] Could not triangulate (degenerate / self-intersecting "
                    f"loop, skipped): {', '.join(failed)}")
            if not parts:
                log("[Extrude] Triangulation produced no facets — check that the "
                    "profile is a simple (non-self-intersecting) closed loop.")
                QMessageBox.warning(self.main_window, "Extrude → STL",
                                    "Could not triangulate any profile (degenerate "
                                    "or self-intersecting loop).")
                return
            tris = np.vstack(parts)
            write_binary_stl(path, tris)
        except Exception as e:
            log(f"[Extrude] Failed: {e}")
            QMessageBox.warning(self.main_window, "Extrude → STL", str(e))
            return

        log(f"--- Extruded {len(loops)} loop(s) [{', '.join(used)}] → "
            f"{len(tris):,} facets, thickness {thickness:g} (z {z0:g}..{z1:g}) ---")
        log(f"STL written to {path}")

        reply = QMessageBox.question(
            self.main_window, "Extrude → STL",
            "STL saved.\n\nLoad it into the Immersed Solid (STL→φ) page now?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes)
        if reply == QMessageBox.StandardButton.Yes:
            self._load_stl3d(path, auto_fit=True)
            self.main_window.mode_combo.setCurrentIndex(5)   # Immersed Solid
