from __future__ import annotations
import csv
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QHBoxLayout, QLabel, QCheckBox,
    QPushButton, QButtonGroup, QLineEdit, QTableWidget, QTableWidgetItem,
    QHeaderView, QSpinBox, QFileDialog, QScrollArea, QFrame, QComboBox,
)

from app.views.collapsible import CollapsibleSection
from app.utils import (
    make_button, SPIN_STYLE, align_form_labels, LINEEDIT_STYLE, COMBO_STYLE,
)
from app.views.clean_double_spin_box import CleanDoubleSpinBox

_TABLE_QSS = (
    "QTableWidget{background:#181b2a;color:#a0a8c0;border:1px solid #333852;"
    "gridline-color:#2c2e43;} QHeaderView::section{background:#1e2235;"
    "color:#a0a8c0;border:none;padding:3px;}")
_SCROLLBAR_QSS = """
    QScrollBar:vertical { border: none; background: #0c0d16; width: 10px; margin: 0px; }
    QScrollBar::handle:vertical { background: #2c2e43; min-height: 20px; border-radius: 5px; }
    QScrollBar::handle:vertical:hover { background: #3e415e; }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
"""
_COLORMAPS = ["turbo", "viridis", "inferno", "plasma", "coolwarm", "jet", "RdBu_r"]


class ResultControlPanel(QWidget):
    """Results-mode left sidebar: interactive post-processing tools.

    Industrial-style probe (point query, all variables listed) and line probe
    (plot over line), iso-value overlay, min/max location, color-scale (colormap,
    log / symmetric), vector & streamline controls, and area-weighted field
    statistics. All controls drive the ResultCanvasView. The panel scrolls, and
    every section starts collapsed.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: #121422; color: #a0a8c0;")
        self._canvas = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.verticalScrollBar().setStyleSheet(_SCROLLBAR_QSS)
        content = QWidget()
        content.setStyleSheet("background: #121422; color: #a0a8c0;")
        root = QVBoxLayout(content)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(6)

        self._build_tools(root)
        self._build_probes(root)
        self._build_line(root)
        self._build_iso(root)
        self._build_extrema(root)
        self._build_color(root)
        self._build_vectors(root)
        self._build_stats(root)
        root.addStretch()

        scroll.setWidget(content)
        outer.addWidget(scroll)

    # ------------------------------------------------------------------ #
    # Section builders  (every section starts collapsed)
    # ------------------------------------------------------------------ #
    def _build_tools(self, root):
        sec = CollapsibleSection("Probe Tools", start_collapsed=True)
        root.addWidget(sec)
        hint = QLabel("Pick a tool, then click on the plot. Off = pan/zoom (and "
                      "clears probes & line).")
        hint.setStyleSheet("color:#7a82a0; font-size: 10px;")
        hint.setWordWrap(True)
        sec.add_widget(hint)

        row = QHBoxLayout()
        row.setSpacing(4)
        self.tool_off = QPushButton("Off")
        self.tool_probe = QPushButton("Probe")
        self.tool_line = QPushButton("Line")
        self._tool_group = QButtonGroup(self)
        self._tool_group.setExclusive(True)
        for b in (self.tool_off, self.tool_probe, self.tool_line):
            b.setCheckable(True)
            b.setStyleSheet(
                "QPushButton{background:#1d2436;color:#cdd3ee;border:1px solid #2d3356;"
                "border-radius:4px;padding:4px;font-size:11px;}"
                "QPushButton:checked{background:#27406a;border-color:#5a9ad4;color:#fff;}")
            self._tool_group.addButton(b)
            row.addWidget(b)
        self.tool_off.setChecked(True)
        sec.add_layout(row)
        self.tool_off.clicked.connect(lambda: self._set_mode(None))
        self.tool_probe.clicked.connect(lambda: self._set_mode("probe"))
        self.tool_line.clicked.connect(lambda: self._set_mode("line"))

    def _build_probes(self, root):
        sec = CollapsibleSection("Probes", start_collapsed=True)
        root.addWidget(sec)
        self.probe_table = QTableWidget(0, 3)
        self.probe_table.setHorizontalHeaderLabels(["#", "x", "y"])
        self.probe_table.setFixedHeight(110)
        self.probe_table.setStyleSheet(_TABLE_QSS)
        self.probe_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.probe_table.verticalHeader().setVisible(False)
        self.probe_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        sec.add_widget(self.probe_table)

        btns = QHBoxLayout(); btns.setSpacing(4)
        self.probe_undo_btn = make_button("Remove Last", "#301a1a")
        self.probe_clear_btn = make_button("Clear", "#301a1a")
        self.probe_export_btn = make_button("Export CSV", "#1a2a3a")
        for b in (self.probe_undo_btn, self.probe_clear_btn, self.probe_export_btn):
            btns.addWidget(b)
        sec.add_layout(btns)

        # Exact-coordinate entry (alternative to clicking on the plot).
        self.probe_x = self._coord_spin(); self.probe_y = self._coord_spin()
        self.probe_add_btn = make_button("Add", "#1e2a38")
        self.probe_add_btn.setFixedWidth(54)
        coord = QHBoxLayout(); coord.setSpacing(4)
        coord.addWidget(self._xy_pair(self.probe_x, self.probe_y), 1)
        coord.addWidget(self.probe_add_btn)
        sec.add_layout(coord)

        # All-variable values for the selected probe.
        det = QLabel("Selected probe — all variables:")
        det.setStyleSheet("color:#7a82a0; font-size: 10px;")
        sec.add_widget(det)
        self.probe_detail = QTableWidget(0, 2)
        self.probe_detail.setHorizontalHeaderLabels(["variable", "value"])
        self.probe_detail.setFixedHeight(150)
        self.probe_detail.setStyleSheet(_TABLE_QSS)
        self.probe_detail.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.probe_detail.verticalHeader().setVisible(False)
        sec.add_widget(self.probe_detail)

        self.probe_undo_btn.clicked.connect(self._on_probe_undo)
        self.probe_clear_btn.clicked.connect(self._on_probe_clear)
        self.probe_export_btn.clicked.connect(self._export_probes)
        self.probe_add_btn.clicked.connect(self._on_probe_add_coord)
        self.probe_table.itemSelectionChanged.connect(self._show_selected_probe_detail)

    def _build_line(self, root):
        sec = CollapsibleSection("Line Probe (plot over line)", start_collapsed=True)
        root.addWidget(sec)
        hint = QLabel("Pick the Line tool and click two points on the plot, or enter "
                      "exact endpoints below. The distribution opens in a chart window "
                      "where you can switch variable.")
        hint.setStyleSheet("color:#7a82a0; font-size: 10px;")
        hint.setWordWrap(True)
        sec.add_widget(hint)

        self.line_x0 = self._coord_spin(); self.line_y0 = self._coord_spin()
        self.line_x1 = self._coord_spin(); self.line_y1 = self._coord_spin()
        sec.add_widget(self._labeled("Start:", self._xy_pair(self.line_x0, self.line_y0)))
        sec.add_widget(self._labeled("End:", self._xy_pair(self.line_x1, self.line_y1)))

        btns = QHBoxLayout(); btns.setSpacing(4)
        self.line_plot_btn = make_button("Plot Line", "#1e2a38")
        self.line_clear_btn = make_button("Clear Line", "#301a1a")
        btns.addWidget(self.line_plot_btn); btns.addWidget(self.line_clear_btn)
        sec.add_layout(btns)
        self.line_plot_btn.clicked.connect(self._on_line_plot_coord)
        self.line_clear_btn.clicked.connect(self._on_line_clear)

    def _build_iso(self, root):
        sec = CollapsibleSection("Iso-contour Lines", start_collapsed=True)
        root.addWidget(sec)
        hint = QLabel("Toggle visibility with the 'Iso' box in the top bar.")
        hint.setStyleSheet("color:#7a82a0; font-size: 10px;")
        hint.setWordWrap(True)
        sec.add_widget(hint)

        # Mode selector: specify levels either as explicit values or a range.
        self.iso_mode = QComboBox()
        self.iso_mode.addItems(["Explicit values", "Range (from–to–step)"])
        self.iso_mode.setStyleSheet(COMBO_STYLE)
        self.iso_mode.setToolTip(
            "Explicit = a comma-separated list of levels.\n"
            "Range = evenly spaced levels from 'from' to 'to' every 'step'.")
        sec.add_widget(self._labeled("Levels:", self.iso_mode))

        # Explicit-values row (shown in Explicit mode).
        self.iso_values = QLineEdit()
        self.iso_values.setStyleSheet(LINEEDIT_STYLE)
        self.iso_values.setPlaceholderText("e.g. 1.0, 0.5  (M=1 sonic line)")
        self.iso_values.setToolTip("Comma-separated iso values")
        self._iso_values_row = self._labeled("Values:", self.iso_values)
        sec.add_widget(self._iso_values_row)

        # Range row (shown in Range mode) — compact spins so it never overflows.
        compact = SPIN_STYLE.replace("max-width: 110px", "max-width: 50px")
        self.iso_from = CleanDoubleSpinBox(); self.iso_to = CleanDoubleSpinBox()
        self.iso_step = CleanDoubleSpinBox()
        for s in (self.iso_from, self.iso_to, self.iso_step):
            s.setRange(-1e9, 1e9); s.setDecimals(3); s.setStyleSheet(compact)
        self.iso_step.setRange(0.0, 1e9)
        self._iso_range_row = QWidget()
        rng = QHBoxLayout(self._iso_range_row)
        rng.setSpacing(3); rng.setContentsMargins(0, 0, 0, 0)
        rlab = QLabel("Range:"); rlab.setStyleSheet("color:#7a82a0;"); rlab.setFixedWidth(64)
        rng.addWidget(rlab)
        for lab, w in [("from", self.iso_from), ("to", self.iso_to), ("step", self.iso_step)]:
            t = QLabel(lab); t.setStyleSheet("color:#7a82a0; font-size:10px;")
            rng.addWidget(t); rng.addWidget(w)
        rng.addStretch()
        sec.add_widget(self._iso_range_row)
        self._iso_range_row.setVisible(False)   # default: Explicit mode

        btns = QHBoxLayout(); btns.setSpacing(4)
        self.iso_apply_btn = make_button("Apply", "#1e2a38")
        self.iso_clear_btn = make_button("Clear", "#301a1a")
        btns.addWidget(self.iso_apply_btn); btns.addWidget(self.iso_clear_btn)
        sec.add_layout(btns)
        self.iso_mode.currentIndexChanged.connect(self._on_iso_mode)
        self.iso_apply_btn.clicked.connect(self._apply_iso)
        self.iso_clear_btn.clicked.connect(self._on_iso_clear)

    def _build_extrema(self, root):
        sec = CollapsibleSection("Min / Max", start_collapsed=True)
        root.addWidget(sec)
        hint = QLabel("Locate and mark the current field's extrema on the plot.")
        hint.setStyleSheet("color:#7a82a0; font-size: 10px;"); hint.setWordWrap(True)
        sec.add_widget(hint)
        self.min_btn = make_button("Mark Min", "#143044")
        self.max_btn = make_button("Mark Max", "#3a1414")
        self.both_btn = make_button("Both", "#1a2a3a")
        self.extrema_clear_btn = make_button("Clear", "#301a1a")
        r1 = QHBoxLayout(); r1.setSpacing(4)
        r1.addWidget(self.min_btn); r1.addWidget(self.max_btn)
        sec.add_layout(r1)
        r2 = QHBoxLayout(); r2.setSpacing(4)
        r2.addWidget(self.both_btn); r2.addWidget(self.extrema_clear_btn)
        sec.add_layout(r2)
        # Readouts of the located extrema.
        self.lbl_minval = self._info_row(sec, "min:")
        self.lbl_maxval = self._info_row(sec, "max:")
        self.min_btn.clicked.connect(lambda: self._mark("min"))
        self.max_btn.clicked.connect(lambda: self._mark("max"))
        self.both_btn.clicked.connect(lambda: self._mark("both"))
        self.extrema_clear_btn.clicked.connect(self._clear_extrema)

    def _sub_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet("color:#6b7390; font-size:10px; font-weight:bold;")
        return lbl

    def _hsep(self) -> QFrame:
        f = QFrame(); f.setFrameShape(QFrame.Shape.HLine)
        f.setStyleSheet("color:#262a3e;")
        return f

    def _labeled(self, text: str, w) -> QWidget:
        """A compact [label | widget] row packed into one QWidget so it can be
        shown/hidden as a unit."""
        box = QWidget(); h = QHBoxLayout(box)
        h.setContentsMargins(0, 0, 0, 0); h.setSpacing(6)
        lab = QLabel(text); lab.setStyleSheet("color:#7a82a0;"); lab.setFixedWidth(64)
        h.addWidget(lab); h.addWidget(w, 1)
        return box

    def _build_color(self, root):
        sec = CollapsibleSection("Color Scale", start_collapsed=True)
        root.addWidget(sec)

        # ── Colormap + shading style ───────────────────────────────────────
        self.cmap_combo = QComboBox()
        self.cmap_combo.addItems(_COLORMAPS)
        self.cmap_combo.setStyleSheet(COMBO_STYLE)
        sec.add_widget(self._labeled("Colormap:", self.cmap_combo))

        self.level_mode = QComboBox()
        self.level_mode.addItems(["Continuous", "Banded — by count", "Banded — by Δ"])
        self.level_mode.setStyleSheet(COMBO_STYLE)
        self.level_mode.setToolTip(
            "Continuous = smooth gradient (default).\n"
            "Banded — by count = N discrete colour bands.\n"
            "Banded — by Δ = bands at a fixed value spacing.")
        sec.add_widget(self._labeled("Shading:", self.level_mode))

        # Only the input for the chosen shading is shown (others hidden, not
        # greyed) so the panel stays uncluttered.
        self.n_levels = QSpinBox()
        self.n_levels.setRange(2, 200); self.n_levels.setValue(24)
        self.n_levels.setStyleSheet(SPIN_STYLE)
        self.n_levels.setToolTip("Number of colour bands.")
        self._count_row = self._labeled("Bands:", self.n_levels)
        sec.add_widget(self._count_row)

        self.level_delta = CleanDoubleSpinBox()
        self.level_delta.setRange(0.0, 1e9); self.level_delta.setDecimals(4)
        self.level_delta.setStyleSheet(SPIN_STYLE)
        self.level_delta.setToolTip("Value spacing between bands.")
        self._delta_row = self._labeled("Δ value:", self.level_delta)
        sec.add_widget(self._delta_row)
        self._count_row.setVisible(False)
        self._delta_row.setVisible(False)

        # ── Range ──────────────────────────────────────────────────────────
        sec.add_widget(self._hsep())
        sec.add_widget(self._sub_label("RANGE"))
        self.auto_cb = QCheckBox("Auto (fit to data)")
        self.auto_cb.setChecked(True)
        self.auto_cb.setStyleSheet("color:#a0a8c0;")
        sec.add_widget(self.auto_cb)
        # Custom-range controls live in one box, hidden while Auto is on.
        self._range_box = QWidget()
        rv = QVBoxLayout(self._range_box)
        rv.setContentsMargins(0, 0, 0, 0); rv.setSpacing(4)
        self.vmin = CleanDoubleSpinBox(); self.vmax = CleanDoubleSpinBox()
        for s in (self.vmin, self.vmax):
            s.setRange(-1e12, 1e12); s.setDecimals(6); s.setStyleSheet(SPIN_STYLE)
        rv.addWidget(self._labeled("Min:", self.vmin))
        rv.addWidget(self._labeled("Max:", self.vmax))
        self.apply_btn = make_button("Apply range", "#1e2a38")
        rv.addWidget(self.apply_btn)
        sec.add_widget(self._range_box)
        self._range_box.setVisible(False)

        # ── Scale transform ────────────────────────────────────────────────
        sec.add_widget(self._hsep())
        sec.add_widget(self._sub_label("SCALE"))
        self.log_cb = QCheckBox("Log scale")
        self.log_cb.setToolTip("Logarithmic colour scale (positive data only).")
        self.sym_cb = QCheckBox("Symmetric about 0")
        self.sym_cb.setToolTip("Symmetric range ±max|v| (signed fields: vorticity, Cp).")
        for cb in (self.log_cb, self.sym_cb):
            cb.setStyleSheet("color:#a0a8c0;")
            sec.add_widget(cb)

        self.cmap_combo.currentTextChanged.connect(self._on_cmap_changed)
        self.level_mode.currentIndexChanged.connect(self._apply_levels)
        self.n_levels.valueChanged.connect(self._apply_levels)
        self.level_delta.valueChanged.connect(self._apply_levels)
        self.auto_cb.toggled.connect(self._on_auto_toggled)
        self.apply_btn.clicked.connect(self._on_apply)
        self.log_cb.toggled.connect(self._apply_norm)
        self.sym_cb.toggled.connect(self._apply_norm)

    def _build_vectors(self, root):
        sec = CollapsibleSection("Vectors / Streamlines", start_collapsed=True)
        root.addWidget(sec)
        hint = QLabel("Turn each overlay on with its box in the top bar; tune it here, "
                      "then Apply.")
        hint.setStyleSheet("color:#7a82a0; font-size: 10px;"); hint.setWordWrap(True)
        sec.add_widget(hint)

        sec.add_widget(self._sub_label("VECTORS"))
        self.vec_density = QSpinBox()
        self.vec_density.setRange(8, 120); self.vec_density.setValue(40)
        self.vec_density.setStyleSheet(SPIN_STYLE)
        self.vec_density.setToolTip("Number of vector glyphs per axis (sampling density).")
        self.vec_scale = CleanDoubleSpinBox()
        self.vec_scale.setRange(0.05, 100.0); self.vec_scale.setValue(1.0)
        self.vec_scale.setDecimals(2); self.vec_scale.setStyleSheet(SPIN_STYLE)
        self.vec_scale.setToolTip(
            "Arrow length scale. Arrow length = velocity × this, in data units; "
            "increase if arrows look too short, decrease if they overlap.")
        sec.add_widget(self._labeled("Density:", self.vec_density))
        sec.add_widget(self._labeled("Scale:", self.vec_scale))

        sec.add_widget(self._sub_label("STREAMLINES"))
        self.stream_density = CleanDoubleSpinBox()
        self.stream_density.setRange(0.2, 6.0); self.stream_density.setValue(1.2)
        self.stream_density.setDecimals(1); self.stream_density.setStyleSheet(SPIN_STYLE)
        self.stream_density.setToolTip("Streamline seeding density.")
        sec.add_widget(self._labeled("Density:", self.stream_density))
        self.stream_lw_cb = QCheckBox("Width by speed")
        self.stream_lw_cb.setChecked(True)
        self.stream_lw_cb.setStyleSheet("color:#a0a8c0;")
        sec.add_widget(self.stream_lw_cb)

        sec.add_widget(self._hsep())
        self.vec_apply_btn = make_button("Apply", "#1e2a38")
        sec.add_widget(self.vec_apply_btn)
        self.vec_apply_btn.clicked.connect(self._apply_vec_stream)

    def _build_stats(self, root):
        info = CollapsibleSection("Field Info / Stats", start_collapsed=True)
        root.addWidget(info)
        self.lbl_var = self._info_row(info, "Variable:")
        self.lbl_min = self._info_row(info, "Data min:")
        self.lbl_max = self._info_row(info, "Data max:")
        self.lbl_mean = self._info_row(info, "Area mean:")
        self.lbl_std = self._info_row(info, "Area std:")
        self.lbl_integral = self._info_row(info, "∫ dA:")

    def _coord_spin(self) -> CleanDoubleSpinBox:
        s = CleanDoubleSpinBox()
        s.setRange(-1e9, 1e9)
        s.setDecimals(4)
        # Compact so an x/y pair fits the narrow sidebar (SPIN_STYLE caps at 110).
        s.setStyleSheet(SPIN_STYLE.replace("max-width: 110px", "max-width: 66px"))
        return s

    def _xy_pair(self, sx, sy) -> QWidget:
        """[x: <spin>  y: <spin>] packed into one widget."""
        box = QWidget(); h = QHBoxLayout(box)
        h.setContentsMargins(0, 0, 0, 0); h.setSpacing(3)
        for lab, w in [("x:", sx), ("y:", sy)]:
            t = QLabel(lab); t.setStyleSheet("color:#7a82a0; font-size:10px;")
            h.addWidget(t); h.addWidget(w)
        h.addStretch()
        return box

    def _info_row(self, sec, label: str) -> QLabel:
        row = QHBoxLayout(); row.setSpacing(6)
        k = QLabel(label); k.setStyleSheet("color:#7a82a0;"); k.setFixedWidth(80)
        v = QLabel("—"); v.setStyleSheet("color:#dde2ff;")
        row.addWidget(k); row.addWidget(v, 1)
        sec.add_layout(row)
        return v

    # ------------------------------------------------------------------ #
    def bind(self, canvas):
        """Connect to the result canvas (called by the controller)."""
        self._canvas = canvas
        canvas.result_rendered.connect(self._on_rendered)
        canvas.probe_added.connect(self._on_probe_added)
        canvas.extrema_found.connect(self._on_extrema_found)
        # Reflect the canvas's current colormap in the sidebar selector.
        self.cmap_combo.blockSignals(True)
        self.cmap_combo.setCurrentText(getattr(canvas, "_cmap", _COLORMAPS[0]))
        self.cmap_combo.blockSignals(False)

    # ── Tools ──────────────────────────────────────────────────────────
    def _set_mode(self, mode):
        if self._canvas is None:
            return
        self._canvas.set_interact_mode(mode)
        # Off doubles as a clear: drop probes & line from the canvas and tables.
        if mode is None:
            self._canvas.clear_probes()
            self._canvas.clear_line()
            self.probe_table.setRowCount(0)
            self.probe_detail.setRowCount(0)

    # ── Probes ─────────────────────────────────────────────────────────
    def _on_probe_added(self, p: dict):
        r = self.probe_table.rowCount()
        self.probe_table.insertRow(r)
        self.probe_table.setItem(r, 0, QTableWidgetItem(f"P{r+1}"))
        self.probe_table.setItem(r, 1, QTableWidgetItem(f"{p['x']:.4g}"))
        self.probe_table.setItem(r, 2, QTableWidgetItem(f"{p['y']:.4g}"))
        self.probe_table.selectRow(r)  # -> _show_selected_probe_detail

    def _show_selected_probe_detail(self):
        if self._canvas is None:
            return
        probes = getattr(self._canvas, "_probes", [])
        r = self.probe_table.currentRow()
        self.probe_detail.setRowCount(0)
        if not (0 <= r < len(probes)):
            return
        for var, val in probes[r]["vals"].items():
            i = self.probe_detail.rowCount()
            self.probe_detail.insertRow(i)
            self.probe_detail.setItem(i, 0, QTableWidgetItem(str(var)))
            txt = f"{val:.6g}" if val == val else "—"  # val==val rejects nan
            self.probe_detail.setItem(i, 1, QTableWidgetItem(txt))

    def _on_probe_undo(self):
        if self._canvas is not None:
            self._canvas.remove_last_probe()
        if self.probe_table.rowCount():
            self.probe_table.removeRow(self.probe_table.rowCount() - 1)
        self._show_selected_probe_detail()

    def _on_probe_clear(self):
        if self._canvas is not None:
            self._canvas.clear_probes()
        self.probe_table.setRowCount(0)
        self.probe_detail.setRowCount(0)

    def _on_probe_add_coord(self):
        if self._canvas is not None:
            self._canvas.add_probe_at(self.probe_x.value(), self.probe_y.value())

    def _export_probes(self):
        if self._canvas is None or not getattr(self._canvas, "_probes", []):
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export Probes", "probes.csv",
                                              "CSV (*.csv);;All Files (*)")
        if not path:
            return
        probes = self._canvas._probes
        variables = list(probes[0]["vals"].keys())
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["#", "x", "y"] + variables)
            for i, p in enumerate(probes):
                w.writerow([f"P{i+1}", p["x"], p["y"]]
                           + [p["vals"].get(v, "") for v in variables])

    # ── Line ───────────────────────────────────────────────────────────
    def _on_line_plot_coord(self):
        if self._canvas is not None:
            self._canvas.add_line_segment(
                (self.line_x0.value(), self.line_y0.value()),
                (self.line_x1.value(), self.line_y1.value()))

    def _on_line_clear(self):
        if self._canvas is not None:
            self._canvas.clear_line()

    # ── Iso ────────────────────────────────────────────────────────────
    def _on_iso_mode(self, *_):
        is_range = self.iso_mode.currentIndex() == 1
        self._iso_values_row.setVisible(not is_range)
        self._iso_range_row.setVisible(is_range)

    def _apply_iso(self, *_):
        if self._canvas is None:
            return
        levels = []
        if self.iso_mode.currentIndex() == 0:  # explicit values
            for tok in self.iso_values.text().replace(";", ",").split(","):
                tok = tok.strip()
                if not tok:
                    continue
                try:
                    levels.append(float(tok))
                except ValueError:
                    pass
        else:  # range from..to inclusive, stepping by step (capped count)
            step = self.iso_step.value()
            if step > 0:
                a, b = self.iso_from.value(), self.iso_to.value()
                if b >= a:
                    v, n = a, 0
                    while v <= b + step * 1e-6 and n < 1000:
                        levels.append(round(v, 10)); v += step; n += 1
        # Applying turns the overlay on (top-bar 'Iso' box is synced by the canvas).
        self._canvas.set_iso(sorted(set(levels)), True)

    def _on_iso_clear(self):
        self.iso_values.clear()
        self.iso_step.setValue(0.0)
        if self._canvas is not None:
            self._canvas.set_iso([], False)

    # ── Extrema ────────────────────────────────────────────────────────
    def _mark(self, which: str):
        # Canvas replaces its marked set each call; reset both readouts first.
        self.lbl_minval.setText("—"); self.lbl_maxval.setText("—")
        if self._canvas is not None:
            self._canvas.mark_extrema(which)

    def _on_extrema_found(self, e: dict):
        txt = f"{e['value']:.4g} @ ({e['x']:.3g}, {e['y']:.3g})"
        (self.lbl_minval if e.get("which") == "min" else self.lbl_maxval).setText(txt)

    def _clear_extrema(self):
        self.lbl_minval.setText("—"); self.lbl_maxval.setText("—")
        if self._canvas is not None:
            self._canvas.clear_extrema()

    # ── Color scale ────────────────────────────────────────────────────
    def _on_cmap_changed(self, name: str):
        if self._canvas is not None and name:
            self._canvas.set_cmap(name)

    def _apply_levels(self, *_):
        mode = ("smooth", "count", "delta")[self.level_mode.currentIndex()]
        # Show only the input relevant to the chosen shading mode.
        self._count_row.setVisible(mode == "count")
        self._delta_row.setVisible(mode == "delta")
        if self._canvas is not None:
            self._canvas.set_levels(mode, self.n_levels.value(), self.level_delta.value())

    def _on_auto_toggled(self, checked: bool):
        # Reveal the Min/Max/Apply box only in custom-range mode.
        self._range_box.setVisible(not checked)
        if self._canvas is not None and checked:
            self._canvas.set_clim_auto(True)

    def _on_apply(self):
        if self._canvas is not None:
            self._canvas.set_clim(self.vmin.value(), self.vmax.value())

    def _apply_norm(self, *_):
        if self._canvas is not None:
            self._canvas.set_color_norm(self.log_cb.isChecked(), self.sym_cb.isChecked())

    # ── Vectors / streamlines ──────────────────────────────────────────
    def _apply_vec_stream(self, *_):
        if self._canvas is not None:
            self._canvas.set_vector_params(self.vec_density.value(), self.vec_scale.value())
            self._canvas.set_stream_params(self.stream_density.value(),
                                           self.stream_lw_cb.isChecked())

    # ── Stats / render echo ────────────────────────────────────────────
    def _on_rendered(self, info: dict):
        self.lbl_var.setText(str(info.get("var", "—")))
        self.lbl_min.setText(f"{info.get('dmin', 0.0):.6g}")
        self.lbl_max.setText(f"{info.get('dmax', 0.0):.6g}")
        stats = self._canvas.integral_stats() if self._canvas is not None else {}
        if stats:
            self.lbl_mean.setText(f"{stats['mean']:.6g}")
            self.lbl_std.setText(f"{stats['std']:.6g}")
            self.lbl_integral.setText(f"{stats['integral']:.6g}")
        else:
            self.lbl_mean.setText(f"{info.get('mean', 0.0):.6g}")
            self.lbl_std.setText("—")
            self.lbl_integral.setText("—")
        if self.auto_cb.isChecked():
            self.vmin.blockSignals(True); self.vmax.blockSignals(True)
            self.vmin.setValue(info.get("vmin", 0.0))
            self.vmax.setValue(info.get("vmax", 1.0))
            self.vmin.blockSignals(False); self.vmax.blockSignals(False)
        # A new result drops the canvas's probes -> clear the tables.
        if self._canvas is not None and not getattr(self._canvas, "_probes", []):
            self.probe_table.setRowCount(0)
            self.probe_detail.setRowCount(0)
