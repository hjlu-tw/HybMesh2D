from __future__ import annotations
import os

import numpy as np

import matplotlib
matplotlib.use("QtAgg")
import matplotlib.tri as mtri

from app.models.result_data import TecplotResult
from app.services.logging_setup import get_logger
from app.services.result_legs import LegSeries, ResultLeg, list_result_legs
from app.views.result_leg_picker import ask_legs
from app.services.restart_points import OTHER
from app.utils import block_signals

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

    def load_result_path(self, path: str, frame: int = -1):
        """Populate the frame selector from the result, then show a frame.

        ``frame`` is a SERIES-wide frame index, not a zone within ``path`` — it
        was named ``zone`` while a load covered one file, and #32 made a load
        cover the legs of a whole solve without renaming it. Negative means "the
        landing frame", which is the last frame of the leg that was opened.
        """
        self._result_path = path
        # A manual colour range is view state for the result that is loaded, so a
        # new file starts clean rather than colouring a new run with the previous
        # one's numbers. Frames of ONE run go through set_result, which keeps it.
        self.reset_clim_store()
        # Never persisted, and off for every load: "This leg only" is an escape
        # the user asks for, not a preference the view carries between results.
        box = getattr(self, "one_leg_cb", None)
        if box is not None:
            with block_signals(box):
                box.setChecked(False)
        # A leg SUBSET is view state for the result being loaded, exactly like the
        # clim store above: a new solve must not inherit the previous one's ticks.
        # The prompt is armed for this load only — it is asked once per LOAD, not
        # once per rebuild, or every "This leg only" toggle would re-ask it.
        self._leg_selection = None
        self._ask_legs_pending = True
        self.reload_legs(frame)

    def reload_legs(self, frame: int = -1):
        """(Re)build the series for ``self._result_path`` and show ``frame``.

        Separate from :meth:`load_result_path` because "This leg only" rebuilds
        the series without being a new load: the clim store, the checkbox and the
        result path all survive a toggle.
        """
        path = self._result_path
        # Index the files first: the series owns the frame cache the playback
        # transport steps through, and the frame list comes from the same indices.
        legs = self._resolve_legs(path)
        self._attach_series(legs.paths, legs.labels)
        n = self._series.n_frames if self._series is not None else 0
        k = (self._landing_frame(path) if frame < 0
             else max(0, min(n - 1, frame))) if n else 0
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
            # No series at all (an unreadable index): fall back to the file's own
            # last zone. Deliberately NOT ``frame`` — that is a series index and
            # this path has no series to index into.
            self.set_result(TecplotResult.from_file(path))

    def _landing_frame(self, path: str) -> int:
        """The last frame of the leg that was OPENED, or of the series.

        The two differ only when an archived leg was named deliberately, and in
        that case the file the user asked for is the one they should be looking at
        — not the newest leg of the solve it happens to belong to (#43). It is
        also where a "This leg only" toggle lands, so the control moves the
        surrounding animation rather than the picture in front of them.
        """
        return self._series.last_frame_of(path)

    # ------------------------------------------------------------------ #
    def _resolve_legs(self, path: str) -> LegSeries:
        """Which files this load covers: every leg of the solve, or just ``path``.

        **Opening any leg opens the solve, and nothing is asked** (#43). #32 put a
        modal on every result load and a permission flag on the entry point so a
        pipeline could suppress it; that made the common case cost a click and
        made an unattended run behave differently from an interactive one for no
        reason either could see. "This leg only" is the escape, and it is a
        control the user can see and reverse rather than a question they have to
        answer before the picture appears.

        Restricting yields a ONE-leg series rather than a different code path, so
        the frame cache, the labels and the ranges work the same way either way.
        """
        found = list_result_legs(path)
        self._legs = found
        if len(found) < 2:
            return found
        if getattr(self, "_ask_legs_pending", False):
            self._ask_legs_pending = False
            # USER-REQUESTED (2026-08-27), reversing half of #43 — see
            # ``views/result_leg_picker`` for which half and why the rest of #43's
            # reasoning still holds. Headless returns None without showing
            # anything, so an unattended run is byte-for-byte what it was.
            self._leg_selection = ask_legs(self, found.legs, path,
                                           found.warnings)
        if self._one_leg_only():
            i = found.index_of(path)
            leg = (found.legs[i] if i >= 0
                   else ResultLeg(kind=OTHER, key="", path=path))
            self._log(f"[Results] playing only {os.path.basename(path)}; this "
                      f"solve has {len(found)} legs (untick 'This leg only' to "
                      "play them as one animation).")
            return LegSeries(legs=(leg,))
        chosen = getattr(self, "_leg_selection", None)
        if chosen is not None:
            # A SUBSET is still a LegSeries, not a second code path — the frame
            # cache, the labels, the global ranges and the warnings all behave
            # the way they do for the whole solve. Same rule as "This leg only".
            kept = tuple(leg for leg in found.legs if leg.key in chosen)
            if kept and len(kept) < len(found.legs):
                dropped = [leg.key for leg in found.legs
                           if leg.key not in chosen]
                names = ", ".join(leg.key for leg in kept)
                self._log(f"[Results] playing {len(kept)} of this solve's "
                          f"{len(found.legs)} legs: {names} "
                          f"(left out: {', '.join(dropped)}).")
                return LegSeries(legs=kept, warnings=found.warnings)
        # One summary line, then every warning in full: each of them changes how
        # the picture should be read, so none of them is folded into the summary.
        self._log(f"[Results] playing {len(found)} legs of this solve as one "
                  f"series: {', '.join(found.labels)}.")
        for msg in found.warnings:
            self._log(msg)
        return found

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
