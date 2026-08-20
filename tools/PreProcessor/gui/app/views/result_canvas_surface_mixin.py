"""Surface-source overlay and surface plot for :class:`ResultCanvasView`.

Owns the three things a chosen surface needs on the canvas side:

* **It is drawn.** A surface plot whose curve you cannot see is a chart of
  unknown geometry — for a φ iso-line or a chained interface cloud, *where* the
  curve went is half the result. Every extracted piece is drawn dim; the piece
  actually plotted is drawn bright.
* **s = 0 is drawn too.** Arc length is meaningless without its origin, so the
  start point gets a ringed marker and an arrow showing the traversal direction,
  and the plot's x-axis label repeats the coordinate. This is why the start rule
  is required rather than defaulted (USER-REQUESTED).
* **Extraction is deferred.** The dialog only edits a ``SurfaceSpec``; nothing is
  contoured, chained or sampled until the user presses Plot / Show.

The heavy lifting is in ``services/surface_source`` (geometry) and
``services/surface_sample`` (ordering + sampling); this mixin is the Qt/matplotlib
glue plus the exact-vs-interpolated decision.
"""
from __future__ import annotations

import numpy as np

from app.services import surface_source as ss
from app.services import surface_sample as sm
from app.services.logging_setup import get_logger

_log = get_logger(__name__)

_SURF_COLOR = "#f472b6"        # pink: distinct from CAD (#e5e7eb) and line (#fbbf24)
_SURF_DIM = "#7f4a63"


class ResultCanvasSurfaceMixin:
    # ------------------------------------------------------------------ #
    def set_controller(self, controller):
        """Give the canvas the controller that provides the non-mesh surface
        sources (STL3d φ, analytic shapes, CAD outlines). Optional: without it
        only the mesh-boundary source is offered."""
        self._ctrl = controller

    def surface_source_options(self) -> list:
        ctrl = getattr(self, "_ctrl", None)
        if ctrl is None:
            return [{"kind": ss.KIND_MESH, "enabled": self._result is not None,
                     "label": ss.KIND_LABELS[ss.KIND_MESH], "detail": "",
                     "reason": "" if self._result is not None else "no result loaded"}]
        return ctrl.surface_source_options(self._result)

    def open_surface_dialog(self):
        """Surface… — pick which curve counts as "the surface", then plot it."""
        from app.views.surface_source_dialog import SurfaceSourceDialog
        if self._result is None:
            from app.utils import report_info
            report_info(self, "Surface", "Load a result first.")
            return
        if self._surf_src_dialog is None:
            self._surf_src_dialog = SurfaceSourceDialog(self)
            from app.utils import keep_on_top, offset_popup
            keep_on_top(self._surf_src_dialog)
            offset_popup(self._surf_src_dialog, self.window())
        dlg = self._surf_src_dialog
        dlg.reload(self.surface_source_options(), self._surface_spec)
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()

    # ------------------------------------------------------------------ #
    # Extraction + preparation (ordering, s = 0, direction)
    # ------------------------------------------------------------------ #
    def build_surface(self, spec) -> dict:
        """Extract, orient and rotate the surface ``spec`` describes.

        Returns ``{"ok", "error", "notes", "curve", "pieces", "start", "info"}``.
        Never raises and never half-applies: on failure the previously shown
        surface stays exactly as it was.
        """
        res: dict = {"ok": False, "error": "", "notes": [], "curve": None,
                     "pieces": [], "start": None, "info": ""}
        if spec.start_rule not in ss.START_RULES:
            res["error"] = ("Pick where s = 0 is (Start of arc length) — it is not "
                            "defaulted, because an arbitrary origin makes two runs "
                            "impossible to compare.")
            return res
        ctrl = getattr(self, "_ctrl", None)
        if spec.kind == ss.KIND_MESH or ctrl is None:
            if self._result is None:
                res["error"] = "No result loaded."
                return res
            if spec.kind != ss.KIND_MESH:
                res["error"] = (f"{ss.KIND_LABELS.get(spec.kind, spec.kind)} needs "
                                "the application controller (not available here).")
                return res
            out = {"curves": ss.mesh_boundary_curves(self._result), "error": "",
                   "notes": []}
        else:
            out = ctrl.build_surface(spec, self._result)
        res["notes"] = list(out.get("notes") or [])
        if out.get("error"):
            res["error"] = out["error"]
            return res
        pieces = out["curves"]
        chosen = ss.pick_curve(pieces, spec.loop)
        if chosen is None:
            res["error"] = "The selected source produced no usable curve."
            return res
        chosen = sm.orient_curve(chosen, spec.ccw)
        chosen, start = sm.rotate_to_start(chosen, spec.start_rule)
        res.update(ok=True, curve=chosen, pieces=pieces, start=start)
        res["info"] = (
            f"{spec.label()} — {len(chosen)} point(s), "
            f"perimeter {chosen.perimeter:.6g}, "
            f"{'closed' if chosen.closed else 'OPEN'}, "
            f"{'CCW' if spec.ccw else 'CW'}, s=0 @ ({start[0]:.6g}, {start[1]:.6g})"
            + (f", {len(pieces)} piece(s) found" if len(pieces) > 1 else ""))
        return res

    def apply_surface_spec(self, spec, show: bool = True) -> dict:
        """Build ``spec`` and, on success, make it the canvas's shown surface."""
        res = self.build_surface(spec)
        if not res["ok"]:
            return res
        self._surface_spec = spec
        self._surface_curve = res["curve"]
        self._surface_pieces = res["pieces"]
        self._surface_start = res["start"]
        self._surface_info = res["info"]
        if show:
            self._surface_on = True
            cb = getattr(self, "surface_cb", None)
            if cb is not None and not cb.isChecked():
                from app.utils import block_signals
                with block_signals(cb):
                    cb.setChecked(True)
        self.render()
        return res

    def _reset_surface_state(self):
        """Drop the extracted curve. The top-bar box is unticked with it: a ticked
        'Surface' with nothing to draw is the same lie as the STL3d 'Fit Δ' box
        left on over a cleared heatmap."""
        self._surface_curve = None
        self._surface_pieces = []
        self._surface_start = None
        self._surface_info = ""
        self._surface_on = False
        cb = getattr(self, "surface_cb", None)
        if cb is not None and cb.isChecked():
            from app.utils import block_signals
            with block_signals(cb):
                cb.setChecked(False)

    def clear_surface(self):
        self._reset_surface_state()
        self.render()

    def refresh_surface(self):
        """Re-extract the shown surface for a newly loaded mesh/field, keeping the
        user's spec. Does NOT render (the caller is mid-reload and will)."""
        spec = getattr(self, "_surface_spec", None)
        if (getattr(self, "_surface_curve", None) is None or spec is None
                or spec.start_rule not in ss.START_RULES):
            return
        res = self.build_surface(spec)
        if res["ok"]:
            self._surface_curve = res["curve"]
            self._surface_pieces = res["pieces"]
            self._surface_start = res["start"]
            self._surface_info = res["info"]
            return
        _log.warning("the shown surface could not be rebuilt for the new result: %s",
                     res["error"])
        self._surface_curve = None
        self._surface_pieces = []
        self._surface_start = None
        self._surface_info = f"surface dropped for this result — {res['error']}"

    def _on_surface_toggled(self, on: bool):
        """The top-bar 'Surface' box: show the chosen curve. With nothing chosen
        yet it opens the picker instead of silently doing nothing."""
        self._surface_on = bool(on)
        if on and self._surface_curve is None:
            self.open_surface_dialog()
            return
        self.render()

    # ------------------------------------------------------------------ #
    # Drawing
    # ------------------------------------------------------------------ #
    def _draw_surface_overlay(self):
        if not getattr(self, "_surface_on", False):
            return
        curve = getattr(self, "_surface_curve", None)
        if curve is None or len(curve) < 2:
            return
        # Other pieces first, dim: a multi-body extraction should show what was
        # found and NOT plotted, so a missing flap is visible rather than implied.
        for piece in getattr(self, "_surface_pieces", []) or []:
            if piece is curve or len(piece) < 2:
                continue
            p = self._closed_xy(piece)
            self.ax.plot(p[:, 0], p[:, 1], "-", color=_SURF_DIM, lw=0.9,
                         alpha=0.75, zorder=6)
        p = self._closed_xy(curve)
        self.ax.plot(p[:, 0], p[:, 1], "-", color=_SURF_COLOR, lw=1.6,
                     alpha=0.95, zorder=7)
        start = getattr(self, "_surface_start", None)
        if start is None or not np.isfinite(start[0]):
            return
        # s = 0 marker + a direction arrow a little way along the curve.
        self.ax.plot([start[0]], [start[1]], "o", ms=9, mfc="none",
                     mec=_SURF_COLOR, mew=2.0, zorder=8)
        self.ax.plot([start[0]], [start[1]], "o", ms=3.5, color=_SURF_COLOR,
                     zorder=8)
        self.ax.annotate("s=0", (start[0], start[1]), color=_SURF_COLOR,
                         fontsize=8, fontweight="bold", xytext=(7, 7),
                         textcoords="offset points", zorder=8)
        # The arrow spans a fixed FRACTION of the perimeter, not a fixed number of
        # points: a staircase iso-line packs its points a fraction of a cell apart,
        # so an index-based tip is invisible on exactly the curves whose traversal
        # direction is least obvious.
        s = sm.arc_length(curve.points, curve.closed, wrap=False)
        k = int(np.searchsorted(s, 0.08 * max(curve.perimeter, 1e-300)))
        k = min(max(k, 1), len(curve.points) - 1)
        tip = curve.points[k]
        if not np.allclose(tip, curve.points[0]):
            self.ax.annotate("", xy=(tip[0], tip[1]),
                             xytext=(curve.points[0][0], curve.points[0][1]),
                             arrowprops={"arrowstyle": "-|>,head_width=0.3,"
                                                       "head_length=0.7",
                                         "color": _SURF_COLOR, "lw": 2.2,
                                         "shrinkA": 7, "shrinkB": 0},
                             zorder=8)

    @staticmethod
    def _closed_xy(curve) -> np.ndarray:
        p = np.asarray(curve.points, dtype=float)
        return np.vstack([p, p[:1]]) if curve.closed and len(p) > 2 else p

    # ------------------------------------------------------------------ #
    # The plot
    # ------------------------------------------------------------------ #
    def plot_surface_series(self, spec) -> dict:
        """Sample the chosen surface and open the line-plot viewer.

        Y offers Cp (whenever the result can derive it), the active variable and
        raw p — the same set as before — plus x/y as alternative abscissae. The
        sample locations, the s = 0 coordinate and whether the values are exact
        or interpolated are all stated in the axis label / window title, because
        a Cp curve read off an interpolated, δ-offset iso-line is a different
        measurement from one read off mesh nodes.
        """
        from app.views.wall_qty_view import WallQuantityDialog
        res = self.apply_surface_spec(spec, show=True)
        if not res["ok"]:
            return res
        curve = res["curve"]
        avail = set(self._result.scalar_variables())
        wanted = [q for q in ("Cp", self._current_var(), "p") if q and q in avail]
        wanted = list(dict.fromkeys(wanted))
        cols: dict = {}
        sample_pts = None
        exact = True
        for q in wanted:
            try:
                s = sm.sample_on_curve(
                    curve, nodal_values=self._node_field(q),
                    interp=self._get_interp(q), offset=spec.offset,
                    flip=spec.flip_normal)
            except Exception:
                _log.warning("could not sample %s along the surface", q,
                             exc_info=True)
                continue
            cols[q] = s["values"]
            sample_pts = s["points"]
            exact = exact and s["exact"]
        if not cols:
            res["ok"] = False
            res["error"] = ("None of Cp / the active variable / p could be sampled "
                            "along this surface.")
            return res
        if sample_pts is None:
            sample_pts = np.asarray(curve.points, dtype=float)
        s_arr = sm.arc_length(sample_pts, curve.closed, wrap=True)
        cols["x"] = sample_pts[:, 0]
        cols["y"] = sample_pts[:, 1]
        s_arr, cols = sm.wrap_series(s_arr, cols, curve.closed)
        nan_frac = 0.0
        first = next(iter(cols.values()))
        if len(first):
            nan_frac = float(np.mean(~np.isfinite(np.asarray(first, dtype=float))))

        if self._surf_dialog is None:
            self._surf_dialog = WallQuantityDialog(self)
            from app.utils import keep_on_top, offset_popup
            keep_on_top(self._surf_dialog)
            offset_popup(self._surf_dialog, self.window())
        start = res["start"]
        how = "exact nodal" if exact else "interpolated"
        if spec.offset:
            how += f", δ={spec.offset:g} along the outward normal"
        xlabel = (f"s (arc length) — s=0 @ ({start[0]:.4g}, {start[1]:.4g}), "
                  f"{'CCW' if spec.ccw else 'CW'}")
        self._surf_dialog.plot_series(s_arr, cols, xlabel=xlabel)
        primary = next(iter(cols), "")
        self._surf_dialog.setWindowTitle(
            f"Surface {primary} vs arc length — {spec.label()} ({how})")
        self._surf_dialog.show()
        self._surf_dialog.raise_()
        self._surf_dialog.activateWindow()
        if nan_frac > 0:
            res["notes"].append(
                f"{nan_frac * 100:.0f}% of the samples fell outside the mesh and "
                "are plotted as gaps" + (" — reduce δ." if spec.offset else "."))
        res["notes"].append(f"Sampled {len(s_arr)} point(s); values are {how}.")
        return res
