from __future__ import annotations
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QCheckBox, QLabel,
    QPushButton,
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
from app.views.result_canvas_interaction_mixin import ResultCanvasInteractionMixin
from app.views.result_canvas_plots_mixin import ResultCanvasPlotsMixin
from app.views.result_canvas_vector_mixin import ResultCanvasVectorMixin
from app.views.result_canvas_controls_mixin import ResultCanvasControlsMixin
from app.views.result_canvas_setup_mixin import ResultCanvasSetupMixin
from app.views.result_canvas_surface_mixin import ResultCanvasSurfaceMixin
from app.views.result_playback_mixin import ResultPlaybackMixin
from app.services.surface_source import SurfaceSpec

from app.services.logging_setup import get_logger

_log = get_logger(__name__)

_BG = "#0c0d16"
_FG = "#a0a8c0"
_COMBO_QSS = (
    "QComboBox{background:#181b30;color:#dde2ff;border:1px solid #2d3356;"
    "border-radius:4px;padding:2px 6px;font-size:11px;min-width:90px;}")
_COLORMAPS = ["turbo", "viridis", "inferno", "plasma", "coolwarm", "jet", "RdBu_r"]


class ResultCanvasView(ResultCanvasInteractionMixin, ResultCanvasPlotsMixin,
                       ResultCanvasSurfaceMixin,
                       ResultCanvasVectorMixin, ResultCanvasControlsMixin,
                       ResultPlaybackMixin, ResultCanvasSetupMixin, QWidget):
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
        # Auto/Custom is one global MODE (one checkbox, one meaning); the manual
        # NUMBERS belong to ONE variable each, exactly as the playback lock's
        # range does (`_range_lock_var`). An unkeyed tuple here is what coloured
        # vorticity with a pressure range — issue #24.
        self._clim_auto = True
        self._clim_by_var: dict[str, tuple[float, float]] = {}

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
        self._solver_probe_pts: list[tuple] = []  # solver probe-file locations (#5)
        self._vec_target = 40
        self._vec_scale = 1.0
        self._stream_density = 1.2
        self._stream_lw_speed = True
        self._interp_cache: dict[str, mtri.LinearTriInterpolator] = {}
        self._init_playback()

        # CAD geometry overlay: raw polyline pieces (list of (N,2) arrays) from
        # the open project segments, drawn over the field each render.
        self._cad_polylines: list = []
        self._cad_on = False
        self._cad_color = "#e5e7eb"

        # Surface source (what "the surface" of a surface plot is). The spec is
        # the user's CHOICE and survives result reloads; the extracted curve does
        # not, because it belongs to one mesh. `_ctrl` is set by the Results panel's
        # bind() and provides the non-mesh sources (STL3d φ, analytic φ, CAD).
        self._ctrl = None
        self._surface_spec = SurfaceSpec()
        self._surface_curve = None
        self._surface_pieces: list = []
        self._surface_start = None
        self._surface_info = ""
        self._surface_on = False

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Control bar (three rows so nothing crowds: data selectors, then
        #    file / view actions, then display toggles) ─────────────────────
        bar = QWidget()
        bar.setStyleSheet("background: #06070d; border-bottom: 1px solid #1c1e36;")
        bar_v = QVBoxLayout(bar)
        bar_v.setContentsMargins(8, 4, 8, 4)
        bar_v.setSpacing(4)
        hl = QHBoxLayout(); hl.setSpacing(6)      # row 1: data selectors
        hl2 = QHBoxLayout(); hl2.setSpacing(6)    # row 2: file / view actions
        hl3 = QHBoxLayout(); hl3.setSpacing(6)    # row 3: display toggles
        for _row in (hl, hl2, hl3):
            bar_v.addLayout(_row)

        # Row 1: load + the variable selectors + zone / render mode.
        self.load_btn = QPushButton("Load Result")
        self.load_btn.setStyleSheet(
            "QPushButton{background:#1d2a3a;color:#dde2ff;border:1px solid #2d3356;"
            "border-radius:4px;padding:3px 10px;font-weight:bold;font-size:11px;}"
            "QPushButton:hover{border-color:#5a9ad4;}")
        hl.addWidget(self.load_btn)

        # #5: TWO-LEVEL variable picker. First pick the KIND in `kind_combo`
        # (raw solver field vs derived post-processing quantity); `var_combo`
        # then lists ONLY that kind's variables. Only ONE variable list is ever
        # on screen, so the raw and derived groups no longer crowd the bar
        # together. The Kind selector hides itself when there are no derived
        # quantities (nothing to switch to).
        self._base_vars: list[str] = []
        self._derived_vars: list[str] = []
        self.kind_label = QLabel("Show:")
        self.kind_label.setStyleSheet(f"color:{_FG};font-size:11px;")
        self.kind_combo = QComboBox(); self.kind_combo.setStyleSheet(_COMBO_QSS)
        self.kind_combo.addItems(["Variable", "Derived"])
        self.kind_combo.setToolTip(
            "Which group the selector lists: raw solver fields (Variable) or "
            "post-processing quantities derived from them (Derived: Cp, |V|, "
            "entropy, total p/T).")
        self.var_combo = QComboBox(); self.var_combo.setStyleSheet(_COMBO_QSS)
        self.zone_combo = QComboBox(); self.zone_combo.setStyleSheet(_COMBO_QSS)
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Filled (cells)", "Smooth contour"])
        self.mode_combo.setStyleSheet(_COMBO_QSS)
        # Colormap moved to the left sidebar (Color Scale); kept here as state.
        self._cmap = _COLORMAPS[0]

        hl.addWidget(self.kind_label); hl.addWidget(self.kind_combo)
        hl.addWidget(self.var_combo)
        for lbl, w in [("Zone:", self.zone_combo), ("Mode:", self.mode_combo)]:
            t = QLabel(lbl); t.setStyleSheet(f"color:{_FG};font-size:11px;")
            hl.addWidget(t); hl.addWidget(w)
        hl.addStretch()

        # Row 1b: transient playback transport. A steady run has one zone and
        # nothing to animate, so the whole group hides itself until a result with
        # several frames is loaded (see _update_playback_ui).
        self._build_playback_bar(bar_v)

        # Row 2: file / view actions.
        self.wallqty_btn = QPushButton("Wall Qty…")
        self.wallqty_btn.setStyleSheet(self.load_btn.styleSheet())
        self.wallqty_btn.setToolTip(
            "Open the wall-quantity line plot (WallForce.dat, vsurface_qty.dat, …)")
        hl2.addWidget(self.wallqty_btn)
        # #11/#8: plot surface quantities (Cp, p, …) along the perimeter. Which
        # curve counts as "the surface" is a choice (mesh boundary / φ iso-line /
        # Fit Δ interface cells / analytic φ / CAD), so the button opens the picker.
        self.surface_btn = QPushButton("Surface…")
        self.surface_btn.setStyleSheet(self.load_btn.styleSheet())
        self.surface_btn.setToolTip(
            "Define the surface (mesh boundary, φ iso-line, Fit Δ interface cells, "
            "analytic φ shape or CAD geometry) and plot Cp / p / the active "
            "variable along it vs arc length.")
        hl2.addWidget(self.surface_btn)
        # #4: the solver's RECORDED probe time-history (probe_data.gui), i.e. the
        # actual values it logged at each probe over the run.
        self.probehist_btn = QPushButton("Probe History…")
        self.probehist_btn.setStyleSheet(self.load_btn.styleSheet())
        self.probehist_btn.setToolTip(
            "Plot the solver's recorded probe time-history (probe_data.gui) vs "
            "iteration — the values logged at each probe point during the run.")
        hl2.addWidget(self.probehist_btn)
        self.fit_btn = QPushButton("Fit View")
        self.fit_btn.setStyleSheet(self.load_btn.styleSheet())
        self.fit_btn.setToolTip("Fit the view to the full result extent")
        hl2.addWidget(self.fit_btn)
        self.clear_btn = QPushButton("Clear")
        self.clear_btn.setStyleSheet(self.load_btn.styleSheet())
        hl2.addWidget(self.clear_btn)
        self.save_btn = QPushButton("Save PNG")
        self.save_btn.setStyleSheet(self.load_btn.styleSheet())
        hl2.addWidget(self.save_btn)
        hl2.addStretch()

        # Row 3: display toggles.
        self.contour_cb = QCheckBox("Contour")
        self.contour_cb.setChecked(True)
        self.contour_cb.setToolTip(
            "Show the filled/contoured scalar field. Turn off to view the "
            "geometry overlay on its own.")
        self.mesh_cb = QCheckBox("Mesh")
        self.stream_cb = QCheckBox("Streamlines")
        self.vector_cb = QCheckBox("Vectors")
        self.iso_cb = QCheckBox("Iso")      # iso-line visibility (levels set in sidebar)
        self.iso_cb.setToolTip("Show iso-contour lines (levels set in the left panel)")
        # The defined surface + its s=0 marker. Ticking it with nothing defined
        # opens the picker rather than doing nothing visible.
        self.surface_cb = QCheckBox("Surface")
        self.surface_cb.setToolTip(
            "Show the defined surface curve on the field, with the arc-length "
            "origin (s=0) and traversal direction marked. Define it in Surface….")
        # #8: toggle the solver probe-point markers, and click one to read its
        # values (added to the probe table like a manual probe).
        self.solverprobe_cb = QCheckBox("Solver probes")
        self.solverprobe_cb.setChecked(True)
        self.solverprobe_cb.setToolTip(
            "Show the solver's probe-point markers. Click a marker to read its "
            "field values (they appear in the probe table on the left).")
        for cb in (self.contour_cb, self.mesh_cb, self.stream_cb, self.vector_cb,
                   self.iso_cb, self.surface_cb, self.solverprobe_cb):
            cb.setStyleSheet(f"color:{_FG};font-size:11px;")
            hl3.addWidget(cb)
        hl3.addStretch()
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
        self.kind_combo.currentIndexChanged.connect(self._on_var_kind_changed)
        self.var_combo.currentIndexChanged.connect(self._on_control_changed)
        self.mode_combo.currentIndexChanged.connect(self._on_control_changed)
        self.contour_cb.toggled.connect(self._on_control_changed)
        self.mesh_cb.toggled.connect(self._on_control_changed)
        self.stream_cb.toggled.connect(self._on_control_changed)
        self.vector_cb.toggled.connect(self._on_control_changed)
        self.iso_cb.toggled.connect(self._on_iso_toggled)
        self.surface_cb.toggled.connect(self._on_surface_toggled)
        self.solverprobe_cb.toggled.connect(lambda _=None: self.render())
        self.zone_combo.currentIndexChanged.connect(self._on_zone_changed)
        self.save_btn.clicked.connect(self._save_png)
        self.fit_btn.clicked.connect(self.reset_view)
        self.clear_btn.clicked.connect(self.clear)
        self.wallqty_btn.clicked.connect(self._open_wall_qty)
        self.surface_btn.clicked.connect(self.open_surface_dialog)
        self.probehist_btn.clicked.connect(self._open_probe_history)
        self._wall_dialog = None
        self._surf_dialog = None
        self._surf_src_dialog = None
        self._hist_dialog = None
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


    # ------------------------------------------------------------------ #
    # Public API (driven by postprocess_ctrl in Phase 3.2)
    # ------------------------------------------------------------------ #


    # ------------------------------------------------------------------ #


    def render(self):
        if self._result is None or self._triang is None:
            return
        var = self._current_var()
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
                _log.debug("could not remove the previous colorbar", exc_info=True)
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
            # Auto = the frame on screen (dmin/dmax). A transient run whose
            # "Lock scale" box is ticked uses the range pinned across ALL its
            # frames instead (playback_clim), so colours mean the same thing in
            # every frame; a manual range still wins over both.
            locked = self.playback_clim()
            manual = self.manual_clim(var)
            # First render of this variable in Custom mode: seed it from its OWN
            # data range and remember that, rather than inheriting the numbers of
            # whatever was displayed before. Remembering is what keeps playback
            # from re-seeding (and so drifting) every frame. The flag travels in
            # the signal because a seeded range is one the user did NOT type, so
            # a panel showing their numbers has to be refreshed.
            seeded = not self._clim_auto and manual is None
            if seeded:
                manual = self.remember_clim(var, dmin, dmax)
            if manual is not None:
                vmin, vmax = manual
            elif locked is not None:
                vmin, vmax = locked
            else:
                vmin, vmax = dmin, dmax
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

            # The field flood + colorbar are optional (top-bar 'Contour'); when
            # off, only the overlays (mesh, iso, CAD geometry) draw, but the
            # field stats below are still computed and emitted.
            if self.contour_cb.isChecked():
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
                "vmin": vmin, "vmax": vmax, "clim_seeded": seeded})

            # Explicit iso-value contour lines (e.g. M=1 sonic line) over the field.
            if self._iso_on and self._iso_levels:
                node_vals = self._node_field(var)
                lv = sorted(set(float(l) for l in self._iso_levels))
                try:
                    cs = self.ax.tricontour(self._triang, node_vals, levels=lv,
                                            colors="#f8fafc", linewidths=0.9)
                    self.ax.clabel(cs, fontsize=7, fmt="%g", colors="#f8fafc")
                except Exception:
                    _log.warning(
                        "iso-line contouring failed; the requested iso-lines are NOT "
                        "drawn", exc_info=True)

            if self.mesh_cb.isChecked():
                self.ax.triplot(self._triang, color="#5a607a", lw=0.2, alpha=0.5)
            if self.stream_cb.isChecked():
                self._draw_streamlines()
            if self.vector_cb.isChecked():
                self._draw_vectors()

            # CAD geometry overlay (independent of the displayed field).
            if self._cad_on:
                self._draw_cad_geometry()
            # The defined surface + its s=0 origin, above the CAD outline (they
            # can coincide, and which one the plot used has to be the visible one).
            self._draw_surface_overlay()

            self._draw_probes()
            self._draw_solver_probes()
            self._draw_line_overlay()
            self._draw_extrema()

            # Title names the frame for a transient run: every zone the solver
            # writes carries the same title ("time 0"), so the position in the
            # file is the only thing that tells two frames apart.
            if self._frame_count() > 1:
                subtitle = self._series.frame_label(self._frame)
            else:
                subtitle = r.zone.title if r.zone else ""
            self.ax.set_title(f"{var}  —  {subtitle}", color=_FG, fontsize=10)
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


    # ------------------------------------------------------------------ #
    # Wave 2/3 API: iso lines, color norm, extrema, vector/stream params, stats
    # ------------------------------------------------------------------ #
