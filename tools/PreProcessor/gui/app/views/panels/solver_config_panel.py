from __future__ import annotations
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QFrame,
    QFormLayout, QComboBox, QLabel,
)
from PyQt6.QtCore import Qt

from app.utils import make_button, COMBO_STYLE, align_form_labels, help_label, find_solver_executables
from app.models.solver_config import PRESETS
from app.views.panels.solver_config_widgets import _edit
from app.views.collapsible import CollapsibleSection
from app.views.panels.solver_config_build_mixin import SolverConfigBuildMixin
from app.views.panels.solver_config_build_mixin_b import SolverConfigBuildMixinB
from app.views.panels.solver_config_bc_mixin import SolverConfigBCMixin
from app.views.panels.solver_config_sync_mixin import SolverConfigSyncMixin
from app.views.panels.solver_units_mixin import SolverUnitsMixin


_SCROLLBAR_QSS = """
    QScrollBar:vertical { border: none; background: #0c0d16; width: 10px; margin: 0px; }
    QScrollBar::handle:vertical { background: #2c2e43; min-height: 20px; border-radius: 5px; }
    QScrollBar::handle:vertical:hover { background: #3e415e; }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
"""


class SolverConfigPanel(QScrollArea, SolverConfigBuildMixin, SolverConfigBuildMixinB,
                        SolverConfigBCMixin, SolverConfigSyncMixin,
                        SolverUnitsMixin):
    """Sidebar panel editing every SolverConfig parameter.

    The controller (Phase 3) connects run_solver_btn / cancel_solver_btn and
    reads/writes the model via get_config()/set_config().
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        # Guards signal handlers (e.g. restart auto-fill) from firing during
        # set_config's programmatic widget updates — they should react only to
        # genuine user interaction.
        self._loading = False
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

        # ── Run / Cancel + config load/save ───────────────────────────────
        # Run Solver / Cancel now live in the top canvas toolbar (reparented by
        # MainWindow); Load/Save Solver Config live in the Solver menu. All four
        # buttons stay as attributes so controller.py keeps its clicked/enable
        # wiring, but none are added to the side panel layout.
        self.run_solver_btn = make_button("Run Solver", "#1e4620")
        self.cancel_solver_btn = make_button("Cancel", "#4a1c1c")
        self.cancel_solver_btn.setEnabled(False)
        self.load_cfg_btn = make_button("Load Solver Config", "#1d2a3a")
        self.save_cfg_btn = make_button("Save Solver Config", "#301540")

        # ── Case & Preset ─────────────────────────────────────────────────
        # Domain type, case name and the workload preset used to sit loose at
        # the top of the panel (outside any section); grouped into one
        # collapsible region so every row lives in a section like the rest.
        self.sec_case = CollapsibleSection("Case & Preset", start_collapsed=True)
        self._layout.addWidget(self.sec_case)

        # Workload preset
        preset_row = QHBoxLayout()
        preset_row.setSpacing(4)
        preset_lbl = QLabel("Preset:")
        preset_lbl.setStyleSheet("color:#7a82a0;")
        self.preset_combo = QComboBox()
        self.preset_combo.addItem("— choose a starting point —")
        self.preset_combo.addItems(list(PRESETS.keys()))
        self.preset_combo.setStyleSheet(COMBO_STYLE)
        self.preset_combo.setToolTip(
            "Apply a manual-grounded starting point (numerics + dissipation), "
            "then fine-tune. Does not change geometry, BCs or iteration counts.")
        self.apply_preset_btn = make_button("Apply", "#1d2a3a")
        self.apply_preset_btn.setFixedWidth(70)
        preset_row.addWidget(preset_lbl)
        preset_row.addWidget(self.preset_combo, 1)
        preset_row.addWidget(self.apply_preset_btn)
        self.sec_case.add_layout(preset_row)
        self.apply_preset_btn.clicked.connect(self._apply_preset)

        # Domain type selector (e2d / e3d) at top
        top_form = QFormLayout()
        self.domain_type = QComboBox()
        self.domain_type.addItems(["e2d", "e3d"])
        self.domain_type.setStyleSheet(COMBO_STYLE)
        self.domain_type.setToolTip("Solver domain dimensionality (e2d = 2D, e3d = 3D)")
        self.case_name = _edit("Case name; solver_ctrl builds case/<name>/{work,grid,dll}")
        top_form.addRow(help_label("Domain Type:", "Solver domain dimensionality"), self.domain_type)
        top_form.addRow(help_label("Case Name:", "Case name for the solver working directory"), self.case_name)
        align_form_labels(top_form, 130)
        self.sec_case.add_layout(top_form)

        self._build_pipeline_section()
        self._build_grid_section()
        self._build_flow_section()
        self._build_turbulence_section()
        self._build_numerics_section()
        self._build_iteration_section()
        self._build_restart_section()
        self._build_output_section()
        self._build_parallel_section()
        self._build_decompose_section()
        self._build_ibm_section()
        self._build_bc_section()

        self._layout.addStretch()

        # Prefill binary paths from the prebuilt binaries under solver/ (D5).
        found = find_solver_executables()
        if found.get("getpgrid"):
            self.getpgrid_binary.setText(found["getpgrid"])
        if found.get("bdecompose"):
            self.bdecompose_binary.setText(found["bdecompose"])
        if found.get("solver"):
            self.solver_binary.setText(found["solver"])

        self.immersed_solid.toggled.connect(self._update_ibm_visibility)
        self.enable_decompose.toggled.connect(self._update_decompose_visibility)
        self.enable_shock.toggled.connect(self._update_shock_visibility)
        self.restart.toggled.connect(self._update_restart_visibility)
        self.restart.toggled.connect(self._autofill_restart_from_last_run)
        self.flow_solu_type.currentTextChanged.connect(self._on_flow_solu_changed)
        self._update_ibm_visibility()
        self._update_decompose_visibility()
        self._update_shock_visibility()
        self._update_restart_visibility()
        # Linf mode + the derived reference-Reynolds read-out (SolverUnitsMixin).
        self._wire_unit_widgets()
