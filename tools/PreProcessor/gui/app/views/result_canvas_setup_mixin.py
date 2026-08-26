from __future__ import annotations
import os

import numpy as np

import matplotlib
matplotlib.use("QtAgg")
import matplotlib.tri as mtri

from app.models.result_data import TecplotResult
from app.services.logging_setup import get_logger
from app.services.result_legs import LegSeries, ResultLeg, list_result_legs
from app.services.restart_points import OTHER
from app.utils import block_signals, confirm

_log = get_logger(__name__)

_BG = "#0c0d16"
_FG = "#a0a8c0"
_COMBO_QSS = (
    "QComboBox{background:#181b30;color:#dde2ff;border:1px solid #2d3356;"
    "border-radius:4px;padding:2px 6px;font-size:11px;min-width:90px;}")
_COLORMAPS = ["turbo", "viridis", "inferno", "plasma", "coolwarm", "jet", "RdBu_r"]


class ResultCanvasSetupMixin:
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

    def load_result_path(self, path: str, zone: int = -1,
                         ask_legs: bool = True):
        """Populate the zone selector from the result, then load the chosen frame.

        ``ask_legs`` is what lets a caller that must not open a modal — a
        pipeline or batch run driving the auto-load at the end of a solve —
        suppress the "open the whole restarted solve?" question. The DECISION
        stays here (a view owns its prompts); only the permission to ask is the
        caller's.
        """
        self._result_path = path
        # A manual colour range is view state for the result that is loaded, so a
        # new file starts clean rather than colouring a new run with the previous
        # one's numbers. Frames of ONE run go through set_result, which keeps it.
        self.reset_clim_store()
        # Index the files first: the series owns the frame cache the playback
        # transport steps through, and the zone list comes from the same indices.
        legs = self._resolve_legs(path, ask_legs)
        self._attach_series(legs.paths, legs.labels)
        n = self._series.n_frames if self._series is not None else 0
        k = (n - 1 if zone < 0 else max(0, min(n - 1, zone))) if n else 0
        self._building = True
        try:
            self.zone_combo.clear()
            # One item per frame OF THE SERIES, labelled by the series so the
            # selector and the frame read-out say the same thing — including which
            # leg of a restarted solve a frame belongs to. The item DATA is the
            # global frame number, which is what ``_on_zone_changed`` shows.
            for i in range(n):
                self.zone_combo.addItem(self._series.frame_label(i), i)
            if n:
                self.zone_combo.setCurrentIndex(k)
        finally:
            self._building = False
        if n:
            self._frame = k
            self.set_result(self._series.frame(k))
            self._update_playback_ui()
        else:
            self.set_result(TecplotResult.from_file(path, zone=zone))

    # ------------------------------------------------------------------ #
    def _resolve_legs(self, path: str, ask: bool) -> LegSeries:
        """Which files this load covers: only ``path``, or every leg of the solve.

        **Ask, do not assume** (#32). A restarted solve's result is several files
        and playing them as one animation is what the user usually wants, but
        opening one leg on its own stays a normal thing to do — so the whole
        series is offered and declining loads exactly the file that was asked
        for. Declining yields a ONE-leg series rather than a different code path,
        so the frame cache, the labels and the ranges work the same way either
        way.

        **Not asking means No**, never "yes on their behalf": a caller that
        cannot put up a modal cannot consent for the user, and one file is what
        every caller got before #32 — the same reason
        :meth:`_confirm_open_legs` answers No when headless.
        """
        found = list_result_legs(path)
        if len(found) < 2:
            return found
        if not (ask and self._confirm_open_legs(found, path)):
            i = found.index_of(path)
            leg = (found.legs[i] if i >= 0
                   else ResultLeg(kind=OTHER, key="", path=path))
            self._log(f"[Results] opened only {os.path.basename(path)}; this "
                      f"solve has {len(found)} legs (open it again and answer "
                      "Yes to play them as one animation).")
            return LegSeries(legs=(leg,))
        for msg in found.warnings:
            self._log(msg)
        self._log(f"[Results] playing {len(found)} legs of this solve as one "
                  f"series: {', '.join(found.labels)}.")
        return found

    def _confirm_open_legs(self, found: LegSeries, path: str) -> bool:
        """Offer the whole restarted solve. Headless answers No.

        No, because that is what every caller did before this existed: a batch or
        CI run asked for one file and must keep getting one file, and the same
        answer is the conservative one for a prompt nobody can see.
        """
        rows = "\n".join(
            f"{leg.key or os.path.basename(leg.path)}: "
            f"{os.path.basename(leg.path)}"
            + ("" if not leg.span.known
               else f"  (to iteration {leg.span.end})")
            for leg in found.legs)
        return confirm(
            self, "Open the whole restarted solve?",
            f"This solve is split across {len(found)} result files — it was "
            f"restarted {len(found) - 1} time(s), and each leg's output was "
            "archived beside it.\n\n"
            "Play them all as one animation?\n\n"
            f"No: open only '{os.path.basename(path)}'.",
            detail="Legs, oldest solution first:\n" + rows,
            headless_default=False)

    def set_result(self, result: TecplotResult):
        # Frames of one transient run share their mesh, so stepping/playing must
        # not rebuild the triangulation (the expensive part) or throw away the
        # probes, line and extrema the user pinned — those mark GEOMETRY, which
        # did not move. Field caches are always dropped: the values did change.
        same_mesh = (
            self._result is not None
            and self._triang is not None
            and result.nodes.shape == self._result.nodes.shape
            and result.elements.shape == self._result.elements.shape
            and np.array_equal(result.elements, self._result.elements)
            and np.array_equal(result.nodes, self._result.nodes))
        self._result = result
        if not same_mesh:
            self._triang = mtri.Triangulation(
                result.nodes[:, 0], result.nodes[:, 1], result.elements)
        self._node_cache: dict[str, np.ndarray] = {}
        self._interp_cache = {}
        if not same_mesh:
            # Probes/line/extrema reference the previous mesh; drop them on reload.
            self._probes = []
            self._line_pts = []
            self._line_seg = None
            self._extrema = []
            # The surface SPEC is the user's choice and survives; the extracted
            # curve belongs to the old mesh/field, so it is rebuilt from the spec
            # (and reported as dropped if the new result cannot produce it).
            self.refresh_surface()
        # Preserve the current zoom/pan across reloads and zone switches (no
        # auto-fit). The first-ever load has no saved view, so it still fits;
        # 'Fit View' or Clear re-fits on demand.

        self._building = True
        try:
            prev = self._current_var()
            self._populate_var_combo(result)
            if prev:
                self.select_variable(prev)
        finally:
            self._building = False
        self.render()

    def clear(self):
        """Clear the loaded result and reset to the empty placeholder."""
        self._detach_series()
        self.reset_clim_store()
        self._building = True
        try:
            self._result = None
            self._triang = None
            self.var_combo.clear()
            self._base_vars = []
            self._derived_vars = []
            self.zone_combo.clear()
        finally:
            self._building = False
        self._interp_cache = {}
        self._probes = []
        self._line_pts = []
        self._line_seg = None
        self._extrema = []
        self._cad_polylines = []
        self._cad_on = False
        self._reset_surface_state()
        self._user_view = None   # Clear re-fits the next load
        if self._cbar is not None:
            try:
                self._cbar.remove()
            except Exception:
                _log.debug(
                    "could not remove the colorbar while "
                    "clearing", exc_info=True)
            self._cbar = None
        self._empty_message("No result loaded.")

    def select_variable(self, code: str) -> bool:
        """Select ``code`` (#5): switch the Kind selector to whichever group owns
        it, repopulate, then select it in ``var_combo``."""
        if code in self._derived_vars:
            target_kind = 1
        elif code in self._base_vars:
            target_kind = 0
        else:
            target_kind = self.kind_combo.currentIndex()   # unknown: search live list
        if self.kind_combo.currentIndex() != target_kind:
            with block_signals(self.kind_combo):
                self.kind_combo.setCurrentIndex(target_kind)
            self._fill_var_combo_for_kind()
        idx = self.var_combo.findData(code)
        if idx < 0:
            idx = self.var_combo.findText(code)
        if idx >= 0:
            with block_signals(self.var_combo):
                self.var_combo.setCurrentIndex(idx)
            return True
        return False

    def _current_var(self) -> str:
        """The active variable CODE (item data), falling back to its text."""
        data = self.var_combo.currentData()
        return data if data else self.var_combo.currentText()
