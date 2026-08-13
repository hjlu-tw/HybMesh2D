"""Surface Definition — which curve the Results surface plot treats as "the surface".

Every source is listed, including the ones this session cannot use: a greyed row
with the reason on it ("run the IB stage first") tells the user what to go and do,
whereas a source that simply isn't shown reads as a feature that does not exist.

Nothing is computed while the dialog is open and being edited (USER-REQUESTED) —
the widgets only build a ``SurfaceSpec``. Contouring the field, chaining the
interface cloud and sampling all happen on Show / Plot, which is also the only
moment an error can appear, so the status line always describes the current pick.

``Start of arc length`` deliberately opens on a placeholder rather than a default:
s = 0 is otherwise wherever the extractor happened to begin, which is
reproducible but geometrically arbitrary, so the two plots you wanted to compare
start in different places.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFormLayout, QFrame, QHBoxLayout, QLabel,
    QListWidget, QListWidgetItem, QPushButton, QRadioButton, QSpinBox,
    QVBoxLayout, QWidget,
)

from app.services import surface_source as ss
from app.utils import block_signals
from app.views.clean_double_spin_box import CleanDoubleSpinBox, SciDoubleSpinBox

_BG = "#0c0d16"
_FG = "#a0a8c0"
_DIM = "#6b7189"
_ACCENT = "#f472b6"
_COMBO_QSS = (
    "QComboBox{background:#181b30;color:#dde2ff;border:1px solid #2d3356;"
    "border-radius:4px;padding:2px 6px;font-size:11px;min-width:110px;}")
_SPIN_QSS = (
    "QAbstractSpinBox{background:#181b30;color:#dde2ff;border:1px solid #2d3356;"
    "border-radius:4px;padding:1px 4px;font-size:11px;}")
_BTN_QSS = (
    "QPushButton{background:#1d2a3a;color:#dde2ff;border:1px solid #2d3356;"
    "border-radius:4px;padding:4px 12px;font-weight:bold;font-size:11px;}"
    "QPushButton:hover{border-color:#5a9ad4;}"
    "QPushButton:disabled{color:#565b73;border-color:#22263c;}")
_LIST_QSS = (
    "QListWidget{background:#181b2a;color:#a0a8c0;border:1px solid #333852;"
    "font-size:11px;}")


class SurfaceSourceDialog(QDialog):
    """Modeless picker for the surface source + arc-length origin."""

    def __init__(self, canvas):
        super().__init__(canvas.window() if hasattr(canvas, "window") else None)
        self._canvas = canvas
        self.setWindowTitle("Surface Definition")
        self.setStyleSheet(f"background:{_BG};color:{_FG};")
        self.setMinimumWidth(520)
        self._radios: dict = {}
        self._opts: dict = {}
        self._building = False

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        head = QLabel("Choose the curve to treat as the surface, then Show it on the "
                      "canvas or Plot along it.")
        head.setWordWrap(True)
        head.setStyleSheet(f"color:{_DIM};font-size:11px;")
        root.addWidget(head)

        self._src_box = QVBoxLayout()
        self._src_box.setSpacing(2)
        holder = QWidget()
        holder.setLayout(self._src_box)
        root.addWidget(holder)

        root.addWidget(self._hline())

        # ── per-source parameters (only the active source's row is shown) ──
        self.params_form = QFormLayout()
        self.params_form.setContentsMargins(0, 0, 0, 0)
        self.params_form.setSpacing(4)
        pw = QWidget(); pw.setLayout(self.params_form)
        root.addWidget(pw)

        self.var_combo = QComboBox(); self.var_combo.setStyleSheet(_COMBO_QSS)
        self.level_sb = CleanDoubleSpinBox()
        self.level_sb.setStyleSheet(_SPIN_QSS)
        self.level_sb.setRange(-1e12, 1e12); self.level_sb.setDecimals(6)
        self.level_sb.setSingleStep(0.1); self.level_sb.setValue(0.5)
        self.loop_sb = QSpinBox(); self.loop_sb.setStyleSheet(_SPIN_QSS)
        self.loop_sb.setRange(-1, 999); self.loop_sb.setValue(-1)
        self.loop_sb.setToolTip("-1 = the longest piece by perimeter; otherwise the "
                                "piece index (0-based) in extraction order.")
        self.slice_sb = QSpinBox(); self.slice_sb.setStyleSheet(_SPIN_QSS)
        self.slice_sb.setRange(-1, 100000); self.slice_sb.setValue(-1)
        self.slice_sb.setToolTip("k-layer of the structured φ field to cut; "
                                 "-1 = the middle layer (the quasi-2D case).")
        self.shape_combo = QComboBox(); self.shape_combo.setStyleSheet(_COMBO_QSS)
        self.cad_list = QListWidget(); self.cad_list.setStyleSheet(_LIST_QSS)
        self.cad_list.setMaximumHeight(96)

        self._rows = {
            "var": self._row("Variable:", self.var_combo),
            "level": self._row("Iso level:", self.level_sb),
            "loop": self._row("Piece:", self.loop_sb),
            "slice": self._row("φ layer (k):", self.slice_sb),
            "shape": self._row("Shape:", self.shape_combo),
            "cad": self._row("Geometries:", self.cad_list),
        }

        root.addWidget(self._hline())

        # ── arc length origin / direction / sampling offset ────────────────
        form = QFormLayout(); form.setSpacing(4)
        self.start_combo = QComboBox(); self.start_combo.setStyleSheet(_COMBO_QSS)
        self.start_combo.addItem("— pick where s = 0 is —", "")
        for rule in ss.START_RULES:
            self.start_combo.addItem(ss.START_RULE_LABELS[rule], rule)
        self.start_combo.setToolTip(
            "Where arc length starts. Not defaulted on purpose: an arbitrary origin "
            "makes two runs impossible to compare. Marked on the canvas as 's=0'.")
        self.dir_combo = QComboBox(); self.dir_combo.setStyleSheet(_COMBO_QSS)
        self.dir_combo.addItem("Counter-clockwise", True)
        self.dir_combo.addItem("Clockwise", False)
        self.offset_sb = SciDoubleSpinBox()
        self.offset_sb.setStyleSheet(_SPIN_QSS)
        self.offset_sb.setRange(0.0, 1e9); self.offset_sb.setValue(0.0)
        self.offset_sb.setToolTip(
            "Sample δ away from the curve along its outward normal. 0 = exactly on "
            "the curve. For an immersed solid the interface itself holds the SOLID "
            "state, so a small δ (about one cell) reads the fluid-side value.")
        self.flip_cb = QCheckBox("Offset the other way")
        self.flip_cb.setStyleSheet(f"color:{_FG};font-size:11px;")
        off_row = QHBoxLayout(); off_row.setSpacing(6)
        off_row.addWidget(self.offset_sb); off_row.addWidget(self.flip_cb)
        off_w = QWidget(); off_w.setLayout(off_row)

        for label, w in (("Start of arc length:", self.start_combo),
                         ("Direction:", self.dir_combo),
                         ("Sample offset δ:", off_w)):
            t = QLabel(label); t.setStyleSheet(f"color:{_FG};font-size:11px;")
            form.addRow(t, w)
        fw = QWidget(); fw.setLayout(form)
        root.addWidget(fw)

        self.status = QLabel("")
        self.status.setWordWrap(True)
        self.status.setStyleSheet(f"color:{_DIM};font-size:11px;")
        root.addWidget(self.status)

        bar = QHBoxLayout(); bar.setSpacing(6)
        self.show_btn = QPushButton("Show on canvas")
        self.plot_btn = QPushButton("Plot vs arc length")
        self.hide_btn = QPushButton("Hide")
        self.close_btn = QPushButton("Close")
        for b in (self.show_btn, self.plot_btn, self.hide_btn, self.close_btn):
            b.setStyleSheet(_BTN_QSS)
        bar.addWidget(self.show_btn); bar.addWidget(self.plot_btn)
        bar.addStretch(); bar.addWidget(self.hide_btn); bar.addWidget(self.close_btn)
        root.addLayout(bar)

        self.show_btn.clicked.connect(self._on_show)
        self.plot_btn.clicked.connect(self._on_plot)
        self.hide_btn.clicked.connect(self._on_hide)
        self.close_btn.clicked.connect(self.close)
        self.start_combo.currentIndexChanged.connect(self._refresh_buttons)

    # ------------------------------------------------------------------ #
    @staticmethod
    def _hline() -> QFrame:
        f = QFrame(); f.setFrameShape(QFrame.Shape.HLine)
        f.setStyleSheet("color:#1c1e36;")
        return f

    def _row(self, label: str, widget) -> tuple:
        t = QLabel(label); t.setStyleSheet(f"color:{_FG};font-size:11px;")
        idx = self.params_form.rowCount()
        self.params_form.addRow(t, widget)
        return (t, widget, idx)

    def _show_rows(self, names):
        """Show only the active source's parameter rows.

        ``setRowVisible`` (Qt 6.4+) takes the row out of the layout entirely;
        hiding the two widgets alone leaves the row's spacing behind, so the form
        grows a blank gap for every source that is not selected."""
        has_row_vis = hasattr(self.params_form, "setRowVisible")
        for key, (lbl, w, idx) in self._rows.items():
            on = key in names
            if has_row_vis:
                self.params_form.setRowVisible(idx, on)
            else:                                    # pragma: no cover - Qt < 6.4
                lbl.setVisible(on); w.setVisible(on)

    # ------------------------------------------------------------------ #
    def reload(self, options: list, spec=None):
        """Rebuild the source list from what this session can offer, restoring the
        previous pick when it is still available."""
        self._building = True
        try:
            prev_kind = getattr(spec, "kind", None)
            while self._src_box.count():
                item = self._src_box.takeAt(0)
                w = item.widget()
                if w is not None:
                    w.setParent(None)
            self._radios.clear()
            self._opts = {o["kind"]: o for o in options}
            first_enabled = None
            for o in options:
                rb = QRadioButton(o.get("label") or o["kind"])
                rb.setEnabled(bool(o.get("enabled")))
                rb.setStyleSheet(
                    f"QRadioButton{{color:{_FG};font-size:11px;font-weight:bold;}}"
                    f"QRadioButton:disabled{{color:#565b73;}}")
                detail = o.get("detail") or ""
                if not o.get("enabled"):
                    why = o.get("reason") or "not available"
                    detail = f"unavailable — {why}"
                sub = QLabel("    " + detail)
                sub.setWordWrap(True)
                sub.setStyleSheet(f"color:{_DIM};font-size:10px;")
                self._src_box.addWidget(rb)
                self._src_box.addWidget(sub)
                rb.toggled.connect(self._on_source_toggled)
                self._radios[o["kind"]] = rb
                if o.get("enabled") and first_enabled is None:
                    first_enabled = o["kind"]
            pick = prev_kind if (prev_kind in self._radios
                                 and self._radios[prev_kind].isEnabled()) else first_enabled
            if spec is not None:
                self._push_spec(spec)
            if pick:
                self._radios[pick].setChecked(True)
        finally:
            self._building = False
        self._apply_offset_unit()
        self._sync_source_params()
        self.status.setText(getattr(self._canvas, "_surface_info", "") or "")
        self.status.setStyleSheet(f"color:{_DIM};font-size:11px;")
        self._refresh_buttons()

    def _apply_offset_unit(self):
        """δ is a physical length, so it carries the model's unit in the box itself
        (never in the label text) — the one rule every length field follows."""
        ctrl = getattr(self._canvas, "_ctrl", None)
        cfg = getattr(ctrl, "global_mesh_config", None) if ctrl else None
        if cfg is None:
            return
        from app.views.units_ui import apply_unit_suffix
        apply_unit_suffix([self.offset_sb], getattr(cfg, "length_unit", "m"),
                          getattr(cfg, "length_unit_name", ""))

    def _push_spec(self, spec):
        with block_signals(self.level_sb, self.loop_sb, self.slice_sb,
                           self.start_combo, self.dir_combo, self.offset_sb,
                           self.flip_cb):
            self.level_sb.setValue(float(spec.level))
            self.loop_sb.setValue(int(spec.loop))
            self.slice_sb.setValue(int(spec.grid_slice))
            i = self.start_combo.findData(spec.start_rule)
            self.start_combo.setCurrentIndex(max(0, i))
            self.dir_combo.setCurrentIndex(0 if spec.ccw else 1)
            self.offset_sb.setValue(float(spec.offset))
            self.flip_cb.setChecked(bool(spec.flip_normal))

    def _on_source_toggled(self, on: bool):
        if on and not self._building:
            self._sync_source_params()
            self._refresh_buttons()

    def current_kind(self) -> str:
        for kind, rb in self._radios.items():
            if rb.isChecked():
                return kind
        return ""

    def _sync_source_params(self):
        kind = self.current_kind()
        o = self._opts.get(kind, {})
        if kind == ss.KIND_MESH:
            self._show_rows(("loop",))
        elif kind == ss.KIND_FIELD_ISO:
            with block_signals(self.var_combo):
                cur = self.var_combo.currentText()
                self.var_combo.clear()
                self.var_combo.addItems(list(o.get("vars") or []))
                want = cur or o.get("default_var") or ""
                j = self.var_combo.findText(want)
                if j >= 0:
                    self.var_combo.setCurrentIndex(j)
            self._show_rows(("var", "level", "loop"))
        elif kind == ss.KIND_GRID_ISO:
            self._show_rows(("level", "slice", "loop"))
        elif kind == ss.KIND_INTERFACE_CELLS:
            self._show_rows(("level", "slice"))
        elif kind == ss.KIND_ANALYTIC:
            with block_signals(self.shape_combo):
                self.shape_combo.clear()
                for sh in o.get("shapes") or []:
                    star = "★ " if sh.get("in_use") else ""
                    self.shape_combo.addItem(star + str(sh.get("label", "shape")), sh)
            self._show_rows(("shape",))
        elif kind == ss.KIND_CAD:
            with block_signals(self.cad_list):
                self.cad_list.clear()
                for sid, nm, color, has_geom in (o.get("sessions") or []):
                    it = QListWidgetItem(nm if has_geom else f"{nm}  (no geometry)")
                    if has_geom:
                        it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                        it.setCheckState(Qt.CheckState.Checked)
                    else:
                        it.setFlags(Qt.ItemFlag.NoItemFlags)
                    it.setData(Qt.ItemDataRole.UserRole, sid)
                    self.cad_list.addItem(it)
            self._show_rows(("cad", "loop"))
        else:
            self._show_rows(())
        self.adjustSize()

    def _refresh_buttons(self):
        ready = bool(self.current_kind()) and bool(self.start_combo.currentData())
        self.show_btn.setEnabled(ready)
        self.plot_btn.setEnabled(ready)
        if not self.start_combo.currentData() and self.current_kind():
            self.status.setText("Pick where s = 0 is to continue.")

    # ------------------------------------------------------------------ #
    def spec(self):
        kind = self.current_kind()
        ids = []
        for i in range(self.cad_list.count()):
            it = self.cad_list.item(i)
            if ((it.flags() & Qt.ItemFlag.ItemIsUserCheckable)
                    and it.checkState() == Qt.CheckState.Checked):
                ids.append(it.data(Qt.ItemDataRole.UserRole))
        return ss.SurfaceSpec(
            kind=kind,
            var=self.var_combo.currentText() or "phi",
            level=float(self.level_sb.value()),
            loop=int(self.loop_sb.value()),
            session_ids=tuple(ids),
            shape=self.shape_combo.currentData(),
            grid_slice=int(self.slice_sb.value()),
            start_rule=self.start_combo.currentData() or "",
            ccw=bool(self.dir_combo.currentData()),
            offset=float(self.offset_sb.value()),
            flip_normal=bool(self.flip_cb.isChecked()),
        )

    def _report(self, res: dict):
        if not res.get("ok"):
            self.status.setText("⚠  " + (res.get("error") or "failed"))
            self.status.setStyleSheet("color:#f85149;font-size:11px;")
            return
        msg = res.get("info", "")
        for n in res.get("notes") or []:
            msg += f"\n• {n}"
        self.status.setText(msg)
        self.status.setStyleSheet(f"color:{_ACCENT};font-size:11px;")
        self.adjustSize()

    def _on_show(self):
        self._report(self._canvas.apply_surface_spec(self.spec(), show=True))

    def _on_plot(self):
        self._report(self._canvas.plot_surface_series(self.spec()))

    def _on_hide(self):
        self._canvas.clear_surface()
        self.status.setText("Surface hidden (the definition above is kept).")
        self.status.setStyleSheet(f"color:{_DIM};font-size:11px;")
