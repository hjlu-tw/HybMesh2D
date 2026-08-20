from __future__ import annotations
import os

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QFrame,
    QFormLayout, QLabel, QPushButton,
)
from PyQt6.QtCore import Qt, pyqtSignal

from app.views.collapsible import CollapsibleSection
from app.utils import (
    make_button, align_form_labels, help_label, make_help_label, block_signals,
)
from app.views.panels.field_widgets import (
    SpecRowsMixin, read_specs, spec_widgets, write_specs,
)
from app.views.panels.stl3d_field_specs import STL3D_SPECS
from app.models.stl3d_config import Stl3dConfig


_SCROLLBAR_QSS = """
    QScrollBar:vertical { border: none; background: #0c0d16; width: 10px; margin: 0px; }
    QScrollBar::handle:vertical { background: #2c2e43; min-height: 20px; border-radius: 5px; }
    QScrollBar::handle:vertical:hover { background: #3e415e; }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
"""


class Stl3dConfigPanel(SpecRowsMixin, QScrollArea):
    """Sidebar panel for the STL3d immersed-solid (STL -> phi) preprocessor.

    The controller connects run_btn / cancel_btn / browse_btn / fit_domain_btn,
    listens to config_changed for the live 3D overlay, and reads/writes the model
    via get_config()/set_config().
    """

    config_changed = pyqtSignal()          # domain / resolution / STL edited

    _SPEC_TABLE = STL3D_SPECS
    _SPEC_MODEL = Stl3dConfig

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

        # ── Run / Cancel ──────────────────────────────────────────────────
        # Generate phi / Cancel now live in the top canvas toolbar (reparented
        # by MainWindow), so they are created here (for controller.py wiring +
        # enable/disable) but not added to the side panel. The old panel "Fit
        # View" is removed — the 3D canvas toolbar already provides Fit View.
        self.run_btn = make_button("Generate phi", "#1e4620")
        self.cancel_btn = make_button("Cancel", "#4a1c1c")
        self.cancel_btn.setEnabled(False)

        # The STL↔φ fit is measured automatically after each successful run
        # (controller._on_stl3d_finished → check_stl3d_fit); the result appears in
        # the card below + as the canvas deviation heatmap. No manual button.

        # Fit result card — a compact, color-coded summary of the last Check Fit so
        # the verdict + key metrics are visible at a glance instead of being buried
        # in the log. Hidden until a fit check completes (see set_fit_result()).
        self.fit_result_card = QFrame()
        self.fit_result_card.setObjectName("fitCard")
        self.fit_result_card.setStyleSheet(
            "#fitCard{background:#10131f;border:1px solid #2d3356;border-radius:6px;}")
        fit_v = QVBoxLayout(self.fit_result_card)
        fit_v.setContentsMargins(8, 6, 8, 8)
        fit_v.setSpacing(3)
        # Title row: "STL ↔ φ Fit" + a small "?" help icon carrying the full,
        # plain-language explanation of the numbers (so the card itself stays terse).
        title_row = QHBoxLayout()
        title_row.setSpacing(4)
        fit_title = QLabel("STL ↔ φ Fit")
        fit_title.setStyleSheet("color:#dde2ff; font-weight:bold; font-size:11px;")
        title_row.addWidget(fit_title)
        title_row.addWidget(make_help_label(
            "How well the voxel (φ) solid reproduces the STL surface.\n"
            "• Surface within 1 cell — share of φ's surface within one cell of the "
            "STL; this drives the verdict. Good needs ≥95% within 1 cell AND a "
            "clean tail (≤1% more than 1.5 cells off), so 'mostly fine but a few "
            "loose regions' reads amber, not green. A complex or steeply-angled "
            "shape on a coarse grid strands more surface further out — raise "
            "Nx/Ny to bring it back in.\n"
            "• Average gap — mean distance between φ's surface and the STL (cells).\n"
            "• Volume / Area match — size agreement (+ = φ slightly larger).\n"
            "• Worst gap — the single largest distance, for reference. At a sharp "
            "corner/edge (e.g. a trailing edge) it stays a few cells off at any "
            "resolution, so it alone does not mean a coarse fit."))
        title_row.addStretch()
        self.fit_verdict_lbl = QLabel("")
        self.fit_verdict_lbl.setWordWrap(True)
        self.fit_metrics_lbl = QLabel("")
        self.fit_metrics_lbl.setWordWrap(True)
        self.fit_metrics_lbl.setStyleSheet("color:#a0a8c0; font-size:11px;")
        fit_v.addLayout(title_row)
        fit_v.addWidget(self.fit_verdict_lbl)
        fit_v.addWidget(self.fit_metrics_lbl)
        self.fit_result_card.setVisible(False)
        self._layout.addWidget(self.fit_result_card)

        # One-click hand-off: stage phi + generate the reading DLL + enable IBM,
        # then jump to the Solver tab. Enabled only after a successful run. Lives
        # in the top canvas toolbar (reparented by MainWindow) beside Generate
        # phi / Cancel, so it is created here but not added to the side panel.
        self.send_solver_btn = make_button("Send to Solver  →", "#301540")
        self.send_solver_btn.setEnabled(False)
        self.send_solver_btn.setToolTip(
            "Stage the phi field, generate the immersed-solid init DLL, enable IBM "
            "in the Solver config, and switch to the Solver tab.")

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

        # The controller owns this dialog (it validates the STL and stages it), so the
        # button is created here and only wrapped around the path field's row.
        self.browse_btn = QPushButton("…")
        self.browse_btn.setFixedWidth(32)
        self.browse_btn.setStyleSheet(
            "QPushButton{background:#1d2a3a;color:#dde2ff;border:1px solid #2d3356;"
            "border-radius:4px;padding:2px;} QPushButton:hover{border-color:#5a9ad4;}")

        def _path_row(host, edit):
            row = QHBoxLayout()
            row.setSpacing(4)
            row.addWidget(edit, 1)
            row.addWidget(host.browse_btn)
            w = QWidget()
            w.setLayout(row)
            return w

        self._spec_rows(form, "input", wrap={"stl_path": _path_row})
        align_form_labels(form, 78)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        sec.add_layout(form)

    def _build_domain_section(self):
        sec = CollapsibleSection("Cartesian Domain", start_collapsed=True)
        self._layout.addWidget(sec)

        self.fit_domain_btn = make_button("Auto Domain", "#1d2a3a")
        self.fit_domain_btn.setToolTip(
            "Set the domain bounds to the STL bounding box, padded by margin %")
        self._spec_widgets("margin")
        self.margin_spin.setValue(10.0)          # a padding default, not a model field
        self.margin_spin.setFixedWidth(70)
        margin_row = QHBoxLayout()
        margin_row.setSpacing(4)
        margin_row.addWidget(self.fit_domain_btn, 1)
        mlbl = QLabel("margin %")
        mlbl.setStyleSheet("color:#7a82a0;")
        margin_row.addWidget(mlbl)
        margin_row.addWidget(self.margin_spin)
        sec.add_layout(margin_row)

        # Two per row (min, max): the six bounds share three rows, which is why they
        # are built without form rows of their own.
        form = QFormLayout()
        self._spec_widgets("bounds")
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

        # Label on its own line above the three spins. Side by side, the
        # "Nx, Ny, Nz:" label + 3 spin boxes (each ~83px minimum — 4-digit value
        # plus arrows — in the fixed 360px sidebar) overflow the panel and clip
        # the right spin (and the no-horizontal-scroll viewport then hides it).
        # Stacking lets the three spins use the full row width.
        hdr = QHBoxLayout()
        hdr.setContentsMargins(0, 0, 0, 0)
        hdr.setSpacing(3)
        lbl = QLabel("Nx, Ny, Nz:")
        lbl.setStyleSheet("color:#a0a8c0;")
        hdr.addWidget(lbl)
        hdr.addWidget(make_help_label(
            "Grid points per axis (use Nz=2 for a quasi-2D / planar case)"))
        hdr.addStretch()
        sec.add_layout(hdr)

        n_row = QHBoxLayout()
        n_row.setSpacing(6)
        for w in self._spec_widgets("res"):
            n_row.addWidget(w, 1)          # share the full width equally
        sec.add_layout(n_row)

        for w in self._spec_widgets("res_readout"):
            sec.add_widget(w)

    def _build_search_section(self):
        sec = CollapsibleSection("Search Method", start_collapsed=True)
        self._layout.addWidget(sec)
        form = QFormLayout()
        self._spec_rows(form, "search")
        align_form_labels(form, 78)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        sec.add_layout(form)

    def _build_parallel_section(self):
        sec = CollapsibleSection("Parallel (OpenMP)", start_collapsed=True)
        self._layout.addWidget(sec)

        self._spec_widgets("omp_enable")
        sec.add_widget(self.omp_cb)

        row = QHBoxLayout()
        row.setSpacing(6)
        tlbl = QLabel("Threads:")
        tlbl.setStyleSheet("color:#7a82a0;")
        tlbl.setFixedWidth(78)
        self._spec_widgets("omp")
        self.threads_spin.setEnabled(False)     # follows omp_cb (wired below)
        row.addWidget(tlbl)
        row.addWidget(self.threads_spin)
        row.addStretch()
        sec.add_layout(row)

        hint = QLabel(f"Detected {os.cpu_count() or '?'} logical cores.")
        hint.setStyleSheet("color:#6b7390; font-size:10px;")
        sec.add_widget(hint)

    # ------------------------------------------------------------------ #
    def set_fit_result(self, verdict: str, color: str, metrics: str):
        """Populate the color-coded STL↔φ fit card (called after a Check Fit).

        ``color`` tints the verdict line (green/amber/red); ``metrics`` is a
        multi-line block of the key numbers shown beneath it."""
        self.fit_verdict_lbl.setText(verdict)
        self.fit_verdict_lbl.setStyleSheet(
            f"color:{color}; font-size:12px; font-weight:bold;")
        self.fit_metrics_lbl.setText(metrics)
        self.fit_result_card.setVisible(True)

    def clear_fit_result(self):
        """Hide the fit card — a fresh run / cleared phi makes the last one stale."""
        self.fit_result_card.setVisible(False)

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
        read_specs(self, STL3D_SPECS, cfg)
        return cfg

    def set_config(self, cfg: Stl3dConfig):
        # This panel already blocks its widgets' signals, so nothing escapes; the
        # `_loading` flag is set anyway so all three stage panels answer the
        # controller's "are you populating?" question the same way, and a widget added
        # outside the blocked list cannot quietly become an exception.
        self._loading = True
        try:
            self._set_config_body(cfg)
        finally:
            self._loading = False

    def _set_config_body(self, cfg: Stl3dConfig):
        # The blocked set is the TABLE's widgets, so a field added later is covered
        # rather than becoming the one widget whose signals escape.
        with block_signals(*spec_widgets(self, STL3D_SPECS)):
            write_specs(self, STL3D_SPECS, cfg)
        # Enable flag and thread count are independent, so "enabled with 1 thread"
        # round-trips as enabled rather than being read back as disabled.
        self.threads_spin.setEnabled(bool(getattr(cfg, "omp_enabled", False)))
        self.refresh_derived()
