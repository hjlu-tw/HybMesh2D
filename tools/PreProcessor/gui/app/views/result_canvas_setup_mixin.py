from __future__ import annotations
import numpy as np

import matplotlib
matplotlib.use("QtAgg")
import matplotlib.tri as mtri

from app.models.result_data import TecplotResult

from app.services.logging_setup import get_logger
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

    def load_result_path(self, path: str, zone: int = -1):
        """Populate the zone selector from the file, then load the chosen zone."""
        self._result_path = path
        # Index the file first: the series owns the frame cache the playback
        # transport steps through, and the zone list comes from the same index.
        self._attach_series(path)
        self._building = True
        try:
            zones = TecplotResult.list_zones(path)
            self.zone_combo.clear()
            # A transient run labels every zone "time 0", so the position is the
            # only thing distinguishing them; show the title only when the file
            # actually gives its zones different ones.
            distinct = len({z.title for z in zones}) > 1
            for z in zones:
                label = (f"{z.index + 1}: {z.title}" if distinct
                         else f"Frame {z.index + 1}")
                self.zone_combo.addItem(label, z.index)
            if zones:
                self.zone_combo.setCurrentIndex(len(zones) - 1 if zone < 0 else zone)
        finally:
            self._building = False
        k = len(zones) - 1 if zone < 0 else zone
        if self._series is not None and 0 <= k < self._series.n_frames:
            self._frame = k
            self.set_result(self._series.frame(k))
            self._update_playback_ui()
        else:
            self.set_result(TecplotResult.from_file(path, zone=zone))

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
