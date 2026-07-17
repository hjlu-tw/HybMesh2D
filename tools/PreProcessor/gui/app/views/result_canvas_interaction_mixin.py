"""Interaction / overlay mixin for :class:`ResultCanvasView`.

Behaviour-preserving extraction from ``result_canvas.py`` (kept as a mixin so
methods reference ``self.*`` via the MRO, exactly like ``mesh_bl_mixin.py``).
This groups the Results post-processing interaction tools: probe (point query),
line probe, CAD-like scroll-zoom / drag-pan navigation, and the per-render
overlay drawers (probes, line, CAD geometry, extrema) plus the line-probe chart.
"""
from __future__ import annotations
import numpy as np
from PyQt6.QtCore import Qt

import matplotlib.tri as mtri


class ResultCanvasInteractionMixin:
    """Mouse interaction, view navigation and overlay drawing for the result
    canvas. Requires the host to define ``self.ax``, ``self.canvas``,
    ``self.nav``, ``self.var_combo``, ``self._triang``, ``self._result`` and the
    interaction/overlay state attributes set up in ``ResultCanvasView.__init__``.
    """

    # ------------------------------------------------------------------ #
    # Interaction: probe (point query) and line probe (plot over line)
    # ------------------------------------------------------------------ #
    def set_interact_mode(self, mode):
        """mode in (None, 'probe', 'line'). Switches mouse-click behaviour."""
        self._interact_mode = mode if mode in ("probe", "line") else None
        self._line_pts = []
        self.canvas.setCursor(
            Qt.CursorShape.CrossCursor if self._interact_mode
            else Qt.CursorShape.ArrowCursor)

    def _get_interp(self, var: str) -> mtri.LinearTriInterpolator:
        if var not in self._interp_cache:
            self._interp_cache[var] = mtri.LinearTriInterpolator(
                self._triang, self._node_field(var))
        return self._interp_cache[var]

    def _interp_all(self, x: float, y: float) -> dict:
        """Interpolate every scalar variable at (x, y); skip points outside mesh."""
        out: dict[str, float] = {}
        for var in self._result.scalar_variables():
            try:
                # Evaluate as a 1-element array and fill masked (outside-mesh)
                # points with nan, avoiding the masked->float conversion warning.
                res = self._get_interp(var)(np.array([x]), np.array([y]))
                v = float(np.asarray(np.ma.filled(res, np.nan))[0])
            except Exception:
                v = float("nan")
            out[var] = v
        return out

    def _sample_line(self, p0, p1, n: int, var: str):
        xs = np.linspace(p0[0], p1[0], n)
        ys = np.linspace(p0[1], p1[1], n)
        interp = self._get_interp(var)
        vals = np.asarray(interp(xs, ys).filled(np.nan))
        s = np.hypot(xs - p0[0], ys - p0[1])
        return s, vals, xs, ys

    def _on_click(self, event):
        # Only the left button drives the probe/line tools (right/middle = pan).
        if getattr(event, "button", 1) != 1:
            return
        if self._result is None or event.inaxes is not self.ax:
            return
        # Don't hijack clicks while the navigation toolbar is panning/zooming.
        if getattr(self.nav, "mode", ""):
            return
        x, y = event.xdata, event.ydata
        if x is None or y is None:
            return
        # #8: a click on a solver-probe marker reads its values (works in any
        # mode, so the user doesn't have to arm the probe tool first).
        if self._query_solver_probe(x, y):
            return
        if self._interact_mode is None:
            return
        if self._interact_mode == "probe":
            self.add_probe_at(x, y)
        elif self._interact_mode == "line":
            self._line_pts.append((x, y))
            if len(self._line_pts) >= 2:
                self.add_line_segment(self._line_pts[0], self._line_pts[1])
            else:
                self.render()

    def add_probe_at(self, x: float, y: float):
        """Add a probe at an exact coordinate (used by both click and the
        sidebar's numeric entry)."""
        if self._result is None:
            return
        vals = self._interp_all(x, y)
        self._probes.append({"x": float(x), "y": float(y), "vals": vals})
        self.probe_added.emit({"x": float(x), "y": float(y), "vals": vals})
        self.render()

    def add_line_segment(self, p0, p1):
        """Commit a line segment, sample the current variable, open the chart."""
        if self._result is None:
            return
        self._line_seg = (tuple(p0), tuple(p1))
        self._line_pts = []
        var = self._current_var()          # #9: honour a derived selection too
        s, vals, _, _ = self._sample_line(p0, p1, 200, var)
        self.line_sampled.emit({"var": var, "s": s.tolist(), "vals": vals.tolist(),
                                "p0": tuple(p0), "p1": tuple(p1)})
        self._open_line_plot()
        self.render()

    # ── CAD-like view navigation (scroll zoom + right/middle-drag pan) ──────
    def _on_scroll(self, event):
        if self._result is None or event.inaxes is not self.ax or event.xdata is None:
            return
        base = 1.2
        factor = 1.0 / base if event.button == "up" else base  # up = zoom in
        x0, x1 = self.ax.get_xlim(); y0, y1 = self.ax.get_ylim()
        xc, yc = event.xdata, event.ydata
        nx = (xc - (xc - x0) * factor, xc + (x1 - xc) * factor)
        ny = (yc - (yc - y0) * factor, yc + (y1 - yc) * factor)
        self.ax.set_xlim(nx); self.ax.set_ylim(ny)
        self._user_view = (nx, ny)
        self.canvas.draw_idle()

    def _on_pan_press(self, event):
        # CAD-consistent: left-drag pans when no probe/line tool is active; the
        # right/middle button always pans (so a tool stays usable while panning).
        left_nav = (event.button == 1 and self._interact_mode is None)
        if ((event.button in (2, 3) or left_nav) and self._result is not None
                and event.inaxes is self.ax and event.x is not None):
            bbox = self.ax.get_window_extent()
            x0, x1 = self.ax.get_xlim(); y0, y1 = self.ax.get_ylim()
            self._pan_start = (event.x, event.y, x0, x1, y0, y1,
                               (x1 - x0) / max(bbox.width, 1e-9),
                               (y1 - y0) / max(bbox.height, 1e-9))

    def _on_pan_move(self, event):
        if self._pan_start is None or event.x is None:
            return
        sx, sy, x0, x1, y0, y1, sxs, sys = self._pan_start
        dx = -(event.x - sx) * sxs
        dy = -(event.y - sy) * sys
        self.ax.set_xlim(x0 + dx, x1 + dx); self.ax.set_ylim(y0 + dy, y1 + dy)
        self._user_view = ((x0 + dx, x1 + dx), (y0 + dy, y1 + dy))
        self.canvas.draw_idle()

    def _on_pan_release(self, event):
        self._pan_start = None

    def reset_view(self):
        """Drop the preserved zoom/pan so the next render auto-fits the data."""
        self._user_view = None
        self.render()

    def clear_probes(self):
        self._probes = []
        self.render()

    def remove_last_probe(self):
        if self._probes:
            self._probes.pop()
            self.render()

    def clear_line(self):
        self._line_seg = None
        self._line_pts = []
        self.render()

    # ── Overlay drawers (re-run every render since ax is cleared) ──────────
    def _draw_probes(self):
        for i, p in enumerate(self._probes):
            self.ax.plot(p["x"], p["y"], "o", ms=6, mfc="#f87171", mec="white", mew=0.8)
            self.ax.annotate(f"P{i+1}", (p["x"], p["y"]), color="white", fontsize=8,
                             xytext=(4, 4), textcoords="offset points")

    # ── Solver probe points (#5) ────────────────────────────────────────────
    def set_solver_probe_points(self, pts):
        """Overlay the solver's probe-point locations on the result field (#5).
        ``pts`` is an iterable of (x, y). Persists across variable changes and
        result reloads (the points are physical, not tied to a field)."""
        out = []
        for p in (pts or []):
            try:
                out.append((float(p[0]), float(p[1])))
            except (TypeError, ValueError, IndexError):
                continue
        self._solver_probe_pts = out
        self.render()

    def clear_solver_probe_points(self):
        self._solver_probe_pts = []
        self.render()

    def _solver_probes_visible(self) -> bool:
        cb = getattr(self, "solverprobe_cb", None)
        return cb.isChecked() if cb is not None else True

    def _query_solver_probe(self, x: float, y: float) -> bool:
        """#8: if (x, y) is near a solver probe marker, query that probe's exact
        location (adds it to the probe table like a manual probe so its values
        show) and return True. No-op / False when probes are hidden or none is
        close enough."""
        pts = getattr(self, "_solver_probe_pts", [])
        if not pts or not self._solver_probes_visible():
            return False
        x0, x1 = self.ax.get_xlim()
        y0, y1 = self.ax.get_ylim()
        thr = 0.02 * max(abs(x1 - x0), abs(y1 - y0), 1e-9)
        best, best_d = None, thr
        for (px, py) in pts:
            d = ((px - x) ** 2 + (py - y) ** 2) ** 0.5
            if d <= best_d:
                best_d, best = d, (px, py)
        if best is None:
            return False
        self.add_probe_at(best[0], best[1])
        return True

    def _draw_solver_probes(self):
        if not self._solver_probes_visible():        # #8: checkbox toggle
            return
        for i, (x, y) in enumerate(getattr(self, "_solver_probe_pts", [])):
            self.ax.plot(x, y, "D", ms=7, mfc="#22d3ee", mec="#0b1020",
                         mew=0.9, zorder=6)
            self.ax.annotate(f"#{i+1}", (x, y), color="#22d3ee", fontsize=8,
                             xytext=(5, -9), textcoords="offset points", zorder=6)

    def _draw_line_overlay(self):
        if self._line_seg:
            (x0, y0), (x1, y1) = self._line_seg
            self.ax.plot([x0, x1], [y0, y1], "-", color="#fbbf24", lw=1.4)
            self.ax.plot([x0, x1], [y0, y1], "o", ms=4, color="#fbbf24")
        for pt in self._line_pts:  # partial (first click)
            self.ax.plot(pt[0], pt[1], "o", ms=4, color="#fbbf24")

    # ── CAD geometry overlay ────────────────────────────────────────────────
    def set_cad_geometry(self, polylines, on: bool):
        """Overlay raw CAD polyline pieces. `polylines` is a list of (N,2)
        arrays; short/empty pieces are dropped."""
        self._cad_polylines = [
            np.asarray(p, dtype=float) for p in (polylines or [])
            if p is not None and len(p) >= 2]
        self._cad_on = bool(on)
        self.render()

    def set_cad_color(self, color: str):
        """Set the CAD-overlay line colour (hex)."""
        if color:
            self._cad_color = color
            if self._cad_on:
                self.render()

    def _draw_cad_geometry(self):
        for p in self._cad_polylines:
            if p.ndim == 2 and p.shape[1] >= 2:
                self.ax.plot(p[:, 0], p[:, 1], color=self._cad_color, lw=1.3,
                             alpha=0.9, zorder=5)

    def _draw_extrema(self):
        for e in self._extrema:
            marker = "v" if e["which"] == "min" else "^"
            color = "#38bdf8" if e["which"] == "min" else "#f43f5e"
            self.ax.plot(e["x"], e["y"], marker, ms=10, mfc=color, mec="white", mew=0.8)
            self.ax.annotate(f"{e['which']} {e['value']:.3g}", (e["x"], e["y"]),
                             color="white", fontsize=8, xytext=(5, 5),
                             textcoords="offset points")

    def _open_line_plot(self):
        """Open/refresh the line-probe chart with a variable selector. The chart
        re-samples the committed segment for whatever variable the user picks."""
        from app.views.wall_qty_view import WallQuantityDialog
        if self._line_seg is None:
            return
        if self._line_dialog is None:
            self._line_dialog = WallQuantityDialog(self)
            self._line_dialog.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)  # (#2/#8)
        seg = self._line_seg

        def sampler(var: str):
            s, vals, _, _ = self._sample_line(seg[0], seg[1], 200, var)
            return np.asarray(s), np.asarray(vals)

        self._line_dialog.plot_over_line(
            self._result.scalar_variables(), sampler, self._current_var())
        self._line_dialog.show()
        self._line_dialog.raise_()
        self._line_dialog.activateWindow()
