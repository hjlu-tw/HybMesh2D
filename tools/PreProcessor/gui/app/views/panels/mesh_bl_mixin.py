"""Boundary-layer store + pop-up dialog wiring for MeshConfigPanel, split out
as a mixin (behaviour unchanged). Holds the global-BL widget read/write bridge,
the per-geometry / per-segment BL & BC dialog launchers, and
_apply_global_bl_to_cfg. Expects the host (MeshConfigPanel) to provide the bl_*
widgets, geom_list_widget, _global_bl, _group_bc, _ROLE_DATA, the edit_* buttons
and the panel signals (segment_highlight_requested, mesh_config_changed)."""
from __future__ import annotations
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog
from app.views.panels.mesh_dialogs import (
    PerGeomBLDialog, SegmentBCDialog,
    _BL_OVERRIDE_KEYS, _BL_INT_ATTRS, _BL_BOOL_ATTRS,
)
from app.models.mesh_config import MeshConfig


class MeshConfigBLMixin:
    """BL widget bridge + per-geometry/segment BL & BC dialog launchers."""

    def _wire_bl_widgets(self):
        """Connect every BL-section widget's change signal to _on_bl_widget_changed."""
        for w in (self.bl_initial_thickness, self.bl_growth_rate, self.bl_layers,
                  self.bl_fan_nodes, self.bl_fan_angle_threshold,
                  self.bl_convex_angle_threshold, self.bl_para_fallback_angle,
                  self.bl_concave_angle_threshold, self.bl_concave_influence_multiplier,
                  self.bl_junction_angle_c1, self.bl_junction_angle_c2,
                  self.bl_junction_angle_c3,
                  self.bl_transition_layers, self.bl_transition_growth_rate,
                  self.bl_transition_buffer):
            w.valueChanged.connect(self._on_bl_widget_changed)
        for w in (self.bl_convex_method, self.bl_concave_method,
                  self.bl_junction_method,
                  self.bl_auto_transition_layers):
            w.currentIndexChanged.connect(self._on_bl_widget_changed)
        for w in (self.bl_auto_fan_nodes, self.bl_use_analytic_geom):
            w.toggled.connect(self._on_bl_widget_changed)

    def _read_bl_widgets(self) -> dict:
        """Current BL-section widget values as a {KEY: value} dict (KEYs match
        _BL_OVERRIDE_KEYS / the .dat parameter names)."""
        # The C++ 4-case junction binning assumes C1 <= C2 <= C3, but the three
        # spinboxes range 0-360 independently. Sort them so an out-of-order entry
        # (e.g. C1=300, C2=100) can't silently misclassify the flow-facing angle.
        jc1, jc2, jc3 = sorted((self.bl_junction_angle_c1.value(),
                                self.bl_junction_angle_c2.value(),
                                self.bl_junction_angle_c3.value()))
        return {
            "BL_INITIAL_THICKNESS": self.bl_initial_thickness.value(),
            "BL_GROWTH_RATE": self.bl_growth_rate.value(),
            "BL_LAYERS": self.bl_layers.value(),
            "BL_CONVEX_METHOD": [0, 2][self.bl_convex_method.currentIndex()],
            "BL_FAN_NODES": self.bl_fan_nodes.value(),
            "BL_AUTO_FAN_NODES": 1 if self.bl_auto_fan_nodes.isChecked() else 0,
            "BL_FAN_ANGLE_THRESHOLD": self.bl_fan_angle_threshold.value(),
            "BL_CONVEX_ANGLE_THRESHOLD": self.bl_convex_angle_threshold.value(),
            "BL_PARA_FALLBACK_ANGLE": self.bl_para_fallback_angle.value(),
            "BL_CONCAVE_METHOD": [5][self.bl_concave_method.currentIndex()],
            "BL_CONCAVE_ANGLE_THRESHOLD": self.bl_concave_angle_threshold.value(),
            "BL_CONCAVE_INFLUENCE_MULTIPLIER": self.bl_concave_influence_multiplier.value(),
            "BL_JUNCTION_METHOD": [0, 1][self.bl_junction_method.currentIndex()],
            "BL_JUNCTION_ANGLE_C1": jc1,
            "BL_JUNCTION_ANGLE_C2": jc2,
            "BL_JUNCTION_ANGLE_C3": jc3,
            "BL_TRANSITION_LAYERS": self.bl_transition_layers.value(),
            "BL_AUTO_TRANSITION_LAYERS": self.bl_auto_transition_layers.currentIndex(),
            "BL_TRANSITION_GROWTH_RATE": self.bl_transition_growth_rate.value(),
            "BL_TRANSITION_BUFFER": self.bl_transition_buffer.value(),
            "BL_USE_ANALYTIC_GEOM": 1 if self.bl_use_analytic_geom.isChecked() else 0,
        }

    def _write_bl_widgets(self, d: dict):
        """Set the BL-section widgets from a {KEY: value} dict (missing keys keep
        their current value). Guarded so it doesn't re-enter _on_bl_widget_changed."""
        self._bl_updating = True
        try:
            g = dict(self._read_bl_widgets())
            g.update({k: v for k, v in (d or {}).items() if v is not None})
            self.bl_initial_thickness.setValue(float(g["BL_INITIAL_THICKNESS"]))
            self.bl_growth_rate.setValue(float(g["BL_GROWTH_RATE"]))
            self.bl_layers.setValue(int(round(float(g["BL_LAYERS"]))))
            cm = int(round(float(g["BL_CONVEX_METHOD"])))
            self.bl_convex_method.setCurrentIndex([0, 2].index(cm) if cm in (0, 2) else 1)
            self.bl_fan_nodes.setValue(int(round(float(g["BL_FAN_NODES"]))))
            self.bl_auto_fan_nodes.setChecked(bool(float(g["BL_AUTO_FAN_NODES"])))
            self.bl_fan_angle_threshold.setValue(float(g["BL_FAN_ANGLE_THRESHOLD"]))
            self.bl_convex_angle_threshold.setValue(float(g["BL_CONVEX_ANGLE_THRESHOLD"]))
            self.bl_para_fallback_angle.setValue(float(g["BL_PARA_FALLBACK_ANGLE"]))
            self.bl_concave_method.setCurrentIndex(0)  # combo only offers method 5
            self.bl_concave_angle_threshold.setValue(float(g["BL_CONCAVE_ANGLE_THRESHOLD"]))
            self.bl_concave_influence_multiplier.setValue(float(g["BL_CONCAVE_INFLUENCE_MULTIPLIER"]))
            jm = int(round(float(g["BL_JUNCTION_METHOD"])))
            self.bl_junction_method.setCurrentIndex(jm if jm in (0, 1) else 1)
            self.bl_junction_angle_c1.setValue(float(g["BL_JUNCTION_ANGLE_C1"]))
            self.bl_junction_angle_c2.setValue(float(g["BL_JUNCTION_ANGLE_C2"]))
            self.bl_junction_angle_c3.setValue(float(g["BL_JUNCTION_ANGLE_C3"]))
            self.bl_transition_layers.setValue(int(round(float(g["BL_TRANSITION_LAYERS"]))))
            ati = int(round(float(g["BL_AUTO_TRANSITION_LAYERS"])))
            self.bl_auto_transition_layers.setCurrentIndex(ati if 0 <= ati <= 2 else 0)
            self.bl_transition_growth_rate.setValue(float(g["BL_TRANSITION_GROWTH_RATE"]))
            self.bl_transition_buffer.setValue(float(g["BL_TRANSITION_BUFFER"]))
            self.bl_use_analytic_geom.setChecked(bool(float(g["BL_USE_ANALYTIC_GEOM"])))
        finally:
            self._bl_updating = False

    def _on_bl_widget_changed(self, *args):
        """A BL-section edit updates the GLOBAL boundary layer. Per-geometry
        overrides are edited in the pop-up dialog, not these sections."""
        if self._bl_updating:
            return
        self._global_bl = self._read_bl_widgets()

    def _sync_bl_scope(self):
        """Enable the per-geometry BL / segment-BC dialog buttons for the
        selected geometry. The panel's BL sections always edit the GLOBAL
        default (never swapped)."""
        item = self.geom_list_widget.currentItem()
        idx = self.geom_role_combo.currentIndex() if self.geom_role_combo.isEnabled() else -1
        grows_bl = idx in (0, 4)
        self._bl_target_item = None
        self.edit_bl_btn.setEnabled(grows_bl and item is not None)

        # Per-segment BC button: enabled when a non-seed geometry has a
        # segmented .meta sidecar (exported from CAD with segments).
        seg_ok = False
        if item is not None and idx != 2:
            path = item.data(Qt.ItemDataRole.UserRole)
            if path:
                from app.services.meta_io import read_meta_segments
                segs = read_meta_segments(path)
                seg_ok = len(segs) > 0
        self.edit_seg_bc_btn.setEnabled(seg_ok)

    def _segment_highlighter(self, path):
        """Build a canvas-highlight callback for a geometry's segments: maps each
        seg id to its points (from the .meta POINTS block) and emits them (NaN-
        separated) on segment_highlight_requested. Shared by the segment BC / BL
        pop-ups. Returns the callback."""
        from app.services.meta_io import read_meta_point_segids
        coords_by_sid: dict[int, object] = {}
        try:
            import numpy as np
            pts = np.atleast_2d(np.loadtxt(path))[:, :2]
            sids = read_meta_point_segids(path)
            n = pts.shape[0]
            if n and len(sids) == n:
                # Median boundary step, for the closed-loop wrap sanity check below.
                if n >= 2:
                    d = np.hypot(*(pts[1:] - pts[:-1]).T)
                    med = float(np.median(d[d > 0])) if np.any(d > 0) else 0.0
                else:
                    med = 0.0
                for sid in {s for s in sids if s >= 0}:
                    idxs = [i for i, s in enumerate(sids) if s == sid]
                    if not idxs:
                        continue
                    run = pts[idxs]
                    # The resampler gives each shared CORNER to the segment that
                    # STARTS there, so a segment's own points stop one short of its
                    # END vertex — the highlight would miss its last little stretch.
                    # Append the next boundary point (cyclic) so the whole edge
                    # lights up; guard the wrap by distance so an OPEN geometry's
                    # last segment doesn't draw a long spurious closing line.
                    nxt = max(idxs) + 1
                    if nxt >= n:
                        nxt = 0
                    if nxt not in idxs:
                        step = float(np.hypot(*(pts[nxt] - pts[max(idxs)])))
                        if med <= 0 or step <= 3.0 * med:
                            run = np.vstack([run, pts[nxt]])
                    coords_by_sid[sid] = run
        except Exception:
            coords_by_sid = {}

        def _hl(sel_sids):
            if not sel_sids:
                self.segment_highlight_requested.emit(None)
                return
            import numpy as np
            parts = []
            for s in sel_sids:
                c = coords_by_sid.get(s)
                if c is None or len(c) == 0:
                    continue
                if parts:
                    parts.append(np.array([[np.nan, np.nan]]))
                parts.append(np.asarray(c, dtype=float))
            self.segment_highlight_requested.emit(
                np.vstack(parts) if parts else None)
        return _hl

    def _open_segment_bc_dialog(self):
        """Pop up the per-group BC-type editor for the selected geometry. #4: the
        CAD group NAME is kept (never overwritten); the chosen BC type is stored
        in the per-group map (round-tripped via MeshConfig.group_bc) and used to
        pre-seed the Solver BC table. Does not modify the .meta name column."""
        item = self.geom_list_widget.currentItem()
        if item is None:
            return
        path = item.data(Qt.ItemDataRole.UserRole)
        if not path:
            return
        from app.services.meta_io import read_meta_segments
        segs = read_meta_segments(path)
        if not segs:
            return

        dlg = SegmentBCDialog(item.text(), segs, group_bc=self._group_bc,
                              highlight_cb=self._segment_highlighter(path), parent=self)
        from app.utils import offset_popup
        offset_popup(dlg, self.window())
        accepted = dlg.exec() == QDialog.DialogCode.Accepted
        self.segment_highlight_requested.emit(None)  # clear the highlight
        if accepted:
            self._group_bc = dlg.result_group_bc()
            # #4: persist auto-created patch names for ungrouped segments that
            # got a BC, so they group in the .meta and reach the mesher/solver.
            seg_names = dlg.result_seg_names()
            from app.services.meta_io import write_meta_segbc, write_meta_group_bc
            if seg_names:
                write_meta_segbc(path, seg_names)
            # Persist THIS geometry's label->BC-type map into its .meta so the
            # mapping survives a session reset / config reload (else the labels
            # resolve to nothing and every boundary defaults to wall at mesh time).
            labels = {b for _sid, b, _k in segs if b} | set(seg_names.values())
            write_meta_group_bc(path, {lbl: self._group_bc[lbl]
                                       for lbl in labels if self._group_bc.get(lbl)})
            self.mesh_config_changed.emit(self.get_config())

    def _show_bl_dialog_modeless(self, dlg, on_accept, on_finish=None):
        """Show a PerGeomBLDialog MODELESS (setModal(False) + show) so the MAIN
        window — in particular its Generate button — stays usable while the BL
        editor is open. Mirrors the modeless curve-edit dialog (curve_ctrl.py):
        Apply commits and KEEPS the window open, OK commits and closes, Cancel
        closes. Only one BL dialog exists at a time; the reference on
        self._bl_dialog keeps it alive (else Python GCs the modeless dialog) and is
        cleared when it closes."""
        dlg.setModal(False)
        # Keep it above the app's own main window (Tool window) but not above
        # other applications, and nudged off centre.
        from app.utils import keep_on_top, offset_popup
        keep_on_top(dlg)
        offset_popup(dlg, self.window())
        dlg.accepted.connect(lambda: on_accept(dlg))   # OK -> commit

        def _finish(_r, d=dlg):
            if on_finish is not None:
                on_finish()
            self._bl_dialog = None
            d.deleteLater()
        dlg.finished.connect(_finish)
        self._bl_dialog = dlg
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()

    def _open_global_bl_dialog(self):
        """Edit the GLOBAL boundary-layer parameters in a MODELESS pop-up, so the
        main window's Generate stays clickable (Apply commits + keeps it open)."""
        existing = getattr(self, "_bl_dialog", None)
        if existing is not None:                       # one BL editor at a time
            existing.raise_(); existing.activateWindow(); return

        def _commit(dlg):
            vals = dlg.result_params()
            if vals is None:   # "Use Global" is a no-op when editing the global itself
                return
            self._global_bl = vals
            self._write_bl_widgets(vals)  # keep the (hidden) backing widgets in sync
            self.mesh_config_changed.emit(self.get_config())

        dlg = PerGeomBLDialog("Global default", dict(self._global_bl),
                              dict(self._global_bl), apply_cb=_commit, parent=self)
        self._show_bl_dialog_modeless(dlg, on_accept=_commit)

    def _open_bl_override_dialog(self):
        """Pop up the per-geometry boundary-layer editor for the selected
        geometry: its BL parameters (top) plus, when the geometry has a segmented
        .meta sidecar, per-segment 'grow BL?' toggles (bottom). The parameter
        override is saved onto the geom list item; the per-segment flags are
        written to the .meta (v3 column) and honoured by the mesher. Shown MODELESS
        so the main window's Generate stays usable while it is open."""
        existing = getattr(self, "_bl_dialog", None)
        if existing is not None:                       # one BL editor at a time
            existing.raise_(); existing.activateWindow(); return
        item = self.geom_list_widget.currentItem()
        if item is None:
            return
        idx = self.geom_role_combo.currentIndex()
        if idx not in (0, 4):
            return
        rinfo = dict(item.data(self._ROLE_DATA) or {})

        # Per-segment BL toggles are shown only when the geometry was exported
        # with segments (a segmented .meta sidecar next to its .dat).
        path = item.data(Qt.ItemDataRole.UserRole)
        segs, seg_grow, highlight = [], None, None
        if path:
            from app.services.meta_io import read_meta_segments, read_meta_seg_growbl
            segs = read_meta_segments(path)
            if segs:
                seg_grow = read_meta_seg_growbl(path)
                highlight = self._segment_highlighter(path)

        def _commit(dlg):
            # #4: shared by OK and the Apply-and-keep-open button. Persists the
            # dialog's parameter override onto the geom item plus the per-segment
            # grow-BL flags to the .meta, then republishes the mesh config.
            # Modeless guard: the edited geometry may have been removed from the
            # list while the dialog stayed open — bail rather than touch a deleted
            # item (a QListWidgetItem whose C++ object is gone raises RuntimeError).
            try:
                if item.listWidget() is None:
                    return
            except RuntimeError:
                return
            vals = dlg.result_params()
            if vals:
                rinfo["bl_params"] = vals
                rinfo["role"] = "wall" if idx == 4 else "bl"
                item.setData(self._ROLE_DATA, rinfo)
            else:
                # Cleared: drop bl_params; keep wall / a per-geometry BC, else plain.
                rinfo.pop("bl_params", None)
                if idx == 4:
                    rinfo["role"] = "wall"
                    item.setData(self._ROLE_DATA, rinfo)
                elif rinfo.get("bc"):
                    rinfo["role"] = "bl"
                    item.setData(self._ROLE_DATA, rinfo)
                else:
                    item.setData(self._ROLE_DATA, None)
            # Persist per-segment grow-BL flags (independent of the parameter
            # override — kept even when the user chose 'Use Global').
            if segs and path:
                from app.services.meta_io import write_meta_seg_growbl
                write_meta_seg_growbl(path, dlg.result_seg_grow())
            self._sync_bl_scope()
            self.mesh_config_changed.emit(self.get_config())

        dlg = PerGeomBLDialog(item.text(), dict(self._global_bl),
                              rinfo.get("bl_params"), segments=segs,
                              seg_grow=seg_grow, highlight_cb=highlight,
                              apply_cb=_commit, parent=self)
        # Clear the canvas segment highlight when the dialog finally closes.
        on_finish = (lambda: self.segment_highlight_requested.emit(None)) if segs else None
        self._show_bl_dialog_modeless(dlg, on_accept=_commit, on_finish=on_finish)

    def _apply_global_bl_to_cfg(self, cfg: MeshConfig):
        """Write the authoritative global BL values onto a MeshConfig's BL
        fields (used by get_config regardless of which scope the widgets show)."""
        for key, attr in _BL_OVERRIDE_KEYS:
            if key not in self._global_bl:
                continue
            v = self._global_bl[key]
            if attr in _BL_INT_ATTRS:
                setattr(cfg, attr, int(round(float(v))))
            elif attr in _BL_BOOL_ATTRS:
                setattr(cfg, attr, bool(float(v)))
            else:
                setattr(cfg, attr, float(v))
