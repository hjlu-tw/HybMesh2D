"""Pop-up dialog widgets and boundary-layer field specs for the mesh config
panel. Extracted verbatim from mesh_config_panel.py (behaviour unchanged): the
three self-contained QDialog editors (per-geometry BL override, segment BC
types, per-segment BL toggle) plus the BL override key/spec tables they and
the panel share."""
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
from app.views.bc_widget import BC_TYPE_DEFS
from app.views.clean_double_spin_box import CleanDoubleSpinBox


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
    ("BL_TRANSITION_LAYERS", "bl_transition_layers"),
    ("BL_AUTO_TRANSITION_LAYERS", "bl_auto_transition_layers"),
    ("BL_TRANSITION_GROWTH_RATE", "bl_transition_growth_rate"),
    ("BL_TRANSITION_BUFFER", "bl_transition_buffer"),
    ("BL_USE_ANALYTIC_GEOM", "bl_use_analytic_geom"),
]
# Coercion for _apply_global_bl_to_cfg (all other BL attrs are floats).
_BL_INT_ATTRS = {"bl_layers", "bl_convex_method", "bl_fan_nodes", "bl_concave_method",
                 "bl_transition_layers", "bl_auto_transition_layers"}
_BL_BOOL_ATTRS = {"bl_auto_fan_nodes", "bl_use_analytic_geom"}

# Field specs for the per-geometry BL override dialog. (KEY, label, kind, opts);
# kind: float | int | choice | bool. Keys match _BL_OVERRIDE_KEYS.
_BL_FIELD_SPECS = [
    ("BL_INITIAL_THICKNESS", "Initial Thickness", "float", dict(lo=1e-6, hi=1.0, dec=6, step=0.001)),
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
                 apply_cb=None, parent=None):
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


class SegmentBCDialog(QDialog):
    """Group-based BC-TYPE editor for one geometry (#4). Segments that share a
    CAD grouping label form ONE row (a group); unnamed segments are listed for
    reference only. Select one OR MANY named rows (Shift/Ctrl-click) and choose a
    BC TYPE from the list (Inlet/Outlet/Wall/Symmetry/Isothermal/Free + Custom…)
    to assign it to that group — the covered segments highlight on the canvas
    (via ``highlight_cb``). The GROUP NAME is the row identity and is NEVER
    overwritten (the assigned BC is stored separately); the name still travels via
    the .meta sidecar and the physical BC type reaches the Solver BC table
    pre-seeded from this map. The ``shape:`` shown in each row is the segment's
    geometry kind (line/circle/smooth/polyline …), NOT a BC. Returns {group name:
    bc type}. Custom is a first-class option (choose 'Custom…' then type a name)."""

    _CUSTOM_LABEL = "Custom…"

    def __init__(self, geom_name: str, segments: list[tuple[int, str, str]],
                 group_bc: dict | None = None, highlight_cb=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Segment boundary conditions — {geom_name}")
        self.setStyleSheet("background:#121422; color:#cdd6f4;")
        self.setMinimumWidth(400)
        self.resize(440, 520)
        self._highlight_cb = highlight_cb
        self._kind: dict[int, str] = {sid: k for sid, _bc, k in segments}
        self._name_of: dict[int, str] = {sid: (bc or "").strip() for sid, bc, _k in segments}
        # name -> assigned BC type (starts from the current config map).
        self._group_bc: dict[str, str] = {k: v for k, v in (group_bc or {}).items() if v}
        self._selecting = False   # guard: programmatic edits shouldn't re-fire
        # #4: unnamed segments are still assignable even when nothing was grouped
        # in CAD. Mint a stable, whitespace-free group name per unnamed segment
        # (prefixed by the geometry so it stays unique across geometries in the
        # shared group map). The mint is display-only until the user actually
        # gives that segment a BC, at which point the caller writes the name to
        # the .meta name column (see result_seg_names) so it persists & groups.
        safe = "".join(c if (c.isalnum() or c == '_') else '_'
                       for c in geom_name).strip('_') or "geom"
        self._minted: dict[int, str] = {}
        for sid, bc, _k in segments:
            if not (bc or "").strip():
                self._minted[sid] = f"{safe}_s{sid}"
        self._auto_names = set(self._minted.values())

        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.setSpacing(6)
        hint = QLabel(
            "Each row is a GROUP of segments sharing a patch/group label (set in "
            "CAD), or an individual '(edge N)' if it was never grouped. Select one "
            "or many rows (Shift/Ctrl-click) and CHOOSE A BC TYPE from the list (or "
            "'Custom…' to type your own) — it applies to the whole selection and "
            "the covered segments highlight on the canvas. Assigning a BC to an "
            "ungrouped edge auto-creates a patch for it (no CAD grouping needed). "
            "The BC type is stored separately and pre-seeds the Solver BC table. "
            "'shape:' is the segment's geometry kind (line/circle/smooth…), NOT a BC.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#8a93ad; font-size:10px;")
        outer.addWidget(hint)

        self.seg_list = QListWidget()
        self.seg_list.setSelectionMode(
            QListWidget.SelectionMode.ExtendedSelection)   # Shift/Ctrl multi-select
        self.seg_list.setStyleSheet(
            "background:#181b2a; color:#a0a8c0; border:1px solid #333852; border-radius:3px;")
        # One row per named group (distinct non-empty label, first-appearance
        # order), then one row per unnamed segment. Each row carries (name, sids);
        # name is None for an unnamed segment (BC cannot be assigned by name).
        self._rows: list[tuple[str | None, list[int]]] = self._build_rows(segments)
        for name, sids in self._rows:
            it = QListWidgetItem(self._row_label(name, sids))
            it.setData(Qt.ItemDataRole.UserRole, (name, sids))
            self.seg_list.addItem(it)
        outer.addWidget(self.seg_list, stretch=1)

        editor = QFormLayout()
        # Offer the standard BC TYPES plus an explicit Custom… entry (#4). The
        # combo is editable so a custom name can be typed; blank clears the
        # assignment (geometry default). The chosen value is stored per GROUP NAME,
        # leaving the name itself untouched.
        self.bc_edit = QComboBox()
        self.bc_edit.setEditable(True)
        self.bc_edit.addItem("")   # blank = clear / geometry default
        for _disp, _tech, cfg_val in BC_TYPE_DEFS:
            if cfg_val and cfg_val != "custom":
                self.bc_edit.addItem(cfg_val)
        self.bc_edit.addItem(self._CUSTOM_LABEL)   # pick then type a custom name
        self.bc_edit.setCurrentText("")
        self.bc_edit.setStyleSheet(COMBO_STYLE)
        self.bc_edit.setEnabled(False)
        editor.addRow(help_label("BC type:",
            "Physical BC TYPE for the selected group(s) — pick from the list or "
            "'Custom…' to type your own (blank = geometry default). The group name "
            "is not changed."),
            self.bc_edit)
        align_form_labels(editor, 110)
        outer.addLayout(editor)

        self.seg_list.itemSelectionChanged.connect(self._on_selection_changed)
        self.bc_edit.activated.connect(self._on_bc_activated)

        # #4: assignment is deferred to an explicit Apply (it used to commit live
        # on every keystroke, which re-highlighted the canvas and made the window
        # jump/recede mid-edit). Apply assigns the chosen BC type to the selected
        # group(s) and keeps the window open; OK applies then closes; Cancel
        # closes (earlier Applies already took effect).
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Apply
            | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._on_ok)
        buttons.rejected.connect(self.reject)
        apply_btn = buttons.button(QDialogButtonBox.StandardButton.Apply)
        apply_btn.setToolTip("Assign the chosen BC type to the selected group(s) "
                             "and keep this window open.")
        apply_btn.clicked.connect(self._apply_bc)
        outer.addWidget(buttons)
        if self.seg_list.count():
            self.seg_list.setCurrentRow(0)

    def _build_rows(self, segments: list[tuple[int, str, str]]):
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
        rows: list[tuple[str | None, list[int]]] = [(l, groups[l]) for l in order]
        # Unnamed segments carry their minted name so a BC can be assigned even
        # without CAD grouping (#4); the row is flagged auto for display.
        rows += [(self._minted.get(s), [s]) for s in singles]
        return rows

    def _row_label(self, name: str | None, sids: list[int]) -> str:
        if name in self._auto_names:
            disp = f"(edge {sids[0]})"
        else:
            disp = name if name else "(unnamed)"
        bc = self._group_bc.get(name, "") if name else ""
        bc_txt = f"  →  {bc}" if bc else ""
        kinds = ", ".join(sorted({self._kind.get(s, "") for s in sids if self._kind.get(s)}))
        shape = f"  ·  shape: {kinds}" if kinds else ""
        if len(sids) == 1:
            return f"{disp}{bc_txt}    ·  seg {sids[0]}{shape}"
        ids = ",".join(str(s) for s in sids)
        if len(ids) > 22:
            ids = f"{len(sids)} segs"
        return f"{disp}{bc_txt}    ·  segs {ids}{shape}"

    def _selected_names(self) -> list[str]:
        """Distinct group names among the selected rows (unnamed rows excluded)."""
        out: list[str] = []
        for it in self.seg_list.selectedItems():
            name, _sids = it.data(Qt.ItemDataRole.UserRole)
            if name and name not in out:
                out.append(name)
        return out

    def _selected_sids(self) -> list[int]:
        out: list[int] = []
        for it in self.seg_list.selectedItems():
            _name, sids = it.data(Qt.ItemDataRole.UserRole)
            out.extend(sids or [])
        return out

    def _shared_bc(self, names: list[str]) -> str:
        vals = {self._group_bc.get(n, "") for n in names}
        return vals.pop() if len(vals) == 1 else ""

    def _on_selection_changed(self):
        names = self._selected_names()
        # Every row (named group or minted unnamed edge) is assignable now (#4).
        self.bc_edit.setEnabled(bool(names))
        shown = self._shared_bc(names)
        self._selecting = True
        self.bc_edit.blockSignals(True)
        self.bc_edit.setCurrentText(shown)
        self.bc_edit.lineEdit().setPlaceholderText(
            "(select an edge/group)" if not names
            else ("(mixed)" if not shown else ""))
        self.bc_edit.blockSignals(False)
        self._selecting = False
        if self._highlight_cb:
            self._highlight_cb(self._selected_sids())

    def _on_bc_activated(self, idx: int):
        # 'Custom…' is an affordance: clear the field and let the user type; the
        # stored value is whatever they type, never the literal label.
        if self.bc_edit.itemText(idx) == self._CUSTOM_LABEL:
            self._selecting = True
            self.bc_edit.setCurrentText("")
            self._selecting = False
            self.bc_edit.lineEdit().setFocus()

    def _apply_bc(self):
        """#4: commit the chosen BC type to the selected group(s) on demand
        (Apply / OK) rather than live, and refresh the affected row labels."""
        if self._selecting:
            return
        bc = self.bc_edit.currentText().strip()
        if bc == self._CUSTOM_LABEL:
            return
        for name in self._selected_names():
            if bc:
                self._group_bc[name] = bc
            else:
                self._group_bc.pop(name, None)
        for it in self.seg_list.selectedItems():
            name, sids = it.data(Qt.ItemDataRole.UserRole)
            it.setText(self._row_label(name, sids))

    def _on_ok(self):
        self._apply_bc()
        self.accept()

    def result_group_bc(self) -> dict[str, str]:
        return {k: v for k, v in self._group_bc.items() if v}

    def result_seg_names(self) -> dict[int, str]:
        """{seg_id: minted_name} for previously-unnamed segments that the user
        gave a BC. The caller writes these to the .meta name column so the
        auto-created patch persists and reaches the mesher/solver (#4)."""
        return {sid: nm for sid, nm in self._minted.items() if self._group_bc.get(nm)}


class AssignPatchDialog(QDialog):
    """CAD patch/group assignment that lists ALL edges of the geometry (#8),
    mirroring the segment-BC dialog's list UI. Select one or many edges
    (Shift/Ctrl-click), type or pick a PATCH/GROUP name, and OK tags the
    selected edges with it (the physical BC type is chosen per group later in
    the Mesh Generator). Blank clears the patch (geometry default). The covered
    edges highlight on the canvas as the selection changes (via highlight_cb).
    Returns the chosen name via patch_name() and the target rows via
    selected_indices()."""

    def __init__(self, geom_name: str, edges: list[tuple[int, str, str]],
                 existing: list[str], preselect=None, highlight_cb=None,
                 apply_cb=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Assign patch / group — {geom_name}")
        self.setStyleSheet("background:#121422; color:#cdd6f4;")
        self.setMinimumWidth(400)
        self.resize(440, 520)
        self._highlight_cb = highlight_cb
        self._apply_cb = apply_cb
        self._label_of: dict[int, str] = {}
        preselect = set(preselect or [])

        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.setSpacing(6)
        hint = QLabel(
            "Each row is an EDGE of this geometry. Select one or many "
            "(Shift/Ctrl-click) and type or pick a PATCH/GROUP name to tag them "
            "— the physical BC type is chosen per group later in the Mesh "
            "Generator. Blank = geometry default. The selected edges highlight on "
            "the canvas. 'shape:' is the edge's geometry kind (line/circle/"
            "smooth…), NOT a BC.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#8a93ad; font-size:10px;")
        outer.addWidget(hint)

        self.seg_list = QListWidget()
        self.seg_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.seg_list.setStyleSheet(
            "background:#181b2a; color:#a0a8c0; border:1px solid #333852; border-radius:3px;")
        self._kind_of: dict[int, str] = {}
        self._items: dict[int, QListWidgetItem] = {}
        for idx, label, kind in edges:
            label = (label or "").strip()
            self._label_of[idx] = label
            self._kind_of[idx] = kind or ""
            it = QListWidgetItem(self._row_text(idx))
            it.setData(Qt.ItemDataRole.UserRole, idx)
            self.seg_list.addItem(it)
            self._items[idx] = it
            if idx in preselect:
                it.setSelected(True)
        outer.addWidget(self.seg_list, stretch=1)

        editor = QFormLayout()
        self.name_edit = QComboBox()
        self.name_edit.setEditable(True)
        self.name_edit.addItem("")   # blank = clear / geometry default
        for e in existing:
            self.name_edit.addItem(e)
        self.name_edit.setStyleSheet(COMBO_STYLE)
        editor.addRow(help_label("Patch / group:",
            "Free-form grouping label (e.g. airfoil, wall_top, 1) for the selected "
            "edge(s); blank clears it (geometry default)."), self.name_edit)
        align_form_labels(editor, 110)
        outer.addLayout(editor)

        self.seg_list.itemSelectionChanged.connect(self._on_selection_changed)

        # Apply keeps the dialog OPEN so several patches can be assigned in one
        # sitting (#1); OK applies the current selection and closes, Cancel just
        # closes (any earlier Apply already took effect).
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Apply
            | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        apply_btn = buttons.button(QDialogButtonBox.StandardButton.Apply)
        apply_btn.setToolTip("Assign this name to the selected edges and keep "
                             "this window open for the next group.")
        apply_btn.clicked.connect(self._on_apply)
        outer.addWidget(buttons)
        self._on_selection_changed()

    def _on_apply(self):
        """Assign the current name to the selected edges without closing (#1)."""
        if self._apply_cb is None:
            return
        idxs = self.selected_indices()
        if not idxs:
            return
        name = self.patch_name()
        self._apply_cb(idxs, name)
        # Remember a freshly-typed name so the next group can reuse it, and
        # reflect it on the edge rows so the list stays truthful.
        for i in idxs:
            self._label_of[i] = name
            if i in self._items:
                self._items[i].setText(self._row_text(i))
        if name and self.name_edit.findText(name) < 0:
            self.name_edit.addItem(name)

    def _row_text(self, idx: int) -> str:
        disp = self._label_of.get(idx) or "(unassigned)"
        kind = self._kind_of.get(idx, "")
        shape = f"  ·  shape: {kind}" if kind else ""
        return f"{disp}    ·  edge {idx}{shape}"

    def _on_selection_changed(self):
        idxs = self.selected_indices()
        labels = {self._label_of.get(i, "") for i in idxs}
        shared = next(iter(labels)) if len(labels) == 1 else ""
        self.name_edit.blockSignals(True)
        self.name_edit.setCurrentText(shared)
        self.name_edit.lineEdit().setPlaceholderText("(mixed)" if len(labels) > 1 else "")
        self.name_edit.blockSignals(False)
        if self._highlight_cb:
            self._highlight_cb(idxs)

    def selected_indices(self) -> list[int]:
        return [it.data(Qt.ItemDataRole.UserRole) for it in self.seg_list.selectedItems()]

    def patch_name(self) -> str:
        return self.name_edit.currentText().strip()
