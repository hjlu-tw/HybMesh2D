"""Boundary-layer dialogs and field specs for the mesh config panel. Split from
mesh_dialogs.py (behaviour unchanged): the BL override key/spec tables shared
with the panel, plus the per-segment BL toggle section and the per-geometry BL
override dialog."""
from __future__ import annotations
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QFrame,
    QFormLayout, QComboBox, QSpinBox, QLabel, QCheckBox,
    QListWidget, QListWidgetItem, QDialog, QDialogButtonBox,
)
from PyQt6.QtCore import Qt
from app.utils import (
    make_button, COMBO_STYLE, SPIN_STYLE, align_form_labels, help_label,
)
from app.views.clean_double_spin_box import CleanDoubleSpinBox, SciDoubleSpinBox


# Boundary-layer parameters that can be overridden per geometry: the .dat/C++
# KEY (include/Config.hpp BLParams) paired with the MeshConfig attribute. These
# are the fields the panel's BL sections edit; when a geometry override is
# active the same widgets edit that geometry's values instead of the global ones.
_BL_OVERRIDE_KEYS = [
    ("BL_INITIAL_THICKNESS", "bl_initial_thickness"),
    ("BL_GROWTH_RATE", "bl_growth_rate"),
    ("BL_LAYERS", "bl_layers"),
    ("BL_CONVEX_METHOD", "bl_convex_method"),
    ("BL_FAN_NODES", "bl_fan_nodes"),
    ("BL_AUTO_FAN_NODES", "bl_auto_fan_nodes"),
    ("BL_FAN_ANGLE_THRESHOLD", "bl_fan_angle_threshold"),
    ("BL_CONVEX_ANGLE_THRESHOLD", "bl_convex_angle_threshold"),
    ("BL_PARA_FALLBACK_ANGLE", "bl_para_fallback_angle"),
    ("BL_CONCAVE_METHOD", "bl_concave_method"),
    ("BL_CONCAVE_ANGLE_THRESHOLD", "bl_concave_angle_threshold"),
    ("BL_CONCAVE_INFLUENCE_MULTIPLIER", "bl_concave_influence_multiplier"),
    ("BL_JUNCTION_METHOD", "bl_junction_method"),
    ("BL_JUNCTION_ANGLE_C1", "bl_junction_angle_c1"),
    ("BL_JUNCTION_ANGLE_C2", "bl_junction_angle_c2"),
    ("BL_JUNCTION_ANGLE_C3", "bl_junction_angle_c3"),
    ("BL_TRANSITION_LAYERS", "bl_transition_layers"),
    ("BL_AUTO_TRANSITION_LAYERS", "bl_auto_transition_layers"),
    ("BL_TRANSITION_GROWTH_RATE", "bl_transition_growth_rate"),
    ("BL_TRANSITION_BUFFER", "bl_transition_buffer"),
    ("BL_USE_ANALYTIC_GEOM", "bl_use_analytic_geom"),
]
# Coercion for _apply_global_bl_to_cfg (all other BL attrs are floats).
_BL_INT_ATTRS = {"bl_layers", "bl_convex_method", "bl_fan_nodes", "bl_concave_method",
                 "bl_junction_method",
                 "bl_transition_layers", "bl_auto_transition_layers"}
_BL_BOOL_ATTRS = {"bl_auto_fan_nodes", "bl_use_analytic_geom"}

# Field specs for the per-geometry BL override dialog. (KEY, label, kind, opts);
# kind: float | int | choice | bool. Keys match _BL_OVERRIDE_KEYS.
_BL_FIELD_SPECS = [
    # sci=True: a physical length that routinely needs 1e-7..1e-8 (y+~1 on a
    # chord-normalised geometry), which a fixed-notation box cannot express.
    ("BL_INITIAL_THICKNESS", "Initial Thickness", "float", dict(lo=0.0, hi=1e4, sci=True)),
    ("BL_GROWTH_RATE", "Growth Rate", "float", dict(lo=1.001, hi=5.0, dec=4, step=0.05)),
    ("BL_LAYERS", "Layers", "int", dict(lo=0, hi=100)),
    ("BL_CONVEX_METHOD", "Convex Method", "choice", dict(choices=[(0, "Fan"), (2, "Parallelogram")])),
    ("BL_FAN_NODES", "Fan Nodes", "int", dict(lo=1, hi=100)),
    ("BL_AUTO_FAN_NODES", "Auto Fan Nodes", "choice", dict(choices=[(0, "OFF"), (1, "GLOBAL"), (2, "LOCAL")])),
    ("BL_FAN_ANGLE_THRESHOLD", "Fan Threshold (deg)", "float", dict(lo=0.0, hi=360.0, dec=2, step=1.0)),
    ("BL_CONVEX_ANGLE_THRESHOLD", "Convex Threshold (deg)", "float", dict(lo=0.0, hi=360.0, dec=2, step=1.0)),
    ("BL_PARA_FALLBACK_ANGLE", "Para Fallback (deg)", "float", dict(lo=0.0, hi=360.0, dec=2, step=1.0)),
    ("BL_CONCAVE_METHOD", "Concave Method", "choice", dict(choices=[(0, "Merge"), (5, "Thickness Blending")])),
    ("BL_CONCAVE_ANGLE_THRESHOLD", "Concave Threshold (deg)", "float", dict(lo=0.0, hi=360.0, dec=2, step=1.0)),
    ("BL_CONCAVE_INFLUENCE_MULTIPLIER", "Concave Influence", "float", dict(lo=0.0, hi=100.0, dec=2, step=0.5)),
    ("BL_JUNCTION_METHOD", "Junction Method", "choice", dict(choices=[(0, "Taper-to-zero"), (1, "4-case angle-driven")])),
    ("BL_JUNCTION_ANGLE_C1", "Junction θ C1 (deg)", "float", dict(lo=0.0, hi=360.0, dec=2, step=1.0)),
    ("BL_JUNCTION_ANGLE_C2", "Junction θ C2 (deg)", "float", dict(lo=0.0, hi=360.0, dec=2, step=1.0)),
    ("BL_JUNCTION_ANGLE_C3", "Junction θ C3 (deg)", "float", dict(lo=0.0, hi=360.0, dec=2, step=1.0)),
    ("BL_TRANSITION_LAYERS", "Transition Layers", "int", dict(lo=0, hi=100)),
    ("BL_AUTO_TRANSITION_LAYERS", "Auto Transition", "choice", dict(choices=[(0, "OFF"), (1, "GLOBAL"), (2, "LOCAL")])),
    ("BL_TRANSITION_GROWTH_RATE", "Transition Growth", "float", dict(lo=1.001, hi=5.0, dec=4, step=0.05)),
    ("BL_TRANSITION_BUFFER", "Transition Buffer", "float", dict(lo=0.0, hi=100.0, dec=4, step=0.5)),
    ("BL_USE_ANALYTIC_GEOM", "Analytic BL Normals", "bool", dict()),
]


class SegmentBLSection(QWidget):
    """Per-segment 'grow boundary layer?' toggle list for one geometry, as an
    embeddable widget (used inside the per-geometry BL dialog, below the BL
    parameters). Rows are groups (by CAD label) + individual unnamed segments;
    select one or many rows and use 'Grow BL' / 'No BL'. Selected segments
    highlight on the canvas (via ``highlight_cb``). NOTE: where a BL segment meets
    a no-BL segment the layer tapers to zero and the far-field triangulates the
    transition (no clean quad cap). Returns {seg_id: grow_bool}."""

    def __init__(self, segments: list[tuple[int, str, str]],
                 seg_grow: dict | None = None, highlight_cb=None, parent=None):
        super().__init__(parent)
        self._highlight_cb = highlight_cb
        self._kind: dict[int, str] = {sid: k for sid, _bc, k in segments}
        self._grow: dict[int, bool] = {sid: True for sid, _bc, _k in segments}
        for sid, g in (seg_grow or {}).items():
            if sid in self._grow:
                self._grow[sid] = bool(g)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        head = QLabel("Per-segment boundary layer")
        head.setStyleSheet("color:#cdd6f4; font-weight:bold;")
        lay.addWidget(head)
        hint = QLabel(
            "Choose which edges grow a boundary layer. Each row is a group of "
            "segments sharing a CAD label (unnamed segments listed individually). "
            "Where a BL edge meets a no-BL edge the layer tapers to zero and the "
            "far-field mesh fills the transition (no clean quad cap), so prefer "
            "toggling BL off on whole runs (e.g. an outflow face).")
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#8a93ad; font-size:10px;")
        lay.addWidget(hint)

        self.seg_list = QListWidget()
        self.seg_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.seg_list.setStyleSheet(
            "background:#181b2a; color:#a0a8c0; border:1px solid #333852; border-radius:3px;")
        self._rows: list[list[int]] = self._build_rows(segments)
        for sids in self._rows:
            it = QListWidgetItem(self._row_label(sids))
            it.setData(Qt.ItemDataRole.UserRole, sids)
            self.seg_list.addItem(it)
        lay.addWidget(self.seg_list, stretch=1)

        btn_row = QHBoxLayout()
        self.grow_btn = make_button("Grow BL ✓", "#1e4620")
        self.grow_btn.setToolTip("Grow a boundary layer on the selected segments")
        self.nobl_btn = make_button("No BL ✗", "#4a1c1c")
        self.nobl_btn.setToolTip("Do not grow a boundary layer on the selected segments")
        self.grow_btn.setEnabled(False)
        self.nobl_btn.setEnabled(False)
        btn_row.addWidget(self.grow_btn)
        btn_row.addWidget(self.nobl_btn)
        lay.addLayout(btn_row)

        self.seg_list.itemSelectionChanged.connect(self._on_selection_changed)
        self.grow_btn.clicked.connect(lambda: self._apply(True))
        self.nobl_btn.clicked.connect(lambda: self._apply(False))
        if self.seg_list.count():
            self.seg_list.setCurrentRow(0)

    def _build_rows(self, segments: list[tuple[int, str, str]]) -> list[list[int]]:
        groups: dict[str, list[int]] = {}
        order: list[str] = []
        singles: list[int] = []
        for sid, bc, _k in segments:
            label = (bc or "").strip()
            if label:
                if label not in groups:
                    groups[label] = []
                    order.append(label)
                groups[label].append(sid)
            else:
                singles.append(sid)
        rows = [groups[l] for l in order] + [[s] for s in singles]
        self._row_names = {tuple(groups[l]): l for l in order}
        return rows

    def _row_label(self, sids: list[int]) -> str:
        states = {self._grow.get(s, True) for s in sids}
        bl = "BL: on" if states == {True} else ("BL: off" if states == {False} else "BL: mixed")
        name = self._row_names.get(tuple(sids), "")
        disp = name if name else "(unnamed)"
        kinds = ", ".join(sorted({self._kind.get(s, "") for s in sids if self._kind.get(s)}))
        shape = f"  ·  shape: {kinds}" if kinds else ""
        if len(sids) == 1:
            return f"{disp}  ·  {bl}  ·  seg {sids[0]}{shape}"
        ids = ",".join(str(s) for s in sids)
        if len(ids) > 22:
            ids = f"{len(sids)} segs"
        return f"{disp}  ·  {bl}  ·  segs {ids}{shape}"

    def _selected_sids(self) -> list[int]:
        out: list[int] = []
        for it in self.seg_list.selectedItems():
            out.extend(it.data(Qt.ItemDataRole.UserRole) or [])
        return out

    def _on_selection_changed(self):
        sids = self._selected_sids()
        self.grow_btn.setEnabled(bool(sids))
        self.nobl_btn.setEnabled(bool(sids))
        if self._highlight_cb:
            self._highlight_cb(sids)

    def _apply(self, grow: bool):
        for sid in self._selected_sids():
            self._grow[sid] = grow
        for it in self.seg_list.selectedItems():
            it.setText(self._row_label(it.data(Qt.ItemDataRole.UserRole) or []))

    def result_seg_grow(self) -> dict[int, bool]:
        return dict(self._grow)


class PerGeomBLDialog(QDialog):
    """Pop-up editor for ONE geometry's boundary layer. Top: the geometry's BL
    parameter override (always editable, seeded from the geometry's current
    override, or the global BL values when it has none). Bottom (only when the
    geometry has a segmented .meta sidecar): per-segment 'grow BL?' toggles. OK
    saves the parameters as this geometry's override and the per-segment flags to
    the .meta; 'Use Global' clears the parameter override (the per-segment flags
    are still saved) so the geometry follows the global BL parameters."""

    def __init__(self, geom_name: str, defaults: dict, current: dict | None,
                 segments: list[tuple[int, str, str]] | None = None,
                 seg_grow: dict | None = None, highlight_cb=None,
                 apply_cb=None, parent=None, length_unit: str = "",
                 length_unit_name: str = ""):
        # The unit is passed in rather than read from a global: this dialog holds the
        # first-cell height, the one number in the whole GUI where getting the unit
        # wrong by 1000x still produces a mesh that looks plausible.
        self._length_unit = length_unit
        self._length_unit_name = length_unit_name
        super().__init__(parent)
        self.setWindowTitle(f"Boundary Layer — {geom_name}")
        self.setStyleSheet("background:#121422; color:#cdd6f4;")
        self.setMinimumWidth(360)
        self.resize(420, 760 if segments else 600)
        self._widgets = {}
        self._cleared = False
        self._seg_section = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.setSpacing(6)
        hint = QLabel(
            "Boundary layer for THIS geometry only (seeded from the global "
            "values). OK saves it as an override; 'Use Global' clears it.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#8a93ad; font-size:10px;")
        outer.addWidget(hint)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setMinimumHeight(300 if segments else 380)
        content = QWidget()
        form = QFormLayout(content)
        form.setContentsMargins(2, 2, 2, 2)
        seed = dict(defaults)
        if current:
            seed.update(current)
        for key, label, kind, opt in _BL_FIELD_SPECS:
            w = self._make_widget(kind, opt)
            self._set_widget_value(w, kind, seed.get(key))
            self._widgets[key] = (w, kind)
            form.addRow(help_label(label + ":", key), w)
        align_form_labels(form, 160)
        scroll.setWidget(content)
        outer.addWidget(scroll, stretch=2)

        # Per-segment BL on/off toggles, merged into this dialog below the
        # parameters (only when the geometry was exported with segments).
        if segments:
            sep = QFrame()
            sep.setFrameShape(QFrame.Shape.HLine)
            sep.setStyleSheet("color:#333852;")
            outer.addWidget(sep)
            self._seg_section = SegmentBLSection(
                segments, seg_grow=seg_grow, highlight_cb=highlight_cb, parent=self)
            outer.addWidget(self._seg_section, stretch=1)

        # #4: an explicit Apply (when the caller wires apply_cb) commits these
        # settings now and keeps the window open, so editing several values no
        # longer means the dialog closes on every Enter. OK applies+closes.
        std = QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        if apply_cb is not None:
            std |= QDialogButtonBox.StandardButton.Apply
        buttons = QDialogButtonBox(std)
        clear_btn = buttons.addButton("Use Global", QDialogButtonBox.ButtonRole.ResetRole)
        clear_btn.setToolTip("Clear this geometry's override — follow the global BL settings.")
        clear_btn.clicked.connect(self._on_clear)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        if apply_cb is not None:
            ap = buttons.button(QDialogButtonBox.StandardButton.Apply)
            ap.setToolTip("Apply these boundary-layer settings now and keep this "
                          "window open.")
            ap.clicked.connect(lambda: apply_cb(self))
        outer.addWidget(buttons)

    def _on_clear(self):
        self._cleared = True
        self.accept()

    def _make_widget(self, kind, opt):
        if kind == "float":
            if opt.get("sci"):
                # Scientific field: it pins its own decimals and steps by decade,
                # so "dec"/"step" do not apply.
                w = SciDoubleSpinBox()
                w.setRange(opt["lo"], opt["hi"])
                # sci=True marks a physical length, so it is exactly the set that
                # carries the model unit.
                if getattr(self, "_length_unit", ""):
                    from app.services import units
                    w.setSuffix(" " + units.symbol(self._length_unit,
                                                   self._length_unit_name))
            else:
                w = CleanDoubleSpinBox(); w.setRange(opt["lo"], opt["hi"])
                w.setDecimals(opt["dec"]); w.setSingleStep(opt.get("step", 0.1))
            w.setStyleSheet(SPIN_STYLE)
        elif kind == "int":
            w = QSpinBox(); w.setRange(opt["lo"], opt["hi"]); w.setStyleSheet(SPIN_STYLE)
        elif kind == "choice":
            w = QComboBox()
            for val, lbl in opt["choices"]:
                w.addItem(lbl, val)
            w.setStyleSheet(COMBO_STYLE)
        else:
            w = QCheckBox(); w.setStyleSheet("color:#a0a8c0;")
        return w

    def _set_widget_value(self, w, kind, value):
        if value is None:
            return
        if kind == "float":
            w.setValue(float(value))
        elif kind == "int":
            w.setValue(int(round(float(value))))
        elif kind == "choice":
            i = w.findData(int(round(float(value))))
            w.setCurrentIndex(i if i >= 0 else 0)
        else:
            w.setChecked(bool(float(value)))

    def _widget_value(self, w, kind):
        if kind == "float":
            return float(w.value())
        if kind == "int":
            return int(w.value())
        if kind == "choice":
            return int(w.currentData())
        return 1 if w.isChecked() else 0

    def result_params(self) -> dict | None:
        """Full override dict, or None if the user chose 'Use Global'."""
        if self._cleared:
            return None
        return {k: self._widget_value(w, kind) for k, (w, kind) in self._widgets.items()}

    def result_seg_grow(self) -> dict[int, bool]:
        """Per-segment grow-BL flags, or {} when the geometry has no segments.
        Independent of 'Use Global' — the flags are returned either way."""
        return self._seg_section.result_seg_grow() if self._seg_section else {}
