"""Boundary-layer dialogs for the mesh config panel. Split from mesh_dialogs.py:
the per-segment BL toggle section and the per-geometry / global BL parameter
dialog. The parameter TABLES those dialogs are built from live in
mesh_bl_field_specs.py and are re-exported here, so the existing
``from .mesh_dialogs_bl import _BL_FIELD_SPECS`` import paths keep working."""
from __future__ import annotations
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QFrame,
    QFormLayout, QComboBox, QSpinBox, QLabel, QCheckBox,
    QListWidget, QListWidgetItem, QDialog, QDialogButtonBox, QSizePolicy,
)
from PyQt6.QtCore import Qt
from app.utils import (
    make_button, COMBO_STYLE, SPIN_STYLE, align_form_labels, help_label,
)
from app.views.clean_double_spin_box import CleanDoubleSpinBox, SciDoubleSpinBox
from app.views.collapsible import CollapsibleSection
from app.views.panels.mesh_bl_field_specs import (
    _BL_OVERRIDE_KEYS, _BL_INT_ATTRS, _BL_BOOL_ATTRS, _BL_FIELD_SPECS,
    _BL_FIELD_GROUPS, _value_differs,
)

__all__ = [
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


class PerGeomBLDialog(QDialog):
    """Pop-up editor for ONE geometry's boundary layer. Top: the geometry's BL
    parameter override (always editable, seeded from the geometry's current
    override, or the global BL values when it has none), laid out as collapsible
    groups (_BL_FIELD_GROUPS) with only 'Layer Growth' open — the 21 parameters
    are otherwise a wall of fields in which the three that matter most are hard
    to find. Bottom (only when the geometry has a segmented .meta sidecar):
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
    def _build_sections(self, col, seed: dict, defaults: dict):
        """Build one CollapsibleSection per _BL_FIELD_GROUPS entry into ``col``,
        seeding each field from ``seed``. Only groups marked start_expanded open,
        with two exceptions that both err on the side of showing a value rather
        than hiding it: a group holding a value that DIFFERS from ``defaults``
        (i.e. something this geometry actually overrides) is expanded, and any
        spec key missing from the table lands in a trailing 'Other' group."""
        specs = {k: (label, kind, opt) for k, label, kind, opt in _BL_FIELD_SPECS}
        listed = {k for _t, _e, _h, keys in _BL_FIELD_GROUPS for k in keys}
        groups = list(_BL_FIELD_GROUPS)
        stray = [k for k, _lbl, _kind, _opt in _BL_FIELD_SPECS if k not in listed]
        if stray:
            groups.append(("Other", True, "Ungrouped parameters.", stray))

        forced: list = []
        forms: list = []
        labels: list = []
        for title, start_expanded, hint, keys in groups:
            sec = CollapsibleSection(title, start_collapsed=not start_expanded)
            if hint:
                h = QLabel(hint)
                h.setWordWrap(True)
                h.setStyleSheet("color:#8a93ad; font-size:10px;")
                sec.add_widget(h)
            form = QFormLayout()
            form.setContentsMargins(0, 0, 0, 0)
            for key in keys:
                label, kind, opt = specs[key]
                w = self._make_widget(kind, opt)
                self._set_widget_value(w, kind, seed.get(key))
                self._widgets[key] = (w, kind)
                lbl = help_label(label + ":", key)
                labels.append(lbl)
                form.addRow(lbl, w)
            forms.append(form)
            sec.add_layout(form)
            sec.toggle_btn.toggled.connect(lambda _c: self._relayout())
            col.addWidget(sec)
            self._sections.append(sec)
            if any(_value_differs(seed.get(k), defaults.get(k)) for k in keys):
                forced.append(sec)

        # One label column across all groups, MEASURED from the labels actually
        # built rather than a hardcoded width: the widest here ("Concave Threshold
        # (deg)") overflows a guessed 150 and, being right-aligned in a fixed-width
        # cell, loses its first characters — and the next parameter added would go
        # stale again. Bounded so one long label cannot eat the field column.
        col_w = max((lbl.sizeHint().width() for lbl in labels), default=150)
        col_w = min(max(col_w, 120), 240)
        for form in forms:
            align_form_labels(form, col_w)

        # Reopen whatever the user left open last time, then re-apply the
        # overridden-value rule on top: a saved "collapsed" must not hide a value
        # that differs from the global default.
        from app.services import ui_state
        ui_state.restore_section_states(self._STATE_SCOPE, self._sections)
        for sec in forced:
            if not sec.is_expanded:
                sec.expand()

    def _set_all_sections(self, expand: bool):
        self._fit_suspended = True
        try:
            for sec in self._sections:
                sec.expand() if expand else sec.collapse()
        finally:
            self._fit_suspended = False
        self._relayout()

    def showEvent(self, e):
        # First layout pass: size the parameter area (and the window) to whatever
        # groups are open. Done here rather than in __init__ because the segment
        # section and the button box are not in the layout yet at that point.
        super().showEvent(e)
        self._relayout()
        self._shown = True        # from here on, a resize is the user's doing

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self._shown and not self._autofitting:
            self._user_h = self.height()

    def _relayout(self):
        """Cap the parameter area at its content height, so collapsing groups
        hands the space back instead of leaving a tall empty scroll box. A cap,
        not a fixed height: once the open groups are taller than the dialog the
        layout gives less and the scrollbar takes over."""
        if self._fit_suspended:
            return
        # invalidate() first: hiding a section's content posts the layout request,
        # so the cached sizeHint still describes the PREVIOUS state and the cap
        # would be computed from the group the user just closed.
        inner = self._content.layout()
        if inner is not None:
            inner.invalidate()
            inner.activate()
        h = self._content.sizeHint().height() + 4
        self._scroll.setMaximumHeight(max(self._scroll.minimumHeight(), h))
        self.layout().invalidate()
        self.layout().activate()
        self._autofit_height()

    def _autofit_height(self):
        """Follow the open groups with the window height. A fixed window is wrong
        in both directions for an accordion: too tall leaves a dead grey band
        under the collapsed groups, too short makes 'Expand all' scroll a 3-row
        viewport. Bounded by the screen, so expanding everything can never produce
        a window taller than the display, and never below a height the user set
        themselves by dragging the window.

        Works from what the layout ACTUALLY gave the elastic items — the scroll
        area's shortfall against its cap, and the slack handed to whatever absorbs
        leftover space — rather than from a predicted chrome height, so it is exact
        in both directions and self-corrects. It deliberately does not use
        ``self.sizeHint()``: ``QScrollArea::sizeHint()`` is clamped to 24 font
        heights, so the dialog's own hint stops growing after the first group or
        two and the window would never follow."""
        scr = self.screen()
        cap = int(scr.availableGeometry().height() * 0.85) if scr is not None else 1 << 20
        floor = max(self.minimumSizeHint().height(), self._user_h)
        self._autofitting = True
        try:
            for _ in range(2):      # one corrective pass; the layout runs between
                short = self._scroll.maximumHeight() - self._scroll.height()
                want = max(floor, min(self.height() + short - self._slack(), cap))
                if abs(want - self.height()) <= 2:
                    return
                self.resize(self.width(), want)
                self.layout().activate()
        finally:
            self._autofitting = False

    def _slack(self) -> int:
        """Space the layout has handed to the item that absorbs leftovers — the
        trailing spacer, or the per-segment list above its own sizeHint. Shrinking
        the window by it is what lets the accordion fold back up; without it, one
        'Expand all' would leave the window tall for the rest of the session."""
        if self._spacer is not None:
            return self._spacer.geometry().height()
        if self._seg_section is not None:
            return max(0, self._seg_section.height()
                       - self._seg_section.sizeHint().height())
        return 0

    def done(self, r):
        """Remember which groups were left open (per-user, not per-case), so the
        one group an engineer keeps reopening is open next time."""
        from app.services import ui_state
        ui_state.save_section_states(self._STATE_SCOPE, self._sections)
        super().done(r)

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
