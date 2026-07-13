from __future__ import annotations
import os
from PyQt6.QtWidgets import (

    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QFrame,
    QFormLayout, QComboBox, QSpinBox, QLabel,
    QCheckBox, QLineEdit, QListWidget, QListWidgetItem, QFileDialog,
    QMenu, QDialog, QDialogButtonBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from app.views.collapsible import CollapsibleSection
from app.utils import (
    make_button, COMBO_STYLE, SPIN_STYLE, align_form_labels,
    help_label, help_widget, LINEEDIT_STYLE, BC_COLORS, DEFAULT_BC_COLOR,
    keep_on_top
)
from app.models.mesh_config import MeshConfig
from app.views.bc_widget import BCWidget, BC_TYPE_DEFS
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


class PerGeomBLDialog(QDialog):
    """Pop-up editor for ONE geometry's boundary-layer override. Fields are
    always editable (seeded from the geometry's current override, or the global
    BL values when it has none). OK saves the full set as this geometry's
    override; 'Use Global' clears it so the geometry follows the global BL."""

    def __init__(self, geom_name: str, defaults: dict, current: dict | None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Boundary Layer — {geom_name}")
        self.setStyleSheet("background:#121422; color:#cdd6f4;")
        self.setMinimumWidth(360)
        self.resize(400, 600)
        self._widgets = {}
        self._cleared = False

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
        scroll.setMinimumHeight(380)
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
        outer.addWidget(scroll, stretch=1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        clear_btn = buttons.addButton("Use Global", QDialogButtonBox.ButtonRole.ResetRole)
        clear_btn.setToolTip("Clear this geometry's override — follow the global BL settings.")
        clear_btn.clicked.connect(self._on_clear)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
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

        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.setSpacing(6)
        hint = QLabel(
            "Each row is a GROUP of segments sharing a patch/group label (set in "
            "CAD). Select one or many named rows (Shift/Ctrl-click) and CHOOSE A "
            "BC TYPE from the list (or 'Custom…' to type your own) — it applies to "
            "the whole group and the covered segments highlight on the canvas. The "
            "group NAME is kept as-is (never overwritten); the BC type is stored "
            "separately and pre-seeds the Solver BC table. Unnamed segments are "
            "shown for reference — name them in CAD to assign a BC. 'shape:' is the "
            "segment's geometry kind (line/circle/smooth…), NOT a BC.")
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
        self.bc_edit.currentTextChanged.connect(self._on_bc_changed)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
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
        rows += [(None, [s]) for s in singles]
        return rows

    def _row_label(self, name: str | None, sids: list[int]) -> str:
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
        # BC assignment only makes sense for named groups.
        self.bc_edit.setEnabled(bool(names))
        shown = self._shared_bc(names)
        self._selecting = True
        self.bc_edit.blockSignals(True)
        self.bc_edit.setCurrentText(shown)
        self.bc_edit.lineEdit().setPlaceholderText(
            "(name segments in CAD first)" if not names
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

    def _on_bc_changed(self, text: str):
        if self._selecting:
            return
        bc = text.strip()
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

    def result_group_bc(self) -> dict[str, str]:
        return {k: v for k, v in self._group_bc.items() if v}


class SegmentBLDialog(QDialog):
    """Per-segment boundary-layer toggle for one geometry (#1). Rows are groups
    (by CAD label) + individual unnamed segments; select one or many rows and use
    'Grow BL' / 'No BL' to choose whether the boundary layer grows on those
    segments. Selected segments highlight on the canvas (via ``highlight_cb``).
    Saved to the .meta grow-BL column and honoured by the mesher. NOTE: where a
    BL segment meets a no-BL segment the layer tapers to zero and the far-field
    triangulates the transition (no clean quad cap). Returns {seg_id: grow_bool}."""

    def __init__(self, geom_name: str, segments: list[tuple[int, str, str]],
                 seg_grow: dict | None = None, highlight_cb=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Segment boundary layer — {geom_name}")
        self.setStyleSheet("background:#121422; color:#cdd6f4;")
        self.setMinimumWidth(400)
        self.resize(440, 520)
        self._highlight_cb = highlight_cb
        self._kind: dict[int, str] = {sid: k for sid, _bc, k in segments}
        self._grow: dict[int, bool] = {sid: True for sid, _bc, _k in segments}
        for sid, g in (seg_grow or {}).items():
            if sid in self._grow:
                self._grow[sid] = bool(g)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.setSpacing(6)
        hint = QLabel(
            "Choose which edges grow a boundary layer. Each row is a group of "
            "segments sharing a CAD label (unnamed segments listed individually). "
            "Select one or many rows and click 'Grow BL' or 'No BL'. Where a BL "
            "edge meets a no-BL edge the layer tapers to zero and the far-field "
            "mesh fills the transition (no clean quad cap), so prefer toggling BL "
            "off on whole runs (e.g. an outflow face).")
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#8a93ad; font-size:10px;")
        outer.addWidget(hint)

        self.seg_list = QListWidget()
        self.seg_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.seg_list.setStyleSheet(
            "background:#181b2a; color:#a0a8c0; border:1px solid #333852; border-radius:3px;")
        self._rows: list[list[int]] = self._build_rows(segments)
        for sids in self._rows:
            it = QListWidgetItem(self._row_label(sids))
            it.setData(Qt.ItemDataRole.UserRole, sids)
            self.seg_list.addItem(it)
        outer.addWidget(self.seg_list, stretch=1)

        btn_row = QHBoxLayout()
        self.grow_btn = make_button("Grow BL ✓", "#1e4620")
        self.grow_btn.setToolTip("Grow a boundary layer on the selected segments")
        self.nobl_btn = make_button("No BL ✗", "#4a1c1c")
        self.nobl_btn.setToolTip("Do not grow a boundary layer on the selected segments")
        self.grow_btn.setEnabled(False)
        self.nobl_btn.setEnabled(False)
        btn_row.addWidget(self.grow_btn)
        btn_row.addWidget(self.nobl_btn)
        outer.addLayout(btn_row)

        self.seg_list.itemSelectionChanged.connect(self._on_selection_changed)
        self.grow_btn.clicked.connect(lambda: self._apply(True))
        self.nobl_btn.clicked.connect(lambda: self._apply(False))

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)
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
        # Map each row (by its seg-id tuple) to its shared group name, for display.
        self._row_names = {tuple(groups[l]): l for l in order}
        return rows

    def _row_label(self, sids: list[int]) -> str:
        states = {self._grow.get(s, True) for s in sids}
        bl = "BL: on" if states == {True} else ("BL: off" if states == {False} else "BL: mixed")
        # Reuse the group's shared name for display, if any.
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


class MeshConfigPanel(QScrollArea):
    """Scrollable panel containing editor widgets for all Background_para.dat options."""
    geom_files_changed = pyqtSignal(list)
    mesh_config_changed = pyqtSignal(object)
    # Emitted when Domain Source flips (True = custom geometry outline) so the
    # canvas can hide the rectangular domain box + its per-edge BC colours.
    domain_source_changed = pyqtSignal(bool)
    # Emitted with the file path of the geometry selected in the list ("" when
    # none) so the canvas can highlight the matching geometry.
    geom_selection_changed = pyqtSignal(str)
    # Emitted with an Nx2 coords array (or None) to highlight one segment on the
    # canvas while the per-segment BC dialog is open.
    segment_highlight_requested = pyqtSignal(object)
    # #5: emitted by the Output "Export mesh…" button to save the generated mesh.
    export_mesh_requested = pyqtSignal()

    # Per-item data role storing the geometry's mesh role (seed dict or None)
    _ROLE_DATA = Qt.ItemDataRole.UserRole + 1

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setStyleSheet("background: #0c0d16;")

        # Custom scrollbar styling
        self.verticalScrollBar().setStyleSheet("""
            QScrollBar:vertical {
                border: none;
                background: #0c0d16;
                width: 10px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #2c2e43;
                min-height: 20px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical:hover {
                background: #3e415e;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

        content = QWidget()
        content.setStyleSheet("background: #121422; color: #a0a8c0;")
        content.setMaximumWidth(430)  # Prevent content from expanding beyond sidebar
        self._layout = QVBoxLayout(content)
        self._layout.setContentsMargins(6, 6, 6, 6)
        self._layout.setSpacing(6)
        self.setWidget(content)

        # ── Control Buttons ───────────────────────────────────────────────
        self.load_config_btn = make_button("Load Config File")
        self.save_config_btn = make_button("Save Config File", "#301540")
        
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(4)
        btn_layout.addWidget(self.load_config_btn)
        btn_layout.addWidget(self.save_config_btn)
        self._layout.addLayout(btn_layout)

        # Row 2: Preview / Run / Cancel (Redundant, not added to layout to keep sidebar clean since they are in the top toolbar)
        self.preview_btn = make_button("BC Preview", "#1e2a38")
        self.run_mesh_btn = make_button("Mesh Generate", "#1e4620")
        self.cancel_mesh_btn = make_button("Cancel", "#4a1c1c")
        self.cancel_mesh_btn.setEnabled(False)

        # The former separate "Geometry Layers" (session checklist) and
        # "Geometry Input Files" (file list) overlapped, so they are merged into
        # the single geometry list in the "Domain & Geometry" section below. The
        # "Add All Sessions" button is created here and placed in that list's
        # button row.
        self.add_all_sessions_btn = make_button("Add All", "#1a2a3a")
        self.add_all_sessions_btn.setToolTip("Add all exported PreProcessor sessions to this mesh configuration")

        # ── 1. Domain & Geometry Files ────────────────────────────────────
        self.sec_domain = CollapsibleSection("Domain & Geometry", start_collapsed=False)
        self._layout.addWidget(self.sec_domain)

        # Domain source: the rectangular box, or a geometry acting as the outer
        # domain outline. When "Custom geometry" is chosen the box X/Y Min/Max are
        # hidden (the domain comes from whichever geometry has a Domain role in the
        # list below); "Rectangle box" shows them.
        dsrc_form = QFormLayout()
        self.domain_source_combo = QComboBox()
        self.domain_source_combo.addItems(["Rectangle box", "Custom geometry"])
        # #1: default to Custom geometry on first entry (set before the signal is
        # connected so the visibility handler isn't called before its widgets exist).
        self.domain_source_combo.setCurrentIndex(1)
        self.domain_source_combo.setStyleSheet(COMBO_STYLE)
        self.domain_source_combo.setToolTip(
            "Rectangle box: the domain is the X/Y Min/Max box below.\n"
            "Custom geometry: a geometry in the list is the outer domain — set its "
            "role to 'Domain: far-field' (external) or 'Domain: wall' (internal).")
        dsrc_form.addRow(help_label("Domain Source:",
            "Use the rectangular box, or a geometry as the outer domain outline"),
            self.domain_source_combo)
        align_form_labels(dsrc_form, 130)
        self.sec_domain.add_layout(dsrc_form)

        # Bounding box (shown only for the "Rectangle box" source)
        self._domain_box_widget = QWidget()
        dom_form = QFormLayout(self._domain_box_widget)
        dom_form.setContentsMargins(0, 0, 0, 0)
        self.domain_x_min = CleanDoubleSpinBox()
        self.domain_x_min.setRange(-1e6, 1e6)
        self.domain_x_min.setDecimals(4)
        self.domain_x_min.setStyleSheet(SPIN_STYLE)
        self.domain_x_min.setToolTip("Left boundary of the rectangular computational domain")

        self.domain_x_max = CleanDoubleSpinBox()
        self.domain_x_max.setRange(-1e6, 1e6)
        self.domain_x_max.setDecimals(4)
        self.domain_x_max.setStyleSheet(SPIN_STYLE)
        self.domain_x_max.setToolTip("Right boundary of the rectangular computational domain")

        self.domain_y_min = CleanDoubleSpinBox()
        self.domain_y_min.setRange(-1e6, 1e6)
        self.domain_y_min.setDecimals(4)
        self.domain_y_min.setStyleSheet(SPIN_STYLE)
        self.domain_y_min.setToolTip("Bottom boundary of the rectangular computational domain")

        self.domain_y_max = CleanDoubleSpinBox()
        self.domain_y_max.setRange(-1e6, 1e6)
        self.domain_y_max.setDecimals(4)
        self.domain_y_max.setStyleSheet(SPIN_STYLE)
        self.domain_y_max.setToolTip("Top boundary of the rectangular computational domain")

        dom_form.addRow(help_label("Domain X Min:", "Left boundary of the rectangular computational domain"), self.domain_x_min)
        dom_form.addRow(help_label("Domain X Max:", "Right boundary of the rectangular computational domain"), self.domain_x_max)
        dom_form.addRow(help_label("Domain Y Min:", "Bottom boundary of the rectangular computational domain"), self.domain_y_min)
        dom_form.addRow(help_label("Domain Y Max:", "Top boundary of the rectangular computational domain"), self.domain_y_max)
        align_form_labels(dom_form, 130)
        self.sec_domain.add_widget(self._domain_box_widget)

        # #4: the four rectangle-box edge patch names are edited in a POP-UP opened
        # from this button (right under the box), instead of a separate panel
        # section. Only meaningful for the rectangle box, so the button is hidden
        # for a custom domain (whose outer patches come from the outline's per-edge
        # CAD names). The dialog + its widgets are built lazily on first open.
        self.domain_patch_btn = make_button("Domain boundary patches…", "#243a52")
        self.domain_patch_btn.setToolTip(
            "Name the four rectangular-domain box edges (XMin/XMax/YMin/YMax) in a "
            "pop-up. The physical BC type is assigned per patch in the Solver → "
            "Boundary Conditions table (auto-detected from the generated mesh).")
        self.sec_domain.add_widget(self.domain_patch_btn)
        self.domain_patch_btn.clicked.connect(self._open_domain_patch_dialog)
        self._domain_patch_dialog = None

        self.domain_source_combo.currentIndexChanged.connect(self._update_domain_source_visibility)

        # Geometry file list (the single merged geometry list)
        geom_label = QLabel("Geometry files (add / assign role / remove):")
        geom_label.setStyleSheet("color: #a0b0d0; margin-top: 6px; font-weight: bold;")
        self.sec_domain.add_widget(help_widget(geom_label, "Geometry files to load for meshing"))

        self.geom_list_widget = QListWidget()
        self.geom_list_widget.setFixedHeight(80)
        self.geom_list_widget.setStyleSheet(
            "background: #181b2a; color: #a0a8c0; border: 1px solid #333852; border-radius: 3px;"
        )
        self.sec_domain.add_widget(help_widget(self.geom_list_widget, "List of geometry boundary files to include in the computational domain"))

        # Geometry list control buttons — two rows so four buttons don't force the
        # sidebar wider than its fixed width.
        self.add_active_geom_btn = make_button("Add Active", "#1a2525")
        self.add_active_geom_btn.setToolTip("Add the active PreProcessor resampled file")
        self.add_file_geom_btn = make_button("Browse", "#1d2a3a")
        self.remove_geom_btn = make_button("Remove", "#301a1a")

        geom_btn_row1 = QHBoxLayout(); geom_btn_row1.setSpacing(4)
        geom_btn_row1.addWidget(help_widget(self.add_all_sessions_btn, "Add all exported PreProcessor sessions"))
        geom_btn_row1.addWidget(help_widget(self.add_active_geom_btn, "Add the active PreProcessor resampled geometry"))
        geom_btn_row2 = QHBoxLayout(); geom_btn_row2.setSpacing(4)
        geom_btn_row2.addWidget(help_widget(self.add_file_geom_btn, "Browse for geometry files on disk"))
        geom_btn_row2.addWidget(help_widget(self.remove_geom_btn, "Remove selected geometry file from list"))
        self.sec_domain.add_layout(geom_btn_row1)
        self.sec_domain.add_layout(geom_btn_row2)

        # ── Geometry Role (Boundary vs Refinement Seed) ───────────────────
        # Set the role of the geometry SELECTED in the list above: a body-fitted
        # boundary (grows boundary layers) or a refinement seed (Pointwise-like
        # source that only drives a local minimum mesh size).
        role_label = QLabel("Selected Geometry Role:")
        role_label.setStyleSheet("color: #a0b0d0; margin-top: 6px; font-weight: bold;")
        self.sec_domain.add_widget(help_widget(role_label,
            "Set the role of the geometry selected in the list above."))

        role_form = QFormLayout()
        self.geom_role_combo = QComboBox()
        # Index order is relied on by _on_geom_selection_changed / _on_role_edited /
        # _update_role_visibility below — keep them in sync.
        self.geom_role_combo.addItems([
            "Boundary (grows BL)",              # 0 -> None (obstacle, BL outward)
            "No-BL (far-field size)",           # 1 -> {"role":"nobl"}
            "Seed (refinement source)",         # 2 -> {"role":"seed",...}
            "Domain: far-field (no BL)",        # 3 -> {"role":"farfield"}  (external)
            "Domain: wall (internal, BL in)",   # 4 -> {"role":"wall"}      (internal flow)
        ])
        self.geom_role_combo.setStyleSheet(COMBO_STYLE)
        self.geom_role_combo.setEnabled(False)
        self.geom_role_combo.setToolTip(
            "Boundary: grows a boundary layer (external-flow obstacle / wall) — default.\n"
            "No-BL: no boundary layer; the mesh conforms to it at far-field size.\n"
            "Seed: only drives a local minimum mesh size (no BL, not a boundary).\n"
            "Domain far-field: this closed outline is the outer domain (no BL, external flow).\n"
            "Domain wall: this closed outline is the outer domain and grows its BL inward "
            "(internal flow — mesh the interior).\n"
            "The rectangular box (Domain X/Y Min/Max) is used unless one geometry has a "
            "Domain role. At most one Domain geometry.")

        self.seed_size = CleanDoubleSpinBox()
        self.seed_size.setRange(0.0, 1e4)
        self.seed_size.setDecimals(5)
        self.seed_size.setSpecialValueText("auto")   # value 0 displays as "auto"
        self.seed_size.setStyleSheet(SPIN_STYLE)
        self.seed_size.setToolTip(
            "Target minimum element size at the seed "
            "(0 = auto: follows the seed's own resampled point spacing).")

        self.seed_radius = CleanDoubleSpinBox()
        self.seed_radius.setRange(0.0, 1e6)
        self.seed_radius.setDecimals(5)
        self.seed_radius.setSpecialValueText("auto")
        self.seed_radius.setStyleSheet(SPIN_STYLE)
        self.seed_radius.setToolTip(
            "Influence radius: beyond it the size returns to far-field "
            "(0 = auto: 100x the seed size). Can be set independently of size.")

        self.seed_mode = QComboBox()
        self.seed_mode.addItems(["source (sizing only)", "embed (conform)"])
        self.seed_mode.setStyleSheet(COMBO_STYLE)
        self.seed_mode.setToolTip(
            "source: mesh does NOT conform to the seed (pure sizing source).\n"
            "embed: mesh nodes conform to the seed curve (still no boundary layer).")

        # Per-geometry wall BC / patch name. #2: the inline "Wall BC" field was
        # REMOVED from the role editor — a geometry's wall patch is grouped in CAD
        # (Assign patch / group…) and its BC chosen in Edit segment BCs, so a
        # separate per-geometry field only re-appeared inconsistently (it showed
        # for geometries without segment BCs) and duplicated that flow. The widget
        # is kept alive (not placed in any layout, always hidden) so existing
        # per-geometry `bc` values still round-trip through the role data, and the
        # handlers/signal wiring referencing it stay valid.
        self.geom_bc_combo = QComboBox()
        self.geom_bc_combo.setEditable(True)
        self.geom_bc_combo.setStyleSheet(COMBO_STYLE)
        self.geom_bc_combo.setVisible(False)

        role_form.addRow(help_label("Role:", "Body-fitted boundary or refinement seed"), self.geom_role_combo)
        role_form.addRow(help_label("Seed Size:", "Target min element size at the seed (0 = auto: follows the seed's own point spacing)"), self.seed_size)
        role_form.addRow(help_label("Seed Radius:", "Influence radius (0 = auto ≈ 100x size); independent of seed size"), self.seed_radius)
        role_form.addRow(help_label("Seed Mode:", "source (sizing only) or embed (conform)"), self.seed_mode)

        # Per-geometry boundary layer is edited in a pop-up dialog; the panel's
        # BL sections below always edit the GLOBAL default. The button is enabled
        # only for BL-growing geometries (Boundary / Domain: wall).
        self.edit_bl_btn = make_button("Edit BL for this geometry…", "#243a52")
        self.edit_bl_btn.setToolTip(
            "Open a pop-up to give THIS geometry its own boundary layer "
            "(thickness, growth, layers, corners, transition). The BL sections "
            "in the panel below always edit the GLOBAL default.")
        self.edit_bl_btn.setEnabled(False)
        role_form.addRow(self.edit_bl_btn)

        # Per-segment BC: open a pop-up listing every segment of the selected
        # geometry (from its .meta sidecar) to assign a patch name / BC to each.
        # Enabled only when the geometry has a segmented .meta.
        self.edit_seg_bc_btn = make_button("Edit segment BCs…", "#243a52")
        self.edit_seg_bc_btn.setToolTip(
            "Open a pop-up listing every segment of THIS geometry and assign a "
            "patch name / BC to each (saved to the .meta sidecar). Available for "
            "geometries exported with segments from CAD.")
        self.edit_seg_bc_btn.setEnabled(False)
        role_form.addRow(self.edit_seg_bc_btn)

        # Per-segment boundary-layer toggle (#1): choose which segments of THIS
        # geometry grow a BL. Enabled for BL-growing geometries with a segmented
        # .meta (same availability as the per-segment BC editor, minus seeds).
        self.edit_seg_bl_btn = make_button("Edit segment BL…", "#243a52")
        self.edit_seg_bl_btn.setToolTip(
            "Open a pop-up to choose which segments of THIS geometry grow a "
            "boundary layer (per-edge BL on/off, saved to the .meta sidecar). "
            "Available for BL-growing geometries exported with segments from CAD.")
        self.edit_seg_bl_btn.setEnabled(False)
        role_form.addRow(self.edit_seg_bl_btn)

        align_form_labels(role_form, 130)
        self.sec_domain.add_layout(role_form)
        self._role_form = role_form
        self._role_updating = False

        # BL editing scope: None = global defaults, else the geom list item whose
        # per-geometry override the BL sections currently edit. _global_bl holds
        # the authoritative global values regardless of which scope is shown.
        self._bl_target_item = None
        self._global_bl: dict = {}
        self._bl_updating = False

        self.geom_list_widget.currentItemChanged.connect(self._on_geom_selection_changed)
        self.geom_role_combo.currentIndexChanged.connect(self._on_role_edited)
        self.seed_size.valueChanged.connect(self._on_role_edited)
        self.seed_radius.valueChanged.connect(self._on_role_edited)
        self.seed_mode.currentIndexChanged.connect(self._on_role_edited)
        self.geom_bc_combo.currentTextChanged.connect(self._on_geom_bc_edited)
        self.edit_bl_btn.clicked.connect(self._open_bl_override_dialog)
        self.edit_seg_bc_btn.clicked.connect(self._open_segment_bc_dialog)
        self.edit_seg_bl_btn.clicked.connect(self._open_segment_bl_dialog)
        # #4: per-group BC-type assignments (grouping name -> BC type), edited via
        # the segment-BC dialog and round-tripped through MeshConfig.group_bc.
        self._group_bc: dict = {}
        self._update_role_visibility()

        # ── 2. General Sizing ─────────────────────────────────────────────
        # #11: renamed back to "Mesh Sizing" (it covers surface + far-field, not
        # only the far field).
        self.sec_sizing = CollapsibleSection("Mesh Sizing", start_collapsed=True)
        self._layout.addWidget(self.sec_sizing)

        sizing_form = QFormLayout()
        self.surface_mesh_size = CleanDoubleSpinBox()
        self.surface_mesh_size.setRange(1e-4, 1e4)
        self.surface_mesh_size.setDecimals(4)
        self.surface_mesh_size.setStyleSheet(SPIN_STYLE)
        self.surface_mesh_size.setToolTip("Target element size along the geometry boundary walls")

        self.auto_surface_size = QCheckBox("Auto Surface Sizing")
        self.auto_surface_size.setStyleSheet("color:#a0a8c0;")
        self.auto_surface_size.setToolTip("Automatically determine surface mesh size from geometry spacing")

        # #6: when Auto Surface is on, show the size the mesher will derive (the
        # average resampled point spacing of the boundary geometries — the mesher
        # uses the average BL-front edge length, which equals that spacing).
        self.auto_surface_hint = QLabel("")
        self.auto_surface_hint.setWordWrap(True)
        self.auto_surface_hint.setStyleSheet("color:#6fae7a; font-size:10px;")
        self.auto_surface_hint.setVisible(False)

        self.farfield_mesh_size = CleanDoubleSpinBox()
        self.farfield_mesh_size.setRange(1e-4, 1e4)
        self.farfield_mesh_size.setDecimals(4)
        self.farfield_mesh_size.setStyleSheet(SPIN_STYLE)
        self.farfield_mesh_size.setToolTip("Target element size in the far-field region away from geometry")

        # #11: far-field size also gets an Auto option (mirrors Auto Surface).
        # When on, the mesher derives the far-field size from the domain extent;
        # the manual value stays visible as the fallback.
        self.auto_farfield_size = QCheckBox("Auto Far-field Sizing")
        self.auto_farfield_size.setStyleSheet("color:#a0a8c0;")
        self.auto_farfield_size.setToolTip(
            "Automatically determine the far-field mesh size from the domain "
            "extent (the manual value stays as a fallback).")

        # #6: when Auto Far-field is on, show the size the mesher will derive so
        # the user can see the computed value (updated as the domain changes).
        self.auto_farfield_hint = QLabel("")
        self.auto_farfield_hint.setWordWrap(True)
        self.auto_farfield_hint.setStyleSheet("color:#6fae7a; font-size:10px;")
        self.auto_farfield_hint.setVisible(False)

        self.farfield_growth_rate = CleanDoubleSpinBox()
        self.farfield_growth_rate.setRange(0.01, 10.0)
        self.farfield_growth_rate.setDecimals(4)
        self.farfield_growth_rate.setStyleSheet(SPIN_STYLE)
        self.farfield_growth_rate.setToolTip("Rate of element size expansion from the body/BL outward to the far-field (0.0~1.0)")

        # #7: bidirectional grading — also grow the size from the OUTER domain
        # boundary inward, with its own rate. Off = single direction (body
        # outward), the original behaviour. When on, the mesh stays fine near both
        # the body and the outer boundary and is coarsest in the middle.
        self.farfield_bidirectional = QCheckBox("Bidirectional (grade from outer boundary too)")
        self.farfield_bidirectional.setStyleSheet("color:#a0a8c0;")
        self.farfield_bidirectional.setToolTip(
            "Grade the far-field size from BOTH sides: the body/BL outward AND the "
            "outer domain boundary inward, each with its own growth rate (finest "
            "near both, coarsest in the middle). Off = grow only from the body.")

        self.farfield_growth_rate_outer = CleanDoubleSpinBox()
        self.farfield_growth_rate_outer.setRange(0.01, 10.0)
        self.farfield_growth_rate_outer.setDecimals(4)
        self.farfield_growth_rate_outer.setStyleSheet(SPIN_STYLE)
        self.farfield_growth_rate_outer.setToolTip("Rate of element size expansion inward from the outer domain boundary (bidirectional only)")

        # #11: Surface Size first, then its Auto toggle right after it; likewise
        # Far-field size then its Auto toggle. Ticking Auto no longer hides the
        # manual field (it stays as a fallback the mesher uses if auto can't
        # derive a value).
        sizing_form.addRow(help_label("Surface Size:", "Target element size along the geometry boundary walls"), self.surface_mesh_size)
        sizing_form.addRow("", help_widget(self.auto_surface_size, "Automatically determine surface mesh size from geometry spacing"))
        sizing_form.addRow("", self.auto_surface_hint)
        sizing_form.addRow(help_label("Far-field Size:", "Target element size in the far-field region away from geometry"), self.farfield_mesh_size)
        sizing_form.addRow("", help_widget(self.auto_farfield_size, "Automatically determine the far-field mesh size from the domain extent"))
        sizing_form.addRow("", self.auto_farfield_hint)
        sizing_form.addRow(help_label("Growth Rate:", "Rate of element size expansion from the body/BL outward (0.0~1.0)"), self.farfield_growth_rate)
        sizing_form.addRow("", help_widget(self.farfield_bidirectional, "Also grade the far-field size inward from the outer domain boundary, with its own rate"))
        sizing_form.addRow(help_label("Outer Growth Rate:", "Rate of element size expansion inward from the outer domain boundary (bidirectional only)"), self.farfield_growth_rate_outer)
        align_form_labels(sizing_form, 130)
        self.sec_sizing.add_layout(sizing_form)
        self._sizing_form = sizing_form

        # #6: refresh the computed-size hints when the relevant Auto toggles or the
        # domain box changes (custom-domain extent refreshes via set_config /
        # domain-source changes).
        self.auto_farfield_size.toggled.connect(self._update_auto_farfield_hint)
        self.auto_surface_size.toggled.connect(self._update_auto_surface_hint)
        for _sb in (self.domain_x_min, self.domain_x_max,
                    self.domain_y_min, self.domain_y_max):
            _sb.valueChanged.connect(self._update_auto_farfield_hint)
        # #7: show/hide the outer growth rate with the bidirectional toggle.
        self.farfield_bidirectional.toggled.connect(self._update_bidirectional_visibility)
        self._update_bidirectional_visibility()

        # ── Boundary Layer (global default) ───────────────────────────────
        # The BL parameters are edited in a pop-up (same dialog as the
        # per-geometry override), not duplicated as inline panel fields.
        self.sec_bl = CollapsibleSection("Boundary Layer", start_collapsed=False)
        self._layout.addWidget(self.sec_bl)
        self.edit_global_bl_btn = make_button(
            "Edit boundary layer (global default)…", "#243a52")
        self.edit_global_bl_btn.setToolTip(
            "Edit the GLOBAL boundary-layer parameters (used by every geometry "
            "without a per-geometry override). Same fields as the per-geometry "
            "Edit BL dialog.")
        self.sec_bl.add_widget(self.edit_global_bl_btn)
        self.edit_global_bl_btn.clicked.connect(self._open_global_bl_dialog)

        # ── 3. Boundary Layer Core ────────────────────────────────────────
        # Kept alive to back the global-BL store, but hidden — the params live in
        # the Edit-BL dialog now (see #5). Same for Convex/Concave/Transition BL.
        self.sec_bl_core = CollapsibleSection("Boundary Layer Core", start_collapsed=True)
        self._layout.addWidget(self.sec_bl_core)

        bl_form = QFormLayout()
        self.bl_initial_thickness = CleanDoubleSpinBox()
        self.bl_initial_thickness.setRange(1e-6, 1.0)
        self.bl_initial_thickness.setDecimals(6)
        self.bl_initial_thickness.setStyleSheet(SPIN_STYLE)
        self.bl_initial_thickness.setToolTip("Height of the first boundary layer cell adjacent to the wall")

        self.bl_growth_rate = CleanDoubleSpinBox()
        self.bl_growth_rate.setRange(1.001, 5.0)
        self.bl_growth_rate.setDecimals(4)
        self.bl_growth_rate.setStyleSheet(SPIN_STYLE)
        self.bl_growth_rate.setToolTip("Multiplicative growth factor between successive BL layers (e.g. 1.2 = 20% increase per layer)")

        self.bl_layers = QSpinBox()
        self.bl_layers.setRange(0, 100)
        self.bl_layers.setStyleSheet(SPIN_STYLE)
        self.bl_layers.setToolTip("Total number of structured boundary layer rows to generate")

        bl_form.addRow(help_label("Initial Thick:", "Height of the first boundary layer cell adjacent to the wall"), self.bl_initial_thickness)
        bl_form.addRow(help_label("Growth Rate:", "Multiplicative growth factor between successive BL layers (e.g. 1.2 = 20% increase per layer)"), self.bl_growth_rate)
        bl_form.addRow(help_label("Layers:", "Total number of structured boundary layer rows to generate"), self.bl_layers)
        align_form_labels(bl_form, 130)
        self.sec_bl_core.add_layout(bl_form)

        # ── 4. Transition & Meshing Algorithm ─────────────────────────────
        self.sec_transition = CollapsibleSection("Transition & Meshing Algorithm", start_collapsed=True)
        self._layout.addWidget(self.sec_transition)

        trans_form = QFormLayout()
        self.bl_transition_layers = QSpinBox()
        self.bl_transition_layers.setRange(0, 100)
        self.bl_transition_layers.setStyleSheet(SPIN_STYLE)
        self.bl_transition_layers.setToolTip("Number of transitional element rows blending BL quads into far-field triangles")

        self.bl_auto_transition_layers = QComboBox()
        self.bl_auto_transition_layers.addItems(["0: OFF", "1: GLOBAL", "2: LOCAL"])
        self.bl_auto_transition_layers.setCurrentIndex(2)  # #4: default LOCAL
        self.bl_auto_transition_layers.setStyleSheet(COMBO_STYLE)
        self.bl_auto_transition_layers.setToolTip("Automatically compute transition layer count (OFF / GLOBAL / LOCAL)")

        self.bl_transition_growth_rate = CleanDoubleSpinBox()
        self.bl_transition_growth_rate.setRange(1.001, 5.0)
        self.bl_transition_growth_rate.setDecimals(4)
        self.bl_transition_growth_rate.setStyleSheet(SPIN_STYLE)
        self.bl_transition_growth_rate.setToolTip("Growth rate applied within the transition zone between BL and far-field")

        self.bl_transition_buffer = CleanDoubleSpinBox()
        self.bl_transition_buffer.setRange(0.0, 100.0)
        self.bl_transition_buffer.setDecimals(4)
        self.bl_transition_buffer.setStyleSheet(SPIN_STYLE)
        self.bl_transition_buffer.setToolTip("Buffer distance multiplier around geometry for transition smoothing")

        self.gmsh_algorithm = QComboBox()
        self.gmsh_algorithm.addItems([
            "1: MeshAdapt",
            "2: Automatic",
            "5: Delaunay",
            "6: Frontal-Delaunay",
            "7: BAMG",
            "8: Frontal-Delaunay Quads"
        ])
        self.gmsh_algorithm.setStyleSheet(COMBO_STYLE)
        self.gmsh_algorithm.setToolTip("Meshing algorithm used by Gmsh for far-field triangulation")

        self.gmsh_optimize = QCheckBox("Optimize Mesh Quality")
        self.gmsh_optimize.setStyleSheet("color:#a0a8c0;")
        self.gmsh_optimize.setToolTip("Enable Gmsh mesh quality optimization pass after generation")

        self.bl_use_analytic_geom = QCheckBox("Analytic BL Normals (line/circle)")
        self.bl_use_analytic_geom.setStyleSheet("color:#a0a8c0;")
        self.bl_use_analytic_geom.setToolTip(
            "Grow the boundary layer along exact analytic normals on line/circle surface "
            "segments (instead of finite differences). No effect on smooth/polyline bodies. "
            "Uses the curve kind carried in the geometry's .meta sidecar.")

        trans_form.addRow(self._mesh_sublabel("BOUNDARY-LAYER TRANSITION"))
        trans_form.addRow(help_label("Auto Transition:", "Automatically compute transition layer count (OFF / GLOBAL / LOCAL)"), self.bl_auto_transition_layers)
        trans_form.addRow(help_label("Transition Layers:", "Number of transitional element rows blending BL quads into far-field triangles"), self.bl_transition_layers)
        trans_form.addRow(help_label("Trans Growth Rate:", "Growth rate applied within the transition zone between BL and far-field"), self.bl_transition_growth_rate)
        trans_form.addRow(help_label("Trans Buffer:", "Buffer distance multiplier around geometry for transition smoothing"), self.bl_transition_buffer)
        trans_form.addRow(self._mesh_sublabel("FAR-FIELD MESHING"))
        trans_form.addRow(help_label("Gmsh Algorithm:", "Meshing algorithm used by Gmsh for far-field triangulation"), self.gmsh_algorithm)
        trans_form.addRow("", help_widget(self.gmsh_optimize, "Enable Gmsh mesh quality optimization pass after generation"))
        trans_form.addRow("", help_widget(self.bl_use_analytic_geom,
            "Grow the boundary layer along exact analytic normals on line/circle surfaces"))
        align_form_labels(trans_form, 130)
        self.sec_transition.add_layout(trans_form)
        self._trans_form = trans_form
        self.bl_auto_transition_layers.currentIndexChanged.connect(self._update_transition_visibility)
        self._update_transition_visibility()

        # ── 5. Fan & Convex Corner Handling ────────────────────────────────
        self.sec_convex = CollapsibleSection("Convex Corner Handling", start_collapsed=True)
        self._layout.addWidget(self.sec_convex)

        self.convex_form = QFormLayout()
        self.bl_convex_method = QComboBox()
        self.bl_convex_method.addItems(["0: Fan", "2: Parallelogram"])
        self.bl_convex_method.setStyleSheet(COMBO_STYLE)
        self.bl_convex_method.setCurrentIndex(1)  # Default: Parallelogram
        self.bl_convex_method.setToolTip("Method for handling convex (outward-pointing) corners in the boundary layer")

        self.bl_fan_nodes = QSpinBox()
        self.bl_fan_nodes.setRange(1, 100)
        self.bl_fan_nodes.setStyleSheet(SPIN_STYLE)
        self.bl_fan_nodes.setToolTip("Number of fan elements inserted at convex corners (Fan method only)")

        self.bl_auto_fan_nodes = QCheckBox("Auto Fan Nodes")
        self.bl_auto_fan_nodes.setStyleSheet("color:#a0a8c0;")
        self.bl_auto_fan_nodes.setToolTip("Automatically determine fan node count based on corner angle")

        self.bl_fan_angle_threshold = CleanDoubleSpinBox()
        self.bl_fan_angle_threshold.setRange(0.0, 360.0)
        self.bl_fan_angle_threshold.setDecimals(2)
        self.bl_fan_angle_threshold.setStyleSheet(SPIN_STYLE)
        self.bl_fan_angle_threshold.setToolTip("Minimum corner angle (degrees) to trigger fan insertion")

        self.bl_convex_angle_threshold = CleanDoubleSpinBox()
        self.bl_convex_angle_threshold.setRange(0.0, 360.0)
        self.bl_convex_angle_threshold.setDecimals(2)
        self.bl_convex_angle_threshold.setStyleSheet(SPIN_STYLE)
        self.bl_convex_angle_threshold.setToolTip("Angle threshold to classify a corner as convex")

        self.bl_para_fallback_angle = CleanDoubleSpinBox()
        self.bl_para_fallback_angle.setRange(0.0, 360.0)
        self.bl_para_fallback_angle.setDecimals(2)
        self.bl_para_fallback_angle.setStyleSheet(SPIN_STYLE)
        self.bl_para_fallback_angle.setToolTip("When corner angle exceeds this, fall back to parallelogram method")

        self.convex_form.addRow(help_label("Convex Method:", "Method for handling convex (outward-pointing) corners in the boundary layer"), self.bl_convex_method)
        self.convex_form.addRow(help_label("Fan Nodes:", "Number of fan elements inserted at convex corners (Fan method only)"), self.bl_fan_nodes)
        self.convex_form.addRow("", help_widget(self.bl_auto_fan_nodes, "Automatically determine fan node count based on corner angle"))
        self.convex_form.addRow(help_label("Fan Threshold (deg):", "Minimum corner angle (degrees) to trigger fan insertion"), self.bl_fan_angle_threshold)
        self.convex_form.addRow(help_label("Convex Threshold (deg):", "Angle threshold to classify a corner as convex"), self.bl_convex_angle_threshold)
        self.convex_form.addRow(help_label("Fallback Angle (deg):", "When corner angle exceeds this, fall back to parallelogram method"), self.bl_para_fallback_angle)
        align_form_labels(self.convex_form, 130)
        self.sec_convex.add_layout(self.convex_form)

        # Wire visibility updates for Fan parameters
        self.bl_convex_method.currentIndexChanged.connect(self._update_convex_widgets_visibility)
        self._update_convex_widgets_visibility()

        # ── 6. Concave Corner Handling ────────────────────────────────────
        self.sec_concave = CollapsibleSection("Concave Corner Handling", start_collapsed=True)
        self._layout.addWidget(self.sec_concave)

        concave_form = QFormLayout()
        self.bl_concave_method = QComboBox()
        self.bl_concave_method.addItems(["5: Thickness Blending"])
        self.bl_concave_method.setStyleSheet(COMBO_STYLE)
        self.bl_concave_method.setToolTip("Method for handling concave (inward-pointing) corners in the boundary layer")

        self.bl_concave_angle_threshold = CleanDoubleSpinBox()
        self.bl_concave_angle_threshold.setRange(0.0, 360.0)
        self.bl_concave_angle_threshold.setDecimals(2)
        self.bl_concave_angle_threshold.setStyleSheet(SPIN_STYLE)
        self.bl_concave_angle_threshold.setToolTip("Angle threshold to classify a corner as concave")

        self.bl_concave_influence_multiplier = CleanDoubleSpinBox()
        self.bl_concave_influence_multiplier.setRange(0.0, 100.0)
        self.bl_concave_influence_multiplier.setDecimals(2)
        self.bl_concave_influence_multiplier.setStyleSheet(SPIN_STYLE)
        self.bl_concave_influence_multiplier.setToolTip("Controls how far the concave corner correction propagates along the wall")

        self.bl_merge_concave = QCheckBox("Merge Concave")
        self.bl_merge_concave.setStyleSheet("color:#a0a8c0;")
        self.bl_merge_concave.setToolTip("Merge nearby concave corners into a single correction zone")

        self.bl_smoothing_iters = QSpinBox()
        self.bl_smoothing_iters.setRange(0, 100)
        self.bl_smoothing_iters.setStyleSheet(SPIN_STYLE)
        self.bl_smoothing_iters.setToolTip("Number of Laplacian smoothing passes applied to BL cells near concave corners")

        concave_form.addRow(help_label("Concave Method:", "Method for handling concave (inward-pointing) corners in the boundary layer"), self.bl_concave_method)
        concave_form.addRow(help_label("Concave Threshold:", "Angle threshold to classify a corner as concave"), self.bl_concave_angle_threshold)
        concave_form.addRow(help_label("Influence Mult:", "Controls how far the concave corner correction propagates along the wall"), self.bl_concave_influence_multiplier)
        concave_form.addRow("", help_widget(self.bl_merge_concave, "Merge nearby concave corners into a single correction zone"))
        concave_form.addRow(help_label("Smoothing Iters:", "Number of Laplacian smoothing passes applied to BL cells near concave corners"), self.bl_smoothing_iters)
        align_form_labels(concave_form, 130)
        self.sec_concave.add_layout(concave_form)

        # ── Meshing Algorithm (the global-only params not in the BL dialog) ──
        # gmsh algorithm/optimize + concave merge/smoothing are meshing options
        # (not per-geometry BL), so they stay in the panel while the BL sections
        # (Core/Convex/Concave/Transition) are hidden — their fields are edited
        # in the Edit-BL dialog instead (#5). Re-adding these widgets here moves
        # them out of the now-hidden sections.
        self.sec_meshing = CollapsibleSection("Meshing Algorithm", start_collapsed=True)
        self._layout.addWidget(self.sec_meshing)
        mesh_algo_form = QFormLayout()
        mesh_algo_form.addRow(help_label("Gmsh Algorithm:", "Meshing algorithm used by Gmsh for far-field triangulation"), self.gmsh_algorithm)
        mesh_algo_form.addRow("", help_widget(self.gmsh_optimize, "Enable Gmsh mesh quality optimization pass after generation"))
        mesh_algo_form.addRow("", help_widget(self.bl_merge_concave, "Merge nearby concave corners into a single correction zone"))
        mesh_algo_form.addRow(help_label("Smoothing Iters:", "Laplacian smoothing passes applied to BL cells near concave corners"), self.bl_smoothing_iters)
        align_form_labels(mesh_algo_form, 130)
        self.sec_meshing.add_layout(mesh_algo_form)

        # Hide the BL parameter sections — their fields now live in the Edit-BL
        # dialog (global + per-geometry). The widgets stay alive to back the
        # global-BL store / round-trip.
        for _sec in (self.sec_bl_core, self.sec_convex, self.sec_concave,
                     self.sec_transition):
            _sec.setVisible(False)

        # ── 7. Domain Boundary Patches (rectangle-box edges only) ─────────
        # Only relevant when Domain Source is "Rectangle box"; names the four box
        # edges. The NAME is a patch/grouping label — the physical BC TYPE is
        # assigned per patch later in the Solver → Boundary Conditions table
        # (auto-detected from the mesh), matching industrial software. #4: these
        # live in a pop-up (built into self._domain_patch_body, shown by
        # _open_domain_patch_dialog via the "Domain boundary patches…" button
        # above) instead of a panel section.
        self._domain_patch_body = QWidget()
        io_form = QFormLayout(self._domain_patch_body)
        io_form.setContentsMargins(0, 0, 0, 0)

        self.bc_xmin = BCWidget()
        self.bc_xmin_indicator = self.bc_xmin.indicator
        self.bc_xmin.setToolTip("Patch name for the left domain-box edge")

        self.bc_xmax = BCWidget()
        self.bc_xmax_indicator = self.bc_xmax.indicator
        self.bc_xmax.setToolTip("Patch name for the right domain-box edge")

        self.bc_ymin = BCWidget()
        self.bc_ymin_indicator = self.bc_ymin.indicator
        self.bc_ymin.setToolTip("Patch name for the bottom domain-box edge")

        self.bc_ymax = BCWidget()
        self.bc_ymax_indicator = self.bc_ymax.indicator
        self.bc_ymax.setToolTip("Patch name for the top domain-box edge")

        # Names the four rectangular-domain edges; the physical BC type is set
        # per patch in the Solver stage (auto-detected from the generated mesh).
        self._bc_intro_hint = QLabel(
            "Names the four rectangular-domain box edges (patch labels). The "
            "physical BC type is assigned per patch in the Solver → Boundary "
            "Conditions table, auto-detected from the generated mesh.")
        self._bc_intro_hint.setWordWrap(True)
        self._bc_intro_hint.setStyleSheet("color:#8a93ad; font-size:10px;")

        io_form.addRow(self._bc_intro_hint)
        io_form.addRow(help_label("XMin patch:", "Patch name for the left domain-box edge"), self.bc_xmin)
        io_form.addRow(help_label("XMax patch:", "Patch name for the right domain-box edge"), self.bc_xmax)
        io_form.addRow(help_label("YMin patch:", "Patch name for the bottom domain-box edge"), self.bc_ymin)
        io_form.addRow(help_label("YMax patch:", "Patch name for the top domain-box edge"), self.bc_ymax)
        # Narrow label column: the labels are short so a wide right-aligned column
        # left a big gap and stole width from the BCWidget fields (overflow).
        align_form_labels(io_form, 90)
        io_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        io_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self._io_form = io_form

        # ── 8. Output ─────────────────────────────────────────────────────
        self.sec_output = CollapsibleSection("Output", start_collapsed=True)
        self._layout.addWidget(self.sec_output)

        self.output_filename = QLineEdit()
        self.output_filename.setStyleSheet(LINEEDIT_STYLE)
        self.output_filename.setToolTip("Base filename for mesh output files (extension .* means all formats)")
        # Track whether the user typed a custom output name. While it's still an
        # auto-generated name, set_config refreshes it from the current geometry
        # so different geometries export to different mesh files.
        self._output_name_user_set = False
        self.output_filename.textEdited.connect(
            lambda _t: setattr(self, "_output_name_user_set", True))

        # #5: each write-format is a checkable toggle BUTTON (highlighted green
        # when on) instead of a checkbox — a click selects whether that format is
        # written on Generate. isChecked()/setChecked() keep working, so set_config
        # / get_config are unchanged.
        def _fmt_btn(text):
            b = make_button(text, "#181b2a", border="#2d3356",
                            hover_border="#5a9ad4", checked_bg="#1e4620")
            b.setCheckable(True)
            return b

        self.export_vtk = _fmt_btn("VTK")
        self.export_vtk.setToolTip("Write a .vtk file when the mesh is generated/saved.")
        self.export_starcd = _fmt_btn("STAR-CD")
        self.export_starcd.setToolTip(
            "Write STAR-CD files (.vrt/.cel/.bnd) when the mesh is generated/saved "
            "(required for the solver).")
        self.export_cgns = _fmt_btn("CGNS")
        self.export_cgns.setToolTip(
            "Write a CGNS file (.cgns; unstructured zone + per-BC patches) when the "
            "mesh is generated. Ignored if HybMesh2D was built without the CGNS library.")
        self.enable_collision_detection = QCheckBox("Collision Detection")
        self.enable_collision_detection.setStyleSheet("color:#a0a8c0;")
        self.enable_collision_detection.setToolTip("Enable self-intersection detection during boundary layer generation")

        # #5: an explicit Export button (write the generated mesh in the enabled
        # formats to a chosen location) — the per-format action buttons removed in
        # batch 6 left no output action in this panel. Emits export_mesh_requested,
        # wired by the controller to the same save flow as the Results panel.
        self.export_mesh_btn = make_button("Export mesh…", "#243a52")
        self.export_mesh_btn.setToolTip(
            "Save the generated mesh (in the enabled write formats above) to a "
            "chosen location. Generates first if no mesh exists yet.")

        out_form = QFormLayout()
        out_form.addRow(help_label("Output File:", "Base filename for mesh output files (extension .* means all formats)"), self.output_filename)
        out_form.addRow("", help_widget(self.enable_collision_detection, "Enable self-intersection detection during boundary layer generation"))

        # #5/#8: unified output — each write-format is a checkable toggle button
        # (which files to write on generate). #8-2: one per row (the single row was
        # too wide for the sidebar). Export-to-a-chosen-path uses the Export button
        # below (and the Results panel's Save VTK… / Save STAR-CD…).
        export_layout = QVBoxLayout()
        export_layout.setSpacing(4)
        export_layout.addWidget(help_widget(self.export_vtk, "Write a .vtk file when the mesh is generated"))
        export_layout.addWidget(help_widget(self.export_starcd, "Write STAR-CD files (.vrt/.cel/.bnd) when the mesh is generated (required for the solver)"))
        export_layout.addWidget(help_widget(self.export_cgns, "Write a CGNS file when the mesh is generated"))
        out_form.addRow(help_label("Write formats:", "Which mesh files to write when you generate. Use Export mesh… to save them to a specific path."), export_layout)
        out_form.addRow("", help_widget(self.export_mesh_btn, "Save the generated mesh in the enabled formats to a chosen location"))
        align_form_labels(out_form, 90)
        out_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        out_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.sec_output.add_layout(out_form)

        # Spacer at the end
        self._layout.addStretch()

        # Connect internal Browse button
        self.add_file_geom_btn.clicked.connect(self._on_browse_geom)
        self.remove_geom_btn.clicked.connect(self._on_remove_geom)
        self.export_mesh_btn.clicked.connect(self.export_mesh_requested)  # #5

        # Connect BC textChanged signals
        self.bc_xmin.textChanged.connect(self._update_bc_indicators)
        self.bc_xmax.textChanged.connect(self._update_bc_indicators)
        self.bc_ymin.textChanged.connect(self._update_bc_indicators)
        self.bc_ymax.textChanged.connect(self._update_bc_indicators)

        # Route every BL-section edit through one handler so it lands in either
        # the global defaults or the selected geometry's override.
        self._wire_bl_widgets()
        self._global_bl = self._read_bl_widgets()

        self._update_domain_source_visibility()

    # ── Per-geometry boundary layer (inline) ──────────────────────────────
    def _wire_bl_widgets(self):
        """Connect every BL-section widget's change signal to _on_bl_widget_changed."""
        for w in (self.bl_initial_thickness, self.bl_growth_rate, self.bl_layers,
                  self.bl_fan_nodes, self.bl_fan_angle_threshold,
                  self.bl_convex_angle_threshold, self.bl_para_fallback_angle,
                  self.bl_concave_angle_threshold, self.bl_concave_influence_multiplier,
                  self.bl_transition_layers, self.bl_transition_growth_rate,
                  self.bl_transition_buffer):
            w.valueChanged.connect(self._on_bl_widget_changed)
        for w in (self.bl_convex_method, self.bl_concave_method,
                  self.bl_auto_transition_layers):
            w.currentIndexChanged.connect(self._on_bl_widget_changed)
        for w in (self.bl_auto_fan_nodes, self.bl_use_analytic_geom):
            w.toggled.connect(self._on_bl_widget_changed)

    def _read_bl_widgets(self) -> dict:
        """Current BL-section widget values as a {KEY: value} dict (KEYs match
        _BL_OVERRIDE_KEYS / the .dat parameter names)."""
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
        # Per-segment BL button: same segmented-.meta requirement, but only for
        # BL-growing geometries (Boundary / Domain: wall) — a no-BL/far-field body
        # has no layer to toggle per edge.
        self.edit_seg_bl_btn.setEnabled(seg_ok and grows_bl)

    def _segment_highlighter(self, path):
        """Build a canvas-highlight callback for a geometry's segments: maps each
        seg id to its points (from the .meta POINTS block) and emits them (NaN-
        separated) on segment_highlight_requested. Shared by the segment BC / BL
        pop-ups. Returns the callback."""
        from app.services.meta_io import read_meta_point_segids
        coords_by_sid: dict[int, object] = {}
        try:
            import numpy as np
            pts = np.atleast_2d(np.loadtxt(path))
            sids = read_meta_point_segids(path)
            if pts.shape[0] and len(sids) == pts.shape[0]:
                for sid in {s for s in sids if s >= 0}:
                    idxs = [i for i, s in enumerate(sids) if s == sid]
                    if idxs:
                        coords_by_sid[sid] = pts[idxs][:, :2]
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
        accepted = dlg.exec() == QDialog.DialogCode.Accepted
        self.segment_highlight_requested.emit(None)  # clear the highlight
        if accepted:
            self._group_bc = dlg.result_group_bc()
            self.mesh_config_changed.emit(self.get_config())

    def _open_segment_bl_dialog(self):
        """Pop up the per-segment BL toggle for the selected geometry (#1) and
        write the grow-BL flags back to its .meta sidecar (v3 column). The mesher
        skips BL growth on segments flagged off at the next generation."""
        item = self.geom_list_widget.currentItem()
        if item is None:
            return
        path = item.data(Qt.ItemDataRole.UserRole)
        if not path:
            return
        from app.services.meta_io import (read_meta_segments, read_meta_seg_growbl,
                                           write_meta_seg_growbl)
        segs = read_meta_segments(path)
        if not segs:
            return
        dlg = SegmentBLDialog(item.text(), segs, seg_grow=read_meta_seg_growbl(path),
                              highlight_cb=self._segment_highlighter(path), parent=self)
        accepted = dlg.exec() == QDialog.DialogCode.Accepted
        self.segment_highlight_requested.emit(None)
        if accepted and write_meta_seg_growbl(path, dlg.result_seg_grow()):
            self.mesh_config_changed.emit(self.get_config())

    def _open_global_bl_dialog(self):
        """Edit the GLOBAL boundary-layer parameters in the pop-up dialog."""
        dlg = PerGeomBLDialog("Global default", dict(self._global_bl),
                              dict(self._global_bl), self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        vals = dlg.result_params()
        if vals is None:   # "Use Global" is a no-op when editing the global itself
            return
        self._global_bl = vals
        self._write_bl_widgets(vals)  # keep the (hidden) backing widgets in sync
        self.mesh_config_changed.emit(self.get_config())

    def _open_bl_override_dialog(self):
        """Pop up the per-geometry BL editor for the selected geometry."""
        item = self.geom_list_widget.currentItem()
        if item is None:
            return
        idx = self.geom_role_combo.currentIndex()
        if idx not in (0, 4):
            return
        rinfo = dict(item.data(self._ROLE_DATA) or {})
        dlg = PerGeomBLDialog(item.text(), dict(self._global_bl),
                              rinfo.get("bl_params"), self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
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
        self._sync_bl_scope()
        self.mesh_config_changed.emit(self.get_config())

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

    def _update_domain_source_visibility(self):
        """Show the rectangular box X/Y Min/Max only when Domain Source is
        'Rectangle box'; hide them for 'Custom geometry' (the domain then comes
        from a geometry with a Domain role).

        The domain-box edge patches only apply to the rectangle box, so the button
        that opens their pop-up (#4) is hidden for a custom domain (whose
        outer-boundary patches come from the outline's per-edge CAD names). The
        canvas is told to drop the rectangular box + its patch colours."""
        is_custom = self.domain_source_combo.currentIndex() == 1
        self._domain_box_widget.setVisible(not is_custom)
        self.domain_patch_btn.setVisible(not is_custom)
        if is_custom and self._domain_patch_dialog is not None:
            self._domain_patch_dialog.hide()   # not applicable to a custom domain

        # #6: the auto far-field size estimate depends on the domain source.
        self._update_auto_farfield_hint()

        self.domain_source_changed.emit(is_custom)

    def _open_domain_patch_dialog(self):
        """#4: pop-up to name the four rectangle-box edges (built lazily). The
        BCWidget edits commit live (read back by get_config at generate time), so
        the dialog only needs a Close button — no explicit Apply."""
        if self._domain_patch_dialog is None:
            dlg = QDialog(self)
            dlg.setWindowTitle("Domain boundary patches")
            dlg.setStyleSheet("background:#121422; color:#cdd6f4;")
            dlg.setMinimumWidth(360)
            lay = QVBoxLayout(dlg)
            lay.setContentsMargins(10, 10, 10, 10)
            lay.setSpacing(6)
            lay.addWidget(self._domain_patch_body)
            buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
            buttons.rejected.connect(dlg.reject)
            buttons.accepted.connect(dlg.accept)
            lay.addWidget(buttons)
            keep_on_top(dlg)   # #2: never sink below the main window
            self._domain_patch_dialog = dlg
        self._domain_patch_dialog.show()
        self._domain_patch_dialog.raise_()
        self._domain_patch_dialog.activateWindow()

    def _domain_extent(self) -> float | None:
        """Largest side of the computational domain, matching the C++ far-field
        heuristic (max(xMax-xMin, yMax-yMin)). Rectangle box → the box; custom →
        the bounds of the Domain-role geometry, else the union of all listed
        geometries. Returns None when it can't be determined."""
        is_custom = self.domain_source_combo.currentIndex() == 1
        if not is_custom:
            dx = self.domain_x_max.value() - self.domain_x_min.value()
            dy = self.domain_y_max.value() - self.domain_y_min.value()
            ext = max(dx, dy)
            return ext if ext > 0 else None
        # Custom domain: read geometry bounds (prefer a Domain-role geometry).
        try:
            import numpy as np
        except Exception:
            return None
        domain_paths, other_paths = [], []
        for row in range(self.geom_list_widget.count()):
            it = self.geom_list_widget.item(row)
            p = it.data(Qt.ItemDataRole.UserRole)
            if not p:
                continue
            rinfo = it.data(self._ROLE_DATA) or {}
            (domain_paths if rinfo.get("role") in ("farfield", "wall")
             else other_paths).append(p)
        xmin = ymin = float("inf")
        xmax = ymax = float("-inf")
        for p in (domain_paths or other_paths):
            try:
                pts = np.atleast_2d(np.loadtxt(p))
                if pts.size == 0 or pts.shape[1] < 2:
                    continue
                xmin = min(xmin, float(np.nanmin(pts[:, 0])))
                xmax = max(xmax, float(np.nanmax(pts[:, 0])))
                ymin = min(ymin, float(np.nanmin(pts[:, 1])))
                ymax = max(ymax, float(np.nanmax(pts[:, 1])))
            except Exception:
                continue
        if xmax > xmin or ymax > ymin:
            return max(xmax - xmin, ymax - ymin)
        return None

    def _update_auto_farfield_hint(self, *args):
        """#6: when Auto Far-field Sizing is on, show the far-field size the mesher
        will derive from the domain extent (5% of the larger side). The mesher also
        clamps it to be >= the last BL thickness, which isn't known in the GUI."""
        on = self.auto_farfield_size.isChecked()
        self.auto_farfield_hint.setVisible(on)
        if not on:
            return
        extent = self._domain_extent()
        if extent and extent > 0:
            size = extent * 0.05
            self.auto_farfield_hint.setText(
                f"Auto far-field ≈ {size:.4g}  (5% of domain extent {extent:.4g}; "
                "the mesher clamps it to ≥ the last BL thickness)")
        else:
            self.auto_farfield_hint.setText(
                "Auto far-field: computed from the domain extent at mesh time.")

    def _surface_spacing_estimate(self) -> float | None:
        """Average adjacent-point spacing across the boundary geometries — the
        value the mesher's Auto Surface size resolves to (it averages the BL-front
        edge lengths, which equal the surface point spacing). None if it can't be
        determined (no boundary geometry / unreadable files)."""
        try:
            import numpy as np
        except Exception:
            return None
        total = 0.0
        count = 0
        for row in range(self.geom_list_widget.count()):
            it = self.geom_list_widget.item(row)
            p = it.data(Qt.ItemDataRole.UserRole)
            if not p:
                continue
            role = (it.data(self._ROLE_DATA) or {}).get("role")
            if role in ("seed", "farfield"):   # not body-fitted surfaces
                continue
            try:
                pts = np.atleast_2d(np.loadtxt(p))
                if pts.shape[0] < 2 or pts.shape[1] < 2:
                    continue
                d = np.diff(pts[:, :2], axis=0)
                seg = np.sqrt((d * d).sum(axis=1))
                seg = seg[np.isfinite(seg) & (seg > 0)]   # skip NaN piece-breaks
                if seg.size:
                    total += float(seg.sum())
                    count += int(seg.size)
            except Exception:
                continue
        return (total / count) if count else None

    def _update_auto_surface_hint(self, *args):
        """#6: when Auto Surface Sizing is on, show the size the mesher will
        derive (average boundary point spacing)."""
        on = self.auto_surface_size.isChecked()
        self.auto_surface_hint.setVisible(on)
        if not on:
            return
        size = self._surface_spacing_estimate()
        if size and size > 0:
            self.auto_surface_hint.setText(
                f"Auto surface ≈ {size:.4g}  (average boundary point spacing)")
        else:
            self.auto_surface_hint.setText(
                "Auto surface: computed from the boundary point spacing at mesh time.")

    def _update_bidirectional_visibility(self, *args):
        """#7: show the Outer Growth Rate only when bidirectional grading is on."""
        on = self.farfield_bidirectional.isChecked()
        self.farfield_growth_rate_outer.setVisible(on)
        lbl = self._sizing_form.labelForField(self.farfield_growth_rate_outer)
        if lbl:
            lbl.setVisible(on)

    def _update_bc_indicators(self):
        """Parse boundary condition texts and update indicator backgrounds accordingly."""
        for edit, indicator in [
            (self.bc_xmin, self.bc_xmin_indicator),
            (self.bc_xmax, self.bc_xmax_indicator),
            (self.bc_ymin, self.bc_ymin_indicator),
            (self.bc_ymax, self.bc_ymax_indicator),
        ]:
            val = edit.text().strip().lower()
            color = BC_COLORS.get(val, DEFAULT_BC_COLOR)
            indicator.setStyleSheet(
                f"background-color: {color}; border-radius: 4px; border: 1px solid #333852;"
            )

    def _on_browse_geom(self):
        """Prompt file dialog to select external geometry files."""
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select Geometry File", "", "Geometry Files (*.dat);;All Files (*)"
        )
        for f in files:
            # We want to display the relative path or absolute path
            # For simplicity, store absolute path but list basename
            item = QListWidgetItem(os.path.basename(f))
            item.setData(Qt.ItemDataRole.UserRole, f)
            self.geom_list_widget.addItem(item)
            
        geom_files = []
        for row in range(self.geom_list_widget.count()):
            geom_files.append(self.geom_list_widget.item(row).data(Qt.ItemDataRole.UserRole))
        self.geom_files_changed.emit(geom_files)

    def _on_remove_geom(self):
        """Remove selected geometry file from the list."""
        for item in self.geom_list_widget.selectedItems():
            self.geom_list_widget.takeItem(self.geom_list_widget.row(item))

        geom_files = []
        for row in range(self.geom_list_widget.count()):
            geom_files.append(self.geom_list_widget.item(row).data(Qt.ItemDataRole.UserRole))
        self.geom_files_changed.emit(geom_files)

    def _on_geom_selection_changed(self, current, previous=None):
        """Populate the role editor from the geometry selected in the list."""
        self._role_updating = True
        try:
            if current is None:
                self.geom_role_combo.setEnabled(False)
                self.geom_role_combo.setCurrentIndex(0)
                self.seed_size.setValue(0.0)
                self.seed_radius.setValue(0.0)
                self.seed_mode.setCurrentIndex(0)
                self.geom_bc_combo.setCurrentText("")
            else:
                self.geom_role_combo.setEnabled(True)
                rinfo = current.data(self._ROLE_DATA)
                role_name = rinfo.get("role") if rinfo else None
                self.geom_bc_combo.setCurrentText(rinfo.get("bc", "") if rinfo else "")
                # "bl" is a boundary that grows a BL with per-geometry overrides,
                # so it maps to the same combo entry as a plain boundary.
                role_to_index = {None: 0, "bl": 0, "nobl": 1, "seed": 2,
                                 "farfield": 3, "wall": 4}
                self.geom_role_combo.setCurrentIndex(role_to_index.get(role_name, 0))
                if role_name == "seed":
                    self.seed_size.setValue(float(rinfo.get("size") or 0.0))
                    self.seed_radius.setValue(float(rinfo.get("radius") or 0.0))
                    self.seed_mode.setCurrentIndex(1 if rinfo.get("mode") == "embed" else 0)
                else:
                    self.seed_size.setValue(0.0)
                    self.seed_radius.setValue(0.0)
                    self.seed_mode.setCurrentIndex(0)
        finally:
            self._role_updating = False
        self._update_role_visibility()
        # Point the BL sections at this geometry's override (or the global default).
        self._sync_bl_scope()
        # Tell the canvas which geometry is selected so it can highlight it.
        path = current.data(Qt.ItemDataRole.UserRole) if current is not None else ""
        self.geom_selection_changed.emit(path or "")

    def _on_role_edited(self, *args):
        """Commit the role editor state onto the selected geometry item and
        re-emit the config so previews re-style boundary vs seed."""
        if self._role_updating:
            return
        item = self.geom_list_widget.currentItem()
        if item is None:
            return
        # Carry any existing per-geometry BL override + wall BC across role
        # changes (BL only survives between the BL-growing roles).
        prev = item.data(self._ROLE_DATA) or {}
        bl_params = prev.get("bl_params")
        bc = prev.get("bc")
        idx = self.geom_role_combo.currentIndex()
        if idx == 2:  # Seed (no wall BC / BL)
            size = self.seed_size.value()
            radius = self.seed_radius.value()
            item.setData(self._ROLE_DATA, {
                "role": "seed",
                "size": size if size > 0 else None,
                # radius is independent of size (an explicit radius is kept even
                # when the size is auto).
                "radius": radius if radius > 0 else None,
                "mode": "embed" if self.seed_mode.currentIndex() == 1 else "source",
            })
        elif idx == 1:   # No-BL obstacle (conform at far-field size)
            rinfo = {"role": "nobl"}
            if bc:
                rinfo["bc"] = bc
            item.setData(self._ROLE_DATA, rinfo)
        elif idx == 3:   # Domain: far-field outline (external, no BL)
            rinfo = {"role": "farfield"}
            if bc:
                rinfo["bc"] = bc
            item.setData(self._ROLE_DATA, rinfo)
        elif idx == 4:   # Domain: wall (internal flow, BL grows inward)
            rinfo = {"role": "wall"}
            if bl_params:
                rinfo["bl_params"] = bl_params
            if bc:
                rinfo["bc"] = bc
            item.setData(self._ROLE_DATA, rinfo)
        else:            # Boundary obstacle (grows BL)
            if bl_params or bc:
                rinfo = {"role": "bl"}
                if bl_params:
                    rinfo["bl_params"] = bl_params
                if bc:
                    rinfo["bc"] = bc
                item.setData(self._ROLE_DATA, rinfo)
            else:
                item.setData(self._ROLE_DATA, None)
        self._update_role_visibility()
        # A role change may enable/disable overriding; re-point the BL sections.
        self._sync_bl_scope()
        self.mesh_config_changed.emit(self.get_config())

    def _on_geom_bc_edited(self, *args):
        """Commit the per-geometry wall BC / patch name onto the selected item."""
        if self._role_updating:
            return
        item = self.geom_list_widget.currentItem()
        if item is None:
            return
        bc = self.geom_bc_combo.currentText().strip()
        rinfo = dict(item.data(self._ROLE_DATA) or {})
        if bc:
            if not rinfo.get("role"):
                rinfo["role"] = "bl"   # a plain boundary needs a dict to carry bc
            rinfo["bc"] = bc
            item.setData(self._ROLE_DATA, rinfo)
        else:
            rinfo.pop("bc", None)
            # Drop the role entry if nothing meaningful is left on it.
            if rinfo.get("role") == "bl" and not rinfo.get("bl_params"):
                item.setData(self._ROLE_DATA, None)
            else:
                item.setData(self._ROLE_DATA, rinfo or None)
        self.mesh_config_changed.emit(self.get_config())

    def _update_role_visibility(self):
        """Show seed params only for a selected seed geometry. Size and radius are
        independent, so radius stays editable even when the size is auto. (#2: the
        per-geometry Wall BC field was removed from this editor.)"""
        enabled = self.geom_role_combo.isEnabled()
        idx = self.geom_role_combo.currentIndex()
        is_seed = enabled and idx == 2
        for w in (self.seed_size, self.seed_radius, self.seed_mode):
            w.setVisible(is_seed)
            w.setEnabled(is_seed)
            lbl = self._role_form.labelForField(w)
            if lbl:
                lbl.setVisible(is_seed)

    def set_config(self, cfg: MeshConfig):
        """Populate widget values from a MeshConfig model instance."""
        # Suppress the BL change handler while bulk-populating, and reset the BL
        # edit scope to global; the selection sync at the end re-points it.
        self._bl_updating = True
        self._bl_target_item = None
        # 1. Domain
        self.domain_x_min.setValue(cfg.domain_x_min)
        self.domain_x_max.setValue(cfg.domain_x_max)
        self.domain_y_min.setValue(cfg.domain_y_min)
        self.domain_y_max.setValue(cfg.domain_y_max)
        # Domain source: a geometry acting as the outer domain → Custom; an
        # external-flow config with geometries but no domain outline → Rectangle
        # box; a fresh/empty config → default to Custom geometry (#1: entering the
        # mesh generator defaults to Custom).
        if cfg.domain_file:
            dsrc = 1
        elif cfg.geom_files:
            dsrc = 0
        else:
            dsrc = 1
        self.domain_source_combo.blockSignals(True)
        self.domain_source_combo.setCurrentIndex(dsrc)
        self.domain_source_combo.blockSignals(False)
        self._update_domain_source_visibility()

        # Geometries (with per-file role carried as item data). Block selection
        # signals during the rebuild, then resync the role editor once.
        self.geom_list_widget.blockSignals(True)
        self.geom_list_widget.clear()
        for f in cfg.geom_files:
            item = QListWidgetItem(os.path.basename(f))
            item.setData(Qt.ItemDataRole.UserRole, f)
            rinfo = cfg.geom_roles.get(f)
            if rinfo:
                item.setData(self._ROLE_DATA, dict(rinfo))
            self.geom_list_widget.addItem(item)
        self.geom_list_widget.blockSignals(False)

        # #4: per-group BC-type assignments carried on the config.
        self._group_bc = dict(cfg.group_bc or {})

        # 2. Sizing
        self.surface_mesh_size.setValue(cfg.surface_mesh_size)
        self.auto_surface_size.setChecked(cfg.auto_surface_size)
        self.farfield_mesh_size.setValue(cfg.farfield_mesh_size)
        self.auto_farfield_size.setChecked(cfg.auto_farfield_size)
        self.farfield_growth_rate.setValue(cfg.farfield_growth_rate)
        # #7: bidirectional far-field grading
        self.farfield_bidirectional.setChecked(cfg.farfield_bidirectional)
        self.farfield_growth_rate_outer.setValue(cfg.farfield_growth_rate_outer)
        self._update_bidirectional_visibility()

        # 3. BL Core
        self.bl_initial_thickness.setValue(cfg.bl_initial_thickness)
        self.bl_growth_rate.setValue(cfg.bl_growth_rate)
        self.bl_layers.setValue(cfg.bl_layers)

        # 4. Convex
        convex_methods = [0, 2]
        if cfg.bl_convex_method in convex_methods:
            self.bl_convex_method.setCurrentIndex(convex_methods.index(cfg.bl_convex_method))
        else:
            self.bl_convex_method.setCurrentIndex(1)
        self.bl_fan_nodes.setValue(cfg.bl_fan_nodes)
        self.bl_auto_fan_nodes.setChecked(cfg.bl_auto_fan_nodes)
        self.bl_fan_angle_threshold.setValue(cfg.bl_fan_angle_threshold)
        self.bl_convex_angle_threshold.setValue(cfg.bl_convex_angle_threshold)
        self.bl_para_fallback_angle.setValue(cfg.bl_para_fallback_angle)

        # 5. Concave
        concave_methods = [5]
        if cfg.bl_concave_method in concave_methods:
            self.bl_concave_method.setCurrentIndex(concave_methods.index(cfg.bl_concave_method))
        else:
            self.bl_concave_method.setCurrentIndex(0)
        self.bl_concave_angle_threshold.setValue(cfg.bl_concave_angle_threshold)
        self.bl_concave_influence_multiplier.setValue(cfg.bl_concave_influence_multiplier)
        self.bl_merge_concave.setChecked(cfg.bl_merge_concave)
        self.bl_smoothing_iters.setValue(cfg.bl_smoothing_iters)

        # 6. Transition
        self.bl_transition_layers.setValue(cfg.bl_transition_layers)
        self.bl_auto_transition_layers.setCurrentIndex(cfg.bl_auto_transition_layers)
        self.bl_transition_growth_rate.setValue(cfg.bl_transition_growth_rate)
        self.bl_transition_buffer.setValue(cfg.bl_transition_buffer)

        gmsh_algos = [1, 2, 5, 6, 7, 8]
        if cfg.gmsh_algorithm in gmsh_algos:
            self.gmsh_algorithm.setCurrentIndex(gmsh_algos.index(cfg.gmsh_algorithm))
        else:
            self.gmsh_algorithm.setCurrentIndex(3)  # default: 6
        self.gmsh_optimize.setChecked(cfg.gmsh_optimize != 0)
        self.bl_use_analytic_geom.setChecked(bool(cfg.bl_use_analytic_geom))

        # 7. Domain boundary patches (rectangle-box edges) + output
        self.bc_xmin.setText(cfg.bc_xmin)
        self.bc_xmax.setText(cfg.bc_xmax)
        self.bc_ymin.setText(cfg.bc_ymin)
        self.bc_ymax.setText(cfg.bc_ymax)
        # bc_geom is no longer a panel field; the model default (a geometry's wall
        # patch) is set per-geometry (Wall BC) / per-segment instead.

        # Suggested name from BOUNDARY geometries only (seeds share geom_files
        # but shouldn't drive the name).
        boundaries = cfg.boundary_files
        if not cfg.geom_files or len(boundaries) == 0:
            default_name = "results/meshes/mesh_cartesian.*"
        elif len(boundaries) == 1:
            stem = os.path.splitext(os.path.basename(boundaries[0]))[0]
            default_name = f"results/meshes/mesh_{stem}.*"
        else:
            # Multiple boundaries: name after all their stems so different
            # geometry sets still export to distinct files.
            stems = "_".join(os.path.splitext(os.path.basename(b))[0]
                             for b in boundaries)
            default_name = f"results/meshes/mesh_{stems}.*"
        # An auto-generated name (empty, or the "results/meshes/mesh_*" pattern
        # we produce) is refreshed to match the current geometry so switching
        # geometries changes the export name; a name the user typed is kept.
        def _is_auto(name: str) -> bool:
            return (not name) or name.startswith("results/meshes/mesh_")

        incoming = (cfg.output_filename or "").strip()
        widget_text = self.output_filename.text().strip()
        if incoming and not _is_auto(incoming):
            # Explicit custom name carried in the config (e.g. a loaded file).
            self.output_filename.setText(incoming)
            self._output_name_user_set = True
        elif self._output_name_user_set and widget_text and not _is_auto(widget_text):
            # Keep the custom name the user already typed into the field.
            pass
        else:
            self.output_filename.setText(default_name)
            self._output_name_user_set = False

        self.export_vtk.setChecked(cfg.export_vtk)
        self.export_starcd.setChecked(cfg.export_starcd)
        self.export_cgns.setChecked(cfg.export_cgns)
        self.enable_collision_detection.setChecked(cfg.enable_collision_detection)

        # The BL widgets now hold cfg's global defaults — snapshot them as the
        # authoritative global BL, then release the population guard.
        self._global_bl = self._read_bl_widgets()
        self._bl_updating = False

        # Sync the role editor + BL override scope + canvas highlight to the
        # current selection (may re-point the BL sections to a geometry override).
        self._on_geom_selection_changed(self.geom_list_widget.currentItem())

        # #6: refresh the auto size hints now the checkboxes + domain/geoms are set.
        self._update_auto_farfield_hint()
        self._update_auto_surface_hint()

        # Update canvas preview geometries and config
        self.mesh_config_changed.emit(cfg)

    def get_config(self) -> MeshConfig:
        """Collect widget values and return a MeshConfig model instance."""
        cfg = MeshConfig()
        
        # 1. Domain
        cfg.domain_x_min = self.domain_x_min.value()
        cfg.domain_x_max = self.domain_x_max.value()
        cfg.domain_y_min = self.domain_y_min.value()
        cfg.domain_y_max = self.domain_y_max.value()

        # Geometries (+ per-file role read back from item data)
        cfg.geom_files = []
        cfg.geom_roles = {}
        for row in range(self.geom_list_widget.count()):
            item = self.geom_list_widget.item(row)
            p = item.data(Qt.ItemDataRole.UserRole)
            cfg.geom_files.append(p)
            rinfo = item.data(self._ROLE_DATA)
            if rinfo and rinfo.get("role") in ("seed", "nobl", "farfield", "wall", "bl"):
                cfg.geom_roles[p] = dict(rinfo)

        # #4: per-group BC-type assignments (kept separate from the group names).
        cfg.group_bc = dict(self._group_bc)

        # 2. Sizing
        cfg.surface_mesh_size = self.surface_mesh_size.value()
        cfg.auto_surface_size = self.auto_surface_size.isChecked()
        cfg.farfield_mesh_size = self.farfield_mesh_size.value()
        cfg.auto_farfield_size = self.auto_farfield_size.isChecked()
        cfg.farfield_growth_rate = self.farfield_growth_rate.value()
        # #7: bidirectional far-field grading
        cfg.farfield_bidirectional = self.farfield_bidirectional.isChecked()
        cfg.farfield_growth_rate_outer = self.farfield_growth_rate_outer.value()

        # 3-6. Boundary layer: the override-able fields come from the
        # authoritative global-BL store (so a per-geometry override currently
        # shown in the widgets is not mistaken for the global value).
        self._apply_global_bl_to_cfg(cfg)

        # Non-override BL / meshing fields are always global — read from widgets.
        cfg.bl_merge_concave = self.bl_merge_concave.isChecked()
        cfg.bl_smoothing_iters = self.bl_smoothing_iters.value()
        gmsh_algos = [1, 2, 5, 6, 7, 8]
        cfg.gmsh_algorithm = gmsh_algos[self.gmsh_algorithm.currentIndex()]
        cfg.gmsh_optimize = 1 if self.gmsh_optimize.isChecked() else 0

        # 7. Domain boundary patches (rectangle-box edges) + output.
        # cfg.bc_geom keeps its model default (geometry wall patch) — it is no
        # longer a panel field; per-geometry / per-segment names override it.
        cfg.bc_xmin = self.bc_xmin.text().strip()
        cfg.bc_xmax = self.bc_xmax.text().strip()
        cfg.bc_ymin = self.bc_ymin.text().strip()
        cfg.bc_ymax = self.bc_ymax.text().strip()
        cfg.output_filename = self.output_filename.text().strip()

        cfg.export_vtk = self.export_vtk.isChecked()
        cfg.export_starcd = self.export_starcd.isChecked()
        cfg.export_cgns = self.export_cgns.isChecked()
        cfg.enable_collision_detection = self.enable_collision_detection.isChecked()

        return cfg

    def current_geom_roles(self) -> dict:
        """Return {path: role_dict} for the seed geometries currently listed,
        read straight from item data — no full MeshConfig rebuild. Used by the
        live preview path so a geom-file change doesn't re-parse every widget."""
        roles = {}
        for row in range(self.geom_list_widget.count()):
            item = self.geom_list_widget.item(row)
            rinfo = item.data(self._ROLE_DATA)
            if rinfo and rinfo.get("role") == "seed":
                roles[item.data(Qt.ItemDataRole.UserRole)] = rinfo
        return roles

    def _mesh_sublabel(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet("color:#6b7390; font-size:10px; font-weight:bold;")
        return lbl

    def _update_transition_visibility(self):
        """Hide the manual Transition Layers count when Auto Transition computes it."""
        manual = self.bl_auto_transition_layers.currentIndex() == 0  # 0: OFF
        self.bl_transition_layers.setVisible(manual)
        lbl = self._trans_form.labelForField(self.bl_transition_layers)
        if lbl:
            lbl.setVisible(manual)

    def _update_convex_widgets_visibility(self):
        method_str = self.bl_convex_method.currentText()
        is_fan = "0: Fan" in method_str

        self.bl_fan_nodes.setVisible(is_fan)
        self.bl_auto_fan_nodes.setVisible(is_fan)
        self.bl_fan_angle_threshold.setVisible(is_fan)

        label_nodes = self.convex_form.labelForField(self.bl_fan_nodes)
        if label_nodes:
            label_nodes.setVisible(is_fan)

        label_threshold = self.convex_form.labelForField(self.bl_fan_angle_threshold)
        if label_threshold:
            label_threshold.setVisible(is_fan)
