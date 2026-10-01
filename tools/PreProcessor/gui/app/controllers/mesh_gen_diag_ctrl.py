"""What the mesh stage TELLS the user about a run it is not performing.

Split off ``mesh_gen_ctrl.py`` when that file ran out of room for the work coming
to it (#159), along the seam it already had: the other half LAUNCHES the mesher
and handles what comes back, while everything here is diagnosis — the pre-flight
warning about an input the stage cannot fully read, the per-geometry scan that
reports point counts and bounds, and the post-mortem that reads an intersection
out of the mesher's own log and points at it on the canvas. None of the three
starts, stops or inspects a worker.

Mixed into :class:`~app.controllers.mesh_gen_ctrl.MeshGenControllerMixin` rather
than wired into ``controller.py`` beside it, so ``self._scan_geometry_files`` and
``self._try_highlight_self_intersection_error`` resolve exactly as they did and
no caller — nor the gates that read these methods by source — is touched.
"""
from __future__ import annotations
import os

from app.services.geom_path_identity import readable_geom_path
from app.services.logging_setup import get_logger
from app.services.mesh_modes import MESH_MODE_HYBRID, missing_mesh_input

__all__ = ["MeshGenDiagnosticsMixin", "mesh_input_warning"]

_log = get_logger(__name__)


def mesh_input_warning(cfg) -> str:
    """The pre-flight warning for a config the mesh stage cannot fully run, or "".

    A module function rather than a method so a gate can ask it what the user
    would be TOLD without launching a worker — which is where the defect it
    exists to hold actually lived.

    What the stage is missing is answered per mode by ``missing_mesh_input``, and
    the REASON is used, not just its truth value: the first cut of #56 wrote
    ``if not cfg.geom_files and missing_mesh_input(cfg)`` and so told a
    multi-block config with no topology that it had no geometry, sending the user
    to the CAD tab for the other path's problem. Non-blocking, as it has always
    been — the mesher gives the authoritative error.
    """
    why = missing_mesh_input(cfg)
    if not why:
        return ""
    hint = ""
    # Keyed on the MODE, never on the reason's TEXT: this repo has already had to
    # reverse one law that was compared as a string at eight sites.
    if int(getattr(cfg, "mesh_mode", MESH_MODE_HYBRID) or 0) == MESH_MODE_HYBRID:
        hint = (" The mesh will have no boundary/BL. If you drew with 'Add "
                "analytic edge', run 'Save & Export' in CAD mode (or 'Add "
                "Active'/check it in Geometry Layers) so it is written to a "
                ".dat first.")
    return f"[WARNING] {why}.{hint}"

class MeshGenDiagnosticsMixin:
    """The mesh stage's pre-flight scan and its post-mortem read of the log."""

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
            # The entry is a SPELLING; readable_geom_path is the one verb that
            # turns it into the file to open. Reading it raw resolved a
            # repo-relative entry (a loaded workspace, a saved script, the
            # resample stage) against the process cwd.
            gp = readable_geom_path(gf)
            if not gp:
                # Not logged here: the pre-flight above already refused the run
                # over it (cfg.geom_files_not_on_disk(), which asks the filesystem
                # -- deliberately NOT validate(), which is pure).
                # This loop only skips it for the bbox scan -- a WARNING beside
                # a fatal error reads as "the run went ahead anyway", which is
                # exactly what it used to do.
                continue
            try:
                pts = np.loadtxt(gp, ndmin=2)
            except Exception as e:
                # Fall back to a bare point count so at least the diagnostic prints.
                try:
                    with open(gp) as _f:
                        npts = sum(1 for ln in _f if ln.strip())
                    self.log(
                        f"[geom] {os.path.basename(gf)} ({npts} points)")
                    # No exc_info: this branch RECOVERED, and a traceback on a
                    # path that succeeded is the noise the standard's `debug`
                    # grade exists to avoid. The message names both halves.
                    _log.debug("bbox scan: %r parsed by hand after %s", gp, e)
                except OSError:
                    # readable_geom_path said the file is THERE and neither
                    # reader can open it: a genuine read failure, not a geometry
                    # the user has not made yet. WARNING because this geometry
                    # silently leaves the bbox the scan is computing, and the run
                    # goes ahead (the pre-flight only refuses files that are
                    # ABSENT). exc_info carries the open's error chained onto the
                    # np.loadtxt one above it.
                    _log.warning("bbox scan: could not read geometry %r: %s",
                                 gp, e, exc_info=True)
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
