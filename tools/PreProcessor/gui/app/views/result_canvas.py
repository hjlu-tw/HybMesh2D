from __future__ import annotations
import os
import numpy as np
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QCheckBox, QLabel,
    QPushButton, QFileDialog,
)

import matplotlib
matplotlib.use("QtAgg")
from matplotlib.backends.backend_qtagg import (
    FigureCanvasQTAgg, NavigationToolbar2QT,
)
from matplotlib.figure import Figure
import matplotlib.tri as mtri
import matplotlib.colors as mcolors

from app.models.result_data import TecplotResult

_BG = "#0c0d16"
_FG = "#a0a8c0"
_COMBO_QSS = (
    "QComboBox{background:#181b30;color:#dde2ff;border:1px solid #2d3356;"
    "border-radius:4px;padding:2px 6px;font-size:11px;min-width:90px;}")
_COLORMAPS = ["turbo", "viridis", "inferno", "plasma", "coolwarm", "jet", "RdBu_r"]


class ResultCanvasView(QWidget):
    """Matplotlib-embedded 2D result viewer.

    Renders a cell-centered scalar field as a filled contour (tripcolor) or a
    smooth contour (tricontourf on node-averaged data), with optional mesh
    wireframe, velocity streamlines and vector glyphs. Streamlines use
    TecplotResult.cell_to_node + LinearTriInterpolator sampled onto a regular
    grid, then matplotlib streamplot (R6).
    """

    # Emitted after each render with the field's data range and applied clim,
    # so a control panel can show stats / sync its color-scale inputs.
    result_rendered = pyqtSignal(dict)
    probe_added = pyqtSignal(dict)     # {"x","y","vals":{var:val}}
    line_sampled = pyqtSignal(dict)    # {"var","s":[...],"vals":[...],"p0","p1"}
    extrema_found = pyqtSignal(dict)   # {"which","var","x","y","value"}

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background: {_BG};")
        self._result: TecplotResult | None = None
        self._triang: mtri.Triangulation | None = None
        self._building = False  # guard against re-entrant renders during setup
        self._clim_auto = True
        self._clim: tuple[float, float] | None = None

        # Interaction / overlay state (Results post-processing tools).
        self._interact_mode = None        # None / "probe" / "line"
        self._probes: list[dict] = []     # pinned point queries
        self._line_pts: list[tuple] = []  # clicks accumulating a line segment
        self._line_seg = None             # committed (p0, p1)
        self._iso_levels: list[float] = []
        self._iso_on = False
        self._log_scale = False
        self._symmetric = False
        self._level_mode = "smooth"  # "smooth" (continuous) / "count" / "delta"
        self._n_levels = 24          # bands when mode == "count"
        self._level_delta = 0.0      # band spacing when mode == "delta"
        self._extrema: list[dict] = []    # marked min/max points
        self._vec_target = 40
        self._vec_scale = 1.0
        self._stream_density = 1.2
        self._stream_lw_speed = True
        self._interp_cache: dict[str, mtri.LinearTriInterpolator] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Control bar ────────────────────────────────────────────────────
        bar = QWidget()
        bar.setStyleSheet("background: #06070d; border-bottom: 1px solid #1c1e36;")
        hl = QHBoxLayout(bar)
        hl.setContentsMargins(8, 4, 8, 4)
        hl.setSpacing(6)

        self.load_btn = QPushButton("Load Result")
        self.load_btn.setStyleSheet(
            "QPushButton{background:#1d2a3a;color:#dde2ff;border:1px solid #2d3356;"
            "border-radius:4px;padding:3px 10px;font-weight:bold;font-size:11px;}"
            "QPushButton:hover{border-color:#5a9ad4;}")
        hl.addWidget(self.load_btn)

        self.var_combo = QComboBox(); self.var_combo.setStyleSheet(_COMBO_QSS)
        self.zone_combo = QComboBox(); self.zone_combo.setStyleSheet(_COMBO_QSS)
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Filled (cells)", "Smooth contour"])
        self.mode_combo.setStyleSheet(_COMBO_QSS)
        # Colormap moved to the left sidebar (Color Scale); kept here as state.
        self._cmap = _COLORMAPS[0]

        for lbl, w in [("Var:", self.var_combo), ("Zone:", self.zone_combo),
                       ("Mode:", self.mode_combo)]:
            t = QLabel(lbl); t.setStyleSheet(f"color:{_FG};font-size:11px;")
            hl.addWidget(t); hl.addWidget(w)

        self.mesh_cb = QCheckBox("Mesh")
        self.stream_cb = QCheckBox("Streamlines")
        self.vector_cb = QCheckBox("Vectors")
        self.iso_cb = QCheckBox("Iso")      # iso-line visibility (levels set in sidebar)
        self.iso_cb.setToolTip("Show iso-contour lines (levels set in the left panel)")
        for cb in (self.mesh_cb, self.stream_cb, self.vector_cb, self.iso_cb):
            cb.setStyleSheet(f"color:{_FG};font-size:11px;")
            hl.addWidget(cb)

        hl.addStretch()
        self.wallqty_btn = QPushButton("Wall Qty…")
        self.wallqty_btn.setStyleSheet(self.load_btn.styleSheet())
        self.wallqty_btn.setToolTip(
            "Open the wall-quantity line plot (WallForce.dat, vsurface_qty.dat, …)")
        hl.addWidget(self.wallqty_btn)
        self.clear_btn = QPushButton("Clear")
        self.clear_btn.setStyleSheet(self.load_btn.styleSheet())
        hl.addWidget(self.clear_btn)
        self.save_btn = QPushButton("Save PNG")
        self.save_btn.setStyleSheet(self.load_btn.styleSheet())
        hl.addWidget(self.save_btn)
        root.addWidget(bar)

        # ── Matplotlib figure ──────────────────────────────────────────────
        # Fixed axes rectangles (NOT tight_layout / colorbar(ax=...), which
        # progressively shrink the main axes on every re-render).
        self._AX_RECT = [0.08, 0.08, 0.80, 0.86]
        self._CAX_RECT = [0.90, 0.08, 0.025, 0.86]
        self.figure = Figure(facecolor=_BG)
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.ax = self.figure.add_axes(self._AX_RECT)  # persistent, fixed position
        self._cbar = None
        self.nav = NavigationToolbar2QT(self.canvas, self)
        self.nav.setStyleSheet(f"background:{_BG};color:{_FG};")
        root.addWidget(self.nav)
        root.addWidget(self.canvas, stretch=1)

        self._style_axes()
        self._empty_message("No result loaded.")

        # Signals
        self.var_combo.currentIndexChanged.connect(self._on_control_changed)
        self.mode_combo.currentIndexChanged.connect(self._on_control_changed)
        self.mesh_cb.toggled.connect(self._on_control_changed)
        self.stream_cb.toggled.connect(self._on_control_changed)
        self.vector_cb.toggled.connect(self._on_control_changed)
        self.iso_cb.toggled.connect(self._on_iso_toggled)
        self.zone_combo.currentIndexChanged.connect(self._on_zone_changed)
        self.save_btn.clicked.connect(self._save_png)
        self.clear_btn.clicked.connect(self.clear)
        self.wallqty_btn.clicked.connect(self._open_wall_qty)
        self._wall_dialog = None
        self._line_dialog = None
        # CAD-like view interaction: scroll = zoom about cursor, right/middle
        # drag = pan. Left click stays reserved for probe/line tools.
        self._user_view = None      # (xlim, ylim) preserved across re-renders
        self._pan_start = None      # (event.x, event.y, xlim, ylim) during a pan drag
        self.canvas.mpl_connect("button_press_event", self._on_click)
        self.canvas.mpl_connect("scroll_event", self._on_scroll)
        self.canvas.mpl_connect("button_press_event", self._on_pan_press)
        self.canvas.mpl_connect("motion_notify_event", self._on_pan_move)
        self.canvas.mpl_connect("button_release_event", self._on_pan_release)

    # ------------------------------------------------------------------ #
    def _style_axes(self):
        self.ax.set_facecolor(_BG)
        for spine in self.ax.spines.values():
            spine.set_color("#2c2e43")
        self.ax.tick_params(colors=_FG, labelsize=8)
        # 'datalim' keeps the axes box at its fixed rect (adjusting data limits
        # to preserve aspect) so the plot area never shrinks between renders;
        # 'box' would resize the box per render.
        self.ax.set_aspect("equal", adjustable="datalim")

    def _empty_message(self, text: str):
        self.ax.clear()
        self._style_axes()
        self.ax.text(0.5, 0.5, text, color="#4a4e69", ha="center", va="center",
                     transform=self.ax.transAxes, fontsize=12)
        self.canvas.draw_idle()

    # ------------------------------------------------------------------ #
    # Public API (driven by postprocess_ctrl in Phase 3.2)
    # ------------------------------------------------------------------ #
    def list_zones(self, path: str):
        return TecplotResult.list_zones(path)

    def load_result_path(self, path: str, zone: int = -1):
        """Populate the zone selector from the file, then load the chosen zone."""
        self._building = True
        try:
            zones = TecplotResult.list_zones(path)
            self._result_path = path
            self.zone_combo.clear()
            for z in zones:
                self.zone_combo.addItem(f"{z.index}: {z.title}", z.index)
            if zones:
                self.zone_combo.setCurrentIndex(len(zones) - 1 if zone < 0 else zone)
        finally:
            self._building = False
        self.set_result(TecplotResult.from_file(path, zone=zone))

    def set_result(self, result: TecplotResult):
        self._result = result
        self._triang = mtri.Triangulation(
            result.nodes[:, 0], result.nodes[:, 1], result.elements)
        self._node_cache: dict[str, np.ndarray] = {}
        self._interp_cache = {}
        # Probes/line/extrema reference the previous mesh; drop them on reload.
        self._probes = []
        self._line_pts = []
        self._line_seg = None
        self._extrema = []
        self._user_view = None   # new mesh -> auto-fit

        self._building = True
        try:
            prev = self.var_combo.currentText()
            self.var_combo.clear()
            self.var_combo.addItems(result.scalar_variables())
            if prev and prev in result.scalar_variables():
                self.var_combo.setCurrentText(prev)
        finally:
            self._building = False
        self.render()

    def clear(self):
        """Clear the loaded result and reset to the empty placeholder."""
        self._building = True
        try:
            self._result = None
            self._triang = None
            self.var_combo.clear()
            self.zone_combo.clear()
        finally:
            self._building = False
        self._interp_cache = {}
        self._probes = []
        self._line_pts = []
        self._line_seg = None
        self._extrema = []
        self._user_view = None
        if self._cbar is not None:
            try:
                self._cbar.remove()
            except Exception:
                pass
            self._cbar = None
        self._empty_message("No result loaded.")

    def set_clim_auto(self, auto: bool):
        """Auto color scale = use the field's data min/max each render."""
        self._clim_auto = bool(auto)
        self.render()

    def set_clim(self, vmin: float, vmax: float):
        """Set a manual color-scale range and switch off auto."""
        self._clim_auto = False
        self._clim = (float(vmin), float(vmax))
        self.render()

    # ------------------------------------------------------------------ #
    def _node_field(self, var: str) -> np.ndarray:
        if var not in self._node_cache:
            self._node_cache[var] = self._result.cell_to_node(var)
        return self._node_cache[var]

    def _on_zone_changed(self):
        if self._building or self._result is None:
            return
        path = getattr(self, "_result_path", "")
        if path:
            z = self.zone_combo.currentData()
            self.set_result(TecplotResult.from_file(path, zone=z if z is not None else -1))

    def _on_control_changed(self):
        if not self._building:
            self.render()

    def render(self):
        if self._result is None or self._triang is None:
            return
        var = self.var_combo.currentText()
        if not var:
            return
        cmap = self._cmap
        r = self._result

        # Clear only the main axes contents; its position is fixed and it is
        # never removed, so the plot area can't shrink between renders. The old
        # colorbar (and its axes) is removed and a fresh colorbar axes is created
        # at a fixed rect each render.
        self.ax.clear()
        if self._cbar is not None:
            try:
                self._cbar.remove()  # also removes its colorbar axes
            except Exception:
                pass
            self._cbar = None
        self._style_axes()

        try:
            # Determine the field array and its true data range, then the color
            # limits (auto = data range, else the user-set clim).
            if self.mode_combo.currentText().startswith("Filled"):
                vals = r.get_cell_field(var)
            else:
                vals = self._node_field(var)
            import numpy as _np
            finite = vals[_np.isfinite(vals)]
            dmin = float(finite.min()) if finite.size else 0.0
            dmax = float(finite.max()) if finite.size else 1.0
            mean = float(finite.mean()) if finite.size else 0.0
            if self._clim_auto or self._clim is None:
                vmin, vmax = dmin, dmax
            else:
                vmin, vmax = self._clim
            # Symmetric scale (about zero) is useful for signed fields (vorticity,
            # pressure coefficient); applied before the flat-field widening.
            if self._symmetric:
                a = max(abs(vmin), abs(vmax)) or 0.5
                vmin, vmax = -a, a
            if vmin == vmax:  # flat field -> widen slightly so the colormap shows
                vmin, vmax = vmin - 0.5, vmax + 0.5

            # Log color scale (residual/pressure spanning orders of magnitude).
            # Requires strictly positive limits; fall back to linear otherwise.
            norm = None
            use_log = self._log_scale and not self._symmetric
            if use_log:
                pos = finite[finite > 0]
                lo = float(pos.min()) if pos.size else 0.0
                if lo > 0 and vmax > lo:
                    vmin = max(vmin, lo) if vmin > 0 else lo
                    norm = mcolors.LogNorm(vmin=vmin, vmax=vmax)
                else:
                    use_log = False  # non-positive data -> cannot log-scale

            # Contour level boundaries (N bands => N+1 boundaries). "smooth" uses a
            # high count for a near-continuous gradient; "count"/"delta" are the
            # Tecplot-style banded modes.
            mode = self._level_mode
            nb = max(2, int(self._n_levels)) if mode == "count" else 64
            if mode == "delta" and self._level_delta > 0 and not use_log:
                levels = _np.arange(vmin, vmax + self._level_delta * 0.5, self._level_delta)
                if levels.size < 2:
                    levels = _np.linspace(vmin, vmax, 2)
            elif use_log:
                levels = _np.logspace(_np.log10(vmin), _np.log10(vmax), nb + 1)
            else:
                levels = _np.linspace(vmin, vmax, nb + 1)
            # Discrete banding only in the explicit count/delta modes (smooth and
            # log stay continuous).
            banded = (mode in ("count", "delta")) and not use_log

            if self.mode_combo.currentText().startswith("Filled"):
                if use_log:
                    mappable = self.ax.tripcolor(
                        self._triang, facecolors=vals, cmap=cmap, shading="flat", norm=norm)
                elif banded:
                    bnorm = mcolors.BoundaryNorm(levels, matplotlib.colormaps[cmap].N)
                    mappable = self.ax.tripcolor(
                        self._triang, facecolors=vals, cmap=cmap, shading="flat", norm=bnorm)
                else:  # smooth, continuous flood (original default)
                    mappable = self.ax.tripcolor(
                        self._triang, facecolors=vals, cmap=cmap, shading="flat",
                        vmin=vmin, vmax=vmax)
            else:
                mappable = self.ax.tricontourf(
                    self._triang, vals, levels=levels, cmap=cmap,
                    norm=norm, extend="both")

            cax = self.figure.add_axes(self._CAX_RECT)
            self._cbar = self.figure.colorbar(mappable, cax=cax)
            self._cbar.ax.tick_params(colors=_FG, labelsize=8)
            self._cbar.set_label(var, color=_FG)
            self.result_rendered.emit({
                "var": var, "dmin": dmin, "dmax": dmax, "mean": mean,
                "vmin": vmin, "vmax": vmax})

            # Explicit iso-value contour lines (e.g. M=1 sonic line) over the field.
            if self._iso_on and self._iso_levels:
                node_vals = self._node_field(var)
                lv = sorted(set(float(l) for l in self._iso_levels))
                try:
                    cs = self.ax.tricontour(self._triang, node_vals, levels=lv,
                                            colors="#f8fafc", linewidths=0.9)
                    self.ax.clabel(cs, fontsize=7, fmt="%g", colors="#f8fafc")
                except Exception:
                    pass

            if self.mesh_cb.isChecked():
                self.ax.triplot(self._triang, color="#5a607a", lw=0.2, alpha=0.5)
            if self.stream_cb.isChecked():
                self._draw_streamlines()
            if self.vector_cb.isChecked():
                self._draw_vectors()

            self._draw_probes()
            self._draw_line_overlay()
            self._draw_extrema()

            self.ax.set_title(
                f"{var}  —  {r.zone.title if r.zone else ''}", color=_FG, fontsize=10)
            # Preserve the user's zoom/pan across re-renders (variable/overlay
            # changes); set_result clears it so a new mesh auto-fits.
            if self._user_view is not None:
                self.ax.set_xlim(self._user_view[0])
                self.ax.set_ylim(self._user_view[1])
        except Exception as e:  # pragma: no cover - defensive against bad data
            self._empty_message(f"Render error: {e}")
            return

        self.canvas.draw_idle()

    # ------------------------------------------------------------------ #
    def _velocity_nodes(self):
        """Return (u_node, v_node) or None if no velocity variables present."""
        # Velocity components are named differently across solver outputs;
        # match common pairs case-insensitively rather than only literal "u"/"v".
        lower = {n.lower(): n for n in self._result.variables}
        for ux, vy in (("u", "v"), ("vx", "vy"), ("u-velocity", "v-velocity"),
                       ("x-velocity", "y-velocity"), ("velocity-x", "velocity-y"),
                       ("velocityx", "velocityy")):
            if ux in lower and vy in lower:
                return self._node_field(lower[ux]), self._node_field(lower[vy])
        return None

    def _stream_grid(self, n: int = 220):
        x, y = self._result.nodes[:, 0], self._result.nodes[:, 1]
        x0, x1, y0, y1 = x.min(), x.max(), y.min(), y.max()
        ar = (y1 - y0) / (x1 - x0) if x1 > x0 else 1.0
        nx, ny = n, max(8, int(n * ar))
        gx = np.linspace(x0, x1, nx)
        gy = np.linspace(y0, y1, ny)
        return np.meshgrid(gx, gy)

    def _draw_streamlines(self):
        vel = self._velocity_nodes()
        if vel is None:
            return
        u_node, v_node = vel
        iu = mtri.LinearTriInterpolator(self._triang, u_node)
        iv = mtri.LinearTriInterpolator(self._triang, v_node)
        gx, gy = self._stream_grid()
        # Masked (outside triangulation / holes) -> 0 so streamplot stays finite.
        U = np.asarray(iu(gx, gy).filled(0.0))
        V = np.asarray(iv(gx, gy).filled(0.0))
        speed = np.hypot(U, V)
        lw = (0.5 + 1.5 * (speed / (speed.max() + 1e-30))
              if self._stream_lw_speed else 0.8)
        self.ax.streamplot(gx, gy, U, V, color="#e2e8f0", density=self._stream_density,
                           linewidth=lw, arrowsize=0.7)

    def _draw_vectors(self):
        vel = self._velocity_nodes()
        if vel is None:
            return
        u_node, v_node = vel
        x, y = self._result.nodes[:, 0], self._result.nodes[:, 1]
        target = max(4, int(self._vec_target))
        step = max(1, x.size // (target * target))
        # scale_units/xy with a user scale: larger _vec_scale -> longer arrows.
        self.ax.quiver(x[::step], y[::step],
                       u_node[::step] * self._vec_scale, v_node[::step] * self._vec_scale,
                       color="#dde2ff", scale_units="xy", angles="xy", width=0.0025)

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
        if (self._interact_mode is None or self._result is None
                or event.inaxes is not self.ax):
            return
        # Don't hijack clicks while the navigation toolbar is panning/zooming.
        if getattr(self.nav, "mode", ""):
            return
        x, y = event.xdata, event.ydata
        if x is None or y is None:
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
        var = self.var_combo.currentText()
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

    def _draw_line_overlay(self):
        if self._line_seg:
            (x0, y0), (x1, y1) = self._line_seg
            self.ax.plot([x0, x1], [y0, y1], "-", color="#fbbf24", lw=1.4)
            self.ax.plot([x0, x1], [y0, y1], "o", ms=4, color="#fbbf24")
        for pt in self._line_pts:  # partial (first click)
            self.ax.plot(pt[0], pt[1], "o", ms=4, color="#fbbf24")

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
        seg = self._line_seg

        def sampler(var: str):
            s, vals, _, _ = self._sample_line(seg[0], seg[1], 200, var)
            return np.asarray(s), np.asarray(vals)

        self._line_dialog.plot_over_line(
            self._result.scalar_variables(), sampler, self.var_combo.currentText())
        self._line_dialog.show()
        self._line_dialog.raise_()
        self._line_dialog.activateWindow()

    # ------------------------------------------------------------------ #
    # Wave 2/3 API: iso lines, color norm, extrema, vector/stream params, stats
    # ------------------------------------------------------------------ #
    def set_cmap(self, name: str):
        self._cmap = name
        self.render()

    def set_iso(self, levels: list, on: bool):
        """Set iso levels from the sidebar; syncs the top-bar 'Iso' checkbox."""
        self._iso_levels = list(levels)
        self._iso_on = bool(on)
        self.iso_cb.blockSignals(True)
        self.iso_cb.setChecked(self._iso_on)
        self.iso_cb.blockSignals(False)
        self.render()

    def _on_iso_toggled(self, on: bool):
        self._iso_on = bool(on)
        self.render()

    def set_color_norm(self, log: bool, symmetric: bool):
        self._log_scale = bool(log)
        self._symmetric = bool(symmetric)
        self.render()

    def set_levels(self, mode: str, n_levels: int = None, delta: float = None):
        """Contour level mode: 'smooth' (continuous), 'count' (band count) or
        'delta' (fixed band spacing)."""
        if mode in ("smooth", "count", "delta"):
            self._level_mode = mode
        if n_levels is not None:
            self._n_levels = max(2, int(n_levels))
        if delta is not None:
            self._level_delta = max(0.0, float(delta))
        self.render()

    def set_vector_params(self, target: int, scale: float):
        self._vec_target = int(target)
        self._vec_scale = float(scale)
        if self.vector_cb.isChecked():
            self.render()

    def set_stream_params(self, density: float, lw_by_speed: bool):
        self._stream_density = float(density)
        self._stream_lw_speed = bool(lw_by_speed)
        if self.stream_cb.isChecked():
            self.render()

    def mark_extrema(self, which: str):
        """Mark the min and/or max of the current field's nodal values."""
        if self._result is None:
            return
        var = self.var_combo.currentText()
        if not var:
            return
        node_vals = self._node_field(var)
        finite = np.isfinite(node_vals)
        if not finite.any():
            return
        x, y = self._result.nodes[:, 0], self._result.nodes[:, 1]
        self._extrema = []
        wants = ("min", "max") if which == "both" else (which,)
        for w in wants:
            idx = (np.where(finite, node_vals, np.inf).argmin() if w == "min"
                   else np.where(finite, node_vals, -np.inf).argmax())
            e = {"which": w, "var": var, "x": float(x[idx]),
                 "y": float(y[idx]), "value": float(node_vals[idx])}
            self._extrema.append(e)
            self.extrema_found.emit(e)
        self.render()

    def clear_extrema(self):
        self._extrema = []
        self.render()

    def integral_stats(self, var: str | None = None) -> dict:
        """Area-weighted integral / mean / std / min / max of the current field."""
        if self._result is None:
            return {}
        var = var or self.var_combo.currentText()
        if not var:
            return {}
        cell = np.asarray(self._result.get_cell_field(var), dtype=float)
        n = self._result.nodes
        tri = self._result.elements
        # Triangle areas via the cross product of two edges.
        x = n[:, 0][tri]; y = n[:, 1][tri]
        area = 0.5 * np.abs((x[:, 1] - x[:, 0]) * (y[:, 2] - y[:, 0])
                            - (x[:, 2] - x[:, 0]) * (y[:, 1] - y[:, 0]))
        m = np.isfinite(cell) & np.isfinite(area)
        cell, area = cell[m], area[m]
        tot_area = float(area.sum())
        if tot_area <= 0 or cell.size == 0:
            return {}
        integral = float((cell * area).sum())
        wmean = integral / tot_area
        var_w = float((area * (cell - wmean) ** 2).sum() / tot_area)
        return {"var": var, "integral": integral, "area": tot_area,
                "mean": wmean, "std": var_w ** 0.5,
                "min": float(cell.min()), "max": float(cell.max())}

    # ------------------------------------------------------------------ #
    def _open_wall_qty(self):
        """Open the wall-quantity line plot, pre-pointed at the current result's
        directory and auto-loading a known wall file if one sits beside it."""
        from app.views.wall_qty_view import WallQuantityDialog
        if self._wall_dialog is None:
            self._wall_dialog = WallQuantityDialog(self)
        dlg = self._wall_dialog
        result_dir = os.path.dirname(getattr(self, "_result_path", "") or "")
        dlg._last_dir = result_dir
        if result_dir:
            for name in ("vsurface_qty.dat", "WallForce.dat", "tWall_values.dat"):
                cand = os.path.join(result_dir, name)
                if os.path.exists(cand):
                    dlg.load_path(cand)
                    break
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()

    def _save_png(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Plot", "", "PNG (*.png);;PDF (*.pdf);;All Files (*)")
        if path:
            self.figure.savefig(path, dpi=200, facecolor=_BG)
