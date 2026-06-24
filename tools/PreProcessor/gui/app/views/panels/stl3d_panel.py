from __future__ import annotations
import os

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QFrame,
    QFormLayout, QComboBox, QSpinBox, QLabel, QLineEdit, QCheckBox,
    QPushButton, QFileDialog,
)
from PyQt6.QtCore import Qt, pyqtSignal

from app.views.collapsible import CollapsibleSection
from app.views.clean_double_spin_box import CleanDoubleSpinBox
from app.utils import (
    make_button, COMBO_STYLE, SPIN_STYLE, LINEEDIT_STYLE,
    align_form_labels, help_label, block_signals,
)
from app.models.stl3d_config import Stl3dConfig


_SCROLLBAR_QSS = """
    QScrollBar:vertical { border: none; background: #0c0d16; width: 10px; margin: 0px; }
    QScrollBar::handle:vertical { background: #2c2e43; min-height: 20px; border-radius: 5px; }
    QScrollBar::handle:vertical:hover { background: #3e415e; }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
"""


def _spin_style(width: int | None) -> str:
    """SPIN_STYLE, optionally re-capped to ``width`` px so several spins fit one
    row inside the narrow sidebar (the default 110px cap overflows a 3-spin row)."""
    if width is None:
        return SPIN_STYLE
    return SPIN_STYLE.replace("max-width: 110px", f"max-width: {width}px")


def _dspin(lo: float, hi: float, decimals: int, tip: str,
           width: int | None = None) -> CleanDoubleSpinBox:
    s = CleanDoubleSpinBox()
    s.setRange(lo, hi)
    s.setDecimals(decimals)
    s.setStyleSheet(_spin_style(width))
    s.setToolTip(tip)
    return s


def _ispin(lo: int, hi: int, tip: str, width: int | None = None) -> QSpinBox:
    s = QSpinBox()
    s.setRange(lo, hi)
    s.setStyleSheet(_spin_style(width))
    s.setToolTip(tip)
    return s


class Stl3dConfigPanel(QScrollArea):
    """Sidebar panel for the STL3d immersed-solid (STL -> phi) preprocessor.

    The controller connects run_btn / cancel_btn / browse_btn / fit_domain_btn,
    listens to config_changed for the live 3D overlay, and reads/writes the model
    via get_config()/set_config().
    """

    config_changed = pyqtSignal()          # domain / resolution / STL edited

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setStyleSheet("background: #0c0d16;")
        self.verticalScrollBar().setStyleSheet(_SCROLLBAR_QSS)

        content = QWidget()
        content.setStyleSheet("background: #121422; color: #a0a8c0;")
        content.setMaximumWidth(430)
        self._layout = QVBoxLayout(content)
        self._layout.setContentsMargins(6, 6, 6, 6)
        self._layout.setSpacing(6)
        self.setWidget(content)

        # ── Run / Cancel / Fit ────────────────────────────────────────────
        self.run_btn = make_button("Generate phi", "#1e4620")
        self.cancel_btn = make_button("Cancel", "#4a1c1c")
        self.cancel_btn.setEnabled(False)
        self.fit_btn = make_button("Fit View", "#1d2a3a")
        run_row = QHBoxLayout()
        run_row.setSpacing(4)
        run_row.addWidget(self.run_btn)
        run_row.addWidget(self.cancel_btn)
        run_row.addWidget(self.fit_btn)
        self._layout.addLayout(run_row)

        # One-click hand-off: stage phi + generate the reading DLL + enable IBM,
        # then jump to the Solver tab. Enabled only after a successful run.
        self.send_solver_btn = make_button("Send to Solver  →", "#301540")
        self.send_solver_btn.setEnabled(False)
        self.send_solver_btn.setToolTip(
            "Stage the phi field, generate the immersed-solid init DLL, enable IBM "
            "in the Solver config, and switch to the Solver tab.")
        self._layout.addWidget(self.send_solver_btn)

        self.status_lbl = QLabel("Load an STL surface to begin.")
        self.status_lbl.setWordWrap(True)
        self.status_lbl.setStyleSheet("color:#7a82a0; font-size:11px;")
        self._layout.addWidget(self.status_lbl)

        self._build_input_section()
        self._build_domain_section()
        self._build_resolution_section()
        self._build_search_section()
        self._build_parallel_section()

        self._layout.addStretch()

        self._wire_live_signals()

    # ------------------------------------------------------------------ #
    def _build_input_section(self):
        sec = CollapsibleSection("STL Input", start_collapsed=True)
        self._layout.addWidget(sec)
        form = QFormLayout()

        self.stl_path = QLineEdit()
        self.stl_path.setStyleSheet(LINEEDIT_STYLE)
        self.stl_path.setReadOnly(True)
        self.stl_path.setToolTip("STL surface file to mark against the Cartesian grid")
        self.browse_btn = QPushButton("…")
        self.browse_btn.setFixedWidth(32)
        self.browse_btn.setStyleSheet(
            "QPushButton{background:#1d2a3a;color:#dde2ff;border:1px solid #2d3356;"
            "border-radius:4px;padding:2px;} QPushButton:hover{border-color:#5a9ad4;}")
        path_row = QHBoxLayout()
        path_row.setSpacing(4)
        path_row.addWidget(self.stl_path, 1)
        path_row.addWidget(self.browse_btn)
        path_w = QWidget()
        path_w.setLayout(path_row)

        self.ascii_combo = QComboBox()
        self.ascii_combo.addItems(["Auto-detect", "ASCII", "Binary"])
        self.ascii_combo.setStyleSheet(COMBO_STYLE)
        self.ascii_combo.setToolTip("STL encoding. Auto-detect reads the file header.")

        self.case_name = QLineEdit("phi")
        self.case_name.setStyleSheet(LINEEDIT_STYLE)
        self.case_name.setToolTip("Output case name -> <case>_phi_tec.dat / <case>_stl_tec.dat")

        form.addRow(help_label("STL File:", "STL surface file"), path_w)
        form.addRow(help_label("Encoding:", "STL encoding (ASCII / binary)"), self.ascii_combo)
        form.addRow(help_label("Case Name:", "Output case name"), self.case_name)
        align_form_labels(form, 78)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        sec.add_layout(form)

    def _build_domain_section(self):
        sec = CollapsibleSection("Cartesian Domain", start_collapsed=True)
        self._layout.addWidget(sec)

        self.fit_domain_btn = make_button("Auto Domain", "#1d2a3a")
        self.fit_domain_btn.setToolTip(
            "Set the domain bounds to the STL bounding box, padded by margin %")
        margin_row = QHBoxLayout()
        margin_row.setSpacing(4)
        margin_row.addWidget(self.fit_domain_btn, 1)
        mlbl = QLabel("margin %")
        mlbl.setStyleSheet("color:#7a82a0;")
        self.margin_spin = _dspin(0.0, 100.0, 1, "Padding around the STL bounding box, in % of extent")
        self.margin_spin.setValue(10.0)
        self.margin_spin.setFixedWidth(70)
        margin_row.addWidget(mlbl)
        margin_row.addWidget(self.margin_spin)
        sec.add_layout(margin_row)

        form = QFormLayout()
        self.xmin = _dspin(-1e9, 1e9, 6, "Domain x min", width=90)
        self.xmax = _dspin(-1e9, 1e9, 6, "Domain x max", width=90)
        self.ymin = _dspin(-1e9, 1e9, 6, "Domain y min", width=90)
        self.ymax = _dspin(-1e9, 1e9, 6, "Domain y max", width=90)
        self.zmin = _dspin(-1e9, 1e9, 6, "Domain z min", width=90)
        self.zmax = _dspin(-1e9, 1e9, 6, "Domain z max", width=90)
        for lo, hi, lbl in [(self.xmin, self.xmax, "X range:"),
                            (self.ymin, self.ymax, "Y range:"),
                            (self.zmin, self.zmax, "Z range:")]:
            row = QHBoxLayout()
            row.setSpacing(4)
            row.addWidget(lo)
            row.addWidget(hi)
            w = QWidget()
            w.setLayout(row)
            form.addRow(help_label(lbl, "Cartesian domain bounds (min, max)"), w)
        align_form_labels(form, 78)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        sec.add_layout(form)

    def _build_resolution_section(self):
        sec = CollapsibleSection("Grid Resolution", start_collapsed=True)
        self._layout.addWidget(sec)
        form = QFormLayout()
        self.nx = _ispin(2, 4096, "Number of grid points in x", width=66)
        self.ny = _ispin(2, 4096, "Number of grid points in y", width=66)
        self.nz = _ispin(1, 4096, "Number of grid points in z (use 2 for a quasi-2D / planar case)", width=66)
        self.nx.setValue(128); self.ny.setValue(128); self.nz.setValue(2)
        n_row = QHBoxLayout()
        n_row.setSpacing(4)
        for w in (self.nx, self.ny, self.nz):
            n_row.addWidget(w)
        nw = QWidget()
        nw.setLayout(n_row)
        form.addRow(help_label("Nx, Ny, Nz:", "Grid points per axis"), nw)
        align_form_labels(form, 78)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        sec.add_layout(form)

        self.derived_lbl = QLabel("")
        self.derived_lbl.setWordWrap(True)
        self.derived_lbl.setStyleSheet("color:#8892b0; font-size:11px;")
        sec.add_widget(self.derived_lbl)
        self.warn_lbl = QLabel("")
        self.warn_lbl.setWordWrap(True)
        self.warn_lbl.setStyleSheet("color:#eab308; font-size:11px;")
        self.warn_lbl.setVisible(False)
        sec.add_widget(self.warn_lbl)

    def _build_search_section(self):
        sec = CollapsibleSection("Search Method", start_collapsed=True)
        self._layout.addWidget(sec)
        form = QFormLayout()
        self.search_combo = QComboBox()
        self.search_combo.addItems([
            "All elements (robust, slower)",
            "Close x-range (faster, may miss large elements)",
        ])
        self.search_combo.setStyleSheet(COMBO_STYLE)
        self.search_combo.setToolTip(
            "Ray-tracing element search. All-elements never misses a triangle but "
            "scales with surface size; close x-range is faster on uniform meshes.")
        form.addRow(help_label("Method:", "Ray-tracing element search strategy"), self.search_combo)
        align_form_labels(form, 78)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        sec.add_layout(form)

    def _build_parallel_section(self):
        sec = CollapsibleSection("Parallel (OpenMP)", start_collapsed=True)
        self._layout.addWidget(sec)

        self.omp_cb = QCheckBox("Enable OpenMP")
        self.omp_cb.setStyleSheet("color:#a0a8c0;")
        self.omp_cb.setToolTip(
            "Off = single-threaded (default). On = parallel ray tracing across the "
            "chosen number of threads. Biggest gains on heavy STLs / all-element search.")
        sec.add_widget(self.omp_cb)

        row = QHBoxLayout()
        row.setSpacing(6)
        tlbl = QLabel("Threads:")
        tlbl.setStyleSheet("color:#7a82a0;")
        tlbl.setFixedWidth(78)
        self.threads_spin = QSpinBox()
        self.threads_spin.setRange(1, 256)
        self.threads_spin.setValue(max(1, os.cpu_count() or 1))   # default = all cores
        self.threads_spin.setStyleSheet(_spin_style(70))
        self.threads_spin.setEnabled(False)
        self.threads_spin.setToolTip("OMP_NUM_THREADS used when OpenMP is enabled")
        row.addWidget(tlbl)
        row.addWidget(self.threads_spin)
        row.addStretch()
        sec.add_layout(row)

        hint = QLabel(f"Detected {os.cpu_count() or '?'} logical cores.")
        hint.setStyleSheet("color:#6b7390; font-size:10px;")
        sec.add_widget(hint)

    # ------------------------------------------------------------------ #
    def omp_threads(self) -> int:
        """Effective OMP_NUM_THREADS: 1 (serial) unless OpenMP is enabled."""
        return self.threads_spin.value() if self.omp_cb.isChecked() else 1

    # ------------------------------------------------------------------ #
    def _wire_live_signals(self):
        for w in (self.xmin, self.xmax, self.ymin, self.ymax, self.zmin, self.zmax,
                  self.nx, self.ny, self.nz):
            w.valueChanged.connect(self._on_cfg_edited)
        self.case_name.textChanged.connect(lambda *_: self.config_changed.emit())
        self.omp_cb.toggled.connect(self.threads_spin.setEnabled)

    def _on_cfg_edited(self, *_):
        self.refresh_derived()
        self.config_changed.emit()

    def refresh_derived(self):
        """Recompute dx/dy/dz, cell count, and the over-resolution warning."""
        cfg = self.get_config()
        dx, dy, dz = cfg.spacings()
        n = cfg.cell_count
        self.derived_lbl.setText(
            f"dx={dx:.4g}  dy={dy:.4g}  dz={dz:.4g}\nTotal cells: {n:,}")
        if n > 4_000_000:
            self.warn_lbl.setText(
                f"⚠ {n:,} cells — ray tracing and rendering may be slow.")
            self.warn_lbl.setVisible(True)
        else:
            self.warn_lbl.setVisible(False)

    # ------------------------------------------------------------------ #
    def get_config(self, cfg: Stl3dConfig | None = None) -> Stl3dConfig:
        cfg = cfg or Stl3dConfig()
        cfg.stl_path = self.stl_path.text().strip()
        cfg.case_name = self.case_name.text().strip() or "phi"
        # Encoding: ASCII/Binary override; Auto-detect resolves to ASCII here and
        # is set concretely by the controller when an STL is loaded.
        enc = self.ascii_combo.currentText()
        cfg.ascii = (enc != "Binary")
        cfg.xmin, cfg.xmax = self.xmin.value(), self.xmax.value()
        cfg.ymin, cfg.ymax = self.ymin.value(), self.ymax.value()
        cfg.zmin, cfg.zmax = self.zmin.value(), self.zmax.value()
        cfg.nx, cfg.ny, cfg.nz = self.nx.value(), self.ny.value(), self.nz.value()
        cfg.all_search = self.search_combo.currentIndex() == 0
        cfg.omp_threads = self.omp_threads()   # 1 = serial (OpenMP off)
        return cfg

    def set_config(self, cfg: Stl3dConfig):
        widgets = [self.xmin, self.xmax, self.ymin, self.ymax, self.zmin, self.zmax,
                   self.nx, self.ny, self.nz, self.case_name, self.ascii_combo,
                   self.search_combo, self.stl_path]
        with block_signals(*widgets):
            self.stl_path.setText(cfg.stl_path)
            self.case_name.setText(cfg.case_name)
            self.ascii_combo.setCurrentText("ASCII" if cfg.ascii else "Binary")
            self.xmin.setValue(cfg.xmin); self.xmax.setValue(cfg.xmax)
            self.ymin.setValue(cfg.ymin); self.ymax.setValue(cfg.ymax)
            self.zmin.setValue(cfg.zmin); self.zmax.setValue(cfg.zmax)
            self.nx.setValue(cfg.nx); self.ny.setValue(cfg.ny); self.nz.setValue(cfg.nz)
            self.search_combo.setCurrentIndex(0 if cfg.all_search else 1)
        # omp_threads > 1 means OpenMP was enabled with that thread count.
        with block_signals(self.omp_cb, self.threads_spin):
            enabled = int(getattr(cfg, "omp_threads", 1) or 1) > 1
            self.omp_cb.setChecked(enabled)
            self.threads_spin.setEnabled(enabled)
            if enabled:
                self.threads_spin.setValue(int(cfg.omp_threads))
        self.refresh_derived()
