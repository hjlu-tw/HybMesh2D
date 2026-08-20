"""Boundary-condition / patch dialogs for the mesh config panel. Split from
mesh_dialogs.py (behaviour unchanged): the group-based BC-type editor and the
CAD patch/group assignment dialog."""
from __future__ import annotations
from PyQt6.QtWidgets import (
    QVBoxLayout, QFormLayout, QComboBox, QLabel,
    QListWidget, QListWidgetItem, QDialog, QDialogButtonBox,
)
from PyQt6.QtCore import Qt
from app.utils import COMBO_STYLE, align_form_labels, help_label, block_signals
from app.views.bc_widget import BC_TYPE_DEFS


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
        with block_signals(self.bc_edit):
            self.bc_edit.setCurrentText(shown)
            self.bc_edit.lineEdit().setPlaceholderText(
                "(select an edge/group)" if not names
                else ("(mixed)" if not shown else ""))
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
        with block_signals(self.name_edit):
            self.name_edit.setCurrentText(shared)
            self.name_edit.lineEdit().setPlaceholderText("(mixed)" if len(labels) > 1 else "")
        if self._highlight_cb:
            self._highlight_cb(idxs)

    def selected_indices(self) -> list[int]:
        return [it.data(Qt.ItemDataRole.UserRole) for it in self.seg_list.selectedItems()]

    def patch_name(self) -> str:
        return self.name_edit.currentText().strip()
