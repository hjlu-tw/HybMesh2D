"""Boundary-layer dialogs for the mesh config panel. Split from mesh_dialogs.py:
the per-segment BL toggle section and the per-geometry / global BL parameter
dialog. The parameter TABLES those dialogs are built from live in
mesh_bl_field_specs.py and are re-exported here, so the existing
``from .mesh_dialogs_bl import _BL_FIELD_SPECS`` import paths keep working."""
from __future__ import annotations
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QFrame, QLabel,
    QListWidget, QListWidgetItem, QDialog, QDialogButtonBox, QSizePolicy,
)
from PyQt6.QtCore import Qt
from app.utils import make_button
from app.views.panels.field_widgets import make_widget, read_widget, write_widget
from app.views.panels.mesh_bl_dialog_layout import BLDialogLayoutMixin
from app.views.panels.mesh_bl_field_specs import (
    BL_SPECS, _BL_OVERRIDE_KEYS, _BL_INT_ATTRS, _BL_BOOL_ATTRS, _BL_FIELD_SPECS,
    _BL_FIELD_GROUPS, _value_differs,
)

__all__ = [
    "BL_SPECS",
    "_BL_OVERRIDE_KEYS", "_BL_INT_ATTRS", "_BL_BOOL_ATTRS", "_BL_FIELD_SPECS",
    "_BL_FIELD_GROUPS", "_value_differs",
    "SegmentBLSection", "PerGeomBLDialog",
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


class PerGeomBLDialog(BLDialogLayoutMixin, QDialog):
    """Pop-up editor for ONE geometry's boundary layer. Top: the geometry's BL
    parameter override (always editable, seeded from the geometry's current
    override, or the global BL values when it has none), laid out as collapsible
    groups (_BL_FIELD_GROUPS), all CLOSED to start — the 21 parameters are otherwise a
    wall of fields, and the dialog now opens as a short list of headers you pick from.
    (A group is still opened by the state the user left it in, or by holding a
    per-geometry override.) Bottom (only when the geometry has a segmented .meta sidecar):
    per-segment 'grow BL?' toggles. OK saves the parameters as this geometry's
    override and the per-segment flags to the .meta; 'Use Global' clears the
    parameter override (the per-segment flags are still saved) so the geometry
    follows the global BL parameters."""

    # Section expand/collapse state is remembered under this scope (view state
    # only — never case data, see services/ui_state.py).
    _STATE_SCOPE = "PerGeomBLDialog"

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
        self.setMinimumWidth(380)
        self.resize(460, 700 if segments else 460)   # first guess; refit on show
        self._widgets = {}
        self._cleared = False
        self._seg_section = None
        self._sections = []
        # Window-fitting state (see _autofit_height): _user_h is a height the USER
        # chose by dragging the window, which the accordion must never shrink past;
        # _autofitting distinguishes our own resizes from theirs.
        self._autofitting = False
        self._user_h = 0
        self._shown = False
        self._spacer = None
        # Seeding a section can toggle it (an overridden group opens itself), and
        # the toggle handler measures a layout that __init__ has not finished
        # building yet; Expand/Collapse all would likewise refit once per group.
        # Both suspend fitting and do a single pass at the end.
        self._fit_suspended = True

        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.setSpacing(6)
        hint = QLabel(
            "Boundary layer for THIS geometry only (seeded from the global "
            "values). OK saves it as an override; 'Use Global' clears it.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#8a93ad; font-size:10px;")
        outer.addWidget(hint)

        tools = QHBoxLayout()
        tools.setSpacing(4)
        tools.addStretch(1)
        exp_btn = make_button("Expand all", "#26293c", padding="2px 8px",
                              font_size="10px")
        col_btn = make_button("Collapse all", "#26293c", padding="2px 8px",
                              font_size="10px")
        exp_btn.clicked.connect(lambda: self._set_all_sections(True))
        col_btn.clicked.connect(lambda: self._set_all_sections(False))
        tools.addWidget(exp_btn)
        tools.addWidget(col_btn)
        outer.addLayout(tools)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setMinimumHeight(140)
        self._content = QWidget()
        col = QVBoxLayout(self._content)
        col.setContentsMargins(2, 2, 2, 2)
        col.setSpacing(2)
        seed = dict(defaults)
        if current:
            seed.update(current)
        self._build_sections(col, seed, defaults)
        col.addStretch(1)
        self._scroll.setWidget(self._content)
        # The parameter area is the only STRETCHED item: it takes what its open
        # groups need (bounded by the cap _relayout sets) and the surplus falls
        # through to the stretch-0 spacer / the per-segment list. A stretched
        # spacer competed with it proportionally instead and left the groups short
        # of their own cap — a scrollbar over three visible rows.
        outer.addWidget(self._scroll, stretch=1)
        if not segments:
            outer.addStretch(0)   # collapsed groups give the space back, not a gap
            self._spacer = outer.itemAt(outer.count() - 1)

        # Per-segment BL on/off toggles, merged into this dialog below the
        # parameters (only when the geometry was exported with segments).
        if segments:
            sep = QFrame()
            sep.setFrameShape(QFrame.Shape.HLine)
            sep.setStyleSheet("color:#333852;")
            outer.addWidget(sep)
            self._seg_section = SegmentBLSection(
                segments, seg_grow=seg_grow, highlight_cb=highlight_cb, parent=self)
            # Expanding every parameter group must not squeeze the segment list to
            # a two-row sliver; it keeps a usable floor and the params scroll.
            self._seg_section.setMinimumHeight(190)
            # Stretch 0 + Expanding (like the spacer above): it takes the space
            # LEFT OVER once the open parameter groups have theirs, rather than
            # competing for it and leaving both areas scrolling.
            self._seg_section.setSizePolicy(QSizePolicy.Policy.Preferred,
                                            QSizePolicy.Policy.Expanding)
            outer.addWidget(self._seg_section, stretch=0)

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
        self._fit_suspended = False   # first fit happens on the first showEvent

    # ── grouped field layout ──────────────────────────────────────────────
    def _on_clear(self):
        self._cleared = True
        self.accept()

    # The kind -> widget mapping is shared with every config panel
    # (views/panels/field_widgets.py). This dialog used to keep its own copy, so the
    # 21 parameters had two descriptions of the same widget that were free to drift.
    def _make_widget(self, spec):
        w = make_widget(spec)
        # The one thing this host adds: a physical length carries the MODEL unit, and
        # the dialog is handed it rather than reading a global — this is the first-cell
        # height, the one number where a 1000x unit error still produces a plausible
        # mesh.
        if spec.is_length and getattr(self, "_length_unit", ""):
            from app.services import units
            w.setSuffix(" " + units.symbol(self._length_unit, self._length_unit_name))
        return w

    def _set_widget_value(self, w, spec, value):
        write_widget(w, spec, value)

    def _widget_value(self, w, spec):
        return read_widget(w, spec)

    def result_params(self) -> dict | None:
        """Full override dict, or None if the user chose 'Use Global'."""
        if self._cleared:
            return None
        return {k: self._widget_value(w, spec) for k, (w, spec) in self._widgets.items()}

    def result_seg_grow(self) -> dict[int, bool]:
        """Per-segment grow-BL flags, or {} when the geometry has no segments.
        Independent of 'Use Global' — the flags are returned either way."""
        return self._seg_section.result_seg_grow() if self._seg_section else {}
